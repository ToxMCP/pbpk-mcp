"""Tests for MCP resource discovery endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mcp.session_registry import registry
from mcp.tools.load_simulation import LoadSimulationRequest, load_simulation
from mcp.tools.set_parameter_value import SetParameterValueRequest, set_parameter_value
from mcp_bridge.app import create_app
from mcp_bridge.config import AppConfig


@pytest.fixture()
def client() -> TestClient:
    registry.clear()
    app = create_app(config=AppConfig())
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        app.state.jobs.shutdown()
        app.state.adapter.shutdown()
        registry.clear()


def _load_demo_simulation(simulation_id: str = "demo") -> LoadSimulationRequest:
    return LoadSimulationRequest.model_validate(
        {
            "filePath": "tests/fixtures/demo.pkml",
            "simulationId": simulation_id,
        }
    )


def _set_parameter(
    simulation_id: str,
    *,
    path: str,
    value: float,
    unit: str | None = None,
) -> SetParameterValueRequest:
    payload: dict[str, object] = {
        "simulationId": simulation_id,
        "parameterPath": path,
        "value": value,
    }
    if unit is not None:
        payload["unit"] = unit
    return SetParameterValueRequest.model_validate(payload)


def test_simulation_resource_listing_returns_registered_sessions(client: TestClient) -> None:
    adapter = client.app.state.adapter
    request = _load_demo_simulation("sim-a")
    load_simulation(adapter, request)

    response = client.get("/mcp/resources/simulations")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["simulationId"] == "sim-a"
    assert "ETag" in response.headers


def test_simulation_resource_etag_supports_conditional_requests(client: TestClient) -> None:
    adapter = client.app.state.adapter
    load_simulation(adapter, _load_demo_simulation("sim-b"))

    first = client.get("/mcp/resources/simulations")
    etag = first.headers.get("ETag")
    assert etag is not None

    second = client.get("/mcp/resources/simulations", headers={"If-None-Match": etag})
    assert second.status_code == 304
    assert second.headers.get("ETag") == etag


def test_simulation_resource_pagination_and_search(client: TestClient) -> None:
    adapter = client.app.state.adapter
    for suffix in ("alpha", "beta", "gamma"):
        load_simulation(adapter, _load_demo_simulation(f"sim-{suffix}"))

    page = client.get("/mcp/resources/simulations", params={"page": 2, "limit": 1})
    assert page.status_code == 200
    payload = page.json()
    assert payload["page"] == 2
    assert payload["limit"] == 1
    assert payload["total"] == 3
    assert len(payload["items"]) == 1

    search = client.get("/mcp/resources/simulations", params={"search": "beta"})
    assert search.status_code == 200
    filtered = search.json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["simulationId"] == "sim-beta"


def test_parameter_resource_listing_returns_parameter_metadata(client: TestClient) -> None:
    adapter = client.app.state.adapter
    simulation_id = "sim-params"
    load_simulation(adapter, _load_demo_simulation(simulation_id))
    set_parameter_value(
        adapter, _set_parameter(simulation_id, path="Organism|Weight", value=70.0, unit="kg")
    )
    set_parameter_value(
        adapter, _set_parameter(simulation_id, path="Organism|Height", value=180.0, unit="cm")
    )

    response = client.get(
        "/mcp/resources/parameters",
        params={"simulationId": simulation_id, "page": 1, "limit": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["simulationId"] == simulation_id
    assert item["path"].startswith("Organism|")
    assert "ETag" in response.headers
    assert "Last-Modified" in response.headers


def test_parameter_resource_conditional_request_and_not_found(client: TestClient) -> None:
    adapter = client.app.state.adapter
    simulation_id = "sim-conditional"
    load_simulation(adapter, _load_demo_simulation(simulation_id))
    set_parameter_value(
        adapter, _set_parameter(simulation_id, path="Organism|Clearance", value=1.5, unit="L/h")
    )

    first = client.get("/mcp/resources/parameters", params={"simulationId": simulation_id})
    etag = first.headers.get("ETag")
    assert etag is not None

    second = client.get(
        "/mcp/resources/parameters",
        params={"simulationId": simulation_id},
        headers={"If-None-Match": etag},
    )
    assert second.status_code == 304

    missing = client.get("/mcp/resources/parameters", params={"simulationId": "unknown"})
    assert missing.status_code == 404
    payload = missing.json()
    assert payload["error"]["code"] == "NotFound"
    assert payload["error"]["details"][0]["field"] == "simulationId"
