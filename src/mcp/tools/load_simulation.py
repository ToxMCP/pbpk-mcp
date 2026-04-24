"""Deprecated compatibility shim for ``mcp.tools.load_simulation``."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.tools.load_simulation' is deprecated; use "
    "'mcp_bridge.pbpk_tools.load_simulation'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools.load_simulation import *  # noqa: F403
