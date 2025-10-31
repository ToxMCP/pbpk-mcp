"""Server-side enforcement for critical tool confirmation."""

from __future__ import annotations

from fastapi import Request, status

from ..constants import CONFIRMATION_HEADER
from ..errors import ErrorCode, http_error

_TRUE_VALUES = {"true", "1", "yes", "y", "confirmed"}


def is_confirmed(request: Request) -> bool:
    """Return True when the request carries an affirmative confirmation header."""

    header_value = request.headers.get(CONFIRMATION_HEADER)
    if not header_value:
        return False
    return header_value.split(",")[0].strip().lower() in _TRUE_VALUES


def require_confirmation(request: Request) -> None:
    """Raise if the confirmation header is missing or falsey."""

    if not is_confirmed(request):
        raise http_error(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            message="Critical tool call requires explicit confirmation.",
            code=ErrorCode.CONFIRMATION_REQUIRED,
            hint=f"Include '{CONFIRMATION_HEADER}: true' after obtaining user approval.",
        )
