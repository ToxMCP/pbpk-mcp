"""Deprecated compatibility shim for ``mcp.tools.discover_models``."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.tools.discover_models' is deprecated; use "
    "'mcp_bridge.pbpk_tools.discover_models'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools.discover_models import *  # noqa: F403
