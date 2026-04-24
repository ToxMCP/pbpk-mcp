"""Tests for parameter change governance (snapshot + sweep detection)."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_bridge.pbpk_tools.set_parameter_value import (
    SetParameterValueRequest,
    set_parameter_value,
)
from mcp_bridge.session_registry import registry
from mcp_bridge.adapter.mock import InMemoryAdapter
from mcp_bridge import app as app_module
from mcp_bridge.app import create_app
from mcp_bridge.config import AppConfig
from mcp_bridge.parameter_bounds import ParameterBoundsRegistry
from mcp_bridge.security.simple_jwt import jwt
from mcp_bridge.storage.snapshot_store import SimulationSnapshotStore


def _register(handle) -> None:
    registry.register(handle, metadata=handle.metadata, allow_replace=True)


def _operator_headers(secret: str) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": "parameter-governance-operator",
            "roles": ["operator"],
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        },
        secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


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


def test_relative_update_mode_applies_delta(tmp_path) -> None:
    adapter = InMemoryAdapter()
    adapter.init()
    handle = adapter.load_simulation("tests/fixtures/demo.pkml", simulation_id="relative-test")
    _register(handle)
    adapter.set_parameter_value("relative-test", "Organism|Liver|Volume", 1.5, "L")

    result = set_parameter_value(
        adapter,
        SetParameterValueRequest(
            simulationId="relative-test",
            parameterPath="Organism|Liver|Volume",
            value=0.1,
            unit="L",
            updateMode="relative",
        ),
        snapshot_store=SimulationSnapshotStore(str(tmp_path)),
    )

    assert result.parameter.value == pytest.approx(1.6)
    assert result.parameter.unit == "L"
    assert adapter.get_parameter_value("relative-test", "Organism|Liver|Volume").value == pytest.approx(
        1.6
    )

    adapter.shutdown()


def test_rest_parameter_updates_return_governance_and_record_audit(tmp_path) -> None:
    secret = "test-dev-secret-must-be-32-bytes"
    audit_path = tmp_path / "audit"
    snapshot_path = tmp_path / "snapshots"
    model_root = tmp_path / "models"
    model_root.mkdir()
    model_path = model_root / "rest-governance.pkml"
    model_path.write_text("", encoding="utf-8")

    config = AppConfig.model_validate(
        {
            "environment": "development",
            "auth_allow_anonymous": False,
            "auth_dev_secret": secret,
            "audit_enabled": True,
            "audit_storage_path": str(audit_path),
            "snapshot_storage_path": str(snapshot_path),
            "service_version": "0.5.0-test",
        }
    )

    with mock.patch.dict(os.environ, {"ADAPTER_MODEL_PATHS": str(model_root)}, clear=False):
        with mock.patch.object(app_module, "build_adapter", return_value=InMemoryAdapter()):
            with TestClient(create_app(config=config)) as client:
                headers = _operator_headers(secret)
                load = client.post(
                    "/load_simulation",
                    headers=headers,
                    json={
                        "filePath": str(model_path),
                        "simulationId": "rest-governance",
                        "confirm": True,
                    },
                )
                assert load.status_code == 201

                first_write = client.post(
                    "/set_parameter_value",
                    headers=headers,
                    json={
                        "simulationId": "rest-governance",
                        "parameterPath": "Organism|Liver|Volume",
                        "value": 1.5,
                        "unit": "L",
                        "confirm": True,
                    },
                )
                assert first_write.status_code == 200

                relative_write = client.post(
                    "/set_parameter_value",
                    headers=headers,
                    json={
                        "simulationId": "rest-governance",
                        "parameterPath": "Organism|Liver|Volume",
                        "value": 0.1,
                        "unit": "L",
                        "updateMode": "relative",
                        "confirm": True,
                    },
                )
                assert relative_write.status_code == 200
                payload = relative_write.json()

    assert payload["parameter"]["value"] == pytest.approx(1.6)
    assert payload["parameter"]["unit"] == "L"
    assert payload["governance"]["snapshotId"] is not None
    assert payload["governance"]["boundsReference"] == ["ICRP 89"]

    events: list[dict] = []
    for path in sorted(audit_path.rglob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))

    parameter_changes = [event for event in events if event.get("eventType") == "parameter.changed"]
    assert len(parameter_changes) == 2
    assert parameter_changes[-1]["oldValue"] == pytest.approx(1.5)
    assert parameter_changes[-1]["newValue"] == pytest.approx(1.6)
