"""Error types for the ospsuite adapter."""

from __future__ import annotations

from enum import Enum


class AdapterErrorCode(str, Enum):
    INVALID_INPUT = "InvalidInput"
    NOT_FOUND = "NotFound"
    ENVIRONMENT_MISSING = "EnvironmentMissing"
    INTEROP_ERROR = "InteropError"
    TIMEOUT = "Timeout"


class AdapterError(RuntimeError):
    """Base error for adapter failures."""

    def __init__(
        self, code: AdapterErrorCode, message: str, *, details: dict[str, str] | None = None
    ):
        super().__init__(message)
        self.code = code
        self.details = details or {}

    def __str__(self) -> str:
        base = f"{self.code.value}: {self.args[0]}"
        if self.details:
            return f"{base} ({self.details})"
        return base
