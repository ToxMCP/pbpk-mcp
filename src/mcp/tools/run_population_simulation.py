"""Deprecated compatibility shim for ``mcp.tools.run_population_simulation``."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.tools.run_population_simulation' is deprecated; use "
    "'mcp_bridge.pbpk_tools.run_population_simulation'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools.run_population_simulation import *  # noqa: F403
