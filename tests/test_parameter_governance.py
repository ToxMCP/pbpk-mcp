"""Tests for parameter change governance (snapshot + sweep detection)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp.tools.set_parameter_value import (
    SetParameterValueRequest,
    set_parameter_value,
)
from mcp.session_registry import registry
from mcp_bridge.adapter.mock import InMemoryAdapter
from mcp_bridge.parameter_bounds import ParameterBoundsRegistry
from mcp_bridge.storage.snapshot_store import SimulationSnapshotStore


def _register(handle) -> None:
    registry.register(handle, metadata=handle.metadata, allow_replace=True)


def test_snapshot_created_on_parameter_change(tmp_path) -> None:
    adapter = InMemoryAdapter()
    adapter.init()
    handle = adapter.load_simulation("tests/fixtures/demo.pkml", simulation_id="snap-test")
    _register(handle)

    snapshot_store = SimulationSnapshotStore(str(tmp_path))

    payload = SetParameterValueRequest(
        simulationId="snap-test",
        parameterPath="Organ.Liver.Volume",
        value=1.5,
    )

    result = set_parameter_value(
        adapter,
        payload,
        audit_trail=None,
        snapshot_store=snapshot_store,
    )

    assert result.governance.snapshot_id is not None
    assert result.governance.snapshot_id.startswith("202")

    # Verify it was persisted
    records = snapshot_store.list("snap-test")
    assert len(records) == 1
    assert records[0].snapshot_id == result.governance.snapshot_id

    adapter.shutdown()


def test_sweep_alert_detected_after_multiple_changes(tmp_path) -> None:
    adapter = InMemoryAdapter()
    adapter.init()
    handle = adapter.load_simulation("tests/fixtures/demo.pkml", simulation_id="sweep-test")
    _register(handle)

    snapshot_store = SimulationSnapshotStore(str(tmp_path))

    # Fake audit trail that accumulates events
    class FakeAudit:
        enabled = True
        _events: list[dict] = []

        def record_event(self, event_type: str, payload: dict) -> None:
            self._events.append({"eventType": event_type, **payload})

        def fetch_events(self, *, limit: int, event_type: str | None = None):
            return [
                e for e in self._events
                if event_type is None or e.get("eventType") == event_type
            ][-limit:]

    audit = FakeAudit()

    # First 5 changes to the same parameter (6th triggers frequent_changes >5)
    for value in (1.0, 1.1, 1.2, 1.3, 1.35):
        payload = SetParameterValueRequest(
            simulationId="sweep-test",
            parameterPath="Organ.Liver.Volume",
            value=value,
        )
        set_parameter_value(adapter, payload, audit_trail=audit, snapshot_store=snapshot_store)

    # 6th change should trigger frequent_changes alert
    payload = SetParameterValueRequest(
        simulationId="sweep-test",
        parameterPath="Organ.Liver.Volume",
        value=1.4,
    )
    result = set_parameter_value(adapter, payload, audit_trail=audit, snapshot_store=snapshot_store)

    assert any(a["type"] == "frequent_changes" for a in result.governance.sweep_alerts)

    adapter.shutdown()


def test_bounds_reference_included_in_governance(tmp_path) -> None:
    adapter = InMemoryAdapter()
    adapter.init()
    handle = adapter.load_simulation("tests/fixtures/demo.pkml", simulation_id="bounds-test")
    _register(handle)

    snapshot_store = SimulationSnapshotStore(str(tmp_path))

    payload = SetParameterValueRequest(
        simulationId="bounds-test",
        parameterPath="Organism|Liver|Volume",
        value=1.5,
    )

    result = set_parameter_value(
        adapter,
        payload,
        audit_trail=None,
        snapshot_store=snapshot_store,
    )

    bounds = ParameterBoundsRegistry.lookup("Organism|Liver|Volume")
    assert bounds is not None
    assert result.governance.bounds_reference == bounds.references

    adapter.shutdown()
