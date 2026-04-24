"""Deprecated compatibility shim for ``mcp.tools.get_results``."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.tools.get_results' is deprecated; use "
    "'mcp_bridge.pbpk_tools.get_results'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools.get_results import *  # noqa: F403
