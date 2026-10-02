"""Exercise the isolation boundary and protocol/security behavior with real SDKs."""

import json

import httpx2
import pytest
from mcp import Client
from mcp.shared.exceptions import MCPError
from starlette.requests import Request
from starlette.testclient import TestClient

from pbpk_mcp_sdk2.backend import Backend
from pbpk_mcp_sdk2.http import create_app
from pbpk_mcp_sdk2.server import INVOCATION_KEY, RESULT_ANNOTATIONS_KEY, create_server
from pbpk_mcp_sdk2.settings import Settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


def backend(handler, **settings):
    config = Settings(**settings)
    return Backend(
        config,
        httpx2.AsyncClient(base_url=config.backend_url, transport=httpx2.MockTransport(handler)),
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://remote.example",
        "https://user:secret@example.com",
        "https://example.com/path",
        "https://example.com?redirect=other",
        "file:///tmp/backend",
    ],
)
def test_backend_origin_rejects_unsafe_configuration(url):
    with pytest.raises(ValueError):
        Settings(backend_url=url)


def test_http_never_inherits_stdio_owner_token():
    gateway = backend(lambda request: httpx2.Response(200), bearer_token="local-owner")
    anonymous = Request({"type": "http", "headers": []})
    caller = Request(
        {
            "type": "http",
            "headers": [
                (b"authorization", b"Bearer caller"),
                (b"x-mcp-confirm", b"true"),
                (b"cookie", b"secret"),
            ],
        }
    )
    assert gateway.headers(anonymous) == {}
    assert gateway.headers(None) == {"authorization": "Bearer local-owner"}
    assert gateway.headers(caller) == {"authorization": "Bearer caller", "x-mcp-confirm": "true"}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"jsonrpc": "2.0", "id": 999, "result": {}},
        {"jsonrpc": "2.0", "id": 1, "error": "broken"},
    ],
)
async def test_malformed_backend_response_is_sanitized(payload):
    gateway = backend(lambda request: httpx2.Response(200, json=payload))
    with pytest.raises(MCPError, match="invalid response"):
        await gateway.invoke("resources/list", {}, None)
    await gateway.close()


@pytest.mark.anyio
async def test_expected_errors_keep_details_but_internal_errors_are_sanitized():
    codes = iter([-32602, -32603])

    def handle(request):
        body = json.loads(request.content)
        return httpx2.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "error": {
                    "code": next(codes),
                    "message": "backend detail",
                    "data": {"field": "value"},
                },
            },
        )

    gateway = backend(handle)
    with pytest.raises(MCPError) as expected:
        await gateway.invoke("resources/read", {}, None)
    assert expected.value.data == {"field": "value"}
    with pytest.raises(MCPError) as internal:
        await gateway.invoke("resources/read", {}, None)
    assert internal.value.message == "PBPK request failed." and internal.value.data is None
    await gateway.close()


@pytest.mark.anyio
async def test_real_sdk_preserves_invocation_and_rendering_annotations():
    calls = []

    def handle(request):
        if request.method == "GET":
            assert request.url.path == "/mcp/list_tools"
            return httpx2.Response(200, json={})
        body = json.loads(request.content)
        if body["method"] == "tools/list":
            return httpx2.Response(
                200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"tools": []}}
            )
        calls.append(body)
        result = {
            "content": [{"type": "text", "text": "result"}],
            "isError": False,
            "annotations": {
                "idempotencyKey": "repeat-key",
                "trustBearing": True,
                "requiresContextualRendering": True,
            },
        }
        return httpx2.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": result})

    gateway = backend(handle)
    async with Client(create_server(gateway)) as client:
        result = await client.call_tool(
            "run_simulation",
            {"simulationId": "test"},
            meta={INVOCATION_KEY: {"critical": True, "idempotencyKey": "repeat-key"}},
        )
    assert calls[0]["params"] == {
        "name": "run_simulation",
        "arguments": {"simulationId": "test"},
        "critical": True,
        "idempotencyKey": "repeat-key",
    }
    assert result.meta[RESULT_ANNOTATIONS_KEY]["requiresContextualRendering"] is True
    await gateway.close()


@pytest.mark.parametrize("path", ["/mcp", "/mcp/jsonrpc"])
def test_legacy_proxy_keeps_exact_body_alias_headers_and_empty_notification(path):
    body = b'{"jsonrpc":"2.0","method":"initialized"}'

    def handle(request):
        assert request.url.path == path and request.content == body
        assert "authorization" not in request.headers
        return httpx2.Response(202, headers={"x-request-id": "backend-id"})

    gateway = backend(handle, bearer_token="owner")
    with TestClient(create_app(gateway.settings, gateway), base_url="http://localhost") as client:
        response = client.post(path, content=body)
    assert response.status_code == 202 and response.content == b""
    assert response.headers["x-request-id"] == "backend-id"


@pytest.mark.parametrize("path", ["/mcp", "/mcp/jsonrpc"])
def test_limit_precedes_both_parsers_and_counts_chunked_bytes(path):
    def forbidden(request):
        raise AssertionError("oversized body reached backend")

    gateway = backend(forbidden, max_request_bytes=10)
    with TestClient(create_app(gateway.settings, gateway), base_url="http://localhost") as client:
        assert client.post(path, content=b"x" * 11).status_code == 413
        assert client.post(path, content=iter([b"x" * 6, b"x" * 6])).status_code == 413


@pytest.mark.parametrize("code", [401, 403, 429])
def test_modern_auth_status_preserves_role_boundary(code):
    gateway = backend(lambda request: httpx2.Response(code), bearer_token="owner")
    with TestClient(create_app(gateway.settings, gateway), base_url="http://localhost") as client:
        response = client.post(
            "/mcp",
            headers={"mcp-protocol-version": "2026-07-28", "mcp-method": "tools/list"},
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
    assert response.status_code == code
    if code == 401:
        assert response.headers["www-authenticate"] == "Bearer"


def test_modern_host_origin_and_browser_routing_headers():
    gateway = backend(lambda request: httpx2.Response(200))
    with TestClient(create_app(gateway.settings, gateway), base_url="http://localhost") as client:
        assert (
            client.options(
                "/mcp",
                headers={
                    "origin": "http://localhost:1234",
                    "access-control-request-headers": "mcp-method,mcp-name,mcp-protocol-version",
                },
            ).status_code
            == 204
        )
        assert (
            client.options(
                "/mcp",
                headers={
                    "origin": "http://localhost.attacker:1234",
                    "access-control-request-headers": "mcp-method",
                },
            ).status_code
            == 403
        )
        headers = {
            "mcp-protocol-version": "2026-07-28",
            "mcp-method": "tools/list",
            "accept": "application/json, text/event-stream",
        }
        assert (
            client.post(
                "/mcp",
                headers={**headers, "host": "attacker.example"},
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
            ).status_code
            == 421
        )
        assert (
            client.post(
                "/mcp",
                headers={**headers, "origin": "https://attacker.example"},
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
            ).status_code
            == 403
        )
