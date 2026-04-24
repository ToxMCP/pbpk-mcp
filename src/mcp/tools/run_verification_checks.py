"""Deprecated compatibility shim for ``mcp.tools.run_verification_checks``."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.tools.run_verification_checks' is deprecated; use "
    "'mcp_bridge.pbpk_tools.run_verification_checks'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools.run_verification_checks import *  # noqa: F403
