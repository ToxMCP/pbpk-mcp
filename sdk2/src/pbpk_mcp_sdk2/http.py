from __future__ import annotations

import json
from contextlib import asynccontextmanager

import httpx2
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from mcp_types import PROTOCOL_VERSION_META_KEY
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from .backend import Backend
from .body_limit import MCPBodyLimitMiddleware
from .server import create_server
from .settings import Settings

LEGACY_REVISIONS = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}
HOP_HEADERS = {
    "host",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "content-length",
}
MODERN_CORS_HEADERS = {
    "authorization",
    "content-type",
    "mcp-protocol-version",
    "mcp-method",
    "mcp-name",
    "mcp-session-id",
    "last-event-id",
    "x-mcp-confirm",
    "x-request-id",
}


def modern_request(request: Request, body: bytes):
    revision = request.headers.get("mcp-protocol-version")
    if revision and revision not in LEGACY_REVISIONS:
        return True
    try:
        payload = json.loads(body)
    except ValueError:
        return False
    params = payload.get("params") if isinstance(payload, dict) else None
    metadata = params.get("_meta") if isinstance(params, dict) else None
    return isinstance(metadata, dict) and PROTOCOL_VERSION_META_KEY in metadata


def allowed_origin(origin: str, patterns: list[str]):
    for pattern in patterns:
        if origin == pattern:
            return True
        if pattern.endswith(":*"):
            base = pattern[:-2]
            if origin == base:
                return True
            if origin.startswith(base + ":"):
                port = origin[len(base) + 1 :]
                if port.isdigit() and 1 <= int(port) <= 65535:
                    return True
    return False


class SDKResponse(Response):
    def __init__(self, app, body, origin=None):
        super().__init__()
        self.application = app
        self.body = body
        self.origin = origin

    async def __call__(self, scope, receive, send):
        supplied = False

        async def replay():
            nonlocal supplied
            if not supplied:
                supplied = True
                return {"type": "http.request", "body": self.body, "more_body": False}
            return await receive()

        # The alias keeps its public URL; the SDK's internal route is /mcp.
        sdk_scope = {**scope, "path": "/mcp", "raw_path": b"/mcp"}

        async def cors_send(message):
            if self.origin and message["type"] == "http.response.start":
                message = {
                    **message,
                    "headers": [
                        *message.get("headers", []),
                        (b"access-control-allow-origin", self.origin.encode()),
                        (b"access-control-allow-credentials", b"true"),
                        (b"access-control-expose-headers", b"mcp-session-id, www-authenticate"),
                        (b"vary", b"Origin"),
                    ],
                }
            await send(message)

        await self.application(sdk_scope, replay, cors_send)


def create_app(settings: Settings | None = None, backend: Backend | None = None):
    settings = settings or Settings()
    backend = backend or Backend(settings)
    sdk = create_server(backend).streamable_http_app(
        json_response=True,
        stateless_http=True,
        max_request_body_size=settings.max_request_bytes,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=settings.hosts(),
            allowed_origins=settings.origins(),
        ),
    )

    @asynccontextmanager
    async def lifespan(app):
        try:
            async with sdk.router.lifespan_context(sdk):
                yield
        finally:
            await backend.close()

    async def forward(request: Request, body: bytes | None = None):
        path = request.url.path
        if request.url.query:
            path += "?" + request.url.query
        headers = {
            name: value for name, value in request.headers.items() if name not in HOP_HEADERS
        }
        try:
            response = await backend.client.request(
                request.method,
                path,
                headers=headers,
                content=await request.body() if body is None else body,
            )
        except httpx2.HTTPError:
            return JSONResponse({"error": "PBPK backend is unavailable."}, status_code=502)
        response_headers = {
            name: value
            for name, value in response.headers.items()
            if name not in HOP_HEADERS and name != "content-encoding"
        }
        return Response(
            response.content, status_code=response.status_code, headers=response_headers
        )

    async def endpoint(request: Request):
        if request.method == "OPTIONS":
            requested = {
                item.strip().lower()
                for item in request.headers.get("access-control-request-headers", "").split(",")
            }
            if requested.intersection({"mcp-protocol-version", "mcp-method", "mcp-name"}):
                origin = request.headers.get("origin", "")
                if not allowed_origin(origin, settings.origins()) or not requested.issubset(
                    MODERN_CORS_HEADERS
                ):
                    return Response(status_code=403)
                return Response(
                    status_code=204,
                    headers={
                        "Access-Control-Allow-Origin": origin,
                        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
                        "Access-Control-Allow-Credentials": "true",
                        "Access-Control-Allow-Headers": ", ".join(sorted(MODERN_CORS_HEADERS)),
                        "Vary": "Origin",
                    },
                )
            return await forward(request)
        if request.method != "POST":
            return await forward(request)
        body = await request.body()
        if not modern_request(request, body):
            return await forward(request, body)
        try:
            payload = json.loads(body)
        except ValueError:
            payload = {}
        if isinstance(payload, dict) and payload.get("method") in {
            "tools/list",
            "tools/call",
            "prompts/list",
            "prompts/get",
        }:
            try:
                await backend.authenticate(request)
            except MCPError as error:
                code = 401 if error.code == -32000 else 403 if error.code == -32001 else 502
                headers = {"WWW-Authenticate": "Bearer"} if code == 401 else {}
                origin = request.headers.get("origin", "")
                if allowed_origin(origin, settings.origins()):
                    headers.update(
                        {
                            "Access-Control-Allow-Origin": origin,
                            "Access-Control-Allow-Credentials": "true",
                            "Access-Control-Expose-Headers": "WWW-Authenticate",
                            "Vary": "Origin",
                        }
                    )
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": payload.get("id"),
                        "error": {"code": error.code, "message": error.message},
                    },
                    status_code=code,
                    headers=headers,
                )
        origin = request.headers.get("origin", "")
        return SDKResponse(
            sdk, body, origin if allowed_origin(origin, settings.origins()) else None
        )

    app = Starlette(
        routes=[
            Route("/mcp", endpoint, methods=["GET", "POST", "OPTIONS"]),
            Route("/mcp/jsonrpc", endpoint, methods=["GET", "POST", "OPTIONS"]),
            Route(
                "/mcp/{path:path}",
                forward,
                methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            ),
            Route("/health", forward),
        ],
        lifespan=lifespan,
    )
    app.add_middleware(MCPBodyLimitMiddleware, max_bytes=settings.max_request_bytes)
    return app
