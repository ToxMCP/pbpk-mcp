from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import validate


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_bridge.app import create_app  # noqa: E402
from mcp_bridge.config import AppConfig  # noqa: E402


def _rpc(method: str, *, params: dict | None = None, request_id: object = 1) -> dict[str, object]:
    payload: dict[str, object] = {"jsonrpc": "2.0", "method": method, "id": request_id}
    if params is not None:
        payload["params"] = params
    return payload


class McpJsonRpcProtocolTests(unittest.TestCase):
    def _build_client(self, **overrides: object) -> TestClient:
        config = AppConfig.model_validate(
            {
                "environment": "development",
                "auth_allow_anonymous": True,
                "audit_enabled": False,
                "service_version": "0.5.0-test",
                **overrides,
            }
        )
        return TestClient(create_app(config=config))

    def test_initialize_defaults_to_latest_protocol_and_clean_success_shape(self) -> None:
        with self._build_client() as client:
            response = client.post("/mcp", json=_rpc("initialize", params={}))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), {"jsonrpc", "id", "result"})
        self.assertEqual(body["result"]["protocolVersion"], "2025-11-25")
        self.assertEqual(body["result"]["capabilities"]["tools"], {"listChanged": False})
        self.assertEqual(body["result"]["capabilities"]["resources"], {"listChanged": False})
        self.assertNotIn("error", body)

    def test_initialize_negotiates_legacy_protocol_when_requested(self) -> None:
        with self._build_client() as client:
            response = client.post(
                "/mcp",
                json=_rpc("initialize", params={"protocolVersion": "2025-03-26"}),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["protocolVersion"], "2025-03-26")

    def test_error_shape_excludes_result_and_rejects_null_id(self) -> None:
        with self._build_client() as client:
            unknown = client.post("/mcp", json=_rpc("no/such/method", request_id="abc"))
            null_id = client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "initialize", "id": None},
            )

        self.assertEqual(unknown.status_code, 200)
        unknown_body = unknown.json()
        self.assertEqual(set(unknown_body), {"jsonrpc", "id", "error"})
        self.assertEqual(unknown_body["id"], "abc")
        self.assertNotIn("result", unknown_body)

        self.assertEqual(null_id.status_code, 400)
        null_id_body = null_id.json()
        self.assertEqual(set(null_id_body), {"jsonrpc", "error"})
        self.assertEqual(null_id_body["error"]["code"], -32600)

    def test_notifications_and_client_responses_return_empty_202(self) -> None:
        with self._build_client() as client:
            initialized = client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "initialized"},
            )
            notification = client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "notifications/progress"},
            )
            client_response = client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": "server-request-1", "result": {}},
            )

        for response in (initialized, notification, client_response):
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.content, b"")

    def test_get_mcp_is_405_until_sse_transport_exists(self) -> None:
        with self._build_client() as client:
            response = client.get("/mcp")

        self.assertEqual(response.status_code, 405)

    def test_tools_list_exposes_output_schema_and_standard_annotations(self) -> None:
        with self._build_client() as client:
            response = client.post("/mcp", json=_rpc("tools/list"))

        self.assertEqual(response.status_code, 200)
        tools = response.json()["result"]["tools"]
        self.assertGreater(len(tools), 0)
        for tool in tools:
            self.assertIn("inputSchema", tool)
            self.assertIn("outputSchema", tool)
            annotations = tool.get("annotations") or {}
            self.assertTrue(
                {"readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"}.issubset(
                    annotations
                )
            )

    def test_tools_call_returns_structured_content_matching_output_schema(self) -> None:
        with self._build_client() as client:
            tools_response = client.post("/mcp", json=_rpc("tools/list"))
            call_response = client.post(
                "/mcp",
                json=_rpc(
                    "tools/call",
                    params={"name": "discover_models", "arguments": {"limit": 1}},
                ),
            )

        catalog = {
            tool["name"]: tool
            for tool in tools_response.json()["result"]["tools"]
            if isinstance(tool, dict)
        }
        result = call_response.json()["result"]
        structured = result["structuredContent"]
        self.assertFalse(result["isError"])
        self.assertEqual(json.loads(result["content"][0]["text"]), structured)
        validate(instance=structured, schema=catalog["discover_models"]["outputSchema"])

    def test_resources_are_listed_and_public_resources_can_be_read_without_auth(self) -> None:
        with self._build_client(auth_allow_anonymous=False) as client:
            listed = client.post("/mcp", json=_rpc("resources/list"))
            read = client.post(
                "/mcp",
                json=_rpc("resources/read", params={"uri": "pbpk://schemas/catalog"}),
            )
            protected = client.post(
                "/mcp",
                json=_rpc("resources/read", params={"uri": "pbpk://models"}),
            )
            templates = client.post("/mcp", json=_rpc("resources/templates/list"))

        self.assertEqual(listed.status_code, 200)
        listed_uris = {item["uri"] for item in listed.json()["result"]["resources"]}
        self.assertIn("pbpk://schemas/catalog", listed_uris)
        self.assertNotIn("pbpk://models", listed_uris)

        self.assertEqual(read.status_code, 200)
        contents = read.json()["result"]["contents"]
        self.assertEqual(contents[0]["uri"], "pbpk://schemas/catalog")
        self.assertIn("items", json.loads(contents[0]["text"]))

        self.assertEqual(protected.status_code, 200)
        self.assertEqual(protected.json()["error"]["code"], -32000)

        template_uris = {
            item["uriTemplate"] for item in templates.json()["result"]["resourceTemplates"]
        }
        self.assertIn("pbpk://parameters/{simulationId}", template_uris)

    def test_authenticated_viewers_can_see_protected_resource_descriptors(self) -> None:
        with self._build_client(auth_allow_anonymous=True) as client:
            response = client.post("/mcp", json=_rpc("resources/list"))

        self.assertEqual(response.status_code, 200)
        uris = {item["uri"] for item in response.json()["result"]["resources"]}
        self.assertIn("pbpk://models", uris)
        self.assertIn("pbpk://simulations", uris)

    def test_transport_origin_and_strict_mode(self) -> None:
        with self._build_client(
            mcp_allowed_origins=("https://allowed.example",),
            mcp_strict_transport=True,
        ) as client:
            invalid_origin = client.post(
                "/mcp",
                headers={
                    "Origin": "https://evil.example",
                    "Accept": "application/json, text/event-stream",
                    "MCP-Protocol-Version": "2025-11-25",
                },
                json=_rpc("initialize"),
            )
            missing_accept = client.post(
                "/mcp",
                headers={"MCP-Protocol-Version": "2025-11-25"},
                json=_rpc("initialize"),
            )
            valid = client.post(
                "/mcp",
                headers={
                    "Origin": "https://allowed.example",
                    "Accept": "application/json, text/event-stream",
                    "MCP-Protocol-Version": "2025-11-25",
                },
                json=_rpc("initialize"),
            )

        self.assertEqual(invalid_origin.status_code, 403)
        self.assertEqual(invalid_origin.json()["error"]["code"], -32001)
        self.assertEqual(missing_accept.status_code, 400)
        self.assertEqual(valid.status_code, 200)

    def test_missing_origin_still_works_for_cli_clients(self) -> None:
        with self._build_client(mcp_allowed_origins=("https://allowed.example",)) as client:
            response = client.post("/mcp", json=_rpc("initialize"))

        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
