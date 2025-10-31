"""Command-line interface for running MCP Bridge performance benchmarks."""

from __future__ import annotations

import argparse
import asyncio
import cProfile
import json
import math
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import httpx
import pstats

from mcp_bridge.app import create_app
from mcp_bridge.config import AppConfig
from mcp_bridge.security.simple_jwt import jwt

try:  # pragma: no cover - optional dependency
    import psutil  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    psutil = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Dataclasses to capture per-run and per-step metrics
# ---------------------------------------------------------------------------


@dataclass
class StepResult:
    """Timing information for a single benchmark step."""

    name: str
    duration_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "durationMs": round(self.duration_ms, 3),
        }
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload


@dataclass
class RunResult:
    """Aggregate metrics and metadata captured for one benchmark iteration."""

    iteration: int
    started_at: str
    finished_at: str
    wall_time_ms: float
    steps: List[StepResult]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "wallTimeMs": round(self.wall_time_ms, 3),
            "steps": [step.to_dict() for step in self.steps],
            "metadata": self.metadata,
        }


@dataclass
class ProcessSample:
    """Snapshot of process resource usage for optional instrumentation."""

    supported: bool
    cpu_seconds: float | None = None
    wall_seconds: float | None = None
    cpu_util_percent: float | None = None
    rss_start_bytes: int | None = None
    rss_end_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"supported": self.supported}
        if not self.supported:
            return payload
        payload["cpuSeconds"] = round(self.cpu_seconds or 0.0, 6)
        payload["wallSeconds"] = round(self.wall_seconds or 0.0, 6)
        payload["cpuUtilisationPercent"] = None
        if self.cpu_util_percent is not None:
            payload["cpuUtilisationPercent"] = round(self.cpu_util_percent, 3)
        payload["rssBytesStart"] = self.rss_start_bytes
        payload["rssBytesEnd"] = self.rss_end_bytes
        return payload


# ---------------------------------------------------------------------------
# HTTP client wrapper
# ---------------------------------------------------------------------------


class BenchmarkClient:
    """Thin wrapper around httpx.AsyncClient to add auth headers and timing helpers."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        token: str,
        request_timeout: float,
    ) -> None:
        self._client = client
        self._headers = {"Authorization": f"Bearer {token}"}
        self._timeout = request_timeout

    async def post_json(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        expected_status: Iterable[int] | int = (200,),
    ) -> dict[str, Any]:
        start = time.perf_counter()
        response = await self._client.post(
            path,
            json=payload,
            headers=self._headers,
            timeout=self._timeout,
        )
        duration_ms = (time.perf_counter() - start) * 1000.0
        expected = {expected_status} if isinstance(expected_status, int) else set(expected_status)
        if response.status_code not in expected:
            details = _safe_json(response)
            raise RuntimeError(
                f"{path} failed: status={response.status_code} expected={expected} detail={details}"
            )
        data = response.json()
        # Attach duration to response metadata for callers wanting raw timings.
        data["_requestDurationMs"] = duration_ms
        return data


# ---------------------------------------------------------------------------
# Scenario execution
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run MCP Bridge performance benchmarks",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--scenario", choices=["smoke"], default="smoke", help="Benchmark scenario")
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Total number of scenario iterations to execute",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Maximum number of concurrent iterations",
    )
    parser.add_argument(
        "--simulation-file",
        default="tests/fixtures/demo.pkml",
        help="Path to the PBPK model used for load_simulation",
    )
    parser.add_argument(
        "--parameter-path",
        default="Organism|Weight",
        help="Parameter path used for set/get value steps",
    )
    parser.add_argument(
        "--transport",
        choices=["asgi", "http"],
        default="asgi",
        help="Transport mode: in-process ASGI or external HTTP endpoint",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL for HTTP transport (ignored in ASGI mode)",
    )
    parser.add_argument(
        "--output-dir",
        default="var/benchmarks",
        help="Directory to store benchmark result artefacts",
    )
    parser.add_argument(
        "--job-backend",
        choices=["thread", "celery"],
        default=None,
        help="Override job backend when launching an in-process (ASGI) benchmark. "
        "Defaults to the JOB_BACKEND environment variable or 'thread'.",
    )
    parser.add_argument(
        "--celery-broker-url",
        default=None,
        help="Celery broker URL used when job backend is celery (defaults to CELERY_BROKER_URL env).",
    )
    parser.add_argument(
        "--celery-result-backend",
        default=None,
        help=(
            "Celery result backend URL used when job backend is celery "
            "(defaults to CELERY_RESULT_BACKEND env)."
        ),
    )
    parser.add_argument(
        "--celery-task-always-eager",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Execute Celery tasks eagerly within the API process. "
            "Defaults to True when running in ASGI mode, otherwise uses configuration."
        ),
    )
    parser.add_argument(
        "--celery-task-eager-propagates",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Propagate exceptions during eager Celery execution (defaults to existing configuration).",
    )
    parser.add_argument(
        "--celery-inline-worker",
        action="store_true",
        help=(
            "Launch an in-process Celery worker (memory transport) when benchmarking with ASGI. "
            "Automatically disables eager execution."
        ),
    )
    parser.add_argument(
        "--celery-inline-worker-concurrency",
        type=int,
        default=None,
        help="Concurrency for the inline Celery worker (defaults to the --concurrency value).",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Optional label stored in the benchmark JSON output",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=60.0,
        help="Per-request timeout in seconds",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help="Polling interval (seconds) for job status checks",
    )
    parser.add_argument(
        "--job-timeout",
        type=float,
        default=300.0,
        help="Maximum time to wait for async jobs to finish (seconds)",
    )
    parser.add_argument(
        "--roles",
        nargs="+",
        default=["operator", "viewer"],
        help="Roles embedded in the generated dev token",
    )
    parser.add_argument(
        "--subject",
        default="benchmark-client",
        help="Subject claim for the generated dev token",
    )
    parser.add_argument(
        "--dev-secret",
        default="benchmark-secret",
        help="Shared secret for signing development tokens (ASGI mode)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Pre-generated bearer token (required for HTTP transport if dev secret not shared)",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Capture cProfile stats during the benchmark run",
    )
    parser.add_argument(
        "--profile-output",
        default=None,
        help="Optional explicit path for cProfile output (.prof). Defaults under output-dir",
    )
    parser.add_argument(
        "--profile-top",
        type=int,
        default=25,
        help="Number of top cumulative functions to record in the JSON summary when profiling",
    )
    return parser.parse_args(argv)


async def _run_iterations(
    scenario: str,
    client: BenchmarkClient,
    *,
    dataset: Path,
    parameter_path: str,
    iterations: int,
    concurrency: int,
    poll_interval: float,
    job_timeout: float,
) -> list[RunResult]:
    semaphore = asyncio.Semaphore(max(concurrency, 1))
    runs: list[RunResult] = []

    async def worker(iteration: int) -> RunResult:
        async with semaphore:
            return await _run_smoke_iteration(
                client=client,
                dataset=dataset,
                parameter_path=parameter_path,
                poll_interval=poll_interval,
                job_timeout=job_timeout,
                iteration=iteration,
            )

    tasks = [asyncio.create_task(worker(index + 1)) for index in range(iterations)]
    for task in asyncio.as_completed(tasks):
        runs.append(await task)
    runs.sort(key=lambda item: item.iteration)
    return runs


async def _run_smoke_iteration(
    *,
    client: BenchmarkClient,
    dataset: Path,
    parameter_path: str,
    poll_interval: float,
    job_timeout: float,
    iteration: int,
) -> RunResult:
    """Execute the smoke scenario once covering load/set/get/run flows."""

    simulation_id = f"bench-{uuid.uuid4().hex[:8]}"
    steps: list[StepResult] = []
    metadata: dict[str, Any] = {"simulationId": simulation_id}
    started = datetime.now(timezone.utc)

    def _record_step(name: str, duration_ms: float, extra: Optional[dict[str, Any]] = None) -> None:
        steps.append(StepResult(name=name, duration_ms=duration_ms, metadata=extra or {}))

    # Load simulation
    load_payload = {"filePath": str(dataset), "simulationId": simulation_id}
    load_response = await client.post_json(
        "/load_simulation",
        load_payload,
        expected_status=201,
    )
    _record_step("load_simulation", load_response["_requestDurationMs"])

    # Mutate parameter
    set_payload = {
        "simulationId": simulation_id,
        "parameterPath": parameter_path,
        "value": 70.0,
        "unit": "kg",
        "comment": f"iteration-{iteration}",
    }
    set_response = await client.post_json(
        "/set_parameter_value",
        set_payload,
    )
    _record_step("set_parameter_value", set_response["_requestDurationMs"])

    # Confirm parameter value fetch
    get_payload = {"simulationId": simulation_id, "parameterPath": parameter_path}
    get_response = await client.post_json("/get_parameter_value", get_payload)
    _record_step("get_parameter_value", get_response["_requestDurationMs"])

    # Submit async simulation
    run_response = await client.post_json(
        "/run_simulation",
        {"simulationId": simulation_id, "runId": f"bench-{iteration}"},
        expected_status=202,
    )
    job_id = run_response["jobId"]
    metadata["jobId"] = job_id
    _record_step("run_simulation", run_response["_requestDurationMs"])

    # Wait for job completion
    job_result, wait_metrics = await _poll_job_status(
        client,
        job_id=job_id,
        poll_interval=poll_interval,
        timeout_seconds=job_timeout,
    )
    metadata.update(
        {
            "jobStatus": job_result.get("status"),
            "jobResultHandle": job_result.get("resultHandle"),
            "jobAttempts": job_result.get("attempts"),
        }
    )
    _record_step("wait_for_job", wait_metrics["durationMs"], wait_metrics["metadata"])

    # Fetch results when available
    result_handle = job_result.get("resultHandle") or {}
    results_id = result_handle.get("resultsId")
    if results_id:
        results_response = await client.post_json(
            "/get_simulation_results",
            {"resultsId": results_id},
        )
        metadata["resultsId"] = results_id
        _record_step("get_simulation_results", results_response["_requestDurationMs"])
    else:  # pragma: no cover - defensive guard for failed jobs
        metadata["resultsId"] = None

    finished = datetime.now(timezone.utc)
    wall_ms = (finished - started).total_seconds() * 1000.0
    return RunResult(
        iteration=iteration,
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        wall_time_ms=wall_ms,
        steps=steps,
        metadata=metadata,
    )


async def _poll_job_status(
    client: BenchmarkClient,
    *,
    job_id: str,
    poll_interval: float,
    timeout_seconds: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Poll job status until completion or timeout."""

    deadline = time.perf_counter() + timeout_seconds
    polls = 0
    final: dict[str, Any] | None = None
    start = time.perf_counter()

    while time.perf_counter() <= deadline:
        polls += 1
        status_response = await client.post_json("/get_job_status", {"jobId": job_id})
        state = status_response.get("status", "").lower()
        if state in {"succeeded", "failed", "timeout", "cancelled"}:
            final = status_response
            break
        await asyncio.sleep(poll_interval)

    if final is None:
        raise TimeoutError(f"Job {job_id} did not reach terminal state within {timeout_seconds}s")

    duration_ms = (time.perf_counter() - start) * 1000.0
    queue_wait = _interval_seconds(final.get("submittedAt"), final.get("startedAt"))
    runtime = _interval_seconds(final.get("startedAt"), final.get("finishedAt"))
    metadata = {
        "pollCount": polls,
        "queueWaitSeconds": queue_wait,
        "runtimeSeconds": runtime,
        "status": final.get("status"),
    }
    return final, {"durationMs": duration_ms, "metadata": metadata}


# ---------------------------------------------------------------------------
# Result aggregation helpers
# ---------------------------------------------------------------------------


def _summarise_steps(runs: list[RunResult]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    step_names = {step.name for run in runs for step in run.steps}
    for name in sorted(step_names):
        durations = [step.duration_ms for run in runs for step in run.steps if step.name == name]
        summary[name] = _summarise_series(durations)
    return summary


def _summarise_job_metrics(runs: list[RunResult]) -> dict[str, Any]:
    queue_waits: list[float] = []
    runtimes: list[float] = []
    polls: list[int] = []
    statuses: list[str] = []

    for run in runs:
        for step in run.steps:
            if step.name != "wait_for_job":
                continue
            meta = step.metadata
            queue = meta.get("queueWaitSeconds")
            runtime = meta.get("runtimeSeconds")
            poll_count = meta.get("pollCount")
            status = meta.get("status")
            if isinstance(queue, (int, float)):
                queue_waits.append(float(queue))
            if isinstance(runtime, (int, float)):
                runtimes.append(float(runtime))
            if isinstance(poll_count, int):
                polls.append(poll_count)
            if isinstance(status, str):
                statuses.append(status)

    job_summary: dict[str, Any] = {}
    if queue_waits:
        job_summary["queueWaitSeconds"] = _summarise_series(queue_waits)
    if runtimes:
        job_summary["runtimeSeconds"] = _summarise_series(runtimes)
    if polls:
        job_summary["pollCount"] = _summarise_series([float(p) for p in polls])
    if statuses:
        job_summary["statuses"] = {status: statuses.count(status) for status in sorted(set(statuses))}
    return job_summary


def _summarise_series(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0}
    ordered = sorted(values)
    total = sum(ordered)
    count = len(ordered)
    mean_val = total / count
    return {
        "count": count,
        "min": round(ordered[0], 3),
        "max": round(ordered[-1], 3),
        "mean": round(mean_val, 3),
        "p50": round(_percentile(ordered, 0.50), 3),
        "p90": round(_percentile(ordered, 0.90), 3),
        "p95": round(_percentile(ordered, 0.95), 3),
    }


def _percentile(sorted_values: list[float], quantile: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * quantile
    lower = math.floor(k)
    upper = math.ceil(k)
    if lower == upper:
        return sorted_values[int(k)]
    weight_upper = k - lower
    weight_lower = 1 - weight_upper
    return sorted_values[lower] * weight_lower + sorted_values[upper] * weight_upper


def _interval_seconds(start_iso: Any, end_iso: Any) -> float | None:
    if not start_iso or not end_iso:
        return None
    try:
        start_dt = datetime.fromisoformat(str(start_iso).replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(str(end_iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    delta = (end_dt - start_dt).total_seconds()
    return round(delta, 6)


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:200]


def _summarise_profile(profiler: cProfile.Profile, limit: int) -> list[dict[str, Any]]:
    stats = pstats.Stats(profiler)
    stats.strip_dirs()
    entries: list[dict[str, Any]] = []
    for (filename, line_no, func_name), data in stats.stats.items():
        primitive_calls, total_calls, total_time, cumulative_time, _ = data
        entries.append(
            {
                "function": f"{filename}:{line_no}:{func_name}",
                "primitiveCalls": primitive_calls,
                "totalCalls": total_calls,
                "totalTime": round(total_time, 6),
                "cumulativeTime": round(cumulative_time, 6),
            }
        )
    entries.sort(key=lambda item: item["cumulativeTime"], reverse=True)
    if limit <= 0:
        return entries
    return entries[:limit]


# ---------------------------------------------------------------------------
# Process metrics collector
# ---------------------------------------------------------------------------


class ProcessMetricsCollector:
    """Capture process CPU and memory deltas using psutil when available."""

    def __init__(self) -> None:
        self._process = psutil.Process() if psutil is not None else None
        self._start_cpu: Any = None
        self._start_wall: float | None = None
        self._start_rss: int | None = None

    def start(self) -> None:
        if self._process is None:  # pragma: no cover - optional path
            return
        try:
            self._start_cpu = self._process.cpu_times()
            self._start_wall = time.perf_counter()
            self._start_rss = getattr(self._process.memory_info(), "rss", None)
        except (psutil.Error, OSError):  # pragma: no cover - defensive guard
            self._process = None

    def finish(self) -> ProcessSample:
        if self._process is None or self._start_cpu is None or self._start_wall is None:
            return ProcessSample(supported=False)
        try:
            cpu_times = self._process.cpu_times()
            cpu_user = float(cpu_times.user - self._start_cpu.user)
            cpu_system = float(cpu_times.system - self._start_cpu.system)
            cpu_total = max(0.0, cpu_user + cpu_system)
            wall_elapsed = max(0.0, time.perf_counter() - self._start_wall)
            cpu_util = None
            if wall_elapsed > 0:
                cpu_count = psutil.cpu_count() or 1
                cpu_util = min(100.0, (cpu_total / wall_elapsed) / cpu_count * 100.0)
            rss_end = getattr(self._process.memory_info(), "rss", None)
            return ProcessSample(
                supported=True,
                cpu_seconds=cpu_total,
                wall_seconds=wall_elapsed,
                cpu_util_percent=cpu_util,
                rss_start_bytes=self._start_rss,
                rss_end_bytes=rss_end,
            )
        except (psutil.Error, OSError):  # pragma: no cover - defensive guard
            return ProcessSample(supported=False)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


async def _async_main(args: argparse.Namespace) -> int:
    dataset = Path(args.simulation_file).expanduser().resolve()
    if not dataset.is_file():
        print(f"[error] Simulation file not found: {dataset}", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("MCP_MODEL_SEARCH_PATHS", str(dataset.parent))

    token = args.token
    transport: httpx.AsyncBaseTransport | None = None
    app = None
    base_url = args.base_url
    resolved_job_backend = args.job_backend or os.getenv("JOB_BACKEND")
    resolved_celery_metadata: dict[str, Any] = {}
    inline_worker_ctx = None
    inline_worker_requested = False
    inline_worker_concurrency: Optional[int] = None

    if args.transport == "asgi":
        # Configure in-process app with dev auth secret so we can mint tokens locally.
        base_config = AppConfig.from_env()
        job_backend = resolved_job_backend or base_config.job_backend
        overrides: dict[str, Any] = {
            "adapter_backend": "inmemory",
            "environment": "development",
            "auth_dev_secret": args.dev_secret,
            "audit_storage_path": "var/audit",
            "audit_enabled": True,
            "population_storage_path": "var/population-results",
            "job_backend": job_backend,
        }
        if job_backend == "celery":
            inline_worker_requested = bool(args.celery_inline_worker)
            inline_worker_concurrency = (
                args.celery_inline_worker_concurrency or max(1, args.concurrency)
            )
            broker_url = (
                args.celery_broker_url
                or os.getenv("CELERY_BROKER_URL")
                or base_config.celery_broker_url
            )
            result_backend = (
                args.celery_result_backend
                or os.getenv("CELERY_RESULT_BACKEND")
                or base_config.celery_result_backend
            )
            always_eager = args.celery_task_always_eager
            if inline_worker_requested:
                always_eager = False
            elif always_eager is None:
                # Default to eager execution for in-process benchmarks unless explicitly disabled.
                always_eager = True
            eager_propagates = (
                args.celery_task_eager_propagates
                if args.celery_task_eager_propagates is not None
                else base_config.celery_task_eager_propagates
            )
            overrides.update(
                {
                    "celery_broker_url": broker_url,
                    "celery_result_backend": result_backend,
                    "celery_task_always_eager": always_eager,
                    "celery_task_eager_propagates": eager_propagates,
                }
            )
            resolved_celery_metadata = {
                "brokerUrl": broker_url,
                "resultBackend": result_backend,
                "taskAlwaysEager": always_eager,
                "taskEagerPropagates": eager_propagates,
                "inlineWorker": {"enabled": inline_worker_requested},
            }
            if inline_worker_requested and inline_worker_concurrency is not None:
                resolved_celery_metadata["inlineWorker"]["concurrency"] = inline_worker_concurrency
        config = base_config.model_copy(update=overrides)
        resolved_job_backend = config.job_backend

        app = create_app(config=config)
        await app.router.startup()
        transport = httpx.ASGITransport(app=app)
        base_url = "http://benchmark.local"
        if token is None:
            token = jwt.encode(
                {"sub": args.subject, "roles": args.roles},
                args.dev_secret,
                algorithm="HS256",
            )
        if (
            job_backend == "celery"
            and inline_worker_requested
            and not config.celery_task_always_eager
        ):
            try:
                from celery.contrib.testing.worker import start_worker
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise RuntimeError(
                    "celery.contrib.testing is required for --celery-inline-worker. Install celery[test]."
                ) from exc
            from mcp_bridge.services.celery_app import (
                configure_celery as _configure_celery,
            )

            celery_instance = _configure_celery(config)
            celery_instance.loader.import_default_modules()
            if "celery.ping" not in celery_instance.tasks:  # pragma: no cover - defensive
                @celery_instance.task(name="celery.ping")
                def _benchmark_ping():
                    return "pong"

            inline_worker_ctx = start_worker(
                celery_instance,
                pool="threads",
                concurrency=inline_worker_concurrency or max(1, args.concurrency),
            )
            inline_worker_ctx.__enter__()
    else:
        if token is None:
            print(
                "[error] --token must be provided when using HTTP transport without a shared dev secret",
                file=sys.stderr,
            )
            return 1

    collector = ProcessMetricsCollector()
    collector.start()

    profiler: cProfile.Profile | None = cProfile.Profile() if args.profile else None
    profile_summary: list[dict[str, Any]] | None = None

    async with httpx.AsyncClient(base_url=base_url, transport=transport) as async_client:
        client = BenchmarkClient(async_client, token=token, request_timeout=args.request_timeout)

        if profiler is not None:
            profiler.enable()

        runs = await _run_iterations(
            args.scenario,
            client,
            dataset=dataset,
            parameter_path=args.parameter_path,
            iterations=max(1, args.iterations),
            concurrency=max(1, args.concurrency),
            poll_interval=max(0.05, args.poll_interval),
            job_timeout=max(1.0, args.job_timeout),
        )

        if profiler is not None:
            profiler.disable()
            profile_summary = _summarise_profile(profiler, max(1, args.profile_top))
        proc_metrics = collector.finish()

    if inline_worker_ctx is not None:  # pragma: no branch - ensure cleanup
        inline_worker_ctx.__exit__(None, None, None)

    if transport and hasattr(transport, "close"):
        maybe_close = transport.close
        if asyncio.iscoroutinefunction(maybe_close):  # type: ignore[arg-type]
            await maybe_close()  # type: ignore[misc]
        else:
            maybe_close()  # type: ignore[call-arg]

    if app is not None:
        await app.router.shutdown()

    summary = _summarise_series([run.wall_time_ms for run in runs])
    steps_summary = _summarise_steps(runs)
    job_metrics = _summarise_job_metrics(runs)
    warnings: list[str] = []
    if not proc_metrics.supported:
        warnings.append("psutil not installed - CPU/memory metrics unavailable")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result_payload: dict[str, Any] = {
        "timestamp": timestamp,
        "scenario": args.scenario,
        "label": args.label,
        "config": {
            "iterations": max(1, args.iterations),
            "concurrency": max(1, args.concurrency),
            "simulationFile": str(dataset),
            "parameterPath": args.parameter_path,
            "transport": args.transport,
            "baseUrl": base_url,
            "pollInterval": max(0.05, args.poll_interval),
            "jobTimeout": max(1.0, args.job_timeout),
            "roles": args.roles,
            "subject": args.subject,
            "jobBackend": resolved_job_backend,
        },
        "summary": summary,
        "steps": steps_summary,
        "jobMetrics": job_metrics,
        "runs": [run.to_dict() for run in runs],
        "processMetrics": proc_metrics.to_dict(),
        "warnings": warnings,
    }
    if resolved_celery_metadata:
        result_payload["config"]["celery"] = resolved_celery_metadata

    if profiler is not None:
        if args.profile_output:
            profile_path = Path(args.profile_output).expanduser()
            if not profile_path.is_absolute():
                profile_path = (Path.cwd() / profile_path).resolve()
            profile_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            profile_dir = output_dir / "profiles"
            profile_dir.mkdir(parents=True, exist_ok=True)
            profile_path = profile_dir / f"{timestamp}-{args.scenario}.prof"
        profiler.dump_stats(str(profile_path))
        profile_payload: dict[str, Any] = {
            "statsFile": str(profile_path),
            "top": profile_summary or [],
        }
        try:
            profile_payload["relativePath"] = str(profile_path.relative_to(Path.cwd()))
        except ValueError:
            pass
        result_payload["profile"] = profile_payload

    output_path = output_dir / f"{timestamp}-{args.scenario}.json"
    output_path.write_text(json.dumps(result_payload, indent=2))

    print(f"[ok] Scenario '{args.scenario}' completed")
    print(f"     iterations: {summary.get('count', 0)}")
    print(f"     wall p95: {summary.get('p95')} ms")
    print(f"     output: {output_path}")
    if warnings:
        print("     warnings:")
        for item in warnings:
            print(f"       - {item}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        return asyncio.run(_async_main(args))
    except KeyboardInterrupt:  # pragma: no cover - CLI convenience
        print("\n[warn] Benchmark interrupted by user", file=sys.stderr)
        return 130


__all__ = ["main"]
