"""Deprecated compatibility shim for ``mcp.tools.run_sensitivity_analysis``."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.tools.run_sensitivity_analysis' is deprecated; use "
    "'mcp_bridge.pbpk_tools.run_sensitivity_analysis'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools.run_sensitivity_analysis import *  # noqa: F403
