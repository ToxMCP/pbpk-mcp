#!/usr/bin/env python3
"""Live load-test script for rxode2 population simulations.

Measures actual worker container memory usage at increasing cohort sizes
so the resource-quota estimator can be calibrated with real data.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_bridge.security.simple_jwt import jwt  # noqa: E402

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_MODEL_PATH = "/app/var/models/rxode2/reference_compound/reference_compound_population_rxode2_model.R"
DEFAULT_SIZES = [100, 500, 1000, 1500, 2000]
WORKER_CONTAINER = "pbpk_mcp-worker-1"


def build_auth_headers(auth_dev_secret: str | None, bearer_token: str | None) -> dict[str, str]:
    if bearer_token:
        return {"authorization": f"Bearer {bearer_token}"}
    if auth_dev_secret:
        token = jwt.encode(
            {
                "sub": "population-load-test",
                "roles": ["admin"],
                "iat": int(time.time()),
                "exp": int(time.time()) + 7200,
            },
            auth_dev_secret,
            algorithm="HS256",
        )
        return {"authorization": f"Bearer {token}"}
    return {}


def http_json(url: str, payload: dict | None = None, *, timeout: int = 120, headers: dict[str, str] | None = None) -> dict:
    data = None
    request_headers: dict[str, str] = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode()
        request_headers["content-type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        raise RuntimeError(f"{url} returned HTTP {exc.code}: {json.dumps(parsed)}") from exc


def call_tool(base_url: str, tool: str, arguments: dict, *, critical: bool = False, timeout: int = 120, headers: dict[str, str] | None = None) -> dict:
    response = http_json(
        f"{base_url.rstrip('/')}/mcp/call_tool",
        payload={"tool": tool, "arguments": arguments, **({"critical": True} if critical else {})},
        timeout=timeout,
        headers=headers,
    )
    return response["structuredContent"]


def poll_job(base_url: str, job_id: str, *, timeout_seconds: int = 600, headers: dict[str, str] | None = None) -> dict:
    deadline = time.time() + timeout_seconds
    last_status: dict | None = None
    while time.time() < deadline:
        payload = call_tool(base_url, "get_job_status", {"jobId": job_id}, timeout=30, headers=headers)
        last_status = payload
        if payload["status"] in {"succeeded", "failed", "cancelled", "timeout"}:
            return payload
        time.sleep(1.0)
    raise RuntimeError(f"Timed out waiting for job {job_id}: {json.dumps(last_status)}")


def sample_docker_stats_mb(container_name: str) -> float | None:
    """Return current memory usage of a container in MB, or None if unavailable."""
    try:
        result = subprocess.run(
            ["docker", "stats", container_name, "--no-stream", "--format", "{{.MemUsage}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        # Format is typically "123.4MiB / 4GiB" or "1.234GiB / 4GiB"
        line = result.stdout.strip().split("\n")[0].strip()
        if not line:
            return None
        mem_part = line.split("/")[0].strip()
        # Convert to MB
        value_str = mem_part[:-3]  # strip MiB or GiB
        unit = mem_part[-3:].upper()
        value = float(value_str)
        if unit == "GIB":
            return value * 1024.0
        if unit == "MIB":
            return value
        if unit == "KIB":
            return value / 1024.0
        return value
    except Exception:
        return None


def parse_memory_mb(mem_usage_str: str) -> float | None:
    """Parse a docker stats MemUsage string into MB."""
    try:
        mem_part = mem_usage_str.split("/")[0].strip()
        # Handle both "123.4MiB" and "1.2GiB"
        if mem_part.endswith("GiB"):
            return float(mem_part[:-3].strip()) * 1024.0
        if mem_part.endswith("MiB"):
            return float(mem_part[:-3].strip())
        if mem_part.endswith("KiB"):
            return float(mem_part[:-3].strip()) / 1024.0
        return None
    except Exception:
        return None


@dataclass
class LoadTestRun:
    cohort_size: int
    job_id: str | None = None
    status: str | None = None
    queued_at: float | None = None
    started_at: float | None = None
    finished_at: float | None = None
    peak_worker_memory_mb: float | None = None
    baseline_worker_memory_mb: float | None = None
    runtime_seconds: float | None = None
    queue_wait_seconds: float | None = None
    error: str | None = None
    result_id: str | None = None
    chunk_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cohortSize": self.cohort_size,
            "jobId": self.job_id,
            "status": self.status,
            "queuedAt": self.queued_at,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "peakWorkerMemoryMb": self.peak_worker_memory_mb,
            "baselineWorkerMemoryMb": self.baseline_worker_memory_mb,
            "runtimeSeconds": self.runtime_seconds,
            "queueWaitSeconds": self.queue_wait_seconds,
            "error": self.error,
            "resultId": self.result_id,
            "chunkCount": self.chunk_count,
        }


def run_single_load_test(
    base_url: str,
    simulation_id: str,
    cohort_size: int,
    headers: dict[str, str],
    worker_container: str,
    timeout_seconds: int = 600,
) -> LoadTestRun:
    run = LoadTestRun(cohort_size=cohort_size)

    # Baseline memory before submitting
    run.baseline_worker_memory_mb = sample_docker_stats_mb(worker_container)

    try:
        response = call_tool(
            base_url,
            "run_population_simulation",
            {
                "simulationId": simulation_id,
                "cohort": {"size": cohort_size, "seed": 42},
                "outputs": {"aggregates": ["meanCmax", "sdCmax", "meanAUC", "sdAUC"]},
            },
            critical=True,
            timeout=60,
            headers=headers,
        )
        run.job_id = response["jobId"]
        run.queued_at = time.time()
    except Exception as exc:
        run.status = "submit_failed"
        run.error = str(exc)
        return run

    # Poll job status while sampling docker stats
    deadline = time.time() + timeout_seconds
    peak_mem = run.baseline_worker_memory_mb or 0.0
    last_status: dict | None = None

    while time.time() < deadline:
        mem = sample_docker_stats_mb(worker_container)
        if mem is not None and mem > peak_mem:
            peak_mem = mem

        try:
            status_payload = call_tool(base_url, "get_job_status", {"jobId": run.job_id}, timeout=30, headers=headers)
            last_status = status_payload
        except Exception as exc:
            run.status = "status_poll_failed"
            run.error = str(exc)
            run.peak_worker_memory_mb = peak_mem
            return run

        if status_payload["status"] in {"succeeded", "failed", "cancelled", "timeout"}:
            run.status = status_payload["status"]
            run.started_at = status_payload.get("startedAt")
            run.finished_at = status_payload.get("finishedAt")
            run.result_id = status_payload.get("resultId")
            break

        time.sleep(1.0)
    else:
        run.status = "timed_out"
        run.error = f"Job did not complete within {timeout_seconds}s"

    run.peak_worker_memory_mb = peak_mem

    if isinstance(run.started_at, (int, float)) and isinstance(run.finished_at, (int, float)):
        run.runtime_seconds = round(run.finished_at - run.started_at, 3)
    elif isinstance(run.queued_at, (int, float)) and isinstance(run.finished_at, (int, float)):
        run.runtime_seconds = round(run.finished_at - run.queued_at, 3)

    if isinstance(run.queued_at, (int, float)) and isinstance(run.started_at, (int, float)):
        run.queue_wait_seconds = round(run.started_at - run.queued_at, 3)

    if run.status == "succeeded" and run.result_id:
        try:
            result_payload = call_tool(base_url, "get_population_results", {"resultsId": run.result_id}, timeout=60, headers=headers)
            run.chunk_count = len(result_payload.get("chunks") or [])
        except Exception as exc:
            run.error = f"Result fetch failed: {exc}"

    return run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live population load test for rxode2 worker memory profiling")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH)
    parser.add_argument("--simulation-id", default="loadtest-ref-compound")
    parser.add_argument("--sizes", nargs="+", type=int, default=DEFAULT_SIZES, help="Cohort sizes to test")
    parser.add_argument("--worker-container", default=WORKER_CONTAINER)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--output", default="var/benchmarks/population_load_test.json")
    parser.add_argument("--auth-dev-secret", default="pbpk-local-dev-secret-32bytes-long")
    parser.add_argument("--bearer-token", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    headers = build_auth_headers(args.auth_dev_secret, args.bearer_token)
    simulation_id = args.simulation_id

    print(f"[info] Load test starting against {args.base_url}")
    print(f"[info] Model: {args.model_path}")
    print(f"[info] Simulation ID: {simulation_id}")
    print(f"[info] Cohort sizes: {args.sizes}")
    print(f"[info] Worker container: {args.worker_container}")

    # Ensure model is loaded (idempotent if already present)
    print("[info] Ensuring simulation is loaded...")
    try:
        call_tool(
            args.base_url,
            "load_simulation",
            {"filePath": args.model_path, "simulationId": simulation_id},
            critical=True,
            timeout=180,
            headers=headers,
        )
    except RuntimeError as exc:
        if "already registered" not in str(exc).lower():
            print(f"[error] Failed to load simulation: {exc}", file=sys.stderr)
            return 1
        print("[info] Simulation already loaded (ok)")

    runs: list[LoadTestRun] = []
    for size in args.sizes:
        print(f"\n[run] Cohort size {size} ...", flush=True)
        run = run_single_load_test(
            base_url=args.base_url,
            simulation_id=simulation_id,
            cohort_size=size,
            headers=headers,
            worker_container=args.worker_container,
            timeout_seconds=args.timeout_seconds,
        )
        runs.append(run)
        print(f"[run] -> status={run.status} peak_mem={run.peak_worker_memory_mb} MB runtime={run.runtime_seconds} s")
        if run.error:
            print(f"[run] -> error: {run.error}")

    # Simple linear regression on successful runs to estimate MB/patient
    successful = [r for r in runs if r.status == "succeeded" and r.peak_worker_memory_mb is not None and r.baseline_worker_memory_mb is not None]
    regression: dict[str, Any] = {"slopeMbPerPatient": None, "interceptMb": None, "r2": None}
    if len(successful) >= 2:
        n = len(successful)
        sum_x = sum(r.cohort_size for r in successful)
        sum_y = sum(r.peak_worker_memory_mb - (r.baseline_worker_memory_mb or 0) for r in successful)
        sum_xx = sum(r.cohort_size ** 2 for r in successful)
        sum_xy = sum(r.cohort_size * (r.peak_worker_memory_mb - (r.baseline_worker_memory_mb or 0)) for r in successful)
        denominator = n * sum_xx - sum_x ** 2
        if denominator != 0:
            slope = (n * sum_xy - sum_x * sum_y) / denominator
            intercept = (sum_y - slope * sum_x) / n
            ss_res = sum(
                ((r.peak_worker_memory_mb - (r.baseline_worker_memory_mb or 0)) - (slope * r.cohort_size + intercept)) ** 2
                for r in successful
            )
            mean_y = sum_y / n
            ss_tot = sum(((r.peak_worker_memory_mb - (r.baseline_worker_memory_mb or 0)) - mean_y) ** 2 for r in successful)
            r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 1.0
            regression = {
                "slopeMbPerPatient": round(slope, 6),
                "interceptMb": round(intercept, 3),
                "r2": round(r2, 6),
            }

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "baseUrl": args.base_url,
        "modelPath": args.model_path,
        "simulationId": simulation_id,
        "workerContainer": args.worker_container,
        "regression": regression,
        "runs": [r.to_dict() for r in runs],
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\n[ok] Report written to {output_path}")
    print(json.dumps(regression, indent=2))
    return 0 if all(r.status == "succeeded" for r in runs) else 1


if __name__ == "__main__":
    sys.exit(main())
