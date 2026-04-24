from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_bridge.audit.trail import LocalAuditTrail, compute_event_hash  # noqa: E402
from mcp_bridge.audit.verify import verify_audit_trail  # noqa: E402
from mcp_bridge.app import create_app  # noqa: E402
from mcp_bridge.config import AppConfig  # noqa: E402
from mcp_bridge.security.auth import AuthContext  # noqa: E402


def _build_event(*, event_type: str, timestamp: str, previous_hash: str, payload: dict[str, object]) -> dict[str, object]:
    event = {
        "eventId": f"{event_type}-{timestamp}",
        "timestamp": timestamp,
        "eventType": event_type,
        "previousHash": previous_hash,
        **payload,
    }
    event["hash"] = compute_event_hash(event)
    return event


def _dev_auth_header(secret: str = "dev-secret-must-be-32-bytes-long", role: str = "admin") -> dict[str, str]:
    import jwt
    import time
    token = jwt.encode(
        {
            "sub": f"audit-verify-{role}",
            "roles": [role],
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        },
        secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _make_app(config: AppConfig):
    return create_app(config=config)


def _local_config(tmpdir: str) -> AppConfig:
    return AppConfig.model_validate(
        {
            "environment": "development",
            "auth_dev_secret": "dev-secret-must-be-32-bytes-long",
            "audit_enabled": True,
            "audit_storage_path": tmpdir,
            "audit_storage_backend": "local",
            "service_version": "0.4.3-test",
        }
    )


class AuditVerifyEndpointTests(unittest.TestCase):
    def test_verify_local_audit_trail_via_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            first = _build_event(
                event_type="http.mcp.day1",
                timestamp="2026-04-10T10:00:00+00:00",
                previous_hash="0" * 64,
                payload={"request": {"path": "/day1"}},
            )
            second = _build_event(
                event_type="http.mcp.day2",
                timestamp="2026-04-10T10:01:00+00:00",
                previous_hash=str(first["hash"]),
                payload={"request": {"path": "/day2"}},
            )
            path = base / "2026" / "04" / "10.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(first) + "\n" + json.dumps(second) + "\n", encoding="utf-8")

            config = _local_config(str(base))
            with TestClient(_make_app(config)) as client:
                response = client.post("/audit/verify", json={"storage": "local"}, headers=_dev_auth_header())

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data["ok"])
            self.assertEqual(data["checkedEvents"], 2)
            self.assertEqual(data["message"], "Verified")

    def test_verify_local_with_date_range(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            first = _build_event(
                event_type="http.mcp.day1",
                timestamp="2026-04-09T23:59:59+00:00",
                previous_hash="0" * 64,
                payload={"request": {"path": "/day1"}},
            )
            second = _build_event(
                event_type="http.mcp.day2",
                timestamp="2026-04-10T00:00:01+00:00",
                previous_hash=str(first["hash"]),
                payload={"request": {"path": "/day2"}},
            )
            (base / "2026" / "04" / "09.jsonl").parent.mkdir(parents=True, exist_ok=True)
            (base / "2026" / "04" / "09.jsonl").write_text(json.dumps(first) + "\n", encoding="utf-8")
            (base / "2026" / "04" / "10.jsonl").write_text(json.dumps(second) + "\n", encoding="utf-8")

            config = _local_config(str(base))
            with TestClient(_make_app(config)) as client:
                response = client.post(
                    "/audit/verify",
                    json={"storage": "local", "start": "2026/04/10", "end": "2026/04/10"},
                    headers=_dev_auth_header(),
                )

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data["ok"])
            self.assertEqual(data["checkedEvents"], 1)

    def test_verify_local_detects_tampered_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            event = _build_event(
                event_type="http.mcp.tampered",
                timestamp="2026-04-10T10:00:00+00:00",
                previous_hash="0" * 64,
                payload={"request": {"path": "/tampered"}},
            )
            event["hash"] = "deadbeef" * 8
            path = base / "2026" / "04" / "10.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")

            config = _local_config(str(base))
            with TestClient(_make_app(config)) as client:
                response = client.post("/audit/verify", json={"storage": "local"}, headers=_dev_auth_header())

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertFalse(data["ok"])
            self.assertIn("Hash mismatch", data["message"])

    def test_verify_local_detects_broken_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            first = _build_event(
                event_type="http.mcp.first",
                timestamp="2026-04-10T10:00:00+00:00",
                previous_hash="0" * 64,
                payload={"request": {"path": "/first"}},
            )
            second = _build_event(
                event_type="http.mcp.second",
                timestamp="2026-04-10T10:01:00+00:00",
                previous_hash="0" * 64,
                payload={"request": {"path": "/second"}},
            )
            path = base / "2026" / "04" / "10.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(first) + "\n" + json.dumps(second) + "\n", encoding="utf-8")

            config = _local_config(str(base))
            with TestClient(_make_app(config)) as client:
                response = client.post("/audit/verify", json={"storage": "local"}, headers=_dev_auth_header())

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertFalse(data["ok"])
            self.assertIn("Hash chain mismatch", data["message"])

    def test_verify_s3_rejects_missing_bucket(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _local_config(str(tmpdir))
            with TestClient(_make_app(config)) as client:
                response = client.post("/audit/verify", json={"storage": "s3"}, headers=_dev_auth_header())

            self.assertEqual(response.status_code, 400)
            self.assertIn("S3 bucket is required", response.text)

    def test_verify_requires_admin_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _local_config(str(tmpdir))
            with TestClient(_make_app(config)) as client:
                response = client.post(
                    "/audit/verify",
                    json={"storage": "local"},
                    headers=_dev_auth_header(role="operator"),
                )

            self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
