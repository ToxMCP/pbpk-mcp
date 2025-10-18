"""Application entrypoint for running the MCP Bridge server."""

from __future__ import annotations

import os

import uvicorn

from .app import create_app
from .config import load_config

config = load_config()
app = create_app(config=config)

if __name__ == "__main__":  # pragma: no cover - manual invocation
    uvicorn.run(
        "mcp_bridge.main:app",
        host=config.host,
        port=config.port,
        reload=os.getenv("UVICORN_RELOAD", "0") == "1",
        log_config=None,
    )
