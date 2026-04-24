"""Unit tests for session rehydration on API startup."""

from __future__ import annotations

from unittest.mock import MagicMock

from mcp_bridge.adapter.errors import AdapterError, AdapterErrorCode
from mcp_bridge.adapter.schema import SimulationHandle
from mcp_bridge.app import _rehydrate_sessions
from mcp_bridge.session_registry import SessionRegistry


def _make_registry(handles: list[SimulationHandle]) -> SessionRegistry:
    registry = SessionRegistry()
    for handle in handles:
        registry.register(handle)
    return registry


def _make_snapshot_store(snapshots: dict[str, dict] | None = None) -> MagicMock:
    store = MagicMock()
    store.load.return_value = None

    def _load_side_effect(simulation_id: str, snapshot_id: str | None = None):
        data = (snapshots or {}).get(simulation_id)
        if data is None:
            return None
        record = MagicMock()
        record.snapshot_id = data.get("snapshot_id", "snap-1")
        record.state = data.get("state", {})
        return record

    store.load.side_effect = _load_side_effect
    return store


def test_rehydration_loads_simulations_and_restores_snapshots() -> None:
    adapter = MagicMock()
    logger = MagicMock()

    handles = [
        SimulationHandle(simulation_id="sim-1", file_path="/models/a.pkml"),
        SimulationHandle(simulation_id="sim-2", file_path="/models/b.pkml"),
    ]
    registry = _make_registry(handles)
    snapshots = {
        "sim-1": {
            "snapshot_id": "snap-1",
            "state": {
                "parameters": [
                    {"path": "Organism|Liver|Volume", "value": 1.5, "unit": "L"},
                ]
            },
        },
    }
    snapshot_store = _make_snapshot_store(snapshots)

    _rehydrate_sessions(adapter, registry, snapshot_store, logger)

    adapter.load_simulation.assert_any_call("/models/a.pkml", simulation_id="sim-1")
    adapter.load_simulation.assert_any_call("/models/b.pkml", simulation_id="sim-2")
    adapter.set_parameter_value.assert_called_once_with(
        "sim-1", "Organism|Liver|Volume", 1.5, "L"
    )

    info_calls = [c for c in logger.info.call_args_list if "rehydration.complete" in str(c)]
    assert info_calls
    complete_call = info_calls[0]
    assert complete_call.kwargs["reloaded"] == 2
    assert complete_call.kwargs["restored"] == 1
    assert complete_call.kwargs["failed"] == 0


def test_rehydration_gracefully_skips_missing_simulations() -> None:
    adapter = MagicMock()
    adapter.load_simulation.side_effect = [
        AdapterError(AdapterErrorCode.NOT_FOUND, "File missing"),
        MagicMock(),
    ]
    logger = MagicMock()

    handles = [
        SimulationHandle(simulation_id="sim-bad", file_path="/models/missing.pkml"),
        SimulationHandle(simulation_id="sim-good", file_path="/models/good.pkml"),
    ]
    registry = _make_registry(handles)
    snapshot_store = _make_snapshot_store()

    _rehydrate_sessions(adapter, registry, snapshot_store, logger)

    assert adapter.load_simulation.call_count == 2

    info_calls = [c for c in logger.info.call_args_list if "rehydration.complete" in str(c)]
    assert info_calls
    complete_call = info_calls[0]
    assert complete_call.kwargs["reloaded"] == 1
    assert complete_call.kwargs["failed"] == 1


def test_rehydration_noop_when_registry_empty() -> None:
    adapter = MagicMock()
    logger = MagicMock()
    registry = SessionRegistry()
    snapshot_store = _make_snapshot_store()

    _rehydrate_sessions(adapter, registry, snapshot_store, logger)

    adapter.load_simulation.assert_not_called()
    logger.info.assert_not_called()


def test_rehydration_continues_when_snapshot_restore_fails() -> None:
    adapter = MagicMock()
    logger = MagicMock()

    handles = [
        SimulationHandle(simulation_id="sim-1", file_path="/models/a.pkml"),
    ]
    registry = _make_registry(handles)

    snapshot_store = MagicMock()
    snapshot_store.load.side_effect = RuntimeError("disk corrupt")

    _rehydrate_sessions(adapter, registry, snapshot_store, logger)

    adapter.load_simulation.assert_called_once()
    logger.warning.assert_called_once()
    assert "snapshot_failed" in str(logger.warning.call_args)
