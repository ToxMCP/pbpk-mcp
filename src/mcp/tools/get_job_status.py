"""Deprecated compatibility shim for ``mcp.tools.get_job_status``."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.tools.get_job_status' is deprecated; use "
    "'mcp_bridge.pbpk_tools.get_job_status'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools.get_job_status import *  # noqa: F403
