"""Deprecated compatibility namespace for PBPK MCP tools.

New code should import from ``mcp_bridge.pbpk_tools`` and
``mcp_bridge.session_registry``. This package remains temporarily so older
PBPK MCP clients do not break during the namespace migration.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "The top-level 'mcp' PBPK namespace is deprecated; use "
    "'mcp_bridge.pbpk_tools' and 'mcp_bridge.session_registry'.",
    DeprecationWarning,
    stacklevel=2,
)

from mcp_bridge.pbpk_tools import *  # noqa: F403
from mcp_bridge.pbpk_tools import __all__ as _tool_exports
from mcp_bridge.session_registry import (
    RedisSessionRegistry,
    SessionRegistry,
    SessionRegistryError,
    registry,
    set_registry,
)

__all__ = [
    "SessionRegistry",
    "RedisSessionRegistry",
    "SessionRegistryError",
    "registry",
    "set_registry",
    *_tool_exports,
]
