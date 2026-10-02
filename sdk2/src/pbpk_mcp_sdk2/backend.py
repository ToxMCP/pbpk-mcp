from __future__ import annotations

import itertools
from typing import Any

import httpx2
from mcp.shared.exceptions import MCPError
from starlette.requests import Request

from .settings import Settings

FORWARDED_CONTEXT_HEADERS = {
    "authorization",
    "x-mcp-confirm",
    "traceparent",
    "x-request-id",
    "x-correlation-id",
    "x-mcp-session-id",
}


class Backend:
    def __init__(self, settings: Settings, client: httpx2.AsyncClient | None = None):
        self.settings = settings
        self.client = client or httpx2.AsyncClient(
            base_url=settings.backend_url,
            timeout=httpx2.Timeout(None, connect=10, pool=10),
            follow_redirects=False,
        )
        self.ids = itertools.count(1)

    def headers(self, request: Request | None) -> dict[str, str]:
        # The configured bearer token belongs exclusively to local stdio.
        # An unauthenticated HTTP caller must never inherit the owner's token.
        if request is not None:
            return {
                name: value
                for name, value in request.headers.items()
                if name in FORWARDED_CONTEXT_HEADERS
            }
        token = self.settings.bearer_token
        return {"authorization": "Bearer " + token.get_secret_value()} if token else {}

    async def authenticate(self, request: Request | None):
        try:
            response = await self.client.get("/mcp/list_tools", headers=self.headers(request))
        except httpx2.HTTPError as error:
            raise MCPError(-32002, "PBPK backend is unavailable.") from error
        if response.status_code == 401:
            raise MCPError(-32000, "Authentication required.")
        if response.status_code == 403:
            raise MCPError(-32001, "Access denied.")
        if response.status_code != 200:
            raise MCPError(-32002, "PBPK backend is unavailable.")

    async def invoke(self, method: str, params: dict[str, Any], request: Request | None):
        if method in {"tools/list", "tools/call", "prompts/list", "prompts/get"}:
            await self.authenticate(request)
        request_id = next(self.ids)
        headers = {
            **self.headers(request),
            "mcp-protocol-version": "2025-11-25",
            "accept": "application/json, text/event-stream",
        }
        try:
            response = await self.client.post(
                "/mcp",
                headers=headers,
                json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
            )
            payload = response.json()
        except (httpx2.HTTPError, ValueError) as error:
            raise MCPError(-32002, "PBPK backend is unavailable.") from error
        if (
            not isinstance(payload, dict)
            or payload.get("id") != request_id
            or payload.get("jsonrpc") != "2.0"
        ):
            raise MCPError(-32002, "PBPK backend returned an invalid response.")
        if "error" in payload:
            if not isinstance(payload["error"], dict) or not isinstance(
                payload["error"].get("code"), int
            ):
                raise MCPError(-32002, "PBPK backend returned an invalid response.")
            code = payload["error"].get("code", -32603)
            messages = {
                -32601: "Method, tool or resource not found.",
                -32602: "Invalid method parameters.",
                -32000: "Authentication required.",
                -32001: "Access denied.",
                -32002: "PBPK tool execution failed.",
            }
            if code == -32603:
                raise MCPError(code, "PBPK request failed.")
            # Expected domain errors carry actionable validation/confirmation
            # details. Only unexpected backend failures lose raw details.
            raise MCPError(
                code,
                payload["error"].get("message", messages.get(code, "PBPK request failed.")),
                payload["error"].get("data"),
            )
        if response.status_code != 200 or "result" not in payload:
            raise MCPError(-32002, "PBPK backend returned an invalid response.")
        return payload["result"]

    async def close(self):
        await self.client.aclose()
