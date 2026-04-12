#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_OUTPUT = WORKSPACE_ROOT / "var" / "public_release_preflight_summary.json"
DEFAULT_RELEASE_READINESS_OUTPUT = WORKSPACE_ROOT / "var" / "release_readiness_summary.json"
DEFAULT_SMOKE_OUTPUT = WORKSPACE_ROOT / "var" / "workspace_model_smoke_report.json"
DEFAULT_POPULATION_SMOKE_OUTPUT = WORKSPACE_ROOT / "var" / "workspace_model_smoke_rxode2_report.json"
DEFAULT_AUDIT_PATH = WORKSPACE_ROOT / "var" / "audit"
DEFAULT_LIVE_TESTS = (
    "tests/test_runtime_security_live_stack.py",
    "tests/test_model_discovery_live_stack.py",
    "tests/test_oecd_live_stack.py",
)


@dataclass(frozen=True)
class StepSpec:
    name: str
    command: tuple[str, ...]
    timeout_seconds: int
    summary_kind: str = "text"
    output_path: Path | None = None


def build_auth_args(*, bearer_token: str | None, auth_dev_secret: str | None) -> list[str]:
    if bearer_token:
        return ["--bearer-token", bearer_token]
    if auth_dev_secret:
        return ["--auth-dev-secret", auth_dev_secret]
    return []


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the maintainer-facing pre-public PBPK MCP release gate against a running local stack."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="PBPK MCP base URL.")
    parser.add_argument(
        "--python-executable",
        default=sys.executable,
        help="Python executable used for subordinate checks.",
    )
    parser.add_argument(
        "--make-executable",
        default="make",
        help="Make executable used for runtime-contract-test.",
    )
    parser.add_argument(
        "--bearer-token",
        default=None,
        help="Bearer token to use for authenticated live probes. Overrides dev-token generation when set.",
    )
    parser.add_argument(
        "--auth-dev-secret",
        default="pbpk-local-dev-secret",
        help="HS256 dev secret used to mint local operator tokens for live probes.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Path to write the preflight JSON summary.",
    )
    parser.add_argument(
        "--audit-path",
        default=str(DEFAULT_AUDIT_PATH),
        help="Local audit directory or s3://bucket/prefix used for the signoff-index dry run.",
    )
    parser.add_argument(
        "--audit-region",
        default=None,
        help="Optional region for S3-backed signoff-index dry runs.",
    )
    parser.add_argument(
        "--audit-endpoint-url",
        default=None,
        help="Optional S3-compatible endpoint URL for signoff-index dry runs.",
    )
    parser.add_argument(
        "--audit-force-path-style",
        action="store_true",
        help="Use S3 path-style addressing for signoff-index dry runs.",
    )
    parser.add_argument(
        "--ready-timeout-seconds",
        type=int,
        default=600,
        help="Total timeout for the runtime-ready wait step.",
    )
    parser.add_argument(
        "--ready-per-request-timeout-seconds",
        type=int,
        default=30,
        help="Per-request timeout for the runtime-ready wait step.",
    )
    parser.add_argument(
        "--ready-stable-successes",
        type=int,
        default=2,
        help="Required consecutive successful readiness probes.",
    )
    parser.add_argument(
        "--workspace-smoke-search",
        default="reference_compound",
        help="Model search term used by the workspace smoke checks.",
    )
    parser.add_argument(
        "--workspace-smoke-limit",
        type=int,
        default=1,
        help="Maximum number of models to exercise in each workspace smoke check.",
    )
    parser.add_argument(
        "--skip-runtime-ready",
        action="store_true",
        help="Skip waiting for the live stack to become ready.",
    )
    parser.add_argument(
        "--skip-runtime-contract",
        action="store_true",
        help="Skip make runtime-contract-test.",
    )
    parser.add_argument(
        "--skip-release-readiness",
        action="store_true",
        help="Skip scripts/release_readiness_check.py.",
    )
    parser.add_argument(
        "--skip-live-tests",
        action="store_true",
        help="Skip the named live-stack pytest slice.",
    )
    parser.add_argument(
        "--skip-workspace-smoke",
        action="store_true",
        help="Skip deterministic and population workspace smoke checks.",
    )
    parser.add_argument(
        "--skip-signoff-backfill-dry-run",
        action="store_true",
        help="Skip the review-signoff index dry-run check.",
    )
    return parser.parse_args(argv)


def build_preflight_plan(args: argparse.Namespace) -> list[StepSpec]:
    python_executable = str(args.python_executable)
    make_executable = str(args.make_executable)
    auth_args = build_auth_args(
        bearer_token=args.bearer_token,
        auth_dev_secret=args.auth_dev_secret,
    )
    steps: list[StepSpec] = []

    if not args.skip_runtime_ready:
        steps.append(
            StepSpec(
                name="runtime_ready",
                command=(
                    python_executable,
                    "scripts/wait_for_runtime_ready.py",
                    "--base-url",
                    str(args.base_url),
                    "--timeout-seconds",
                    str(args.ready_timeout_seconds),
                    "--per-request-timeout-seconds",
                    str(args.ready_per_request_timeout_seconds),
                    "--stable-successes",
                    str(args.ready_stable_successes),
                    *auth_args,
                ),
                timeout_seconds=max(int(args.ready_timeout_seconds) + 30, 120),
                summary_kind="json_stdout",
            )
        )

    if not args.skip_runtime_contract:
        steps.append(
            StepSpec(
                name="runtime_contract_test",
                command=(make_executable, "runtime-contract-test", f"PY={python_executable}"),
                timeout_seconds=3600,
            )
        )

    if not args.skip_release_readiness:
        steps.append(
            StepSpec(
                name="release_readiness_check",
                command=(
                    python_executable,
                    "scripts/release_readiness_check.py",
                    "--base-url",
                    str(args.base_url),
                    "--skip-unit-tests",
                    *auth_args,
                ),
                timeout_seconds=1800,
                summary_kind="json_stdout",
                output_path=Path(DEFAULT_RELEASE_READINESS_OUTPUT),
            )
        )

    if not args.skip_live_tests:
        steps.append(
            StepSpec(
                name="live_stack_tests",
                command=(
                    python_executable,
                    "-m",
                    "pytest",
                    "-q",
                    *DEFAULT_LIVE_TESTS,
                ),
                timeout_seconds=2400,
            )
        )

    if not args.skip_workspace_smoke:
        deterministic_output = Path(DEFAULT_SMOKE_OUTPUT)
        population_output = Path(DEFAULT_POPULATION_SMOKE_OUTPUT)
        steps.append(
            StepSpec(
                name="workspace_smoke_deterministic",
                command=(
                    python_executable,
                    "scripts/workspace_model_smoke.py",
                    "--base-url",
                    str(args.base_url),
                    "--search",
                    str(args.workspace_smoke_search),
                    "--limit",
                    str(args.workspace_smoke_limit),
                    "--output",
                    str(deterministic_output),
                    *auth_args,
                ),
                timeout_seconds=1800,
                summary_kind="json_file",
                output_path=deterministic_output,
            )
        )
        steps.append(
            StepSpec(
                name="workspace_smoke_population",
                command=(
                    python_executable,
                    "scripts/workspace_model_smoke.py",
                    "--base-url",
                    str(args.base_url),
                    "--search",
                    str(args.workspace_smoke_search),
                    "--limit",
                    str(args.workspace_smoke_limit),
                    "--include-population",
                    "--output",
                    str(population_output),
                    *auth_args,
                ),
                timeout_seconds=1800,
                summary_kind="json_file",
                output_path=population_output,
            )
        )

    if not args.skip_signoff_backfill_dry_run:
        audit_command = [
            python_executable,
            "scripts/backfill_review_signoff_index.py",
            str(args.audit_path),
            "--dry-run",
        ]
        if args.audit_region:
            audit_command.extend(["--region", str(args.audit_region)])
        if args.audit_endpoint_url:
            audit_command.extend(["--endpoint-url", str(args.audit_endpoint_url)])
        if args.audit_force_path_style:
            audit_command.append("--force-path-style")
        steps.append(
            StepSpec(
                name="review_signoff_index_dry_run",
                command=tuple(audit_command),
                timeout_seconds=900,
                summary_kind="json_stdout",
            )
        )

    return steps


def _tail_lines(text: str, *, max_lines: int = 60) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[-max_lines:])


def _parse_stdout_json(stdout: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Expected JSON output but received: {stdout[-500:]!r}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object output but received: {payload!r}")
    return payload


def run_step(step: StepSpec) -> dict[str, Any]:
    started = time.time()
    completed = subprocess.run(
        list(step.command),
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=step.timeout_seconds,
    )
    duration_seconds = round(time.time() - started, 3)
    record: dict[str, Any] = {
        "name": step.name,
        "command": list(step.command),
        "timeoutSeconds": step.timeout_seconds,
        "durationSeconds": duration_seconds,
        "returnCode": completed.returncode,
        "stdoutTail": _tail_lines(completed.stdout.strip()),
        "stderrTail": _tail_lines(completed.stderr.strip()),
    }
    if completed.returncode != 0:
        raise RuntimeError(json.dumps(record, indent=2))

    if step.summary_kind == "json_stdout":
        record["summary"] = _parse_stdout_json(completed.stdout)
        if step.output_path is not None:
            step.output_path.parent.mkdir(parents=True, exist_ok=True)
            step.output_path.write_text(json.dumps(record["summary"], indent=2) + "\n", encoding="utf-8")
            record["summaryPath"] = str(step.output_path)
    elif step.summary_kind == "json_file":
        if step.output_path is None:
            raise RuntimeError(f"{step.name} expected an output path")
        record["summaryPath"] = str(step.output_path)
        record["summary"] = json.loads(step.output_path.read_text(encoding="utf-8"))

    return record


def manual_follow_up_items() -> list[str]:
    return [
        "Confirm the live GitHub main ruleset matches docs/github_branch_protection.md.",
        "Confirm the release notes and README still match the actual runtime and trust surface.",
        "Retain the Model Smoke and Release Artifacts workflow outputs with the release evidence.",
    ]


def write_summary(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    payload: dict[str, Any] = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "baseUrl": args.base_url,
        "pythonExecutable": args.python_executable,
        "steps": [],
        "manualFollowUp": manual_follow_up_items(),
    }

    plan = build_preflight_plan(args)
    try:
        for step in plan:
            payload["steps"].append(run_step(step))
        payload["overallStatus"] = "passed"
        write_summary(output_path, payload)
        print(output_path)
        print(json.dumps({"overallStatus": "passed", "stepCount": len(plan)}, indent=2))
        return 0
    except Exception as exc:  # pragma: no cover - operational aggregation path
        payload["overallStatus"] = "failed"
        payload["failure"] = str(exc)
        write_summary(output_path, payload)
        print(output_path, file=sys.stderr)
        print(json.dumps({"overallStatus": "failed", "failure": str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
