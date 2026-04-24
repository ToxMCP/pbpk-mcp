"""Deprecated compatibility shim for PBPK MCP session registry imports."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.session_registry' is deprecated; use "
    "'mcp_bridge.session_registry'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.session_registry import *  # noqa: F403
