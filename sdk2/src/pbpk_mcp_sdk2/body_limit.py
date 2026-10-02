"""Bound complete MCP bodies before either protocol reads or parses them."""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class MCPBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("path") not in {"/mcp", "/mcp/jsonrpc"}
            or scope.get("method") != "POST"
        ):
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                length = int(declared)
                if length < 0:
                    raise ValueError("negative length")
            except ValueError:
                await self.reject(400, "Invalid Content-Length", scope, receive, send)
                return
            if length > self.max_bytes:
                await self.reject(413, "Request body too large", scope, receive, send)
                return
        chunks = []
        size = 0
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            chunk = event.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                await self.reject(413, "Request body too large", scope, receive, send)
                return
            chunks.append(chunk)
            if not event.get("more_body", False):
                break
        body = b"".join(chunks)
        supplied = False

        async def replay():
            nonlocal supplied
            if not supplied:
                supplied = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def reject(code: int, message: str, scope: Scope, receive: Receive, send: Send) -> None:
        await JSONResponse(
            status_code=code,
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": message},
            },
        )(scope, receive, send)
