"""Tests for audit verification utility."""

from __future__ import annotations

import json

from mcp_bridge.audit import AuditTrail
from mcp_bridge.audit.verify import verify_audit_trail


def test_verify_success(tmp_path) -> None:
    trail = AuditTrail(tmp_path, enabled=True)
    trail.record_event("event", {"payload": {"value": 1}})
    trail.record_event("event", {"payload": {"value": 2}})
    trail.close()

    result = verify_audit_trail(tmp_path)
    assert result.ok
    assert result.checked_events == 2


def test_verify_detects_tampering(tmp_path) -> None:
    trail = AuditTrail(tmp_path, enabled=True)
    trail.record_event("event", {"payload": {"value": 1}})
    trail.record_event("event", {"payload": {"value": 2}})
    trail.close()

    log_file = next(tmp_path.rglob("*.jsonl"))
    lines = log_file.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[1])
    tampered["payload"]["value"] = 999
    lines[1] = json.dumps(tampered, separators=(",", ":"), sort_keys=True)
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = verify_audit_trail(tmp_path)
    assert not result.ok
    assert "Hash mismatch" in result.message
