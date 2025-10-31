from __future__ import annotations

from datetime import datetime, timezone

import pytest

from mcp_bridge.audit.jobs import run_scheduled_verification
from mcp_bridge.audit.trail import AuditTrail
from mcp_bridge.config import AppConfig


def _config(**kwargs) -> AppConfig:
    base = {
        "audit_enabled": True,
        "audit_storage_backend": "local",
        "audit_storage_path": "var/audit-test",
        "audit_verify_lookback_days": 2,
    }
    base.update(kwargs)
    return AppConfig(**base)


def test_run_scheduled_verification_local(tmp_path) -> None:
    trail_path = tmp_path / "audit"
    cfg = _config(audit_storage_path=str(trail_path))
    trail = AuditTrail(trail_path, enabled=True)
    trail.record_event("event", {"value": 1})
    trail.record_event("event", {"value": 2})
    trail.close()

    reference = datetime(2025, 10, 25, tzinfo=timezone.utc)
    outcome = run_scheduled_verification(cfg, reference_time=reference)
    assert outcome.result.ok
    assert outcome.start_key == "2025/10/24"
    assert outcome.end_key == "2025/10/25"


def test_run_scheduled_verification_disabled() -> None:
    cfg = _config(audit_enabled=False)
    outcome = run_scheduled_verification(cfg)
    assert outcome.result.ok
    assert outcome.result.checked_events == 0
    assert outcome.result.message == "Audit trail disabled"
