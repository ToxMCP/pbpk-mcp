"""Logging utilities for the MCP Bridge service."""

from __future__ import annotations

import logging
from typing import Any, cast

import structlog

DEFAULT_LOG_LEVEL = "INFO"


def setup_logging(level: str = DEFAULT_LOG_LEVEL) -> None:
    """Configure structlog for JSON output with contextvars support."""
    log_level = _coerce_log_level(level)

    structlog.reset_defaults()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        cache_logger_on_first_use=True,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )

    logging.basicConfig(level=log_level, format="%(message)s")


def _coerce_log_level(level: str) -> int:
    name = level.upper()
    numeric = logging.getLevelName(name)
    if isinstance(numeric, int):
        return numeric
    return logging.INFO


def get_logger(name: str | None = None) -> structlog.types.FilteringBoundLogger:
    return cast(structlog.types.FilteringBoundLogger, structlog.get_logger(name))


def bind_context(**kwargs: Any) -> None:
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context(*keys: str) -> None:
    if keys:
        structlog.contextvars.unbind_contextvars(*keys)
    else:
        structlog.contextvars.clear_contextvars()
