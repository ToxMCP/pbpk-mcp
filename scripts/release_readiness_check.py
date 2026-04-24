#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_bridge.contract import published_schema_ids, release_probe_required_tools  # noqa: E402
from mcp_bridge.curated_publication import (  # noqa: E402
    curated_publication_model_paths,
    curated_publication_model_relative_paths,
)
from mcp_bridge.security.simple_jwt import jwt  # noqa: E402

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
CONTRACT_VERSION = "pbpk-mcp.v1"
OSPSUITE_LOAD_TIMEOUT_SECONDS = 420
OSPSUITE_REPORT_TIMEOUT_SECONDS = 300
ASYNC_REFERENCE_JOB_TIMEOUT_SECONDS = 360
PUBLISHED_CONTRACT_MANIFEST = WORKSPACE_ROOT / "docs" / "architecture" / "contract_manifest.json"
PUBLISHED_RELEASE_BUNDLE_MANIFEST = WORKSPACE_ROOT / "docs" / "architecture" / "release_bundle_manifest.json"
VALIDATE_MANIFESTS_SCRIPT = WORKSPACE_ROOT / "scripts" / "validate_model_manifests.py"
CURATED_WORKSPACE_MODELS = curated_publication_model_paths(WORKSPACE_ROOT)
CURATED_RELATIVE_PATHS = curated_publication_model_relative_paths()
REFERENCE_MODEL = "/app/var/models/rxode2/reference_compound/reference_compound_population_rxode2_model.R"
PREGNANCY_PKML = "/app/var/models/esqlabs/pregnancy-neonates-batch-run/Pregnant_simulation_PKSim.pkml"
PKSIM5_PROJECT = "/app/var/demos/cimetidine/Cimetidine-Model.pksim5"
REQUIRED_TOOLS = frozenset(release_probe_required_tools())
REQUIRED_SCHEMA_IDS = frozenset(published_schema_ids())
REQUEST_HEADERS: dict[str, str] = {}


def build_auth_headers(
    *,
    bearer_token: str | None,
    auth_dev_secret: str | None,
    auth_role: str = "operator",
) -> dict[str, str]:
    if bearer_token:
        return {"authorization": f"Bearer {bearer_token}"}
    if auth_dev_secret:
        token = jwt.encode(
            {
                "sub": f"release-readiness-{auth_role}",
                "roles": [auth_role],
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
            },
            auth_dev_secret,
            algorithm="HS256",
        )
        return {"authorization": f"Bearer {token}"}
    return {}


def _decode_body(body: bytes) -> object:
    text = body.decode()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def http_request(
    url: str,
    *,
    payload: dict | None = None,
    timeout: int = 60,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    data = None
    request_headers: dict[str, str] = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode()
        request_headers.setdefault("content-type", "application/json")

    req = urllib.request.Request(url, data=data, headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return {
                "status": response.status,
                "headers": {key.lower(): value for key, value in response.headers.items()},
                "body": _decode_body(response.read()),
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": exc.code,
            "headers": {key.lower(): value for key, value in (exc.headers or {}).items()},
            "body": _decode_body(exc.read()),
        }


def http_json(url: str, payload: dict | None = None, timeout: int = 60) -> dict:
    response = http_request(url, payload=payload, timeout=timeout, headers=REQUEST_HEADERS)
    if int(response["status"]) >= 400:
        raise RuntimeError(f"{url} returned HTTP {response['status']}: {json.dumps(response['body'])}")
    body = response["body"]
    if not isinstance(body, dict):
        raise RuntimeError(f"{url} returned a non-JSON payload: {body!r}")
    return body


def jsonrpc_request(
    base_url: str,
    method: str,
    *,
    params: dict | None = None,
    headers: dict[str, str] | None = None,
    request_id: int | str = 1,
    timeout: int = 60,
) -> dict[str, object]:
    return http_request(
        f"{base_url}/mcp",
        payload={
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id,
        },
        timeout=timeout,
        headers=headers,
    )


def _tool_names(payload: dict) -> set[str]:
    return {
        str(tool.get("name"))
        for tool in (payload.get("tools") or [])
        if isinstance(tool, dict) and tool.get("name")
    }


def _error_message(payload: object) -> str:
    if isinstance(payload, dict):
        if isinstance(payload.get("error"), dict):
            return str((payload.get("error") or {}).get("message") or payload["error"])
        if "detail" in payload:
            return str(payload["detail"])
    return str(payload)


def call_tool(base_url: str, tool: str, arguments: dict, *, critical: bool = False, timeout: int = 60) -> dict:
    response = http_json(
        f"{base_url}/mcp/call_tool",
        payload={"tool": tool, "arguments": arguments, **({"critical": True} if critical else {})},
        timeout=timeout,
    )
    return response["structuredContent"]


def call_tool_error(base_url: str, tool: str, arguments: dict, *, critical: bool = False, timeout: int = 60) -> str:
    try:
        call_tool(base_url, tool, arguments, critical=critical, timeout=timeout)
    except RuntimeError as exc:
        return str(exc)
    raise RuntimeError(f"{tool} unexpectedly succeeded for arguments {arguments}")


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
        ["python3", "-m", "unittest", "-v", "tests/test_capability_matrix.py"],
        cwd=WORKSPACE_ROOT,
        check=True,
    )
    subprocess.run(
        ["python3", "-m", "unittest", "-v", "tests/test_ngra_object_schemas.py"],
        cwd=WORKSPACE_ROOT,
        check=True,
    )
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
    subprocess.run(
        ["python3", "-m", "unittest", "-v", "tests/test_load_simulation_contract.py"],
        cwd=WORKSPACE_ROOT,
        check=True,
    )
    subprocess.run(
        ["python3", "-m", "unittest", "-v", "tests/test_external_pbpk_bundle.py"],
        cwd=WORKSPACE_ROOT,
        check=True,
    )


def run_curated_manifest_gate() -> dict:
    command = [
        sys.executable,
        str(VALIDATE_MANIFESTS_SCRIPT),
        "--strict",
        "--require-explicit-ngra",
        "--curated-publication-set",
    ]

    completed = subprocess.run(
        command,
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Curated manifest gate returned non-JSON output: "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        ) from exc

    if completed.returncode != 0:
        raise RuntimeError(
            "Curated manifest gate failed: "
            f"{json.dumps(payload)}"
        )
    return payload


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_security_posture_check(
    base_url: str,
    *,
    bearer_token: str | None = None,
    auth_dev_secret: str | None = None,
) -> dict[str, object]:
    summary: dict[str, object] = {}

    anonymous_catalog = http_request(f"{base_url}/mcp/list_tools", timeout=30)
    anonymous_mode = anonymous_catalog["headers"].get("x-pbpk-security-mode") == "anonymous-development"
    summary["anonymousMode"] = anonymous_mode
    summary["restAnonymousStatus"] = anonymous_catalog["status"]

    public_schemas = http_request(f"{base_url}/mcp/resources/schemas?limit=5", timeout=30)
    assert_true(
        int(public_schemas["status"]) == 200,
        f"Published schema resources should remain publicly readable: {public_schemas}",
    )

    expected_protected_statuses = {403} if anonymous_mode else {401, 403}

    if anonymous_mode:
        assert_true(
            int(anonymous_catalog["status"]) == 200,
            f"Anonymous-development mode should expose the viewer tool catalog: {anonymous_catalog}",
        )
        anonymous_tools = _tool_names(anonymous_catalog["body"]) if isinstance(anonymous_catalog["body"], dict) else set()
        assert_true(
            "discover_models" in anonymous_tools,
            "Anonymous-development tool catalog should retain viewer discovery tools",
        )
        assert_true(
            "load_simulation" not in anonymous_tools,
            f"Anonymous-development tool catalog must not expose operator tools: {sorted(anonymous_tools)}",
        )
        anonymous_models = http_request(
            f"{base_url}/mcp/resources/models?search=reference_compound&limit=5",
            timeout=30,
        )
        assert_true(
            int(anonymous_models["status"]) == 200,
            f"Anonymous-development mode should keep viewer model resources readable: {anonymous_models}",
        )
        summary["restAnonymousViewerTools"] = sorted(anonymous_tools)
        summary["restAnonymousModelsStatus"] = anonymous_models["status"]
    else:
        assert_true(
            int(anonymous_catalog["status"]) in {401, 403},
            f"Non-anonymous deployments should not expose the tool catalog without auth: {anonymous_catalog}",
        )
        anonymous_models = http_request(
            f"{base_url}/mcp/resources/models?search=reference_compound&limit=5",
            timeout=30,
        )
        assert_true(
            int(anonymous_models["status"]) in {401, 403},
            f"Protected model resources should not be readable anonymously outside dev-viewer mode: {anonymous_models}",
        )
        summary["restAnonymousModelsStatus"] = anonymous_models["status"]

    metrics_anonymous = http_request(f"{base_url}/metrics", timeout=15)
    assert_true(
        int(metrics_anonymous["status"]) in expected_protected_statuses,
        f"Anonymous metrics access should be denied: {metrics_anonymous}",
    )
    console_shell = http_request(f"{base_url}/console", timeout=15)
    assert_true(
        int(console_shell["status"]) == 404,
        f"Retired /console shell should remain absent from the runtime surface: {console_shell}",
    )
    console_asset = http_request(f"{base_url}/console/assets/app.js", timeout=15)
    assert_true(
        int(console_asset["status"]) == 404,
        f"Retired /console assets should remain absent from the runtime surface: {console_asset}",
    )
    stale_console_static = http_request(f"{base_url}/console/static/app.js", timeout=15)
    assert_true(
        int(stale_console_static["status"]) == 404,
        f"The retired unauthenticated /console/static mount should remain absent: {stale_console_static}",
    )
    console_anonymous = http_request(f"{base_url}/console/api/samples", timeout=15)
    assert_true(
        int(console_anonymous["status"]) == 404,
        f"Retired /console/api surface should remain absent: {console_anonymous}",
    )

    operator_headers = build_auth_headers(
        bearer_token=bearer_token,
        auth_dev_secret=auth_dev_secret,
        auth_role="operator",
    )
    assert_true(bool(operator_headers), "Release readiness requires operator credentials for live checks")
    operator_catalog = http_request(
        f"{base_url}/mcp/list_tools",
        timeout=30,
        headers=operator_headers,
    )
    assert_true(
        int(operator_catalog["status"]) == 200,
        f"Operator token could not access the MCP tool catalog: {operator_catalog}",
    )
    operator_tools = _tool_names(operator_catalog["body"]) if isinstance(operator_catalog["body"], dict) else set()
    assert_true(
        {"discover_models", "load_simulation", "run_simulation"}.issubset(operator_tools),
        f"Operator token should expose critical execution tools: {sorted(operator_tools)}",
    )

    operator_no_confirm = http_request(
        f"{base_url}/mcp/call_tool",
        payload={
            "tool": "load_simulation",
            "arguments": {
                "filePath": REFERENCE_MODEL,
                "simulationId": f"release-auth-no-critical-{uuid4().hex[:8]}",
            },
        },
        timeout=60,
        headers=operator_headers,
    )
    assert_true(
        int(operator_no_confirm["status"]) == 428,
        f"Critical REST tools should still require confirmation for operator tokens: {operator_no_confirm}",
    )
    assert_true(
        "critical=true" in _error_message(operator_no_confirm["body"]).lower(),
        f"REST confirmation error should tell operators how to confirm critical tools: {operator_no_confirm}",
    )

    anonymous_call = http_request(
        f"{base_url}/mcp/call_tool",
        payload={
            "tool": "load_simulation",
            "critical": True,
            "arguments": {
                "filePath": REFERENCE_MODEL,
                "simulationId": f"release-auth-anon-{uuid4().hex[:8]}",
            },
        },
        timeout=60,
    )
    assert_true(
        int(anonymous_call["status"]) in expected_protected_statuses,
        f"Anonymous critical REST calls should be blocked: {anonymous_call}",
    )

    operator_console = http_request(
        f"{base_url}/console/api/samples",
        timeout=30,
        headers=operator_headers,
    )
    assert_true(
        int(operator_console["status"]) == 404,
        f"Retired /console/api surface should stay absent even with operator auth: {operator_console}",
    )

    viewer_headers: dict[str, str] | None = None
    viewer_tool_count: int | None = None
    if auth_dev_secret and not bearer_token:
        viewer_headers = build_auth_headers(
            bearer_token=None,
            auth_dev_secret=auth_dev_secret,
            auth_role="viewer",
        )
        viewer_catalog = http_request(
            f"{base_url}/mcp/list_tools",
            timeout=30,
            headers=viewer_headers,
        )
        assert_true(
            int(viewer_catalog["status"]) == 200,
            f"Viewer token could not access viewer-scoped tools: {viewer_catalog}",
        )
        viewer_tools = _tool_names(viewer_catalog["body"]) if isinstance(viewer_catalog["body"], dict) else set()
        assert_true(
            "load_simulation" not in viewer_tools,
            f"Viewer token must not expose operator-only tools: {sorted(viewer_tools)}",
        )
        viewer_tool_count = len(viewer_tools)
        if anonymous_mode:
            assert_true(
                viewer_tools == (_tool_names(anonymous_catalog["body"]) if isinstance(anonymous_catalog["body"], dict) else set()),
                "Anonymous-development tool catalog should match explicit viewer-role visibility",
            )

    signoff_simulation_id = f"release-signoff-{uuid4().hex[:8]}"
    signoff_load = http_request(
        f"{base_url}/load_simulation",
        payload={
            "filePath": REFERENCE_MODEL,
            "simulationId": signoff_simulation_id,
            "confirm": True,
        },
        timeout=120,
        headers=operator_headers,
    )
    assert_true(
        int(signoff_load["status"]) == 201,
        f"Operator token could not prepare a simulation for review-signoff security checks: {signoff_load}",
    )
    signoff_anonymous = http_request(
        f"{base_url}/review_signoff",
        payload={
            "simulationId": signoff_simulation_id,
            "scope": "export_oecd_report",
            "disposition": "approved-for-bounded-use",
            "rationale": "Release readiness sign-off probe for bounded report use.",
            "confirm": True,
        },
        timeout=30,
    )
    assert_true(
        int(signoff_anonymous["status"]) in expected_protected_statuses,
        f"Anonymous review-signoff recording should be denied: {signoff_anonymous}",
    )
    signoff_operator_no_confirm = http_request(
        f"{base_url}/review_signoff",
        payload={
            "simulationId": signoff_simulation_id,
            "scope": "export_oecd_report",
            "disposition": "approved-for-bounded-use",
            "rationale": "Release readiness sign-off probe for bounded report use.",
        },
        timeout=30,
        headers=operator_headers,
    )
    assert_true(
        int(signoff_operator_no_confirm["status"]) == 428,
        f"Operator review-signoff recording should still require confirmation: {signoff_operator_no_confirm}",
    )
    signoff_recorded = http_request(
        f"{base_url}/review_signoff",
        payload={
            "simulationId": signoff_simulation_id,
            "scope": "export_oecd_report",
            "disposition": "approved-for-bounded-use",
            "rationale": "Release readiness sign-off probe for bounded report use.",
            "confirm": True,
        },
        timeout=30,
        headers=operator_headers,
    )
    assert_true(
        int(signoff_recorded["status"]) == 200,
        f"Operator review-signoff recording failed: {signoff_recorded}",
    )
    signoff_recorded_body = signoff_recorded["body"]
    assert_true(
        isinstance(signoff_recorded_body, dict)
        and isinstance(signoff_recorded_body.get("operatorReviewSignoff"), dict)
        and (signoff_recorded_body.get("operatorReviewSignoff") or {}).get("status") == "recorded",
        f"Recorded review-signoff summary was not returned after recording: {signoff_recorded}",
    )
    assert_true(
        isinstance(signoff_recorded_body, dict)
        and isinstance(signoff_recorded_body.get("operatorReviewGovernance"), dict)
        and (signoff_recorded_body.get("operatorReviewGovernance") or {}).get("supportsOverride") is False
        and (signoff_recorded_body.get("operatorReviewGovernance") or {}).get("supportsAdjudication") is False,
        f"Recorded review-signoff response should describe non-override, non-adjudicative governance explicitly: {signoff_recorded}",
    )
    signoff_history: dict[str, object] | None = None
    if viewer_headers:
        signoff_viewer = http_request(
            f"{base_url}/review_signoff?simulationId={signoff_simulation_id}&scope=export_oecd_report",
            timeout=30,
            headers=viewer_headers,
        )
        assert_true(
            int(signoff_viewer["status"]) == 200,
            f"Viewer token should be able to read the additive review-signoff summary: {signoff_viewer}",
        )
        signoff_viewer_body = signoff_viewer["body"]
        assert_true(
            isinstance(signoff_viewer_body, dict)
            and isinstance(signoff_viewer_body.get("operatorReviewGovernance"), dict)
            and (signoff_viewer_body.get("operatorReviewGovernance") or {}).get("signoffConfersDecisionAuthority")
            is False,
            f"Viewer-readable review-signoff summary should keep governance limits explicit: {signoff_viewer}",
        )
        signoff_history = http_request(
            f"{base_url}/review_signoff/history?simulationId={signoff_simulation_id}&scope=export_oecd_report&limit=10",
            timeout=30,
            headers=viewer_headers,
        )
        assert_true(
            int(signoff_history["status"]) == 200,
            f"Viewer token should be able to read the additive review-signoff history: {signoff_history}",
        )
        signoff_history_body = signoff_history["body"]
        assert_true(
            isinstance(signoff_history_body, dict)
            and isinstance(signoff_history_body.get("operatorReviewSignoffHistory"), dict)
            and ((signoff_history_body.get("operatorReviewSignoffHistory") or {}).get("returnedEntryCount") or 0) >= 1,
            f"Readable review-signoff history should include at least one recorded event: {signoff_history}",
        )
        latest_history_entry = (
            (signoff_history_body.get("operatorReviewSignoffHistory") or {}).get("entries") or [{}]
        )[0]
        assert_true(
            latest_history_entry.get("action") == "recorded",
            f"Latest review-signoff history entry should reflect the recorded event: {signoff_history}",
        )
        assert_true(
            isinstance(signoff_history_body.get("operatorReviewGovernance"), dict)
            and (signoff_history_body.get("operatorReviewGovernance") or {}).get("supportsOverride") is False,
            f"Viewer-readable review-signoff history should keep non-override governance explicit: {signoff_history}",
        )

    metrics_admin_status: int | None = None
    if auth_dev_secret and not bearer_token:
        admin_headers = build_auth_headers(
            bearer_token=None,
            auth_dev_secret=auth_dev_secret,
            auth_role="admin",
        )
        metrics_admin = http_request(
            f"{base_url}/metrics",
            timeout=15,
            headers=admin_headers,
        )
        assert_true(
            int(metrics_admin["status"]) == 200,
            f"Admin token should access Prometheus metrics: {metrics_admin}",
        )
        assert_true(
            "mcp_http_requests_total" in str(metrics_admin["body"]),
            "Prometheus metrics endpoint did not expose MCP HTTP metrics under admin auth",
        )
        metrics_admin_status = int(metrics_admin["status"])

    jsonrpc_initialize = jsonrpc_request(
        base_url,
        "initialize",
        headers={"content-type": "application/json"},
        timeout=30,
    )
    assert_true(
        int(jsonrpc_initialize["status"]) == 200,
        f"JSON-RPC initialize should remain public and transport-stable: {jsonrpc_initialize}",
    )
    initialize_body = jsonrpc_initialize["body"]
    assert_true(
        isinstance(initialize_body, dict)
        and isinstance(initialize_body.get("result"), dict)
        and (initialize_body.get("result") or {}).get("protocolVersion") == "2025-11-25",
        f"JSON-RPC initialize returned an unexpected protocol payload: {jsonrpc_initialize}",
    )
    initialize_result = initialize_body.get("result") or {}
    assert_true(
        (initialize_result.get("capabilities") or {}).get("tools") == {"listChanged": False}
        and (initialize_result.get("capabilities") or {}).get("resources") == {"listChanged": False},
        f"JSON-RPC initialize did not advertise standard tools/resources capabilities: {jsonrpc_initialize}",
    )

    jsonrpc_anonymous_list = jsonrpc_request(
        base_url,
        "tools/list",
        headers={"content-type": "application/json"},
        timeout=30,
    )
    if anonymous_mode:
        assert_true(
            int(jsonrpc_anonymous_list["status"]) == 200,
            f"Anonymous-development JSON-RPC tools/list should succeed with viewer visibility: {jsonrpc_anonymous_list}",
        )
        rpc_anon_body = jsonrpc_anonymous_list["body"]
        rpc_anon_tools = _tool_names((rpc_anon_body.get("result") or {})) if isinstance(rpc_anon_body, dict) else set()
        assert_true(
            "load_simulation" not in rpc_anon_tools,
            f"Anonymous-development JSON-RPC tool list must stay viewer-only: {sorted(rpc_anon_tools)}",
        )
    else:
        rpc_anon_body = jsonrpc_anonymous_list["body"]
        assert_true(
            isinstance(rpc_anon_body, dict) and isinstance(rpc_anon_body.get("error"), dict),
            f"Non-anonymous JSON-RPC tools/list should reject unauthenticated access: {jsonrpc_anonymous_list}",
        )

    jsonrpc_operator_list = jsonrpc_request(
        base_url,
        "tools/list",
        headers={**operator_headers, "content-type": "application/json"},
        timeout=30,
    )
    assert_true(
        int(jsonrpc_operator_list["status"]) == 200,
        f"Operator JSON-RPC tools/list failed: {jsonrpc_operator_list}",
    )
    rpc_operator_body = jsonrpc_operator_list["body"]
    rpc_operator_tools = _tool_names((rpc_operator_body.get("result") or {})) if isinstance(rpc_operator_body, dict) else set()
    assert_true(
        "load_simulation" in rpc_operator_tools,
        f"Operator JSON-RPC tool list should expose critical execution tools: {sorted(rpc_operator_tools)}",
    )

    jsonrpc_anonymous_call = jsonrpc_request(
        base_url,
        "tools/call",
        params={
            "name": "load_simulation",
            "critical": True,
            "arguments": {
                "filePath": REFERENCE_MODEL,
                "simulationId": f"release-rpc-anon-{uuid4().hex[:8]}",
            },
        },
        headers={"content-type": "application/json"},
        timeout=60,
    )
    rpc_anon_call_body = jsonrpc_anonymous_call["body"]
    assert_true(
        isinstance(rpc_anon_call_body, dict)
        and isinstance(rpc_anon_call_body.get("error"), dict)
        and int((rpc_anon_call_body.get("error") or {}).get("code")) in {-32000, -32001},
        f"Anonymous JSON-RPC critical call should be rejected with auth/role error semantics: {jsonrpc_anonymous_call}",
    )

    jsonrpc_operator_no_confirm = jsonrpc_request(
        base_url,
        "tools/call",
        params={
            "name": "load_simulation",
            "arguments": {
                "filePath": REFERENCE_MODEL,
                "simulationId": f"release-rpc-no-critical-{uuid4().hex[:8]}",
            },
        },
        headers={**operator_headers, "content-type": "application/json"},
        timeout=60,
    )
    rpc_operator_no_confirm_body = jsonrpc_operator_no_confirm["body"]
    assert_true(
        isinstance(rpc_operator_no_confirm_body, dict)
        and isinstance(rpc_operator_no_confirm_body.get("error"), dict)
        and int((rpc_operator_no_confirm_body.get("error") or {}).get("code")) == -32002,
        f"JSON-RPC operator critical calls should still require confirmation: {jsonrpc_operator_no_confirm}",
    )
    assert_true(
        "critical" in str((rpc_operator_no_confirm_body.get("error") or {}).get("message", "")).lower(),
        f"JSON-RPC confirmation error should remain explicit: {jsonrpc_operator_no_confirm}",
    )

    summary.update(
        {
            "restOperatorToolCount": len(operator_tools),
            "restViewerToolCount": viewer_tool_count,
            "metricsAnonymousStatus": metrics_anonymous["status"],
            "metricsAdminStatus": metrics_admin_status,
            "retiredConsoleShellStatus": console_shell["status"],
            "retiredConsoleAssetStatus": console_asset["status"],
            "retiredConsoleStaticStatus": stale_console_static["status"],
            "retiredConsoleAnonymousApiStatus": console_anonymous["status"],
            "retiredConsoleOperatorApiStatus": operator_console["status"],
            "reviewSignoffAnonymousStatus": signoff_anonymous["status"],
            "reviewSignoffOperatorConfirmationStatus": signoff_operator_no_confirm["status"],
            "reviewSignoffRecordedStatus": signoff_recorded["status"],
            "reviewSignoffHistoryViewerStatus": (
                signoff_history["status"] if isinstance(signoff_history, dict) else None
            ),
            "jsonrpcInitializeStatus": jsonrpc_initialize["status"],
            "jsonrpcOperatorToolCount": len(rpc_operator_tools),
            "jsonrpcAnonymousCallErrorCode": (
                (rpc_anon_call_body.get("error") or {}).get("code")
                if isinstance(rpc_anon_call_body, dict)
                else None
            ),
            "jsonrpcOperatorConfirmationErrorCode": (
                (rpc_operator_no_confirm_body.get("error") or {}).get("code")
                if isinstance(rpc_operator_no_confirm_body, dict)
                else None
            ),
        }
    )
    return summary


def run_release_check(
    base_url: str,
    *,
    skip_unit_tests: bool = False,
    bearer_token: str | None = None,
    auth_dev_secret: str | None = None,
) -> dict:
    if not skip_unit_tests:
        run_bridge_tests()

    summary: dict[str, object] = {}
    curated_manifest_gate = run_curated_manifest_gate()
    assert_true(
        not bool((curated_manifest_gate.get("gating") or {}).get("failed")),
        f"Curated manifest publication gate failed: {curated_manifest_gate}",
    )
    assert_true(
        int((curated_manifest_gate.get("summary") or {}).get("explicitNgraDeclarations") or 0)
        == len(CURATED_WORKSPACE_MODELS),
        f"Curated manifest publication gate did not confirm explicit NGRA boundaries for all bundled models: {curated_manifest_gate}",
    )
    summary["curatedManifestGate"] = {
        "checkedPaths": list(CURATED_RELATIVE_PATHS),
        "gating": curated_manifest_gate.get("gating"),
        "summary": curated_manifest_gate.get("summary"),
    }
    summary["securityPosture"] = run_security_posture_check(
        base_url,
        bearer_token=bearer_token,
        auth_dev_secret=auth_dev_secret,
    )

    health = http_json(f"{base_url}/health", timeout=15)
    assert_true(health.get("status") == "ok", f"Health check failed: {health}")
    summary["health"] = health

    tool_catalog = http_json(f"{base_url}/mcp/list_tools", timeout=30)
    tool_names = {tool["name"] for tool in tool_catalog["tools"]}
    assert_true(
        REQUIRED_TOOLS.issubset(tool_names),
        f"Live tool catalog is missing required workflow tools: {sorted(REQUIRED_TOOLS - tool_names)}",
    )

    discovery = call_tool(base_url, "discover_models", {"search": "reference_compound", "limit": 20}, timeout=30)
    items = discovery["items"]
    reference_matches = [item for item in items if "reference_compound" in item["filePath"].lower()]
    assert_true(bool(reference_matches), "Reference compound model not discoverable through discover_models")
    resource_models = http_json(f"{base_url}/mcp/resources/models?search=reference_compound&limit=20", timeout=30)
    resource_matches = [
        item for item in resource_models["items"] if "reference_compound" in item["filePath"].lower()
    ]
    assert_true(bool(resource_matches), "Reference compound model not discoverable through /mcp/resources/models")
    assert_true(
        reference_matches[0]["backend"] == resource_matches[0]["backend"],
        "discover_models and /mcp/resources/models disagree on the reference model backend",
    )
    assert_true(
        reference_matches[0]["runtimeFormat"] == resource_matches[0]["runtimeFormat"],
        "discover_models and /mcp/resources/models disagree on the reference model runtime format",
    )
    discovery_contract = discovery.get("trustSurfaceContract") or {}
    assert_true(
        discovery_contract.get("tool") == "discover_models",
        f"discover_models should expose a top-level trust-surface contract for thin clients: {discovery}",
    )
    assert_true(
        any(
            surface.get("surfacePath") == "items[*].curationSummary"
            for surface in (discovery_contract.get("surfaces") or [])
            if isinstance(surface, dict)
        ),
        f"discover_models trust-surface contract should point clients at item-level curation summaries: {discovery}",
    )
    summary["discovery"] = {
        "total": discovery["total"],
        "referenceMatches": len(reference_matches),
        "firstBackend": reference_matches[0]["backend"],
    }
    summary["toolCatalog"] = {
        "requiredTools": sorted(REQUIRED_TOOLS),
        "missingTools": sorted(REQUIRED_TOOLS - tool_names),
    }

    schema_catalog = http_json(f"{base_url}/mcp/resources/schemas?limit=50", timeout=30)
    schema_ids = {item["schemaId"] for item in schema_catalog["items"]}
    assert_true(
        REQUIRED_SCHEMA_IDS.issubset(schema_ids),
        f"Schema resources are missing published PBPK object schemas: {sorted(REQUIRED_SCHEMA_IDS - schema_ids)}",
    )
    assessment_schema = http_json(f"{base_url}/mcp/resources/schemas/assessmentContext.v1", timeout=30)
    assert_true(
        assessment_schema["schema"]["title"] == "assessmentContext.v1",
        "assessmentContext schema resource returned the wrong schema title",
    )
    assert_true(
        assessment_schema["example"]["objectType"] == "assessmentContext.v1",
        "assessmentContext schema resource returned the wrong example payload",
    )
    capability_resource = http_json(f"{base_url}/mcp/resources/capability-matrix", timeout=30)
    matrix = capability_resource["matrix"]
    matrix_entries = {entry["id"]: entry for entry in matrix["entries"]}
    published_contract_manifest = json.loads(PUBLISHED_CONTRACT_MANIFEST.read_text(encoding="utf-8"))
    assert_true(
        matrix.get("contractVersion") == CONTRACT_VERSION,
        f"Capability matrix resource should advertise {CONTRACT_VERSION}: {matrix}",
    )
    assert_true(
        capability_resource.get("sha256")
        == (published_contract_manifest.get("capabilityMatrix") or {}).get("sha256"),
        "Capability matrix resource should expose the published capability-matrix SHA-256 from the contract manifest",
    )
    assert_true(
        matrix_entries["pksim5-project"]["policy"] == "conversion-only",
        "Capability matrix resource should preserve the conversion-only PK-Sim boundary",
    )
    contract_manifest_resource = http_json(f"{base_url}/mcp/resources/contract-manifest", timeout=30)
    manifest = contract_manifest_resource["manifest"]
    published_release_bundle_manifest = json.loads(
        PUBLISHED_RELEASE_BUNDLE_MANIFEST.read_text(encoding="utf-8")
    )
    release_bundle_manifest_resource = http_json(
        f"{base_url}/mcp/resources/release-bundle-manifest",
        timeout=30,
    )
    release_bundle_manifest = release_bundle_manifest_resource["manifest"]
    assert_true(
        manifest.get("contractVersion") == CONTRACT_VERSION,
        f"Contract manifest resource should advertise {CONTRACT_VERSION}: {manifest}",
    )
    assert_true(
        contract_manifest_resource.get("sha256") == file_sha256(PUBLISHED_CONTRACT_MANIFEST),
        "Contract manifest resource should expose the SHA-256 of the published contract manifest artifact",
    )
    assert_true(
        int((manifest.get("artifactCounts") or {}).get("schemas") or 0) == len(REQUIRED_SCHEMA_IDS),
        "Contract manifest should inventory the full published PBPK-side schema family",
    )
    manifest_schema_ids = {entry["schemaId"] for entry in manifest.get("schemas") or []}
    assert_true(
        REQUIRED_SCHEMA_IDS.issubset(manifest_schema_ids),
        f"Contract manifest is missing published schema ids: {sorted(REQUIRED_SCHEMA_IDS - manifest_schema_ids)}",
    )
    assessment_manifest_entry = next(
        entry for entry in manifest.get("schemas") or [] if entry["schemaId"] == "assessmentContext.v1"
    )
    assert_true(
        assessment_schema.get("sha256") == assessment_manifest_entry.get("sha256"),
        "Assessment schema resource should expose the published schema SHA-256 from the contract manifest",
    )
    assert_true(
        assessment_schema.get("exampleSha256") == assessment_manifest_entry.get("exampleSha256"),
        "Assessment schema resource should expose the published example SHA-256 from the contract manifest",
    )
    assert_true(
        "schemas/extraction-record.json" in (manifest.get("legacyArtifactsExcluded") or []),
        "Contract manifest should explicitly exclude the legacy extraction-record schema from the PBPK-side object family",
    )
    assert_true(
        (manifest.get("contractManifest") or {}).get("classification") == "normative",
        "Contract manifest should classify its own JSON artifact as normative",
    )
    assert_true(
        (manifest.get("capabilityMatrix") or {}).get("classification") == "normative",
        "Contract manifest should classify the capability matrix as normative",
    )
    assert_true(
        all(entry.get("classification") == "normative" for entry in manifest.get("schemas") or []),
        "Contract manifest should classify published schema entries as normative",
    )
    supporting_artifacts = manifest.get("supportingArtifacts") or []
    assert_true(
        all(entry.get("classification") == "supporting" for entry in supporting_artifacts),
        "Contract manifest should classify supporting artifacts explicitly",
    )
    assert_true(
        any(entry.get("relativePath") == "schemas/README.md" for entry in supporting_artifacts),
        "Contract manifest should inventory supporting schema documentation",
    )
    assert_true(
        any(entry.get("relativePath") == "docs/hardening_migration_notes.md" for entry in supporting_artifacts),
        "Contract manifest should hash the hardening migration notes as a supporting artifact",
    )
    assert_true(
        any(entry.get("relativePath") == "docs/pbk_reviewer_signoff_checklist.md" for entry in supporting_artifacts),
        "Contract manifest should hash the reviewer sign-off checklist as a supporting artifact",
    )
    assert_true(
        any(entry.get("relativePath") == "docs/post_release_audit_plan.md" for entry in supporting_artifacts),
        "Contract manifest should hash the post-release audit plan as a supporting artifact",
    )
    assert_true(
        any(
            entry.get("relativePath") == "scripts/release_readiness_check.py"
            for entry in supporting_artifacts
        ),
        "Contract manifest should hash the live release-readiness script as a supporting artifact",
    )
    assert_true(
        any(
            entry.get("relativePath") == "tests/test_runtime_security_live_stack.py"
            for entry in supporting_artifacts
        ),
        "Contract manifest should hash the live runtime security suite as a supporting artifact",
    )
    legacy_policy = manifest.get("legacyArtifactPolicy") or []
    assert_true(
        any(
            entry.get("relativePath") == "schemas/extraction-record.json"
            and entry.get("classification") == "legacy-excluded"
            for entry in legacy_policy
        ),
        "Contract manifest should publish the legacy-excluded extraction-record policy entry",
    )
    assert_true(
        release_bundle_manifest_resource.get("sha256") == file_sha256(PUBLISHED_RELEASE_BUNDLE_MANIFEST),
        "Release bundle manifest resource should expose the SHA-256 of the published release bundle manifest artifact",
    )
    assert_true(
        release_bundle_manifest_resource.get("bundleSha256")
        == published_release_bundle_manifest.get("bundleSha256"),
        "Release bundle manifest resource should preserve the published whole-release bundle digest",
    )
    assert_true(
        int(release_bundle_manifest_resource.get("fileCount") or 0)
        == int(published_release_bundle_manifest.get("fileCount") or 0),
        "Release bundle manifest resource should preserve the published whole-release file count",
    )
    release_bundle_paths = {
        str(entry.get("relativePath"))
        for entry in release_bundle_manifest.get("files") or []
        if entry.get("relativePath")
    }
    assert_true(
        "scripts/release_readiness_check.py" in release_bundle_paths,
        "Release bundle manifest should include the live release-readiness script",
    )
    assert_true(
        "tests/test_runtime_security_live_stack.py" in release_bundle_paths,
        "Release bundle manifest should include the live runtime security suite",
    )
    assert_true(
        (manifest.get("resourceEndpoints") or {}).get("releaseBundleManifest")
        == "/mcp/resources/release-bundle-manifest",
        "Contract manifest should publish the release-bundle resource endpoint",
    )
    summary["resourceCatalog"] = {
        "schemaCount": schema_catalog["total"],
        "assessmentContextSchemaPublished": "assessmentContext.v1" in schema_ids,
        "capabilityMatrixEntries": capability_resource["entryCount"],
        "contractManifestSchemas": int((manifest.get("artifactCounts") or {}).get("schemas") or 0),
        "contractManifestSupportingArtifacts": int((manifest.get("artifactCounts") or {}).get("supporting") or 0),
        "releaseBundleFiles": int(release_bundle_manifest_resource.get("fileCount") or 0),
        "releaseBundleSha256": release_bundle_manifest_resource.get("bundleSha256"),
    }

    full_catalog = call_tool(base_url, "discover_models", {"limit": 200}, timeout=30)
    catalog_formats = sorted({item["runtimeFormat"] for item in full_catalog["items"]})
    assert_true(
        set(catalog_formats).issubset({"pkml", "r"}),
        f"discover_models exposed unsupported runtime formats: {catalog_formats}",
    )

    ospsuite_catalog = call_tool(
        base_url,
        "discover_models",
        {"backend": "ospsuite", "limit": 50},
        timeout=30,
    )
    pkml_matches = [
        item for item in ospsuite_catalog["items"] if item["filePath"] == PREGNANCY_PKML
    ]
    assert_true(bool(pkml_matches), "Reference .pkml model not discoverable through ospsuite catalog view")
    assert_true(
        not bool(pkml_matches[0]["populationSimulation"]),
        f"OSPSuite .pkml entry should not advertise generic population support: {pkml_matches[0]}",
    )
    assert_true(
        bool(reference_matches[0]["populationSimulation"]),
        f"Reference rxode2 model should advertise declared population support: {reference_matches[0]}",
    )
    summary["capabilityMatrix"] = {
        "discoverableRuntimeFormats": catalog_formats,
        "conversionOnlyFormatsExcludedFromCatalog": True,
        "ospsuitePkmlPopulationSimulation": bool(pkml_matches[0]["populationSimulation"]),
        "rxode2ReferencePopulationSimulation": bool(reference_matches[0]["populationSimulation"]),
    }

    external_bundle = call_tool(
        base_url,
        "ingest_external_pbpk_bundle",
        {
            "sourcePlatform": "GastroPlus",
            "sourceVersion": "10.1",
            "modelName": "Release readiness external import",
            "assessmentContext": {
                "contextOfUse": {"regulatoryUse": "research-only"},
                "domain": {"species": "human", "route": "oral"},
                "targetOutput": "Plasma|Parent|Concentration",
            },
            "internalExposure": {
                "targetOutput": "Plasma|Parent|Concentration",
                "species": "human",
                "route": "oral",
                "metrics": {
                    "cmax": {"value": 2.5, "unit": "uM"},
                    "auc0Tlast": {"value": 7.1, "unit": "uM*h"},
                },
            },
            "qualification": {
                "evidenceLevel": "L2",
                "verificationStatus": "checked",
                "platformClass": "commercial",
            },
            "uncertaintyRegister": {
                "ref": "unc-reg-readiness-001",
                "source": "assessment-workbench",
                "scope": "tier-1-systemic",
            },
            "pod": {
                "ref": "pod-readiness-001",
                "metric": "cmax",
                "unit": "uM",
                "source": "httr-benchmark",
            },
            "comparisonMetric": "cmax",
        },
        timeout=30,
    )
    assert_true(
        external_bundle["ngraObjects"]["berInputBundle"]["status"] == "ready-for-external-ber-calculation",
        "External PBPK ingestion should produce a BER-ready bundle when PoD metadata and exposure metrics are present",
    )
    assert_true(
        external_bundle["ngraObjects"]["berInputBundle"]["decisionOwner"] == "external-orchestrator",
        "External PBPK ingestion should preserve the boundary that BER calculation is owned by an external orchestrator",
    )
    assert_true(
        external_bundle["ngraObjects"]["pointOfDepartureReference"]["status"] == "attached-external-reference",
        "External PBPK ingestion should normalize the external PoD reference into a typed handoff object",
    )
    assert_true(
        external_bundle["ngraObjects"]["uncertaintyHandoff"]["decisionOwner"] == "external-orchestrator",
        "External PBPK ingestion should keep cross-domain uncertainty synthesis outside PBPK MCP",
    )
    assert_true(
        external_bundle["ngraObjects"]["uncertaintyRegisterReference"]["status"] == "attached-external-reference",
        "External PBPK ingestion should normalize an external uncertainty-register reference when one is supplied",
    )
    summary["externalImport"] = {
        "sourcePlatform": external_bundle["externalRun"]["sourcePlatform"],
        "berBundleStatus": external_bundle["ngraObjects"]["berInputBundle"]["status"],
        "decisionOwner": external_bundle["ngraObjects"]["berInputBundle"]["decisionOwner"],
        "podReferenceStatus": external_bundle["ngraObjects"]["pointOfDepartureReference"]["status"],
        "uncertaintyHandoffStatus": external_bundle["ngraObjects"]["uncertaintyHandoff"]["status"],
        "uncertaintyRegisterStatus": external_bundle["ngraObjects"]["uncertaintyRegisterReference"]["status"],
    }

    pksim5_error = call_tool_error(
        base_url,
        "load_simulation",
        {"filePath": PKSIM5_PROJECT, "simulationId": f"reject-pksim5-{uuid4().hex[:8]}"},
        critical=True,
        timeout=60,
    )
    assert_true(
        "Direct .pksim5 loading is not supported" in pksim5_error,
        f".pksim5 rejection message was not explicit enough: {pksim5_error}",
    )
    assert_true(
        "export the PK-Sim project to .pkml first" in pksim5_error,
        f".pksim5 rejection message did not include conversion guidance: {pksim5_error}",
    )

    manifest_check = call_tool(
        base_url,
        "validate_model_manifest",
        {"filePath": REFERENCE_MODEL},
        timeout=60,
    )
    assert_true(
        manifest_check["manifest"]["qualificationState"]["state"] == "research-use",
        f"Unexpected reference_compound manifest qualification state: {manifest_check}",
    )
    assert_true(
        manifest_check["manifest"]["manifestStatus"] in {"valid", "partial"},
        f"Reference compound manifest should be statically inspectable: {manifest_check}",
    )
    assert_true(
        bool((manifest_check.get("curationSummary") or {}).get("ngraDeclarationsExplicit")),
        f"Live reference_compound manifest should preserve explicit NGRA boundary declarations: {manifest_check}",
    )
    assert_true(
        bool((manifest_check.get("curationSummary") or {}).get("exportBlockPolicy")),
        f"Live reference_compound manifest should expose curation export-block semantics: {manifest_check}",
    )
    assert_true(
        ((manifest_check.get("curationSummary") or {}).get("renderingGuardrails") or {}).get(
            "actionIfRequiredFieldsMissing"
        )
        == "refuse-rendering",
        f"Live reference_compound manifest should expose refusal semantics for lossy rendering: {manifest_check}",
    )
    benchmark_readiness = (manifest_check.get("curationSummary") or {}).get("regulatoryBenchmarkReadiness") or {}
    assert_true(
        bool(benchmark_readiness.get("advisoryOnly")),
        f"Live reference_compound manifest should expose benchmark readiness as an advisory-only surface: {manifest_check}",
    )
    benchmark_bar_source = benchmark_readiness.get("benchmarkBarSource") or {}
    assert_true(
        bool(benchmark_bar_source.get("sourceManifestSha256")),
        f"Live reference_compound manifest should preserve the benchmark source-manifest hash for traceability: {manifest_check}",
    )
    assert_true(
        bool(benchmark_bar_source.get("fetchedLockSha256")),
        f"Live reference_compound manifest should preserve the benchmark fetched-lock hash for traceability: {manifest_check}",
    )
    assert_true(
        benchmark_bar_source.get("sourceResolution") in {
            "direct-lock-files",
            "audit-manifest-fallback",
            "packaged-contract-fallback",
        },
        f"Live reference_compound manifest should describe how benchmark source hashes were resolved: {manifest_check}",
    )
    assert_true(
        bool(benchmark_readiness.get("recommendedNextArtifacts")),
        f"Live reference_compound manifest should expose benchmark-derived next-artifact guidance: {manifest_check}",
    )
    manifest_contract = manifest_check.get("trustSurfaceContract") or {}
    assert_true(
        manifest_contract.get("tool") == "validate_model_manifest",
        f"validate_model_manifest should expose a top-level trust-surface contract: {manifest_check}",
    )
    assert_true(
        any(
            surface.get("surfacePath") == "curationSummary"
            for surface in (manifest_contract.get("surfaces") or [])
            if isinstance(surface, dict)
        ),
        f"validate_model_manifest trust-surface contract should point clients at curationSummary: {manifest_check}",
    )

    reference_id = f"release-ref-{uuid4().hex[:8]}"
    reference_load = call_tool(
        base_url,
        "load_simulation",
        {"filePath": REFERENCE_MODEL, "simulationId": reference_id},
        critical=True,
        timeout=120,
    )
    assert_true(reference_load["backend"] == "rxode2", f"Unexpected reference model backend: {reference_load}")

    reference_validation = call_tool(
        base_url,
        "validate_simulation_request",
        {"simulationId": reference_id, "request": {"route": "iv-infusion", "contextOfUse": "research-only"}},
        timeout=60,
    )
    assert_true(reference_validation["validation"]["ok"] is True, "Reference compound validation did not pass in-domain")
    assert_true(
        reference_validation["ngraObjects"]["assessmentContext"]["objectType"] == "assessmentContext.v1",
        "validate_simulation_request should expose an assessmentContext NGRA object",
    )
    assert_true(
        reference_validation["ngraObjects"]["pbpkQualificationSummary"]["state"] == "research-use",
        "validate_simulation_request should expose the derived PBPK qualification summary",
    )
    assert_true(
        bool((reference_validation["ngraObjects"]["pbpkQualificationSummary"] or {}).get("exportBlockPolicy")),
        "validate_simulation_request should expose qualification-level export-block semantics",
    )
    validation_contract = reference_validation.get("trustSurfaceContract") or {}
    assert_true(
        validation_contract.get("tool") == "validate_simulation_request",
        f"validate_simulation_request should expose a top-level trust-surface contract: {reference_validation}",
    )
    assert_true(
        any(
            surface.get("surfacePath") == "ngraObjects.pbpkQualificationSummary"
            for surface in (validation_contract.get("surfaces") or [])
            if isinstance(surface, dict)
        ),
        f"validate_simulation_request trust-surface contract should point clients at pbpkQualificationSummary: {reference_validation}",
    )
    assert_true(
        reference_validation["ngraObjects"]["internalExposureEstimate"]["status"] == "not-available",
        "validate_simulation_request should not fabricate an internal exposure estimate before a deterministic run exists",
    )
    cis_validation_signoff = http_json(
        f"{base_url}/review_signoff",
        payload={
            "simulationId": reference_id,
            "scope": "validate_simulation_request",
            "disposition": "acknowledged",
            "rationale": "Release readiness recorded bounded validation review with the research-only claim boundary kept intact.",
            "confirm": True,
        },
        timeout=30,
    )
    assert_true(
        (cis_validation_signoff.get("operatorReviewSignoff") or {}).get("status") == "recorded",
        f"Validation sign-off route did not return a recorded summary: {cis_validation_signoff}",
    )
    reference_validation = call_tool(
        base_url,
        "validate_simulation_request",
        {"simulationId": reference_id, "request": {"route": "iv-infusion", "contextOfUse": "research-only"}},
        timeout=60,
    )
    assert_true(
        (reference_validation.get("operatorReviewSignoff") or {}).get("status") == "recorded",
        f"Validation output should surface the additive operator review sign-off summary: {reference_validation}",
    )
    assert_true(
        (reference_validation.get("operatorReviewSignoff") or {}).get("scope") == "validate_simulation_request",
        f"Validation output surfaced the wrong sign-off scope: {reference_validation}",
    )

    reference_verification = call_tool(
        base_url,
        "run_verification_checks",
        {
            "simulationId": reference_id,
            "request": {"route": "iv-infusion", "contextOfUse": "research-only"},
            "includePopulationSmoke": True,
            "populationCohort": {"size": 10, "seed": 42},
            "populationOutputs": {"aggregates": ["meanCmax", "sdCmax", "meanAUC"]},
        },
        timeout=180,
    )
    assert_true(
        reference_verification["verification"]["status"] == "passed",
        f"Reference compound verification checks did not pass: {reference_verification}",
    )
    assert_true(
        any(check["id"] == "deterministic-smoke" for check in reference_verification["verification"]["checks"]),
        "Verification output is missing the deterministic smoke check",
    )
    assert_true(
        any(check["id"] == "population-smoke" for check in reference_verification["verification"]["checks"]),
        "Verification output is missing the population smoke check",
    )
    assert_true(
        any(
            check["id"] == "deterministic-integrity" and check["status"] == "passed"
            for check in reference_verification["verification"]["checks"]
        ),
        "Verification output is missing the deterministic integrity check",
    )
    assert_true(
        any(
            check["id"] == "deterministic-reproducibility" and check["status"] == "passed"
            for check in reference_verification["verification"]["checks"]
        ),
        "Verification output is missing the deterministic reproducibility check",
    )
    assert_true(
        any(
            check["id"] == "parameter-unit-consistency" and check["status"] == "passed"
            for check in reference_verification["verification"]["checks"]
        ),
        "Verification output is missing the parameter-unit-consistency check",
    )
    assert_true(
        any(
            check["id"] == "systemic-flow-consistency" and check["status"] == "passed"
            for check in reference_verification["verification"]["checks"]
        ),
        "Verification output is missing the systemic-flow-consistency check",
    )
    assert_true(
        any(
            check["id"] == "renal-volume-consistency" and check["status"] == "passed"
            for check in reference_verification["verification"]["checks"]
        ),
        "Verification output is missing the renal-volume-consistency check",
    )
    assert_true(
        any(
            check["id"] == "mass-balance" and check["status"] == "passed"
            for check in reference_verification["verification"]["checks"]
        ),
        "Verification output is missing the mass-balance check",
    )
    assert_true(
        any(
            check["id"] == "solver-stability" and check["status"] == "passed"
            for check in reference_verification["verification"]["checks"]
        ),
        "Verification output is missing the solver-stability check",
    )
    verification_contract = reference_verification.get("trustSurfaceContract") or {}
    assert_true(
        verification_contract.get("tool") == "run_verification_checks",
        f"run_verification_checks should expose a top-level trust-surface contract: {reference_verification}",
    )
    assert_true(
        any(
            surface.get("surfacePath") == "qualificationState"
            for surface in (verification_contract.get("surfaces") or [])
            if isinstance(surface, dict)
        ),
        f"run_verification_checks trust-surface contract should point clients at qualificationState: {reference_verification}",
    )
    cis_report_signoff = http_json(
        f"{base_url}/review_signoff",
        payload={
            "simulationId": reference_id,
            "scope": "export_oecd_report",
            "disposition": "approved-for-bounded-use",
            "rationale": "Release readiness recorded bounded report review with detached-summary risk still requiring nearby caveats.",
            "confirm": True,
        },
        timeout=30,
    )
    assert_true(
        (cis_report_signoff.get("operatorReviewSignoff") or {}).get("status") == "recorded",
        f"Report sign-off route did not return a recorded summary: {cis_report_signoff}",
    )

    reference_report = call_tool(
        base_url,
        "export_oecd_report",
        {"simulationId": reference_id, "request": {"route": "iv-infusion", "contextOfUse": "research-only"}, "parameterLimit": 5},
        timeout=120,
    )
    cis_report_payload = reference_report["report"]
    assert_true(reference_report["tool"] == "export_oecd_report", "export_oecd_report tool response missing")
    assert_true(cis_report_payload["reportVersion"] == "pbpk-oecd-report.v1", "Unexpected OECD report version")
    assert_true(
        cis_report_payload["oecdCoverage"]["coverageVersion"] == "pbpk-oecd-coverage.v1",
        "The exported OECD report should carry the additive OECD coverage map",
    )
    assert_true(
        cis_report_payload["oecdCoverage"]["affectsChecklistScore"] is False,
        "OECD coverage mapping must remain descriptive and must not affect the checklist score",
    )
    assert_true(
        reference_report["ngraObjects"]["assessmentContext"]["objectType"] == "assessmentContext.v1",
        "export_oecd_report should expose top-level NGRA objects for downstream workflows",
    )
    assert_true(
        "ngraObjects" in cis_report_payload,
        "The exported OECD report should remain self-contained and carry its NGRA object block",
    )
    assert_true(
        cis_report_payload["ngraObjects"]["internalExposureEstimate"]["status"] == "available",
        "The exported OECD report should derive internal exposure from the latest deterministic results handle",
    )
    assert_true(
        cis_report_payload["ngraObjects"]["berInputBundle"]["status"] == "incomplete",
        "The PBPK-side BER bundle should remain incomplete until an external point-of-departure reference is attached",
    )
    assert_true(
        cis_report_payload["ngraObjects"]["uncertaintyHandoff"]["status"] == "ready-for-cross-domain-uncertainty-synthesis",
        "The exported OECD report should expose a ready PBPK-side uncertainty handoff object",
    )
    assert_true(
        (reference_report.get("operatorReviewSignoff") or {}).get("status") == "recorded",
        f"Report export should surface the additive operator review sign-off summary: {reference_report}",
    )
    report_contract = reference_report.get("trustSurfaceContract") or {}
    assert_true(
        report_contract.get("tool") == "export_oecd_report",
        f"export_oecd_report should expose a top-level trust-surface contract: {reference_report}",
    )
    report_surface_paths = {
        surface.get("surfacePath")
        for surface in (report_contract.get("surfaces") or [])
        if isinstance(surface, dict)
    }
    assert_true(
        {"report.humanReviewSummary", "report.ngraObjects.pbpkQualificationSummary"}.issubset(report_surface_paths),
        f"export_oecd_report trust-surface contract should point clients at the report review and qualification surfaces: {reference_report}",
    )
    assert_true(
        ((cis_report_payload.get("humanReviewSummary") or {}).get("operatorReviewSignoff") or {}).get("status")
        == "recorded",
        f"report.humanReviewSummary should surface the additive operator review sign-off summary: {reference_report}",
    )
    assert_true(
        bool((cis_report_payload.get("exportBlockPolicy") or {}).get("blockReasons")),
        f"report.exportBlockPolicy should expose machine-readable block reasons: {reference_report}",
    )
    assert_true(
        bool(
            ((cis_report_payload.get("humanReviewSummary") or {}).get("exportBlockPolicy") or {}).get("blockReasons")
        ),
        f"report.humanReviewSummary should surface export-block semantics: {reference_report}",
    )
    assert_true(
        ((cis_report_payload.get("humanReviewSummary") or {}).get("renderingGuardrails") or {}).get(
            "actionIfRequiredFieldsMissing"
        )
        == "refuse-rendering",
        f"report.humanReviewSummary should expose refusal semantics for lossy rendering: {reference_report}",
    )
    assert_true(
        cis_report_payload["oecdChecklist"]["modelPerformanceAndPredictivity"]["status"] == "partial",
        "Reference compound performance checklist should remain partial until real fit evidence is attached",
    )
    assert_true(
        cis_report_payload["performanceEvidence"]["returnedRows"] >= 1,
        "Reference compound report should include exported performance evidence rows",
    )
    assert_true(
        cis_report_payload["performanceEvidence"]["strongestEvidenceClass"] == "runtime-smoke",
        "Reference compound report should classify bundled performance evidence as runtime smoke only",
    )
    assert_true(
        cis_report_payload["performanceEvidence"]["qualificationBoundary"] == "runtime-or-internal-evidence-only",
        "Reference compound report should keep a runtime/internal-only qualification boundary until predictive datasets are attached",
    )
    assert_true(
        cis_report_payload["performanceEvidence"]["limitedToRuntimeOrInternalEvidence"] is True,
        "Reference compound report should explicitly mark its current performance evidence as runtime/internal only",
    )
    assert_true(
        cis_report_payload["performanceEvidence"]["supportsObservedVsPredictedEvidence"] is False,
        "Reference compound report must not claim observed-versus-predicted evidence when none is bundled",
    )
    assert_true(
        cis_report_payload["performanceEvidence"]["supportsPredictiveDatasetEvidence"] is False,
        "Reference compound report must not claim predictive-dataset evidence when none is bundled",
    )
    assert_true(
        cis_report_payload["performanceEvidence"]["supportsExternalQualificationEvidence"] is False,
        "Reference compound report must not claim external qualification evidence when none is bundled",
    )
    assert_true(
        cis_report_payload["parameterTable"]["coverage"]["rowCount"] == cis_report_payload["parameterTable"]["matchedRows"],
        "Parameter-table coverage should describe the matched parameter table rows",
    )
    assert_true(
        "rowsWithExperimentalConditions" in cis_report_payload["parameterTable"]["coverage"],
        "Parameter-table coverage should expose study-condition coverage counts",
    )
    uncertainty_row_ids = {entry["id"] for entry in cis_report_payload["uncertaintyEvidence"]["rows"]}
    assert_true(
        "bounded-variability-propagation-summary" in uncertainty_row_ids,
        f"Reference compound report uncertainty evidence is missing the variability propagation summary row: {sorted(uncertainty_row_ids)}",
    )
    assert_true(
        any(row_id.startswith("bounded-variability-propagation-") and row_id != "bounded-variability-propagation-summary" for row_id in uncertainty_row_ids),
        f"Reference compound report uncertainty evidence is missing quantitative variability propagation rows: {sorted(uncertainty_row_ids)}",
    )
    assert_true(
        "local-sensitivity-screen-summary" in uncertainty_row_ids,
        f"Reference compound report uncertainty evidence is missing the local sensitivity summary row: {sorted(uncertainty_row_ids)}",
    )
    assert_true(
        any(row_id.startswith("local-sensitivity-") and row_id != "local-sensitivity-screen-summary" for row_id in uncertainty_row_ids),
        f"Reference compound report uncertainty evidence is missing quantitative local sensitivity rows: {sorted(uncertainty_row_ids)}",
    )
    assert_true(
        cis_report_payload["executableVerification"]["included"] is True,
        "Reference compound report should include the stored executable verification snapshot after run_verification_checks",
    )
    assert_true(
        cis_report_payload["executableVerification"]["status"] == "passed",
        f"Reference compound report carried an unexpected executable verification status: {cis_report_payload['executableVerification']}",
    )
    report_check_ids = {entry["id"] for entry in cis_report_payload["executableVerification"]["checks"]}
    assert_true(
        "mass-balance" in report_check_ids,
        f"Reference compound report executable verification is missing the mass-balance check: {sorted(report_check_ids)}",
    )
    assert_true(
        "parameter-unit-consistency" in report_check_ids,
        f"Reference compound report executable verification is missing the parameter-unit-consistency check: {sorted(report_check_ids)}",
    )
    assert_true(
        "systemic-flow-consistency" in report_check_ids,
        f"Reference compound report executable verification is missing the systemic-flow-consistency check: {sorted(report_check_ids)}",
    )
    assert_true(
        "renal-volume-consistency" in report_check_ids,
        f"Reference compound report executable verification is missing the renal-volume-consistency check: {sorted(report_check_ids)}",
    )
    assert_true(
        "solver-stability" in report_check_ids,
        f"Reference compound report executable verification is missing the solver-stability check: {sorted(report_check_ids)}",
    )

    run_id = f"{reference_id}-smoke"
    reference_submit = call_tool(
        base_url,
        "run_simulation",
        {"simulationId": reference_id, "runId": run_id},
        critical=True,
        timeout=60,
    )
    reference_job = poll_job(
        base_url,
        reference_submit["jobId"],
        timeout_seconds=ASYNC_REFERENCE_JOB_TIMEOUT_SECONDS,
    )
    assert_true(reference_job["status"] == "succeeded", f"Reference compound simulation failed: {reference_job}")
    reference_results = call_tool(base_url, "get_results", {"resultsId": reference_job["resultId"]}, timeout=60)
    assert_true(len(reference_results["series"]) > 0, "Reference compound deterministic result returned no series")

    population_tool_schema = next(
        tool for tool in tool_catalog["tools"] if tool["name"] == "run_population_simulation"
    )
    required_population_fields = set(population_tool_schema["inputSchema"].get("required") or [])
    assert_true(
        "modelPath" not in required_population_fields,
        f"run_population_simulation should not require modelPath in the converged contract: {required_population_fields}",
    )

    reference_population = call_tool(
        base_url,
        "run_population_simulation",
        {
            "simulationId": reference_id,
            "cohort": {"size": 10, "seed": 42},
            "outputs": {"aggregates": ["meanCmax", "sdCmax", "meanAUC"]},
        },
        critical=True,
        timeout=60,
    )
    reference_population_job = poll_job(base_url, reference_population["jobId"], timeout_seconds=240)
    assert_true(
        reference_population_job["status"] == "succeeded",
        f"Reference compound population simulation failed: {reference_population_job}",
    )
    reference_population_results = call_tool(
        base_url,
        "get_population_results",
        {"resultsId": reference_population_job["resultId"]},
        timeout=60,
    )
    assert_true(
        len(reference_population_results.get("aggregates") or {}) > 0,
        "Reference compound population result returned no aggregates",
    )

    pkml_id = f"release-pkml-{uuid4().hex[:8]}"
    pkml_load = call_tool(
        base_url,
        "load_simulation",
        {"filePath": PREGNANCY_PKML, "simulationId": pkml_id},
        critical=True,
        timeout=OSPSUITE_LOAD_TIMEOUT_SECONDS,
    )
    assert_true(pkml_load["backend"] == "ospsuite", f"Unexpected PKML backend: {pkml_load}")

    pkml_report = call_tool(
        base_url,
        "export_oecd_report",
        {
            "simulationId": pkml_id,
            "request": {"contextOfUse": "research-only"},
            "includeParameterTable": False,
            "parameterLimit": 3,
        },
        timeout=OSPSUITE_REPORT_TIMEOUT_SECONDS,
    )
    pkml_report_payload = pkml_report["report"]
    assert_true(pkml_report_payload["profile"]["profileSource"]["type"] == "sidecar", "OSPSuite sidecar provenance was not preserved")
    assert_true(
        pkml_report_payload["parameterTable"]["included"] is False,
        "OSPSuite release-gate report should skip the live parameter-table preview and rely on the bridge regression instead",
    )

    summary["reference_compound"] = {
        "simulationId": reference_id,
        "manifestState": manifest_check["manifest"]["qualificationState"]["state"],
        "benchmarkReadinessStatus": benchmark_readiness.get("overallStatus"),
        "benchmarkResemblance": benchmark_readiness.get("modelResemblance"),
        "benchmarkTopGapIds": [
            item.get("dimensionId")
            for item in (benchmark_readiness.get("prioritizedGaps") or [])[:3]
            if isinstance(item, dict) and item.get("dimensionId")
        ],
        "benchmarkRecommendedArtifacts": list(benchmark_readiness.get("recommendedNextArtifacts") or [])[:3],
        "validationDecision": reference_validation["validation"]["assessment"]["decision"],
        "verificationStatus": reference_verification["verification"]["status"],
        "executableVerificationStatus": cis_report_payload["executableVerification"]["status"],
        "reportChecklistScore": cis_report_payload["oecdChecklistScore"],
        "performanceChecklistStatus": cis_report_payload["oecdChecklist"]["modelPerformanceAndPredictivity"]["status"],
        "performanceEvidenceRows": cis_report_payload["performanceEvidence"]["returnedRows"],
        "performanceEvidenceBoundary": cis_report_payload["performanceEvidence"]["qualificationBoundary"],
        "uncertaintyHandoffStatus": cis_report_payload["ngraObjects"]["uncertaintyHandoff"]["status"],
        "resultSeries": len(reference_results["series"]),
        "populationAggregates": sorted((reference_population_results.get("aggregates") or {}).keys()),
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
        "--bearer-token",
        default=None,
        help="Bearer token to use for authenticated MCP requests. Overrides dev-token generation when set.",
    )
    parser.add_argument(
        "--auth-dev-secret",
        default="pbpk-local-dev-secret-32bytes-long",
        help="HS256 dev secret used to mint an operator token for local development stacks.",
    )
    parser.add_argument(
        "--skip-unit-tests",
        action="store_true",
        help="Skip the local OECD bridge unit tests and only run live stack checks.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    REQUEST_HEADERS.clear()
    REQUEST_HEADERS.update(
        build_auth_headers(
            bearer_token=args.bearer_token,
            auth_dev_secret=args.auth_dev_secret,
        )
    )
    summary = run_release_check(
        args.base_url,
        skip_unit_tests=args.skip_unit_tests,
        bearer_token=args.bearer_token,
        auth_dev_secret=args.auth_dev_secret,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
