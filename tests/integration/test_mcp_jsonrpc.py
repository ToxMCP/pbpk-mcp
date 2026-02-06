"""Integration coverage for the JSON-RPC MCP transport."""

from __future__ import annotations

import itertools

import pytest
from fastapi.testclient import TestClient

from mcp.session_registry import registry
from mcp_bridge.app import create_app


pytestmark = pytest.mark.compliance


@pytest.fixture()
def client() -> TestClient:
    registry.clear()
    app = create_app()
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        app.state.jobs.shutdown()
        app.state.adapter.shutdown()
        registry.clear()


_id_counter = itertools.count(1)


def jsonrpc_call(
    client: TestClient,
    method: str,
    params: dict | None = None,
    *,
    path: str = "/mcp",
    **kwargs,
):
    request_id = kwargs.pop("id", next(_id_counter))
    payload: dict[str, object] = {"jsonrpc": "2.0", "method": method, "id": request_id}
    if params is not None:
        payload["params"] = params
    return client.post(path, json=payload, **kwargs)


def _extract_json_content(result: dict) -> dict:
    contents = result.get("content") or []
    assert contents, "Expected MCP content array"
    entry = contents[0]
    assert entry["type"] == "json"
    return entry["json"]


def test_initialize_reports_capabilities(client: TestClient) -> None:
    response = jsonrpc_call(client, "initialize", params={"capabilities": {}})
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["protocolVersion"] == "2025-03-26"
    capabilities = payload["result"]["capabilities"]
    assert capabilities["tools"]["enabled"] is True
    assert capabilities["prompts"]["enabled"] is False


def test_list_tools_matches_transport_annotations(client: TestClient) -> None:
    response = jsonrpc_call(client, "mcp/tool/list")
    assert response.status_code == 200
    payload = response.json()
    tools = {entry["name"]: entry for entry in payload["result"]["tools"]}
    assert "load_simulation" in tools
    load_meta = tools["load_simulation"]
    assert load_meta["annotations"]["requiresConfirmation"] is True


def test_tool_invocation_round_trip(client: TestClient) -> None:
    load_response = jsonrpc_call(
        client,
        "mcp/tool/call",
        params={
            "name": "load_simulation",
            "arguments": {
                "filePath": "tests/fixtures/demo.pkml",
                "simulationId": "jsonrpc-demo",
            },
            "critical": True,
        },
    )
    assert load_response.status_code == 200, load_response.text
    load_payload = load_response.json()
    load_result = _extract_json_content(load_payload["result"])
    assert load_result["simulationId"] == "jsonrpc-demo"

    list_response = jsonrpc_call(
        client,
        "mcp/tool/call",
        params={
            "name": "list_parameters",
            "arguments": {"simulationId": "jsonrpc-demo"},
        },
    )
    assert list_response.status_code == 200, list_response.text
    list_payload = list_response.json()
    list_result = _extract_json_content(list_payload["result"])
    assert isinstance(list_result["parameters"], list)


def test_invalid_parameters_surface_jsonrpc_error(client: TestClient) -> None:
    response = jsonrpc_call(
        client,
        "mcp/tool/call",
        params={
            "name": "set_parameter_value",
            "arguments": {
                "simulationId": "missing",
                "parameterPath": "Organism|Weight",
                "value": "invalid",
            },
            "critical": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    error = payload["error"]
    assert error["code"] == -32602
    assert "valid number" in error["message"].lower()
    details = error.get("data") or []
    assert details and details[0].get("field") == "value"


def test_initialized_notification_without_id_returns_204(client: TestClient) -> None:
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "initialized", "params": {"capabilities": {}}},
    )
    assert response.status_code == 204


def test_initialized_with_id_returns_empty_object(client: TestClient) -> None:
    response = jsonrpc_call(client, "initialized", params={})
    assert response.status_code == 200
    assert response.json()["result"] == {}


def test_legacy_jsonrpc_route_still_supported(client: TestClient) -> None:
    response = jsonrpc_call(client, "tools/list", path="/mcp/jsonrpc")
    assert response.status_code == 200
    assert "tools" in response.json()["result"]


def test_parameters_alias_normalized(client: TestClient) -> None:
    load_response = jsonrpc_call(
        client,
        "mcp/tool/call",
        params={
            "name": "load_simulation",
            "parameters": {
                "filePath": "tests/fixtures/demo.pkml",
                "simulationId": "jsonrpc-alias",
            },
            "critical": True,
        },
    )
    assert load_response.status_code == 200
    payload = load_response.json()
    result = _extract_json_content(payload["result"])
    assert result["simulationId"] == "jsonrpc-alias"
