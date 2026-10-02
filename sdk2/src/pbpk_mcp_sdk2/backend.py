from __future__ import annotations

import itertools
import ipaddress
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


def peer_headers(request: Request) -> dict[str, str]:
    if request.client is not None:
        try:
            return {"x-forwarded-for": str(ipaddress.ip_address(request.client.host))}
        except ValueError:
            pass
    return {}


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
                **{
                    name: value
                    for name, value in request.headers.items()
                    if name in FORWARDED_CONTEXT_HEADERS
                },
                **peer_headers(request),
            }
        token = self.settings.bearer_token
        return {"authorization": "Bearer " + token.get_secret_value()} if token else {}

    def authentication_error(self, status: int, request: Request | None):
        # Preserve HTTP authentication/rate status after the SDK has validated
        # the envelope and invoked the backend exactly once. State is local to
        # this ASGI request, never cached across callers or tokens.
        if request is not None:
            request.state.pbpk_auth_status = status
        code, message = {
            401: (-32000, "Authentication required."),
            403: (-32001, "Access denied."),
            429: (-32003, "Rate limit exceeded."),
        }[status]
        return MCPError(code, message)

    async def invoke(self, method: str, params: dict[str, Any], request: Request | None):
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
            if response.status_code in {401, 403, 429}:
                raise self.authentication_error(response.status_code, request)
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
                # The released backend serializes AuthError as an internal RPC
                # error with a status-prefixed string. Recognize only these
                # known status prefixes and expose a generic auth message.
                detail = payload["error"].get("data")
                if response.status_code == 500 and isinstance(detail, str):
                    for status in (401, 403, 429):
                        if detail.startswith(str(status) + ": "):
                            raise self.authentication_error(status, request)
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
