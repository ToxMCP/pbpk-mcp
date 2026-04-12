from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import unittest
from pathlib import Path
from uuid import uuid4


API_BASE_URL = "http://127.0.0.1:8000"
API_CONTAINER = "pbpk_mcp-api-1"
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_bridge.security.simple_jwt import jwt  # noqa: E402


DEV_AUTH_SECRET = "pbpk-local-dev-secret"
REFERENCE_MODEL = "/app/var/models/rxode2/reference_compound/reference_compound_population_rxode2_model.R"


def _auth_headers(role: str) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": f"runtime-security-live-{role}",
            "roles": [role],
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        },
        DEV_AUTH_SECRET,
        algorithm="HS256",
    )
    return {"authorization": f"Bearer {token}"}


def _decode_body(body: bytes) -> object:
    text = body.decode()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def api_request(
    path: str,
    *,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, object]:
    data = None
    request_headers = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode()
        request_headers.setdefault("content-type", "application/json")
    req = urllib.request.Request(f"{API_BASE_URL}{path}", data=data, headers=request_headers)
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


def jsonrpc_request(
    method: str,
    *,
    params: dict | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    return api_request(
        "/mcp",
        payload={
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        },
        headers=headers,
    )


def _tool_names(payload: dict) -> set[str]:
    return {
        str(tool.get("name"))
        for tool in (payload.get("tools") or [])
        if isinstance(tool, dict) and tool.get("name")
    }


@unittest.skipUnless(shutil.which("docker"), "docker is required for live-stack security tests")
class RuntimeSecurityLiveStackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        probe = subprocess.run(
            ["docker", "exec", API_CONTAINER, "true"],
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0:
            raise unittest.SkipTest(f"{API_CONTAINER} is not available")

    def test_anonymous_rest_catalog_is_viewer_only(self) -> None:
        response = api_request("/mcp/list_tools")

        self.assertEqual(response["status"], 200)
        self.assertEqual(response["headers"].get("x-pbpk-security-mode"), "anonymous-development")
        self.assertIsInstance(response["body"], dict)
        tool_names = _tool_names(response["body"])
        self.assertIn("discover_models", tool_names)
        self.assertNotIn("load_simulation", tool_names)
        self.assertNotIn("run_simulation", tool_names)

    def test_role_filtered_rest_catalog_and_confirmation_requirements(self) -> None:
        viewer_catalog = api_request("/mcp/list_tools", headers=_auth_headers("viewer"))
        operator_catalog = api_request("/mcp/list_tools", headers=_auth_headers("operator"))

        self.assertEqual(viewer_catalog["status"], 200)
        self.assertEqual(operator_catalog["status"], 200)
        self.assertIsInstance(viewer_catalog["body"], dict)
        self.assertIsInstance(operator_catalog["body"], dict)

        viewer_tools = _tool_names(viewer_catalog["body"])
        operator_tools = _tool_names(operator_catalog["body"])
        self.assertNotIn("load_simulation", viewer_tools)
        self.assertTrue({"load_simulation", "run_simulation"}.issubset(operator_tools))

        anonymous_call = api_request(
            "/mcp/call_tool",
            payload={
                "tool": "load_simulation",
                "critical": True,
                "arguments": {
                    "filePath": REFERENCE_MODEL,
                    "simulationId": f"rest-anon-denied-{uuid4().hex[:8]}",
                },
            },
        )
        self.assertEqual(anonymous_call["status"], 403)
        self.assertIn("Insufficient permissions", json.dumps(anonymous_call["body"]))

        operator_no_confirm = api_request(
            "/mcp/call_tool",
            payload={
                "tool": "load_simulation",
                "arguments": {
                    "filePath": REFERENCE_MODEL,
                    "simulationId": f"rest-no-confirm-{uuid4().hex[:8]}",
                },
            },
            headers=_auth_headers("operator"),
            timeout=60,
        )
        self.assertEqual(operator_no_confirm["status"], 428)
        self.assertIn("critical=true", json.dumps(operator_no_confirm["body"]).lower())

    def test_live_protected_routes_keep_retired_console_absent(self) -> None:
        metrics_anonymous = api_request("/metrics")
        console_shell = api_request("/console")
        console_asset = api_request("/console/assets/app.js")
        stale_console_static = api_request("/console/static/app.js")
        console_anonymous = api_request("/console/api/samples")

        self.assertEqual(metrics_anonymous["status"], 403)
        self.assertEqual(console_shell["status"], 404)
        self.assertEqual(console_asset["status"], 404)
        self.assertEqual(stale_console_static["status"], 404)
        self.assertEqual(console_anonymous["status"], 404)
        self.assertIn("Insufficient permissions", json.dumps(metrics_anonymous["body"]))
        console_operator = api_request("/console/api/samples", headers=_auth_headers("operator"))
        self.assertEqual(console_operator["status"], 404)

        metrics_admin = api_request("/metrics", headers=_auth_headers("admin"))
        self.assertEqual(metrics_admin["status"], 200)
        self.assertIn("mcp_http_requests_total", str(metrics_admin["body"]))

    def test_review_signoff_route_requires_operator_confirmation_and_allows_viewer_reads(self) -> None:
        simulation_id = f"runtime-signoff-{uuid4().hex[:8]}"
        load_response = api_request(
            "/load_simulation",
            payload={
                "filePath": REFERENCE_MODEL,
                "simulationId": simulation_id,
                "confirm": True,
            },
            headers=_auth_headers("operator"),
            timeout=60,
        )
        self.assertEqual(load_response["status"], 201)

        anonymous_post = api_request(
            "/review_signoff",
            payload={
                "simulationId": simulation_id,
                "scope": "export_oecd_report",
                "disposition": "approved-for-bounded-use",
                "rationale": "Reviewed for bounded report use with explicit caveats retained.",
                "confirm": True,
            },
        )
        self.assertEqual(anonymous_post["status"], 403)

        viewer_post = api_request(
            "/review_signoff",
            payload={
                "simulationId": simulation_id,
                "scope": "export_oecd_report",
                "disposition": "approved-for-bounded-use",
                "rationale": "Reviewed for bounded report use with explicit caveats retained.",
                "confirm": True,
            },
            headers=_auth_headers("viewer"),
        )
        self.assertEqual(viewer_post["status"], 403)

        operator_no_confirm = api_request(
            "/review_signoff",
            payload={
                "simulationId": simulation_id,
                "scope": "export_oecd_report",
                "disposition": "approved-for-bounded-use",
                "rationale": "Reviewed for bounded report use with explicit caveats retained.",
            },
            headers=_auth_headers("operator"),
        )
        self.assertEqual(operator_no_confirm["status"], 428)

        operator_recorded = api_request(
            "/review_signoff",
            payload={
                "simulationId": simulation_id,
                "scope": "export_oecd_report",
                "disposition": "approved-for-bounded-use",
                "rationale": "Reviewed for bounded report use with explicit caveats retained.",
                "confirm": True,
            },
            headers=_auth_headers("operator"),
        )
        self.assertEqual(operator_recorded["status"], 200)
        self.assertEqual(
            operator_recorded["body"]["operatorReviewSignoff"]["status"],
            "recorded",
        )
        self.assertEqual(
            operator_recorded["body"]["operatorReviewGovernance"]["workflowStatus"],
            "descriptive-signoff-only",
        )
        self.assertFalse(operator_recorded["body"]["operatorReviewGovernance"]["supportsOverride"])

        viewer_get = api_request(
            f"/review_signoff?simulationId={simulation_id}&scope=export_oecd_report",
            headers=_auth_headers("viewer"),
        )
        self.assertEqual(viewer_get["status"], 200)
        self.assertEqual(
            viewer_get["body"]["operatorReviewSignoff"]["recordedBy"]["subject"],
            "runtime-security-live-operator",
        )
        self.assertFalse(viewer_get["body"]["operatorReviewGovernance"]["supportsAdjudication"])

        viewer_history = api_request(
            f"/review_signoff/history?simulationId={simulation_id}&scope=export_oecd_report&limit=10",
            headers=_auth_headers("viewer"),
        )
        self.assertEqual(viewer_history["status"], 200)
        self.assertEqual(
            viewer_history["body"]["operatorReviewSignoffHistory"]["entries"][0]["action"],
            "recorded",
        )
        self.assertEqual(
            viewer_history["body"]["operatorReviewSignoffHistory"]["entries"][0]["actor"]["subject"],
            "runtime-security-live-operator",
        )
        self.assertFalse(
            viewer_history["body"]["operatorReviewGovernance"]["signoffConfersDecisionAuthority"]
        )

    def test_jsonrpc_security_matches_rest_posture(self) -> None:
        initialize = jsonrpc_request("initialize", headers={"content-type": "application/json"})
        self.assertEqual(initialize["status"], 200)
        self.assertIsInstance(initialize["body"], dict)
        self.assertEqual(initialize["body"]["result"]["protocolVersion"], "2025-03-26")
        self.assertFalse(initialize["body"]["result"]["capabilities"]["resources"]["enabled"])
        self.assertEqual(
            initialize["body"]["result"]["companionResources"]["mode"],
            "rest-companion-resources",
        )
        self.assertEqual(
            initialize["body"]["result"]["companionResources"]["restBasePath"],
            "/mcp/resources",
        )

        anonymous_list = jsonrpc_request("tools/list", headers={"content-type": "application/json"})
        self.assertEqual(anonymous_list["status"], 200)
        self.assertIsInstance(anonymous_list["body"], dict)
        anonymous_tools = _tool_names(anonymous_list["body"]["result"])
        self.assertIn("discover_models", anonymous_tools)
        self.assertNotIn("load_simulation", anonymous_tools)

        operator_list = jsonrpc_request(
            "tools/list",
            headers={**_auth_headers("operator"), "content-type": "application/json"},
        )
        self.assertEqual(operator_list["status"], 200)
        self.assertIsInstance(operator_list["body"], dict)
        operator_tools = _tool_names(operator_list["body"]["result"])
        self.assertIn("load_simulation", operator_tools)

        anonymous_call = jsonrpc_request(
            "tools/call",
            params={
                "name": "load_simulation",
                "critical": True,
                "arguments": {
                    "filePath": REFERENCE_MODEL,
                    "simulationId": f"rpc-anon-denied-{uuid4().hex[:8]}",
                },
            },
            headers={"content-type": "application/json"},
        )
        self.assertEqual(anonymous_call["status"], 200)
        self.assertIsInstance(anonymous_call["body"], dict)
        self.assertEqual(anonymous_call["body"]["error"]["code"], -32001)

        operator_no_confirm = jsonrpc_request(
            "tools/call",
            params={
                "name": "load_simulation",
                "arguments": {
                    "filePath": REFERENCE_MODEL,
                    "simulationId": f"rpc-no-confirm-{uuid4().hex[:8]}",
                },
            },
            headers={**_auth_headers("operator"), "content-type": "application/json"},
        )
        self.assertEqual(operator_no_confirm["status"], 200)
        self.assertIsInstance(operator_no_confirm["body"], dict)
        self.assertEqual(operator_no_confirm["body"]["error"]["code"], -32002)
        self.assertIn(
            "critical",
            str(operator_no_confirm["body"]["error"]["message"]).lower(),
        )


if __name__ == "__main__":
    unittest.main()
