"""Deprecated compatibility shim for ``mcp.tools.set_parameter_value``."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.tools.set_parameter_value' is deprecated; use "
    "'mcp_bridge.pbpk_tools.set_parameter_value'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools.set_parameter_value import *  # noqa: F403
