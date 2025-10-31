"""Integration tests for MCP discovery and call_tool endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mcp.session_registry import registry
from mcp_bridge.app import create_app
from mcp_bridge.tools.registry import get_tool_registry


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


def test_list_tools_includes_core_tools(client: TestClient) -> None:
    response = client.get("/mcp/list_tools")
    assert response.status_code == 200
    payload = response.json()
    tool_names = {tool["name"] for tool in payload["tools"]}
    assert "load_simulation" in tool_names
    load_tool = next(tool for tool in payload["tools"] if tool["name"] == "load_simulation")
    assert load_tool["annotations"]["requiresConfirmation"] is True


def test_call_tool_load_and_list_parameters(client: TestClient) -> None:
    load_resp = client.post(
        "/mcp/call_tool",
        json=
        {
            "tool": "load_simulation",
            "arguments": {
                "filePath": "tests/fixtures/demo.pkml",
                "simulationId": "mcp-demo",
            },
        },
    )
    assert load_resp.status_code == 200, load_resp.text
    body = load_resp.json()
    assert body["tool"] == "load_simulation"
    assert body["structuredContent"]["simulationId"] == "mcp-demo"

    list_resp = client.post(
        "/mcp/call_tool",
        json={"tool": "list_parameters", "arguments": {"simulationId": "mcp-demo"}},
    )
    assert list_resp.status_code == 200, list_resp.text
    list_body = list_resp.json()
    assert list_body["tool"] == "list_parameters"
    assert isinstance(list_body["structuredContent"]["parameters"], list)


def test_call_tool_handles_validation_errors(client: TestClient) -> None:
    response = client.post(
        "/mcp/call_tool",
        json={
            "tool": "set_parameter_value",
            "arguments": {
                "simulationId": "missing",
                "parameterPath": "Organism|Weight",
                "value": "invalid",
            },
        },
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "InvalidInput"
    assert payload["error"]["details"][0]["field"] == "value"


def test_unknown_tool_returns_not_found(client: TestClient) -> None:
    response = client.post(
        "/mcp/call_tool",
        json={"tool": "non_existent_tool", "arguments": {}},
    )
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "NotFound"


def test_capabilities_endpoint_exposes_adapter_metadata(client: TestClient) -> None:
    response = client.get("/mcp/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["transports"] == ["http-streamable"]
    assert payload["adapter"]["name"] in {"inmemory", "subprocess"}
    assert "defaultMs" in payload["timeouts"]


def test_list_tools_matches_registry_schemas(client: TestClient) -> None:
    response = client.get("/mcp/list_tools")
    assert response.status_code == 200
    payload = response.json()
    listed = {item["name"]: item for item in payload["tools"]}

    registry = get_tool_registry()
    assert set(listed.keys()) == set(registry.keys())

    for name, descriptor in registry.items():
        entry = listed[name]
        assert entry["inputSchema"] == descriptor.request_model.model_json_schema()
        if descriptor.response_model is None:
            assert entry.get("outputSchema") is None
        else:
            assert entry["outputSchema"] == descriptor.response_model.model_json_schema()
        annotations = entry["annotations"]
        assert annotations["critical"] == descriptor.critical
        assert annotations["requiresConfirmation"] == descriptor.requires_confirmation
        assert set(annotations["roles"]) == set(descriptor.roles)


def test_call_tool_rejects_unknown_arguments(client: TestClient) -> None:
    response = client.post(
        "/mcp/call_tool",
        json={"tool": "list_parameters", "arguments": {}},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "InvalidInput"
    details = payload["error"].get("details") or []
    assert details and details[0]["field"] == "simulationId"


def test_call_tool_returns_idempotency_annotation(client: TestClient) -> None:
    response = client.post(
        "/mcp/call_tool",
        json={
            "tool": "list_tools",
        },
    )
    assert response.status_code == 404  # sanity check: list_tools not callable

    response = client.post(
        "/mcp/call_tool",
        json={
            "tool": "list_parameters",
            "arguments": {"simulationId": "demo"},
            "idempotencyKey": "abc123",
        },
    )
    assert response.status_code == 404  # simulation not loaded yet
    payload = response.json()
    assert payload["error"]["code"] == "NotFound"

    load_resp = client.post(
        "/mcp/call_tool",
        json={
            "tool": "load_simulation",
            "arguments": {
                "filePath": "tests/fixtures/demo.pkml",
                "simulationId": "demo",
            },
        },
    )
    assert load_resp.status_code == 200

    list_resp = client.post(
        "/mcp/call_tool",
        json={
            "tool": "list_parameters",
            "arguments": {"simulationId": "demo"},
            "idempotencyKey": "abc123",
        },
    )
    assert list_resp.status_code == 200
    annotations = list_resp.json()["annotations"]
    assert annotations["idempotencyKey"] == "abc123"
