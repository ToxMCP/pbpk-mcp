#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any


DEFAULT_REQUIRED_TOOLS = (
    "discover_models",
    "export_oecd_report",
    "get_job_status",
    "get_population_results",
    "get_results",
    "ingest_external_pbpk_bundle",
    "load_simulation",
    "run_population_simulation",
    "run_simulation",
    "run_verification_checks",
    "validate_model_manifest",
    "validate_simulation_request",
)


def http_json(url: str, *, timeout: float) -> Any:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wait until the local PBPK MCP runtime is stably ready."
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL for the MCP service.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=90.0,
        help="Maximum total time to wait before failing.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=1.0,
        help="Delay between readiness probes.",
    )
    parser.add_argument(
        "--per-request-timeout-seconds",
        type=float,
        default=5.0,
        help="Timeout for each individual HTTP request.",
    )
    parser.add_argument(
        "--stable-successes",
        type=int,
        default=3,
        help="Number of consecutive successful probes required before returning.",
    )
    parser.add_argument(
        "--required-tool",
        action="append",
        default=[],
        help="Required tool name. Repeat to override the default readiness catalog.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    required_tools = tuple(args.required_tool) or DEFAULT_REQUIRED_TOOLS
    deadline = time.time() + args.timeout_seconds
    stable_successes = 0
    last_error: str | None = None

    while time.time() < deadline:
        try:
            health = http_json(
                f"{args.base_url}/health",
                timeout=args.per_request_timeout_seconds,
            )
            if health.get("status") != "ok":
                raise RuntimeError(f"health status is not ok: {health}")

            tools_payload = http_json(
                f"{args.base_url}/mcp/list_tools",
                timeout=args.per_request_timeout_seconds,
            )
            tool_names = {
                tool.get("name")
                for tool in (tools_payload.get("tools") or [])
                if isinstance(tool, dict)
            }
            missing_tools = sorted(tool for tool in required_tools if tool not in tool_names)
            if missing_tools:
                raise RuntimeError(
                    f"tool catalog is incomplete; missing tools: {missing_tools}"
                )

            stable_successes += 1
            if stable_successes >= args.stable_successes:
                print(
                    json.dumps(
                        {
                            "status": "ready",
                            "baseUrl": args.base_url,
                            "version": health.get("version"),
                            "stableSuccesses": stable_successes,
                            "toolCount": len(tool_names),
                        }
                    )
                )
                return 0
        except Exception as exc:  # pragma: no cover - operational polling
            last_error = str(exc)
            stable_successes = 0

        time.sleep(args.poll_interval_seconds)

    summary = {
        "status": "timeout",
        "baseUrl": args.base_url,
        "timeoutSeconds": args.timeout_seconds,
        "lastError": last_error,
    }
    print(json.dumps(summary), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
