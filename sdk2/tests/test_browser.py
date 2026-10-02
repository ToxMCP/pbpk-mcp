import json

import httpx2
from mcp_types import PROTOCOL_VERSION_META_KEY
from starlette.testclient import TestClient

from pbpk_mcp_sdk2.backend import Backend
from pbpk_mcp_sdk2.http import create_app
from pbpk_mcp_sdk2.settings import Settings


def test_actual_modern_response_is_readable_by_allowed_browser():
    def handle(request):
        if request.method == "GET":
            return httpx2.Response(200, json={})
        body = json.loads(request.content)
        return httpx2.Response(
            200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"tools": []}}
        )

    settings = Settings()
    gateway = Backend(
        settings,
        httpx2.AsyncClient(base_url=settings.backend_url, transport=httpx2.MockTransport(handle)),
    )
    with TestClient(create_app(settings, gateway), base_url="http://localhost") as client:
        response = client.post(
            "/mcp/jsonrpc",
            headers={
                "origin": "http://localhost:1234",
                "accept": "application/json, text/event-stream",
                "mcp-method": "tools/list",
                "mcp-protocol-version": "2026-07-28",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {
                    "_meta": {
                        PROTOCOL_VERSION_META_KEY: "2026-07-28",
                        "io.modelcontextprotocol/clientCapabilities": {},
                    }
                },
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["result"]["tools"] == []
        assert response.headers["access-control-allow-origin"] == "http://localhost:1234"


def test_allowed_browser_can_read_authentication_challenge():
    settings = Settings()
    gateway = Backend(
        settings,
        httpx2.AsyncClient(
            base_url=settings.backend_url,
            transport=httpx2.MockTransport(lambda request: httpx2.Response(401)),
        ),
    )
    with TestClient(create_app(settings, gateway), base_url="http://localhost") as client:
        response = client.post(
            "/mcp",
            headers={
                "origin": "http://localhost:1234",
                "mcp-protocol-version": "2026-07-28",
                "mcp-method": "tools/list",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {
                    "_meta": {
                        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                        "io.modelcontextprotocol/clientCapabilities": {},
                    }
                },
            },
        )
        assert response.status_code == 401
        assert "www-authenticate" in response.headers["access-control-expose-headers"].lower()
