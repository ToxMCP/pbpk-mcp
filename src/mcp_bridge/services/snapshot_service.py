"""Utilities for capturing and restoring simulation baseline snapshots."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..adapter.interface import OspsuiteAdapter
from ..storage.snapshot_store import SimulationSnapshotStore, SnapshotRecord


def apply_snapshot_state(
    adapter: OspsuiteAdapter, state: Dict[str, Any], fallback_simulation_id: str
) -> None:
    simulation_id = str(state.get("simulationId") or fallback_simulation_id)
    file_path = state.get("filePath")
    if file_path:
        adapter.load_simulation(file_path, simulation_id=simulation_id)
    for entry in state.get("parameters", []):
        path = entry.get("path")
        value = entry.get("value")
        if path is None or value is None:
            continue
        unit = entry.get("unit")
        adapter.set_parameter_value(simulation_id, path, float(value), unit)


def capture_snapshot(
    adapter: OspsuiteAdapter,
    snapshot_store: SimulationSnapshotStore,
    simulation_id: str,
) -> SnapshotRecord:
    state = adapter.export_simulation_state(simulation_id)
    return snapshot_store.save(simulation_id, state)


def restore_snapshot(
    adapter: OspsuiteAdapter,
    snapshot_store: SimulationSnapshotStore,
    simulation_id: str,
    snapshot_id: Optional[str] = None,
) -> SnapshotRecord:
    record = snapshot_store.load(simulation_id, snapshot_id)
    if record is None:
        raise FileNotFoundError(f"No snapshot found for simulation '{simulation_id}'")
    apply_snapshot_state(adapter, record.state, simulation_id)
    return record


__all__ = [
    "apply_snapshot_state",
    "capture_snapshot",
    "restore_snapshot",
]
