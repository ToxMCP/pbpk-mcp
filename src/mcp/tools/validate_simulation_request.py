"""Deprecated compatibility shim for ``mcp.tools.validate_simulation_request``."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.tools.validate_simulation_request' is deprecated; use "
    "'mcp_bridge.pbpk_tools.validate_simulation_request'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools.validate_simulation_request import *  # noqa: F403
