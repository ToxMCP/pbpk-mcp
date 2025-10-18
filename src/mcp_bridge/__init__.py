"""MCP Bridge server package."""

from importlib import metadata

__all__ = ["__version__"]


try:
    __version__ = metadata.version("mcp-bridge")
except metadata.PackageNotFoundError:  # pragma: no cover - fallback for local runs
    __version__ = "0.1.0"
