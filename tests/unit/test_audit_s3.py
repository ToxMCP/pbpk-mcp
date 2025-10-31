from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

import boto3
import pytest
from botocore.stub import Stubber

from mcp_bridge.audit.trail import S3AuditTrail, compute_event_hash


@pytest.mark.skipif(boto3 is None, reason="boto3 not installed")
def test_s3_audit_trail_writes_with_object_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    client = boto3.client("s3", region_name="us-east-1")
    stubber = Stubber(client)

    base_ts = datetime(2025, 10, 25, 15, 30, 0, tzinfo=timezone.utc)

    class FakeDateTime(datetime):  # type: ignore[misc]
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return base_ts

    monkeypatch.setattr("mcp_bridge.audit.trail.datetime", FakeDateTime)
    monkeypatch.setattr("mcp_bridge.audit.trail.uuid4", lambda: "event-uuid")

    stubber.add_response(
        "list_objects_v2",
        {"IsTruncated": False},
        {"Bucket": "audit-bucket", "Prefix": "bridge/audit/2025/10/25"},
    )

    payload = {"foo": "bar"}
    base_event = {
        "eventId": "event-uuid",
        "timestamp": base_ts.isoformat(),
        "eventType": "test.event",
        **payload,
        "previousHash": "0" * 64,
    }
    expected_hash = compute_event_hash(base_event)
    base_event["hash"] = expected_hash
    expected_body = (
        json.dumps(base_event, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode("utf-8")

    retain_until = base_ts + timedelta(days=7)
    stubber.add_response(
        "put_object",
        {},
        {
            "Bucket": "audit-bucket",
            "Key": "bridge/audit/2025/10/25/153000000000-event-uuid.jsonl",
            "Body": expected_body,
            "ContentType": "application/json",
            "ObjectLockMode": "GOVERNANCE",
            "ObjectLockRetainUntilDate": retain_until,
        },
    )

    stubber.activate()
    trail = S3AuditTrail(
        bucket="audit-bucket",
        prefix="bridge/audit",
        client=client,
        enabled=True,
        object_lock_mode="governance",
        object_lock_retain_days=7,
    )

    trail.record_event("test.event", payload)
    stubber.deactivate()
    stubber.assert_no_pending_responses()
