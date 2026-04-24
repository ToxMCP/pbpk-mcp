"""Deprecated compatibility shim for ``mcp.tools.ingest_external_pbpk_bundle``."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.tools.ingest_external_pbpk_bundle' is deprecated; use "
    "'mcp_bridge.pbpk_tools.ingest_external_pbpk_bundle'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools.ingest_external_pbpk_bundle import *  # noqa: F403
