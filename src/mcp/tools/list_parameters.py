"""Deprecated compatibility shim for ``mcp.tools.list_parameters``."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.tools.list_parameters' is deprecated; use "
    "'mcp_bridge.pbpk_tools.list_parameters'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools.list_parameters import *  # noqa: F403
