"""Tests for the /health endpoint of the FastAPI application."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mcp_bridge import __version__
from mcp_bridge.adapter.ospsuite import SubprocessOspsuiteAdapter
from mcp_bridge.app import create_app
from mcp_bridge.config import AppConfig
from mcp_bridge.constants import CORRELATION_HEADER, SERVICE_NAME


def test_health_endpoint_returns_expected_payload() -> None:
    client = TestClient(create_app(config=AppConfig()))

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == SERVICE_NAME
    assert payload["version"] == __version__
    assert payload["uptimeSeconds"] >= 0
    assert CORRELATION_HEADER in response.headers


def test_correlation_id_header_is_preserved_from_request() -> None:
    client = TestClient(create_app(config=AppConfig()))
    expected_correlation_id = "abc123"

    response = client.get("/health", headers={CORRELATION_HEADER: expected_correlation_id})

    assert response.status_code == 200
    assert response.headers[CORRELATION_HEADER] == expected_correlation_id


def test_create_app_uses_subprocess_adapter_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADAPTER_BACKEND", "subprocess")
    config = AppConfig.from_env()
    app = create_app(config=config)
    try:
        assert isinstance(app.state.adapter, SubprocessOspsuiteAdapter)
    finally:
        app.state.adapter.shutdown()
