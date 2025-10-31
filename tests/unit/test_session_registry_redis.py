from __future__ import annotations

import time

import pytest

from mcp.session_registry import RedisSessionRegistry, SessionRegistryError
from mcp_bridge.adapter.schema import SimulationHandle


fakeredis = pytest.importorskip("fakeredis")


def _make_handle(simulation_id: str = "sim-1") -> SimulationHandle:
    return SimulationHandle(simulation_id=simulation_id, file_path="tests/fixtures/demo.pkml")


def _make_registry(ttl: int | None = None) -> RedisSessionRegistry:
    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server, decode_responses=False)
    return RedisSessionRegistry(client=client, key_prefix="test:sessions", ttl_seconds=ttl)


def test_register_and_get_round_trip() -> None:
    registry = _make_registry()
    handle = _make_handle()
    registry.register(handle, metadata={"source": "test"})

    record = registry.get(handle.simulation_id)
    assert record.handle.simulation_id == handle.simulation_id
    assert record.metadata["source"] == "test"
    assert registry.contains(handle.simulation_id)
    assert handle.simulation_id in registry.list_ids()


def test_duplicate_registration_raises() -> None:
    registry = _make_registry()
    handle = _make_handle()
    registry.register(handle)

    with pytest.raises(SessionRegistryError):
        registry.register(handle)


def test_ttl_eviction_and_prune() -> None:
    ttl_seconds = 1
    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server, decode_responses=False)
    registry = RedisSessionRegistry(client=client, key_prefix="test:sessions", ttl_seconds=ttl_seconds)
    handle = _make_handle()
    registry.register(handle)

    server.advance_time(ttl_seconds + 1)

    with pytest.raises(SessionRegistryError):
        registry.get(handle.simulation_id)
    removed = registry.prune_stale_entries()
    assert handle.simulation_id in removed
    assert handle.simulation_id not in registry.list_ids()


def test_clear_removes_all_records() -> None:
    registry = _make_registry()
    registry.register(_make_handle("sim-a"))
    registry.register(_make_handle("sim-b"))

    registry.clear()
    assert len(tuple(registry.list_ids())) == 0
    assert len(registry.snapshot()) == 0
