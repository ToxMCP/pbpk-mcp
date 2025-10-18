"""Error utilities and standardized responses."""

from __future__ import annotations

import re
from enum import Enum
from http import HTTPStatus
from typing import Any

from starlette.responses import JSONResponse

from .constants import CORRELATION_HEADER

_SENSITIVE_PATTERN = re.compile(r"(?i)(token|secret|password|key)=([^\s]+)")


class ErrorCode(str, Enum):
    INVALID_INPUT = "InvalidInput"
    NOT_FOUND = "NotFound"
    CONFLICT = "Conflict"
    ENVIRONMENT_MISSING = "EnvironmentMissing"
    INTEROP_ERROR = "InteropError"
    TIMEOUT = "Timeout"
    INTERNAL_ERROR = "InternalError"


def redact_sensitive(text: str) -> str:
    """Mask obvious secrets in error messages."""
    return _SENSITIVE_PATTERN.sub(lambda m: f"{m.group(1)}=***", text)


def map_status_to_code(status_code: int) -> ErrorCode:
    if status_code == HTTPStatus.BAD_REQUEST:
        return ErrorCode.INVALID_INPUT
    if status_code == HTTPStatus.NOT_FOUND:
        return ErrorCode.NOT_FOUND
    if status_code == HTTPStatus.CONFLICT:
        return ErrorCode.CONFLICT
    if status_code == HTTPStatus.REQUEST_TIMEOUT:
        return ErrorCode.TIMEOUT
    return ErrorCode.INTERNAL_ERROR


def error_response(
    *,
    code: ErrorCode,
    message: str,
    correlation_id: str,
    status_code: int,
    retryable: bool | None = None,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "error": {
            "code": code.value,
            "message": message,
            "correlationId": correlation_id,
        }
    }
    if retryable is not None:
        payload["error"]["retryable"] = retryable
    if details:
        payload["error"]["details"] = details

    return JSONResponse(
        status_code=status_code,
        content=payload,
        headers={CORRELATION_HEADER: correlation_id},
    )


def default_message(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:  # pragma: no cover - defensive
        return "Unexpected Error"
