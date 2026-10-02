"""JWT/rate state belongs to the backend: exactly one backend call per SDK call."""

import json

import httpx2
import pytest
from mcp import Client
from mcp.shared.exceptions import MCPError
from starlette.testclient import TestClient
from starlette.requests import Request

from pbpk_mcp_sdk2.backend import Backend, peer_headers
from pbpk_mcp_sdk2.http import create_app
from pbpk_mcp_sdk2.server import create_server
from pbpk_mcp_sdk2.settings import Settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


def gateway():
    count = []

    def handle(request):
        assert request.method == "POST", "An auth preflight consumed the token"
        count.append(request)
        body = json.loads(request.content)
        if len(count) == 1:
            return httpx2.Response(
                200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"tools": []}}
            )
        return httpx2.Response(
            500,
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": "401: Replay detected for token identifier",
                },
            },
        )

    settings = Settings(bearer_token="single-use-fixture")
    return (
        Backend(
            settings,
            httpx2.AsyncClient(
                base_url=settings.backend_url, transport=httpx2.MockTransport(handle)
            ),
        ),
        count,
    )


def test_http_single_use_token_succeeds_once_and_replay_is_rejected():
    backend, count = gateway()
    with TestClient(create_app(backend.settings, backend), base_url="http://localhost") as client:
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                    "io.modelcontextprotocol/clientCapabilities": {},
                }
            },
        }
        headers = {
            "authorization": "Bearer caller-single-use",
            "mcp-protocol-version": "2026-07-28",
            "mcp-method": "tools/list",
            "accept": "application/json, text/event-stream",
        }
        assert client.post("/mcp", json=request, headers=headers).status_code == 200
        replay = client.post("/mcp", json=request, headers=headers)
        assert replay.status_code == 401
        assert replay.headers["www-authenticate"] == "Bearer"
        assert "Replay detected" not in replay.text
    assert len(count) == 2
    assert all(item.headers["authorization"] == "Bearer caller-single-use" for item in count)


@pytest.mark.anyio
async def test_stdio_single_use_token_succeeds_once_and_replay_is_rejected():
    backend, count = gateway()
    async with Client(create_server(backend)) as client:
        assert (await client.list_tools()).tools == []
        with pytest.raises(MCPError) as replay:
            await client.list_tools()
        assert replay.value.code == -32000
    assert len(count) == 2
    await backend.close()


def test_rate_identity_uses_validated_peer_and_cannot_be_spoofed_by_header():
    request = Request(
        {
            "type": "http",
            "client": ("203.0.113.42", 1234),
            "headers": [(b"x-forwarded-for", b"attacker-supplied")],
        }
    )
    assert peer_headers(request) == {"x-forwarded-for": "203.0.113.42"}
