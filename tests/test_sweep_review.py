"""Tests for parameter sweep review tracking (M-02 remediation)."""

from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_bridge.audit.sweep_review import (  # noqa: E402
    SWEEP_REVIEWED_EVENT,
    attach_sweep_review,
    build_sweep_review_summary,
    record_sweep_review,
)


def test_no_changes_returns_no_changes() -> None:
    class FakeAudit:
        enabled = True

        def fetch_events(self, *, limit: int, event_type: str | None = None):
            return []

    summary = build_sweep_review_summary(FakeAudit(), "sim-1")
    assert summary["status"] == "no_changes"
    assert summary["requiresReviewerAttention"] is False


def test_sweeps_detected_and_unreviewed() -> None:
    class FakeAudit:
        enabled = True
        _events = [
            {
                "eventType": "parameter.changed",
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:00:00Z",
                "parameterPath": "Organism|Liver|Volume",
                "newValue": 1.0,
                "oldValue": 1.5,
            },
            {
                "eventType": "parameter.changed",
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:01:00Z",
                "parameterPath": "Organism|Liver|Volume",
                "newValue": 1.1,
                "oldValue": 1.0,
            },
            {
                "eventType": "parameter.changed",
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:02:00Z",
                "parameterPath": "Organism|Liver|Volume",
                "newValue": 1.2,
                "oldValue": 1.1,
            },
            {
                "eventType": "parameter.changed",
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:03:00Z",
                "parameterPath": "Organism|Liver|Volume",
                "newValue": 1.3,
                "oldValue": 1.2,
            },
            {
                "eventType": "parameter.changed",
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:04:00Z",
                "parameterPath": "Organism|Liver|Volume",
                "newValue": 1.35,
                "oldValue": 1.3,
            },
            {
                "eventType": "parameter.changed",
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:05:00Z",
                "parameterPath": "Organism|Liver|Volume",
                "newValue": 1.4,
                "oldValue": 1.35,
            },
        ]

        def fetch_events(self, *, limit: int, event_type: str | None = None):
            return [e for e in self._events if event_type is None or e.get("eventType") == event_type]

    summary = build_sweep_review_summary(FakeAudit(), "sim-1")
    assert summary["status"] == "unreviewed_sweeps"
    assert summary["requiresReviewerAttention"] is True
    assert summary["blocksTrustBearingOutput"] is True
    assert any(a["type"] == "frequent_changes" for a in summary["sweepAlerts"])


def test_review_clears_unreviewed_status() -> None:
    class FakeAudit:
        enabled = True
        _events = [
            {
                "eventType": "parameter.changed",
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:00:00Z",
                "parameterPath": "Organism|Liver|Volume",
                "newValue": 1.0,
                "oldValue": 1.5,
            },
            {
                "eventType": "parameter.changed",
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:01:00Z",
                "parameterPath": "Organism|Liver|Volume",
                "newValue": 1.1,
                "oldValue": 1.0,
            },
            {
                "eventType": "parameter.changed",
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:02:00Z",
                "parameterPath": "Organism|Liver|Volume",
                "newValue": 1.2,
                "oldValue": 1.1,
            },
            {
                "eventType": SWEEP_REVIEWED_EVENT,
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:03:00Z",
                "disposition": "acknowledged",
                "identity": {"subject": "operator-1", "roles": ["operator"]},
            },
        ]

        def fetch_events(self, *, limit: int, event_type: str | None = None):
            return [e for e in self._events if event_type is None or e.get("eventType") == event_type]

    summary = build_sweep_review_summary(FakeAudit(), "sim-1")
    assert summary["status"] == "reviewed"
    assert summary["requiresReviewerAttention"] is False
    assert summary["blocksTrustBearingOutput"] is False
    assert summary["reviewedAt"] == "2026-04-15T10:03:00Z"


def test_new_changes_after_review_are_unreviewed() -> None:
    class FakeAudit:
        enabled = True
        _events = [
            {
                "eventType": "parameter.changed",
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:00:00Z",
                "parameterPath": "Organism|Liver|Volume",
                "newValue": 1.0,
            },
            {
                "eventType": "parameter.changed",
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:01:00Z",
                "parameterPath": "Organism|Liver|Volume",
                "newValue": 1.1,
            },
            {
                "eventType": SWEEP_REVIEWED_EVENT,
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:02:00Z",
                "disposition": "acknowledged",
            },
            {
                "eventType": "parameter.changed",
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:03:00Z",
                "parameterPath": "Organism|Liver|Volume",
                "newValue": 1.2,
            },
            {
                "eventType": "parameter.changed",
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:04:00Z",
                "parameterPath": "Organism|Liver|Volume",
                "newValue": 1.3,
            },
            {
                "eventType": "parameter.changed",
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:05:00Z",
                "parameterPath": "Organism|Liver|Volume",
                "newValue": 1.35,
            },
            {
                "eventType": "parameter.changed",
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:06:00Z",
                "parameterPath": "Organism|Liver|Volume",
                "newValue": 1.4,
            },
            {
                "eventType": "parameter.changed",
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:07:00Z",
                "parameterPath": "Organism|Liver|Volume",
                "newValue": 1.45,
            },
            {
                "eventType": "parameter.changed",
                "simulationId": "sim-1",
                "timestamp": "2026-04-15T10:08:00Z",
                "parameterPath": "Organism|Liver|Volume",
                "newValue": 1.5,
            },
        ]

        def fetch_events(self, *, limit: int, event_type: str | None = None):
            return [e for e in self._events if event_type is None or e.get("eventType") == event_type]

    summary = build_sweep_review_summary(FakeAudit(), "sim-1")
    assert summary["status"] == "unreviewed_sweeps"
    assert summary["requiresReviewerAttention"] is True


def test_attach_sweep_review_adds_to_payload() -> None:
    class FakeAudit:
        enabled = True

        def fetch_events(self, *, limit: int, event_type: str | None = None):
            return []

    payload = {"simulationId": "sim-1", "report": {"status": "ok"}}
    attach_sweep_review(payload, audit=FakeAudit(), tool_name="export_oecd_report")
    assert "parameterSweepReview" in payload
    assert "parameterSweepReview" in payload["report"]
