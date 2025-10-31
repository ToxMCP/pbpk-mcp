from __future__ import annotations

from mcp_bridge.storage.snapshot_store import SimulationSnapshotStore


def test_snapshot_store_roundtrip(tmp_path):
    store = SimulationSnapshotStore(tmp_path / "snapshots")
    state = {
        "simulationId": "sim-1",
        "filePath": "tests/fixtures/demo.pkml",
        "parameters": [
            {"path": "Organ.Liver.Weight", "value": 72.0, "unit": "kg"},
            {"path": "Organism|Height", "value": 180.0, "unit": "cm"},
        ],
    }

    record = store.save("sim-1", state)

    loaded = store.load("sim-1")
    assert loaded is not None
    assert loaded.snapshot_id == record.snapshot_id
    assert loaded.state == state
    assert loaded.hash == record.hash

    listings = store.list("sim-1")
    assert len(listings) == 1
    assert listings[0].snapshot_id == record.snapshot_id


def test_snapshot_store_handles_missing(tmp_path):
    store = SimulationSnapshotStore(tmp_path / "snapshots")
    assert store.load("unknown") is None
    assert store.list("unknown") == []
