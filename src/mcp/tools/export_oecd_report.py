"""Deprecated compatibility shim for ``mcp.tools.export_oecd_report``."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.tools.export_oecd_report' is deprecated; use "
    "'mcp_bridge.pbpk_tools.export_oecd_report'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools.export_oecd_report import *  # noqa: F403
