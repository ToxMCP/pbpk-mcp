"""Async helpers for running blocking operations off the event loop."""

from __future__ import annotations

import asyncio
from typing import Callable, TypeVar

T = TypeVar("T")


async def maybe_to_thread(offload: bool, func: Callable[..., T], *args, **kwargs) -> T:
    """Run ``func`` in a worker thread when ``offload`` is True."""

    if offload:
        return await asyncio.to_thread(func, *args, **kwargs)
    return func(*args, **kwargs)


__all__ = ["maybe_to_thread"]
