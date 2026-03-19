#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
CONTRACT_VERSION = "pbpk-mcp.v1"
CISPLATIN_MODEL = "/app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R"
PREGNANCY_PKML = "/app/var/models/esqlabs/pregnancy-neonates-batch-run/Pregnant_simulation_PKSim.pkml"


def http_json(url: str, payload: dict | None = None, timeout: int = 60) -> dict:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["content-type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers)
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


def call_tool(base_url: str, tool: str, arguments: dict, *, critical: bool = False, timeout: int = 60) -> dict:
    response = http_json(
        f"{base_url}/mcp/call_tool",
        payload={"tool": tool, "arguments": arguments, **({"critical": True} if critical else {})},
        timeout=timeout,
    )
    return response["structuredContent"]


def poll_job(base_url: str, job_id: str, timeout_seconds: int = 180) -> dict:
    deadline = time.time() + timeout_seconds
    last_status: dict | None = None
    while time.time() < deadline:
        payload = call_tool(base_url, "get_job_status", {"jobId": job_id}, timeout=30)
        last_status = payload
        if payload["status"] in {"succeeded", "failed", "cancelled", "timeout"}:
            return payload
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting for job {job_id}: {json.dumps(last_status)}")


def run_bridge_tests() -> None:
    subprocess.run(
        ["python3", "-m", "unittest", "-v", "tests/test_oecd_bridge.py"],
        cwd=WORKSPACE_ROOT,
        check=True,
    )
    subprocess.run(
        ["python3", "-m", "unittest", "-v", "tests/test_model_manifest.py"],
        cwd=WORKSPACE_ROOT,
        check=True,
    )


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def run_release_check(base_url: str, *, skip_unit_tests: bool = False) -> dict:
    if not skip_unit_tests:
        run_bridge_tests()

    summary: dict[str, object] = {}

    health = http_json(f"{base_url}/health", timeout=15)
    assert_true(health.get("status") == "ok", f"Health check failed: {health}")
    summary["health"] = health

    discovery = call_tool(base_url, "discover_models", {"search": "cisplatin", "limit": 20}, timeout=30)
    items = discovery["items"]
    cisplatin_matches = [item for item in items if "cisplatin" in item["filePath"].lower()]
    assert_true(bool(cisplatin_matches), "Cisplatin model not discoverable through discover_models")
    summary["discovery"] = {
        "total": discovery["total"],
        "cisplatinMatches": len(cisplatin_matches),
        "firstBackend": cisplatin_matches[0]["backend"],
    }

    manifest_check = call_tool(
        base_url,
        "validate_model_manifest",
        {"filePath": CISPLATIN_MODEL},
        timeout=60,
    )
    assert_true(
        manifest_check["manifest"]["qualificationState"]["state"] == "research-use",
        f"Unexpected cisplatin manifest qualification state: {manifest_check}",
    )
    assert_true(
        manifest_check["manifest"]["manifestStatus"] in {"valid", "partial"},
        f"Cisplatin manifest should be statically inspectable: {manifest_check}",
    )

    cis_id = f"release-cis-{uuid4().hex[:8]}"
    cis_load = call_tool(
        base_url,
        "load_simulation",
        {"filePath": CISPLATIN_MODEL, "simulationId": cis_id},
        critical=True,
        timeout=120,
    )
    assert_true(cis_load["backend"] == "rxode2", f"Unexpected cisplatin backend: {cis_load}")

    cis_validation = call_tool(
        base_url,
        "validate_simulation_request",
        {"simulationId": cis_id, "request": {"route": "iv-infusion", "contextOfUse": "research-only"}},
        timeout=60,
    )
    assert_true(cis_validation["validation"]["ok"] is True, "Cisplatin validation did not pass in-domain")

    cis_report = call_tool(
        base_url,
        "export_oecd_report",
        {"simulationId": cis_id, "request": {"route": "iv-infusion", "contextOfUse": "research-only"}, "parameterLimit": 5},
        timeout=120,
    )
    cis_report_payload = cis_report["report"]
    assert_true(cis_report["tool"] == "export_oecd_report", "export_oecd_report tool response missing")
    assert_true(cis_report_payload["reportVersion"] == "pbpk-oecd-report.v1", "Unexpected OECD report version")
    assert_true(
        cis_report_payload["oecdChecklist"]["modelPerformanceAndPredictivity"]["status"] == "partial",
        "Cisplatin performance checklist should remain partial until real fit evidence is attached",
    )
    assert_true(
        cis_report_payload["performanceEvidence"]["returnedRows"] >= 1,
        "Cisplatin report should include exported performance evidence rows",
    )

    run_id = f"{cis_id}-smoke"
    cis_submit = call_tool(
        base_url,
        "run_simulation",
        {"simulationId": cis_id, "runId": run_id},
        critical=True,
        timeout=60,
    )
    cis_job = poll_job(base_url, cis_submit["jobId"])
    assert_true(cis_job["status"] == "succeeded", f"Cisplatin simulation failed: {cis_job}")
    cis_results = call_tool(base_url, "get_results", {"resultsId": cis_job["resultId"]}, timeout=60)
    assert_true(len(cis_results["series"]) > 0, "Cisplatin deterministic result returned no series")

    pkml_id = f"release-pkml-{uuid4().hex[:8]}"
    pkml_load = call_tool(
        base_url,
        "load_simulation",
        {"filePath": PREGNANCY_PKML, "simulationId": pkml_id},
        critical=True,
        timeout=120,
    )
    assert_true(pkml_load["backend"] == "ospsuite", f"Unexpected PKML backend: {pkml_load}")

    pkml_report = call_tool(
        base_url,
        "export_oecd_report",
        {"simulationId": pkml_id, "request": {"contextOfUse": "research-only"}, "parameterLimit": 3},
        timeout=120,
    )
    pkml_report_payload = pkml_report["report"]
    assert_true(pkml_report_payload["profile"]["profileSource"]["type"] == "sidecar", "OSPSuite sidecar provenance was not preserved")
    assert_true(pkml_report_payload["parameterTable"]["returnedRows"] > 0, "OSPSuite OECD report should include runtime parameter rows")

    summary["cisplatin"] = {
        "simulationId": cis_id,
        "manifestState": manifest_check["manifest"]["qualificationState"]["state"],
        "validationDecision": cis_validation["validation"]["assessment"]["decision"],
        "reportChecklistScore": cis_report_payload["oecdChecklistScore"],
        "performanceChecklistStatus": cis_report_payload["oecdChecklist"]["modelPerformanceAndPredictivity"]["status"],
        "performanceEvidenceRows": cis_report_payload["performanceEvidence"]["returnedRows"],
        "resultSeries": len(cis_results["series"]),
    }
    summary["ospsuite"] = {
        "simulationId": pkml_id,
        "reportDecision": pkml_report_payload["validation"]["assessment"]["decision"],
        "profileSource": pkml_report_payload["profile"]["profileSource"]["type"],
        "parameterRows": pkml_report_payload["parameterTable"]["returnedRows"],
    }

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run release-readiness checks against the local PBPK MCP stack.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="PBPK MCP base URL.")
    parser.add_argument(
        "--skip-unit-tests",
        action="store_true",
        help="Skip the local OECD bridge unit tests and only run live stack checks.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_release_check(args.base_url, skip_unit_tests=args.skip_unit_tests)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
