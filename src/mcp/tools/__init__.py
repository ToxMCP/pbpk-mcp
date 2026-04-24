"""Deprecated compatibility namespace for PBPK MCP tool modules."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.tools' is deprecated; use 'mcp_bridge.pbpk_tools'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools import *  # noqa: F403
from mcp_bridge.pbpk_tools import __all__
