"""HTTP audit middleware."""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Mapping
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from ..security.phi import PHIFilter
from .trail import AuditTrail


def _sha256(data: bytes | None) -> str | None:
    if not data:
        return None
    return hashlib.sha256(data).hexdigest()


def _safe_json_decode(data: bytes | None) -> Any:
    if not data:
        return None
    try:
        return json.loads(data.decode("utf-8"))
    except Exception:  # pragma: no cover - non-JSON payloads
        return None


def _event_type(path: str) -> str:
    cleaned = path.strip("/").replace("/", ".")
    return f"http.mcp.{cleaned}" if cleaned else "http.mcp"


_PHI_FILTER = PHIFilter()
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(token|secret|password|authorization|cookie|api[-_]?key|access[-_]?key|session)"
)


def _redact_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if _SENSITIVE_KEY_PATTERN.search(key):
                redacted[key] = "[REDACTED:SECRET]"
            else:
                redacted[key] = _redact_payload(raw_value)
        return redacted
    if isinstance(value, list):
        return [_redact_payload(item) for item in value]
    if isinstance(value, str):
        redacted_text, _ = _PHI_FILTER.redact(value)
        return redacted_text
    return value


class AuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, audit: AuditTrail) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._audit = audit

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if not self._audit.enabled:
            return await call_next(request)

        start = time.perf_counter()
        try:
            raw_body = await request.body()
            request._body = raw_body  # allow downstream to read again
        except Exception:
            raw_body = b""

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            self._record_event(request, duration_ms, None, error=str(exc))
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        self._record_event(request, duration_ms, response)
        return response

    def _record_event(
        self,
        request: Request,
        duration_ms: float,
        response: Response | None,
        *,
        error: str | None = None,
    ) -> None:
        auth = getattr(request.state, "auth", None)
        identity = None
        if auth is not None:
            identity = {
                "subject": auth.subject,
                "roles": auth.roles,
                "tokenId": auth.token_id,
                "isServiceAccount": auth.is_service_account,
            }

        body = getattr(request, "_body", b"")
        decoded_payload = _safe_json_decode(body)
        event = {
            "correlationId": getattr(request.state, "correlation_id", None),
            "identity": identity,
            "request": {
                "method": request.method,
                "path": request.url.path,
                "query": request.url.query or None,
                "bodyDigest": _sha256(body),
                "payload": _redact_payload(decoded_payload),
            },
            "response": {
                "status": response.status_code if response is not None else None,
                "durationMs": duration_ms,
            },
        }
        if error:
            event["error"] = error

        self._audit.record_event(_event_type(request.url.path), event)
