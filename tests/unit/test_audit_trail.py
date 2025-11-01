"""Tests for the immutable audit trail writer."""

from __future__ import annotations

import json
from pathlib import Path

from mcp_bridge.audit import AuditTrail


def _read_events(directory: Path) -> list[dict]:
    events: list[dict] = []
    for path in sorted(directory.rglob("*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    events.append(json.loads(line))
    return events


def test_audit_trail_writes_hash_chain(tmp_path) -> None:
    audit = AuditTrail(tmp_path, enabled=True)
    audit.record_event("test.event", {"payload": {"value": 1}})
    audit.record_event("test.event", {"payload": {"value": 2}})
    audit.close()

    events = _read_events(tmp_path)
    assert len(events) == 2
    assert events[1]["previousHash"] == events[0]["hash"]
    assert events[0]["hash"] != "0" * 64


def test_audit_trail_disabled(tmp_path) -> None:
    audit = AuditTrail(tmp_path, enabled=False)
    audit.record_event("test.event", {"payload": {"value": 1}})
    audit.close()

    events = list(tmp_path.rglob("*.jsonl"))
    assert not events
