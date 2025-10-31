"""Error utilities and standardized responses."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from http import HTTPStatus
from typing import Any, Iterable, List, Optional

from fastapi import HTTPException
from pydantic import ValidationError
from starlette.responses import JSONResponse

from .constants import CORRELATION_HEADER
from .adapter.errors import AdapterError, AdapterErrorCode

_SENSITIVE_PATTERN = re.compile(r"(?i)(token|secret|password|key)=([^\s]+)")


class ErrorCode(str, Enum):
    INVALID_INPUT = "InvalidInput"
    NOT_FOUND = "NotFound"
    CONFLICT = "Conflict"
    FORBIDDEN = "Forbidden"
    ENVIRONMENT_MISSING = "EnvironmentMissing"
    INTEROP_ERROR = "InteropError"
    TIMEOUT = "Timeout"
    INTERNAL_ERROR = "InternalError"


@dataclass(frozen=True)
class ErrorDetail:
    """Structured hint used by clients to self-correct failed requests."""

    issue: str
    field: Optional[str] = None
    hint: Optional[str] = None
    code: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"issue": self.issue}
        if self.field:
            payload["field"] = self.field
        if self.hint:
            payload["hint"] = self.hint
        if self.code:
            payload["code"] = self.code
        return payload


class DetailedHTTPException(HTTPException):
    """HTTPException extended with structured MCP error metadata."""

    def __init__(
        self,
        *,
        status_code: int,
        message: str,
        code: ErrorCode | None = None,
        retryable: bool | None = None,
        details: Iterable[ErrorDetail] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.error_code = code
        self.retryable_hint = retryable
        self.error_details: list[ErrorDetail] = list(details or [])


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
    if status_code == HTTPStatus.FORBIDDEN:
        return ErrorCode.FORBIDDEN
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
    details: Iterable[ErrorDetail] | None = None,
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
        payload["error"]["details"] = [item.to_dict() for item in details]

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


def error_detail(
    issue: str,
    *,
    field: Optional[str] = None,
    hint: Optional[str] = None,
    code: Optional[str] = None,
) -> ErrorDetail:
    """Convenience helper to build an ErrorDetail entry."""

    return ErrorDetail(issue=issue, field=field, hint=hint, code=code)


def join_field(parts: Iterable[Any]) -> Optional[str]:
    """Convert ValidationError locations into dotted field names."""

    formatted = []
    for part in parts:
        if part in {"__root__", None}:
            continue
        formatted.append(str(part))
    if not formatted:
        return None
    return ".".join(formatted)


def validation_errors_to_details(errors: Iterable[dict[str, Any]]) -> List[ErrorDetail]:
    """Translate pydantic ValidationError entries into ErrorDetail records."""

    details: list[ErrorDetail] = []
    for item in errors:
        issue = item.get("msg", "Invalid value")
        field = join_field(item.get("loc") or ())
        ctx = item.get("ctx") or {}
        hint = ctx.get("hint")
        code = item.get("type")
        details.append(error_detail(issue=issue, field=field, hint=hint, code=code))
    return details


__all__ = [
    "adapter_error_to_http",
    "DetailedHTTPException",
    "ErrorCode",
    "ErrorDetail",
    "http_error",
    "error_detail",
    "error_response",
    "validation_exception",
    "join_field",
    "map_status_to_code",
    "redact_sensitive",
    "validation_errors_to_details",
]


def adapter_error_to_http(exc: AdapterError) -> DetailedHTTPException:
    """Map adapter exceptions to structured HTTP errors."""

    status_map = {
        AdapterErrorCode.INVALID_INPUT: HTTPStatus.BAD_REQUEST,
        AdapterErrorCode.NOT_FOUND: HTTPStatus.NOT_FOUND,
        AdapterErrorCode.ENVIRONMENT_MISSING: HTTPStatus.SERVICE_UNAVAILABLE,
        AdapterErrorCode.INTEROP_ERROR: HTTPStatus.BAD_GATEWAY,
        AdapterErrorCode.TIMEOUT: HTTPStatus.GATEWAY_TIMEOUT,
    }

    code_map = {
        AdapterErrorCode.INVALID_INPUT: ErrorCode.INVALID_INPUT,
        AdapterErrorCode.NOT_FOUND: ErrorCode.NOT_FOUND,
        AdapterErrorCode.ENVIRONMENT_MISSING: ErrorCode.ENVIRONMENT_MISSING,
        AdapterErrorCode.INTEROP_ERROR: ErrorCode.INTEROP_ERROR,
        AdapterErrorCode.TIMEOUT: ErrorCode.TIMEOUT,
    }

    status_code = int(status_map.get(exc.code, HTTPStatus.INTERNAL_SERVER_ERROR))
    error_code = code_map.get(exc.code, ErrorCode.INTERNAL_ERROR)

    detail_entries: list[ErrorDetail] = []
    for key, value in (exc.details or {}).items():
        hint = None
        if exc.code == AdapterErrorCode.NOT_FOUND:
            hint = "Confirm the resource exists and is loaded before calling this tool."
        detail_entries.append(error_detail(issue=str(value), field=str(key), hint=hint))

    message = str(exc.args[0]) if exc.args else str(exc)
    retryable = exc.code in {AdapterErrorCode.TIMEOUT, AdapterErrorCode.INTEROP_ERROR}

    return DetailedHTTPException(
        status_code=status_code,
        message=message,
        code=error_code,
        retryable=retryable,
        details=detail_entries,
    )


def validation_exception(
    exc: ValidationError,
    *,
    status_code: int = HTTPStatus.BAD_REQUEST,
    default_message: str = "Validation failed",
    code: ErrorCode = ErrorCode.INVALID_INPUT,
) -> DetailedHTTPException:
    """Convert a pydantic ValidationError into a DetailedHTTPException."""

    details = validation_errors_to_details(exc.errors())
    message = details[0].issue if details else default_message
    return DetailedHTTPException(
        status_code=status_code,
        message=message,
        code=code,
        details=details,
    )


def http_error(
    *,
    status_code: int,
    message: str,
    code: ErrorCode,
    details: Optional[Iterable[ErrorDetail]] = None,
    field: Optional[str] = None,
    hint: Optional[str] = None,
) -> DetailedHTTPException:
    """Helper to compose DetailedHTTPException with optional detail entries."""

    detail_entries = list(details or [])
    if field or hint:
        detail_entries.append(error_detail(issue=message, field=field, hint=hint))
    return DetailedHTTPException(
        status_code=status_code,
        message=message,
        code=code,
        details=detail_entries,
    )
