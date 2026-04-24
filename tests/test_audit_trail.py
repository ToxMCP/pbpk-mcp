from __future__ import annotations

from copy import deepcopy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_bridge.audit.middleware import AuditMiddleware  # noqa: E402
from mcp_bridge.audit.trail import LocalAuditTrail, S3AuditTrail, compute_event_hash  # noqa: E402
from mcp_bridge.audit.verify import verify_audit_trail  # noqa: E402
from mcp_bridge.review_signoff import (  # noqa: E402
    attach_operator_review_signoff,
    build_operator_review_signoff_history,
    build_operator_review_signoff_summary,
    record_operator_review_signoff,
)
from mcp_bridge.security.auth import AuthContext  # noqa: E402
from mcp_bridge.trust_surface import attach_trust_surface_contract  # noqa: E402


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


class _FakeBody:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


class _FakeS3Client:
    def __init__(self) -> None:
        self._objects: dict[str, dict[str, object]] = {}

    def put_object(self, **params: object) -> None:
        self._objects[str(params["Key"])] = dict(params)

    def list_objects_v2(self, **params: object) -> dict[str, object]:
        prefix = str(params.get("Prefix") or "")
        keys = sorted(key for key in self._objects if key.startswith(prefix))
        return {
            "Contents": [{"Key": key} for key in keys],
            "IsTruncated": False,
        }

    def get_object(self, **params: object) -> dict[str, object]:
        key = str(params["Key"])
        record = self._objects[key]
        return {"Body": _FakeBody(record["Body"])}  # type: ignore[index]


class AuditTrailTests(unittest.TestCase):
    @staticmethod
    def _normalized_operator_review_payload(payload: dict[str, object]) -> dict[str, object]:
        normalized = deepcopy(payload)
        for candidate in (
            normalized,
            normalized.get("report"),
            (
                normalized.get("report", {})
                if isinstance(normalized.get("report"), dict)
                else {}
            ).get("humanReviewSummary"),
        ):
            if not isinstance(candidate, dict):
                continue
            signoff = candidate.get("operatorReviewSignoff")
            if not isinstance(signoff, dict):
                continue
            signoff["recordedAt"] = None
            signoff["revokedAt"] = None
            traceability = signoff.get("traceability")
            if isinstance(traceability, dict):
                traceability["sourceEventId"] = None
                traceability["sourceEventHash"] = None
                traceability["previousHash"] = None
        return normalized

    def test_local_rollover_carries_previous_day_tail_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            day_one = _build_event(
                event_type="http.mcp.day1",
                timestamp="2026-02-20T23:59:59+00:00",
                previous_hash="0" * 64,
                payload={"request": {"path": "/day1"}},
            )
            target = base / "2026" / "02" / "20.jsonl"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(day_one) + "\n", encoding="utf-8")

            audit = LocalAuditTrail(base)
            audit._rollover(datetime(2026, 2, 21, 0, 0, tzinfo=timezone.utc))

            self.assertEqual(audit._tail_hash, day_one["hash"])

    def test_verify_audit_trail_handles_partial_windows_with_prior_chain_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            first = _build_event(
                event_type="http.mcp.day1",
                timestamp="2026-02-20T23:59:59+00:00",
                previous_hash="0" * 64,
                payload={"request": {"path": "/day1"}},
            )
            second = _build_event(
                event_type="http.mcp.day2",
                timestamp="2026-02-21T00:00:01+00:00",
                previous_hash=str(first["hash"]),
                payload={"request": {"path": "/day2"}},
            )
            for relative, event in [
                ("2026/02/20.jsonl", first),
                ("2026/02/21.jsonl", second),
            ]:
                path = base / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(event) + "\n", encoding="utf-8")

            result = verify_audit_trail(base, start="2026/02/21", end="2026/02/21")

            self.assertTrue(result.ok)
            self.assertEqual(result.checked_events, 1)

    def test_audit_middleware_redacts_secrets_and_phi(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            app = FastAPI()
            audit = LocalAuditTrail(tmpdir)
            app.add_middleware(AuditMiddleware, audit=audit)

            @app.post("/echo")
            async def echo(request: Request) -> dict[str, bool]:
                return {"ok": True}

            with TestClient(app) as client:
                response = client.post(
                    "/echo",
                    json={
                        "patientEmail": "alice@example.com",
                        "token": "secret-token-123",
                        "nested": {"authorization": "Bearer abc"},
                    },
                )
            self.assertEqual(response.status_code, 200)
            audit.close()

            paths = sorted(Path(tmpdir).glob("**/*.jsonl"))
            payload = json.loads(paths[-1].read_text(encoding="utf-8").strip())
            request_payload = payload["request"]["payload"]

            self.assertEqual(request_payload["patientEmail"], "[REDACTED:EMAIL]")
            self.assertEqual(request_payload["token"], "[REDACTED:SECRET]")
            self.assertEqual(request_payload["nested"]["authorization"], "[REDACTED:SECRET]")

    def test_s3_fetch_events_returns_recent_entries(self) -> None:
        fake_client = _FakeS3Client()
        audit = S3AuditTrail(bucket="audit", prefix="audit-trail", client=fake_client)
        audit.record_event("event.one", {"payload": {"value": 1}})
        audit.record_event("event.two", {"payload": {"value": 2}})

        events = audit.fetch_events(limit=10)

        self.assertEqual([event["eventType"] for event in events], ["event.two", "event.one"])
        filtered = audit.fetch_events(limit=10, event_type="event.one")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["eventType"], "event.one")

    def test_local_fetch_events_returns_recent_entries_from_large_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            audit = LocalAuditTrail(tmpdir)
            for index in range(250):
                event_type = "event.one" if index % 2 == 0 else "event.two"
                audit.record_event(event_type, {"payload": {"value": index}})

            events = audit.fetch_events(limit=5)

            self.assertEqual(len(events), 5)
            self.assertEqual([event["payload"]["value"] for event in events], [249, 248, 247, 246, 245])
            filtered = audit.fetch_events(limit=3, event_type="event.one")
            self.assertEqual([event["payload"]["value"] for event in filtered], [248, 246, 244])

    def test_local_review_signoff_index_supports_summary_without_main_audit_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            audit = LocalAuditTrail(tmpdir, enabled=True)
            auth = AuthContext(subject="operator-local-index", roles=["operator"], token_id="tok-local-index")
            record_operator_review_signoff(
                audit,
                auth=auth,
                simulation_id="sim-index",
                scope="export_oecd_report",
                disposition="acknowledged",
                rationale="Indexed summary should remain readable without rescanning the full audit tail.",
                service_version="0.4.3-test",
            )

            indexed = audit.fetch_review_signoff_events(
                limit=10,
                simulation_id="sim-index",
                scope="export_oecd_report",
            )
            self.assertEqual(len(indexed), 1)
            self.assertEqual(indexed[0]["eventType"], "review.signoff.recorded")
            self.assertEqual(
                audit.count_review_signoff_events(
                    simulation_id="sim-index",
                    scope="export_oecd_report",
                ),
                1,
            )

            for path in Path(tmpdir).glob("**/*.jsonl"):
                path.unlink()

            summary = build_operator_review_signoff_summary(
                audit,
                simulation_id="sim-index",
                scope="export_oecd_report",
            )
            history = build_operator_review_signoff_history(
                audit,
                simulation_id="sim-index",
                scope="export_oecd_report",
                limit=10,
            )
            self.assertEqual(summary["status"], "recorded")
            self.assertEqual(history["returnedEntryCount"], 1)
            self.assertEqual(history["entries"][0]["action"], "recorded")

    def test_local_backfill_review_signoff_index_restores_legacy_visibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            event = _build_event(
                event_type="review.signoff.recorded",
                timestamp="2026-04-08T12:34:56+00:00",
                previous_hash="0" * 64,
                payload={
                    "identity": {"subject": "legacy-operator", "roles": ["operator"]},
                    "reviewSignoff": {
                        "simulationId": "legacy-local",
                        "scope": "export_oecd_report",
                        "disposition": "acknowledged",
                        "rationale": "Legacy signoff recorded before the dedicated index existed.",
                        "serviceVersion": "0.4.2",
                    },
                },
            )
            path = Path(tmpdir) / "2026" / "04" / "08.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")

            audit = LocalAuditTrail(tmpdir, enabled=True)
            before = build_operator_review_signoff_summary(
                audit,
                simulation_id="legacy-local",
                scope="export_oecd_report",
            )
            self.assertEqual(before["status"], "not-recorded")

            result = audit.backfill_review_signoff_index()
            after = build_operator_review_signoff_summary(
                audit,
                simulation_id="legacy-local",
                scope="export_oecd_report",
            )
            self.assertEqual(result["signoffEvents"], 1)
            self.assertEqual(result["indexedNew"], 1)
            self.assertEqual(after["status"], "recorded")
            self.assertEqual(after["recordedBy"]["subject"], "legacy-operator")

    def test_s3_audit_trail_builds_client_with_endpoint_and_path_style(self) -> None:
        sentinel_client = object()
        with mock.patch("mcp_bridge.audit.trail.build_s3_client", return_value=sentinel_client) as builder:
            audit = S3AuditTrail(
                bucket="audit",
                prefix="audit-trail",
                region="us-east-1",
                endpoint_url="http://minio:9000",
                force_path_style=True,
            )

        self.assertIs(audit._client, sentinel_client)
        builder.assert_called_once_with(
            region="us-east-1",
            endpoint_url="http://minio:9000",
            force_path_style=True,
        )

    def test_s3_signoff_summary_and_history_match_local_backend(self) -> None:
        auth = AuthContext(subject="operator-s3", roles=["operator"], token_id="tok-s3")
        fake_client = _FakeS3Client()
        s3_audit = S3AuditTrail(bucket="audit", prefix="audit-trail", client=fake_client)

        with tempfile.TemporaryDirectory() as tmpdir:
            local_audit = LocalAuditTrail(tmpdir, enabled=True)
            record_operator_review_signoff(
                local_audit,
                auth=auth,
                simulation_id="sim-s3",
                scope="export_oecd_report",
                disposition="acknowledged",
                rationale="Reviewed against bounded-use caveats.",
                service_version="0.4.3-test",
            )
            record_operator_review_signoff(
                s3_audit,
                auth=auth,
                simulation_id="sim-s3",
                scope="export_oecd_report",
                disposition="acknowledged",
                rationale="Reviewed against bounded-use caveats.",
                service_version="0.4.3-test",
            )

            local_summary = build_operator_review_signoff_summary(
                local_audit,
                simulation_id="sim-s3",
                scope="export_oecd_report",
            )
            s3_summary = build_operator_review_signoff_summary(
                s3_audit,
                simulation_id="sim-s3",
                scope="export_oecd_report",
            )
            self.assertEqual(local_summary["status"], s3_summary["status"])
            self.assertEqual(local_summary["disposition"], s3_summary["disposition"])
            self.assertEqual(local_summary["recordedBy"]["subject"], s3_summary["recordedBy"]["subject"])

            s3_history = build_operator_review_signoff_history(
                s3_audit,
                simulation_id="sim-s3",
                scope="export_oecd_report",
                limit=10,
            )
            self.assertEqual(s3_history["status"], "available")
            self.assertEqual(s3_history["returnedEntryCount"], 1)
            self.assertEqual(s3_history["entries"][0]["actor"]["subject"], "operator-s3")

    def test_s3_review_signoff_index_supports_summary_without_primary_audit_objects(self) -> None:
        auth = AuthContext(subject="operator-s3-index", roles=["operator"], token_id="tok-s3-index")
        fake_client = _FakeS3Client()
        audit = S3AuditTrail(bucket="audit", prefix="audit-trail", client=fake_client)
        record_operator_review_signoff(
            audit,
            auth=auth,
            simulation_id="sim-s3-index",
            scope="export_oecd_report",
            disposition="approved-for-bounded-use",
            rationale="Indexed S3 signoff reads should not depend on scanning the main audit prefix.",
            service_version="0.4.3-test",
        )

        indexed = audit.fetch_review_signoff_events(
            limit=10,
            simulation_id="sim-s3-index",
            scope="export_oecd_report",
        )
        self.assertEqual(len(indexed), 1)
        self.assertEqual(indexed[0]["eventType"], "review.signoff.recorded")
        self.assertEqual(
            audit.count_review_signoff_events(
                simulation_id="sim-s3-index",
                scope="export_oecd_report",
            ),
            1,
        )

        for key in list(fake_client._objects):
            if "/_index/" not in key:
                del fake_client._objects[key]

        summary = build_operator_review_signoff_summary(
            audit,
            simulation_id="sim-s3-index",
            scope="export_oecd_report",
        )
        history = build_operator_review_signoff_history(
            audit,
            simulation_id="sim-s3-index",
            scope="export_oecd_report",
            limit=10,
        )
        self.assertEqual(summary["status"], "recorded")
        self.assertEqual(history["returnedEntryCount"], 1)
        self.assertEqual(history["entries"][0]["action"], "recorded")

    def test_s3_backfill_review_signoff_index_restores_legacy_visibility(self) -> None:
        fake_client = _FakeS3Client()
        audit = S3AuditTrail(bucket="audit", prefix="audit-trail", client=fake_client)
        event = _build_event(
            event_type="review.signoff.recorded",
            timestamp="2026-04-08T12:34:56+00:00",
            previous_hash="0" * 64,
            payload={
                "identity": {"subject": "legacy-s3-operator", "roles": ["operator"]},
                "reviewSignoff": {
                    "simulationId": "legacy-s3",
                    "scope": "export_oecd_report",
                    "disposition": "approved-for-bounded-use",
                    "rationale": "Legacy S3 signoff recorded before the dedicated index existed.",
                    "serviceVersion": "0.4.2",
                },
            },
        )
        raw_key = "audit-trail/2026/04/08/123456000000-legacy-event.jsonl"
        fake_client.put_object(
            Bucket="audit",
            Key=raw_key,
            Body=(json.dumps(event) + "\n").encode("utf-8"),
            ContentType="application/json",
        )

        before = build_operator_review_signoff_summary(
            audit,
            simulation_id="legacy-s3",
            scope="export_oecd_report",
        )
        self.assertEqual(before["status"], "not-recorded")

        result = audit.backfill_review_signoff_index()
        after = build_operator_review_signoff_summary(
            audit,
            simulation_id="legacy-s3",
            scope="export_oecd_report",
        )
        self.assertEqual(result["signoffEvents"], 1)
        self.assertEqual(result["indexedNew"], 1)
        self.assertEqual(after["status"], "recorded")
        self.assertEqual(after["recordedBy"]["subject"], "legacy-s3-operator")

    def test_s3_augmented_trust_bearing_report_matches_local_backend(self) -> None:
        auth = AuthContext(subject="operator-s3", roles=["operator"], token_id="tok-s3")
        fake_client = _FakeS3Client()
        s3_audit = S3AuditTrail(bucket="audit", prefix="audit-trail", client=fake_client)

        base_payload = {
            "simulationId": "sim-s3-report",
            "report": {
                "humanReviewSummary": {
                    "plainLanguageSummary": "Human review remains required.",
                    "reviewStatus": {"status": "required"},
                    "cautionSummary": {"highestSeverity": "high"},
                    "summaryTransportRisk": {"plainLanguageSummary": "Carry context with the summary."},
                    "exportBlockPolicy": {
                        "blockReasons": [{"code": "detached-summary-blocked"}]
                    },
                },
                "missingEvidence": ["Observed-versus-predicted dataset not attached."],
                "dossierImprovementSignals": {"advisoryOnly": True, "signals": []},
                "performanceEvidence": {"objectiveMetrics": {"rowCount": 1}},
                "misreadRiskSummary": {
                    "plainLanguageSummary": "Do not overread this bounded report."
                },
                "exportBlockPolicy": {
                    "blockReasons": [{"code": "detached-summary-blocked"}]
                },
                "ngraObjects": {
                    "pbpkQualificationSummary": {
                        "reviewStatus": {"status": "not-declared"},
                        "evidenceBasis": {"basisType": "ivive-linked"},
                        "workflowClaimBoundaries": {
                            "directRegulatoryDoseDerivation": "not-supported"
                        },
                        "cautionSummary": {"highestSeverity": "high"},
                        "exportBlockPolicy": {
                            "blockReasons": [
                                {"code": "direct-regulatory-dose-derivation-blocked"}
                            ]
                        },
                    }
                },
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            local_audit = LocalAuditTrail(tmpdir, enabled=True)
            for audit in (local_audit, s3_audit):
                record_operator_review_signoff(
                    audit,
                    auth=auth,
                    simulation_id="sim-s3-report",
                    scope="export_oecd_report",
                    disposition="acknowledged",
                    rationale="Reviewed against bounded-use caveats.",
                    service_version="0.4.3-test",
                )

            local_payload = deepcopy(base_payload)
            s3_payload = deepcopy(base_payload)

            attach_operator_review_signoff(
                local_payload,
                audit=local_audit,
                tool_name="export_oecd_report",
            )
            attach_operator_review_signoff(
                s3_payload,
                audit=s3_audit,
                tool_name="export_oecd_report",
            )
            attach_trust_surface_contract(local_payload, tool_name="export_oecd_report")
            attach_trust_surface_contract(s3_payload, tool_name="export_oecd_report")

            self.assertEqual(
                local_payload["trustSurfaceContract"],
                s3_payload["trustSurfaceContract"],
            )
            self.assertEqual(
                self._normalized_operator_review_payload(local_payload),
                self._normalized_operator_review_payload(s3_payload),
            )
            self.assertEqual(local_payload["operatorReviewSignoff"]["status"], "recorded")
            self.assertEqual(
                local_payload["report"]["humanReviewSummary"]["operatorReviewSignoff"]["status"],
                "recorded",
            )
            self.assertFalse(local_payload["operatorReviewGovernance"]["supportsOverride"])


if __name__ == "__main__":
    unittest.main()
