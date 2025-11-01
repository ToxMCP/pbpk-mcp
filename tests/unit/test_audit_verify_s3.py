from __future__ import annotations

import io
import json
from datetime import datetime, timedelta, timezone

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from mcp_bridge.audit.trail import compute_event_hash
from mcp_bridge.audit.verify import verify_s3_audit_trail


@pytest.mark.skipif(boto3 is None, reason="boto3 not installed")
def test_verify_s3_success(monkeypatch: pytest.MonkeyPatch) -> None:
    client = boto3.client("s3", region_name="us-east-1")
    stubber = Stubber(client)

    # Prepare a single event payload
    timestamp = datetime(2025, 10, 25, 15, 30, tzinfo=timezone.utc)
    event = {
        "eventId": "event-uuid",
        "timestamp": timestamp.isoformat(),
        "eventType": "test.event",
        "payload": {"value": 1},
        "previousHash": "0" * 64,
    }
    event["hash"] = compute_event_hash(event)
    body_bytes = (json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")

    # list_objects_v2 response
    stubber.add_response(
        "list_objects_v2",
        {
            "IsTruncated": False,
            "Contents": [
                {
                    "Key": "bridge/audit/2025/10/25/153000000000-event-uuid.jsonl",
                    "LastModified": timestamp,
                    "ETag": "etag",
                    "Size": len(body_bytes),
                    "StorageClass": "STANDARD",
                }
            ],
        },
        {"Bucket": "audit-bucket", "Prefix": "bridge/audit"},
    )

    retain_until = timestamp + timedelta(days=7)
    stubber.add_response(
        "head_object",
        {
            "ObjectLockMode": "GOVERNANCE",
            "ObjectLockRetainUntilDate": retain_until,
        },
        {
            "Bucket": "audit-bucket",
            "Key": "bridge/audit/2025/10/25/153000000000-event-uuid.jsonl",
        },
    )

    stream = StreamingBody(io.BytesIO(body_bytes), len(body_bytes))
    stubber.add_response(
        "get_object",
        {"Body": stream},
        {
            "Bucket": "audit-bucket",
            "Key": "bridge/audit/2025/10/25/153000000000-event-uuid.jsonl",
        },
    )

    stubber.activate()
    result = verify_s3_audit_trail(
        bucket="audit-bucket",
        prefix="bridge/audit",
        client=client,
        expected_lock_mode="governance",
        expected_lock_days=7,
    )
    stubber.deactivate()

    assert result.ok
    assert result.checked_events == 1


@pytest.mark.skipif(boto3 is None, reason="boto3 not installed")
def test_verify_s3_retention_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    client = boto3.client("s3", region_name="us-east-1")
    stubber = Stubber(client)

    timestamp = datetime(2025, 10, 25, 15, 30, tzinfo=timezone.utc)
    event = {
        "eventId": "event-uuid",
        "timestamp": timestamp.isoformat(),
        "eventType": "test.event",
        "payload": {"value": 1},
        "previousHash": "0" * 64,
    }
    event["hash"] = compute_event_hash(event)
    body_bytes = (json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")

    stubber.add_response(
        "list_objects_v2",
        {
            "IsTruncated": False,
            "Contents": [
                {
                    "Key": "bridge/audit/2025/10/25/153000000000-event-uuid.jsonl",
                    "LastModified": timestamp,
                    "ETag": "etag",
                    "Size": len(body_bytes),
                    "StorageClass": "STANDARD",
                }
            ],
        },
        {"Bucket": "audit-bucket", "Prefix": "bridge/audit"},
    )

    retain_until = timestamp + timedelta(days=1)
    stubber.add_response(
        "head_object",
        {
            "ObjectLockMode": "GOVERNANCE",
            "ObjectLockRetainUntilDate": retain_until,
        },
        {
            "Bucket": "audit-bucket",
            "Key": "bridge/audit/2025/10/25/153000000000-event-uuid.jsonl",
        },
    )

    stream = StreamingBody(io.BytesIO(body_bytes), len(body_bytes))
    stubber.add_response(
        "get_object",
        {"Body": stream},
        {
            "Bucket": "audit-bucket",
            "Key": "bridge/audit/2025/10/25/153000000000-event-uuid.jsonl",
        },
    )

    stubber.activate()
    result = verify_s3_audit_trail(
        bucket="audit-bucket",
        prefix="bridge/audit",
        client=client,
        expected_lock_mode="governance",
        expected_lock_days=7,
    )
    stubber.deactivate()

    assert not result.ok
    assert "retain-until" in result.message
