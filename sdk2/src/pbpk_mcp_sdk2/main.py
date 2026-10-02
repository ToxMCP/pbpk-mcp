from __future__ import annotations

import argparse
import logging
import sys

import anyio
from mcp.server.stdio import stdio_server

from .backend import Backend
from .server import create_server
from .settings import Settings


async def serve_stdio():
    backend = Backend(Settings())
    try:
        server = create_server(backend)
        async with stdio_server() as (reader, writer):
            await server.run(reader, writer, server.create_initialization_options())
    finally:
        await backend.close()


def stdio_main():
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    anyio.run(serve_stdio)


def http_main():
    import uvicorn
    from .http import create_app

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(create_app(), host=args.host, port=args.port)
