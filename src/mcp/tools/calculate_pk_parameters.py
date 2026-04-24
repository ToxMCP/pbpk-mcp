"""Deprecated compatibility shim for ``mcp.tools.calculate_pk_parameters``."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.tools.calculate_pk_parameters' is deprecated; use "
    "'mcp_bridge.pbpk_tools.calculate_pk_parameters'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools.calculate_pk_parameters import *  # noqa: F403
