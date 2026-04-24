"""Deprecated compatibility shim for ``mcp.tools.cancel_job``."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.tools.cancel_job' is deprecated; use "
    "'mcp_bridge.pbpk_tools.cancel_job'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools.cancel_job import *  # noqa: F403
