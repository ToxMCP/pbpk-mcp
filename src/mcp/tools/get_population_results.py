"""Deprecated compatibility shim for ``mcp.tools.get_population_results``."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.tools.get_population_results' is deprecated; use "
    "'mcp_bridge.pbpk_tools.get_population_results'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools.get_population_results import *  # noqa: F403
