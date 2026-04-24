"""Deprecated compatibility shim for ``mcp.tools.run_parameter_consistency_check``."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.tools.run_parameter_consistency_check' is deprecated; use "
    "'mcp_bridge.pbpk_tools.run_parameter_consistency_check'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools.run_parameter_consistency_check import *  # noqa: F403
