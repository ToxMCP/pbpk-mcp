"""Deprecated compatibility shim for ``mcp.tools.validate_model_manifest``."""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from 'mcp.tools.validate_model_manifest' is deprecated; use "
    "'mcp_bridge.pbpk_tools.validate_model_manifest'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools.validate_model_manifest import *  # noqa: F403
