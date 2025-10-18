"""Tests for centralized error handling."""

from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient

from mcp_bridge.app import create_app
from mcp_bridge.config import AppConfig
from mcp_bridge.constants import CORRELATION_HEADER
from mcp_bridge.errors import ErrorCode


def _build_app():
    app = create_app(config=AppConfig())

    @app.get("/not-found")
    async def _not_found() -> None:
        raise HTTPException(status_code=404, detail="record missing")

    @app.get("/bad-request")
    async def _bad_request() -> None:
        raise HTTPException(status_code=400, detail="token=abcd")

    @app.get("/explode")
    async def _explode() -> None:
        raise RuntimeError("token=abcd")

    return app


def test_http_exception_translates_to_standard_payload() -> None:
    client = TestClient(_build_app(), raise_server_exceptions=False)

    response = client.get("/not-found")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == ErrorCode.NOT_FOUND.value
    assert payload["error"]["message"] == "record missing"
    assert payload["error"]["correlationId"] == response.headers[CORRELATION_HEADER]


def test_http_exception_message_is_redacted() -> None:
    client = TestClient(_build_app(), raise_server_exceptions=False)

    response = client.get("/bad-request")

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == ErrorCode.INVALID_INPUT.value
    assert payload["error"]["message"] == "token=***"


def test_unexpected_exception_returns_internal_error() -> None:
    client = TestClient(_build_app(), raise_server_exceptions=False)

    response = client.get("/explode")

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == ErrorCode.INTERNAL_ERROR.value
    assert payload["error"]["message"] == "Internal server error"
    assert payload["error"]["correlationId"] == response.headers[CORRELATION_HEADER]
