"""MCP Bridge server package."""

from importlib import metadata

__all__ = ["__version__"]


try:
    _resolved_version = metadata.version("mcp-bridge")
except metadata.PackageNotFoundError:  # pragma: no cover - fallback for local runs
    _resolved_version = None

__version__ = _resolved_version or "0.5.0"
