from __future__ import annotations

import time

import pytest

from mcp.session_registry import SessionRegistry, SessionRegistryError
from mcp_bridge.adapter.schema import SimulationHandle


def _make_handle(simulation_id: str = "sim-1") -> SimulationHandle:
    return SimulationHandle(simulation_id=simulation_id, file_path="tests/fixtures/demo.pkml")


def test_register_and_get_round_trip() -> None:
    registry = SessionRegistry()
    handle = _make_handle()

    registry.register(handle, metadata={"source": "test"})

    record = registry.get(handle.simulation_id)
    assert record.handle.simulation_id == handle.simulation_id
    assert record.metadata["source"] == "test"
    assert isinstance(record.created_at, float)
    assert record.last_accessed >= record.created_at


def test_duplicate_registration_raises() -> None:
    registry = SessionRegistry()
    handle = _make_handle()
    registry.register(handle)

    with pytest.raises(SessionRegistryError):
        registry.register(handle)


def test_remove_clears_entry() -> None:
    registry = SessionRegistry()
    handle = _make_handle()
    registry.register(handle)

    registry.remove(handle.simulation_id)
    with pytest.raises(SessionRegistryError):
        registry.get(handle.simulation_id)


def test_touch_updates_last_accessed() -> None:
    registry = SessionRegistry()
    handle = _make_handle()
    registry.register(handle)

    first = registry.get(handle.simulation_id)
    time.sleep(0.01)
    second = registry.get(handle.simulation_id)

    assert second.last_accessed > first.last_accessed
