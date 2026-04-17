from __future__ import annotations

from copy import deepcopy
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp.session_registry import SessionRegistry  # noqa: E402
from mcp_bridge.adapter.schema import SimulationHandle  # noqa: E402
import mcp_bridge.app as app_module  # noqa: E402
from mcp_bridge.app import create_app  # noqa: E402
from mcp_bridge.audit import LocalAuditTrail  # noqa: E402
from mcp_bridge.config import AppConfig  # noqa: E402
from mcp_bridge.review_signoff import (  # noqa: E402
    attach_operator_review_signoff,
    build_operator_review_governance,
    build_operator_review_signoff_history,
    build_operator_review_signoff_summary,
    record_operator_review_signoff,
    revoke_operator_review_signoff,
)
from mcp_bridge.security.auth import AuthContext  # noqa: E402
from mcp_bridge.security.simple_jwt import jwt  # noqa: E402


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


class _TrustBearingAdapter:
    def __init__(self) -> None:
        self._simulations: dict[str, SimulationHandle] = {}
        self._initialised = False

    def init(self) -> None:
        self._initialised = True

    def shutdown(self) -> None:
        self._initialised = False

    def health(self) -> dict[str, object]:
        return {"status": "initialised" if self._initialised else "stopped"}

    def load_simulation(self, file_path: str, simulation_id: str | None = None) -> SimulationHandle:
        handle = SimulationHandle(
            simulation_id=simulation_id or Path(file_path).stem,
            file_path=file_path,
            metadata={"backend": "mock"},
        )
        self._simulations[handle.simulation_id] = handle
        return handle

    def validate_simulation_request(
        self,
        simulation_id: str,
        *,
        request: dict[str, object] | None = None,
        stage: str | None = None,
    ) -> dict[str, object]:
        handle = self._simulations[simulation_id]
        return {
            "simulationId": handle.simulation_id,
            "backend": "mock",
            "stage": stage,
            "request": dict(request or {}),
            "validation": {
                "status": "passed",
                "warnings": [{"message": "Human review remains required."}],
                "assessment": {
                    "decision": "within-declared-guardrails",
                    "qualificationState": {"state": "research-use"},
                    "missingEvidence": ["Observed-versus-predicted dataset not attached."],
                },
            },
            "profile": {
                "name": Path(handle.file_path).name,
            },
            "capabilities": {
                "validationHook": True,
                "runtimeVerificationHook": True,
                "scientificProfile": True,
            },
            "ngraObjects": {
                "pbpkQualificationSummary": {
                    "reviewStatus": {"status": "not-declared"},
                    "evidenceBasis": {"basisType": "ivive-linked"},
                    "workflowClaimBoundaries": {
                        "directRegulatoryDoseDerivation": "not-supported",
                    },
                    "cautionSummary": {"highestSeverity": "high"},
                    "exportBlockPolicy": {
                        "blockReasons": [{"code": "detached-summary-blocked"}],
                    },
                }
            },
        }


class ReviewSignoffTests(unittest.TestCase):
    @staticmethod
    def _auth_headers(secret: str, role: str) -> dict[str, str]:
        token = jwt.encode(
            {
                "sub": f"review-signoff-{role}",
                "roles": [role],
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
            },
            secret,
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _normalize_signoff_paths(payload: dict[str, object]) -> dict[str, object]:
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

    def test_record_and_revoke_summary_survive_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            audit = LocalAuditTrail(tmpdir, enabled=True)
            auth = AuthContext(subject="operator-a", roles=["operator"], token_id="tok-a")

            record_operator_review_signoff(
                audit,
                auth=auth,
                simulation_id="sim-1",
                scope="export_oecd_report",
                disposition="approved-for-bounded-use",
                rationale="Reviewed against declared context of use and retained bounded-use limits.",
                limitations_accepted=["Adult human reference_compound context only"],
                review_focus=["Context of use", "Population support"],
                service_version="0.4.2-test",
            )
            recorded = build_operator_review_signoff_summary(
                audit,
                simulation_id="sim-1",
                scope="export_oecd_report",
            )
            self.assertEqual(recorded["status"], "recorded")
            self.assertEqual(recorded["disposition"], "approved-for-bounded-use")
            self.assertEqual(recorded["recordedBy"]["subject"], "operator-a")
            self.assertIn("does not change qualification state", recorded["plainLanguageSummary"].lower())

            revoke_operator_review_signoff(
                audit,
                auth=auth,
                simulation_id="sim-1",
                scope="export_oecd_report",
                rationale="The supporting review context changed and the earlier bounded-use sign-off is no longer current.",
                service_version="0.4.2-test",
            )
            revoked = build_operator_review_signoff_summary(
                audit,
                simulation_id="sim-1",
                scope="export_oecd_report",
            )
            self.assertEqual(revoked["status"], "revoked")
            self.assertEqual(revoked["revokedBy"]["subject"], "operator-a")
            self.assertIn("treat the output as unsigned", revoked["plainLanguageSummary"].lower())

            history = build_operator_review_signoff_history(
                audit,
                simulation_id="sim-1",
                scope="export_oecd_report",
                limit=10,
            )
            self.assertEqual(history["status"], "available")
            self.assertEqual(history["latestStatus"], "revoked")
            self.assertEqual(history["returnedEntryCount"], 2)
            self.assertEqual(history["entries"][0]["action"], "revoked")
            self.assertEqual(history["entries"][1]["action"], "recorded")
            self.assertEqual(history["entries"][1]["actor"]["subject"], "operator-a")

    def test_operator_review_governance_explicitly_disables_override_semantics(self) -> None:
        governance = build_operator_review_governance("export_oecd_report")
        self.assertEqual(governance["workflowStatus"], "descriptive-signoff-only")
        self.assertFalse(governance["supportsOverride"])
        self.assertFalse(governance["supportsAdjudication"])
        self.assertFalse(governance["signoffChangesQualificationState"])
        self.assertFalse(governance["signoffConfersDecisionAuthority"])
        self.assertTrue(governance["externalAuthorityRequiredForOverrides"])

    def test_attach_operator_review_signoff_augments_report_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            audit = LocalAuditTrail(tmpdir, enabled=True)
            auth = AuthContext(subject="operator-b", roles=["operator"], token_id="tok-b")
            record_operator_review_signoff(
                audit,
                auth=auth,
                simulation_id="sim-2",
                scope="export_oecd_report",
                disposition="acknowledged",
                rationale="Reviewed for bounded interpretation and traceable human-review context.",
                service_version="0.4.2-test",
            )

            payload = {
                "simulationId": "sim-2",
                "report": {
                    "humanReviewSummary": {
                        "humanReviewRequired": True,
                    }
                },
            }
            attach_operator_review_signoff(
                payload,
                audit=audit,
                tool_name="export_oecd_report",
            )

            self.assertIn("operatorReviewSignoff", payload)
            self.assertIn("operatorReviewGovernance", payload)
            self.assertEqual(payload["operatorReviewSignoff"]["status"], "recorded")
            self.assertFalse(payload["operatorReviewGovernance"]["supportsOverride"])
            self.assertEqual(
                payload["report"]["humanReviewSummary"]["operatorReviewSignoff"]["status"],
                "recorded",
            )
            self.assertFalse(
                payload["report"]["humanReviewSummary"]["operatorReviewGovernance"]["supportsAdjudication"]
            )

    def test_review_signoff_route_requires_operator_confirmation_and_is_viewer_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = AppConfig.model_validate(
                {
                    "environment": "development",
                    "auth_allow_anonymous": False,
                    "auth_dev_secret": "test-dev-secret-must-be-32-bytes",
                    "audit_enabled": True,
                    "audit_storage_path": tmpdir,
                    "service_version": "0.4.2-test",
                }
            )

            with TestClient(create_app(config=config)) as client:
                registry: SessionRegistry = client.app.state.session_registry
                registry.register(
                    SimulationHandle(simulation_id="sim-3", file_path="/tmp/test.pkml")
                )

                viewer_denied = client.post(
                    "/review_signoff",
                    headers=self._auth_headers("test-dev-secret-must-be-32-bytes", "viewer"),
                    json={
                        "simulationId": "sim-3",
                        "scope": "export_oecd_report",
                        "disposition": "approved-for-bounded-use",
                        "rationale": "Reviewed for bounded report use with retained caveats.",
                        "confirm": True,
                    },
                )
                self.assertEqual(viewer_denied.status_code, 403)

                operator_needs_confirmation = client.post(
                    "/review_signoff",
                    headers=self._auth_headers("test-dev-secret-must-be-32-bytes", "operator"),
                    json={
                        "simulationId": "sim-3",
                        "scope": "export_oecd_report",
                        "disposition": "approved-for-bounded-use",
                        "rationale": "Reviewed for bounded report use with retained caveats.",
                    },
                )
                self.assertEqual(operator_needs_confirmation.status_code, 428)

                recorded = client.post(
                    "/review_signoff",
                    headers=self._auth_headers("test-dev-secret-must-be-32-bytes", "operator"),
                    json={
                        "simulationId": "sim-3",
                        "scope": "export_oecd_report",
                        "disposition": "approved-for-bounded-use",
                        "rationale": "Reviewed for bounded report use with retained caveats.",
                        "limitationsAccepted": ["Illustrative example only"],
                        "reviewFocus": ["Claim boundaries"],
                        "confirm": True,
                    },
                )
                self.assertEqual(recorded.status_code, 200)
                summary = recorded.json()["operatorReviewSignoff"]
                self.assertEqual(summary["status"], "recorded")
                self.assertEqual(summary["disposition"], "approved-for-bounded-use")
                governance = recorded.json()["operatorReviewGovernance"]
                self.assertEqual(governance["workflowStatus"], "descriptive-signoff-only")
                self.assertFalse(governance["supportsOverride"])

                viewer_read = client.get(
                    "/review_signoff",
                    headers=self._auth_headers("test-dev-secret-must-be-32-bytes", "viewer"),
                    params={"simulationId": "sim-3", "scope": "export_oecd_report"},
                )
                self.assertEqual(viewer_read.status_code, 200)
                self.assertEqual(
                    viewer_read.json()["operatorReviewSignoff"]["recordedBy"]["subject"],
                    "review-signoff-operator",
                )
                self.assertFalse(viewer_read.json()["operatorReviewGovernance"]["supportsAdjudication"])

                viewer_history = client.get(
                    "/review_signoff/history",
                    headers=self._auth_headers("test-dev-secret-must-be-32-bytes", "viewer"),
                    params={"simulationId": "sim-3", "scope": "export_oecd_report", "limit": 10},
                )
                self.assertEqual(viewer_history.status_code, 200)
                history = viewer_history.json()["operatorReviewSignoffHistory"]
                self.assertEqual(history["returnedEntryCount"], 1)
                self.assertEqual(history["entries"][0]["action"], "recorded")
                self.assertEqual(
                    history["entries"][0]["actor"]["subject"],
                    "review-signoff-operator",
                )
                self.assertFalse(
                    viewer_history.json()["operatorReviewGovernance"]["signoffConfersDecisionAuthority"]
                )

    def test_trust_bearing_call_tool_payload_matches_between_local_and_s3_app_backends(self) -> None:
        auth_secret = "test-dev-secret-must-be-32-bytes"
        simulation_id = "sim-backend-signoff"
        model_root = (WORKSPACE_ROOT / "var" / "models").resolve()
        model_path = model_root / "esqlabs" / "esqlabsR" / "simple.pkml"

        def build_config(**overrides: object) -> AppConfig:
            return AppConfig.model_validate(
                {
                    "environment": "development",
                    "auth_allow_anonymous": False,
                    "auth_dev_secret": auth_secret,
                    "audit_enabled": True,
                    "audit_storage_path": str(WORKSPACE_ROOT / "var" / "test-audit"),
                    "service_version": "0.4.3-test",
                    **overrides,
                }
            )

        def exercise_client(client: TestClient, simulation_id: str) -> dict[str, object]:
            load_response = client.post(
                "/mcp/call_tool",
                headers=self._auth_headers(auth_secret, "operator"),
                json={
                    "tool": "load_simulation",
                    "critical": True,
                    "arguments": {
                        "filePath": str(model_path),
                        "simulationId": simulation_id,
                    },
                },
            )
            self.assertEqual(load_response.status_code, 200)

            signoff_response = client.post(
                "/review_signoff",
                headers=self._auth_headers(auth_secret, "operator"),
                json={
                    "simulationId": simulation_id,
                    "scope": "validate_simulation_request",
                    "disposition": "acknowledged",
                    "rationale": "Reviewed for bounded validation use with explicit caveats retained.",
                    "confirm": True,
                },
            )
            self.assertEqual(signoff_response.status_code, 200)

            validation_response = client.post(
                "/mcp/call_tool",
                headers=self._auth_headers(auth_secret, "operator"),
                json={
                    "tool": "validate_simulation_request",
                    "arguments": {
                        "simulationId": simulation_id,
                        "request": {"route": "iv-infusion", "contextOfUse": "research-only"},
                    },
                },
            )
            self.assertEqual(validation_response.status_code, 200)
            body = validation_response.json()
            self.assertEqual(body["structuredContent"]["operatorReviewSignoff"]["status"], "recorded")
            self.assertEqual(
                body["structuredContent"]["trustSurfaceContract"]["tool"],
                "validate_simulation_request",
            )
            return body["structuredContent"]

        with mock.patch.dict(os.environ, {"ADAPTER_MODEL_PATHS": str(model_root)}, clear=False):
            with tempfile.TemporaryDirectory() as tmpdir:
                local_config = build_config(audit_storage_path=tmpdir)
                with mock.patch.object(app_module, "build_adapter", return_value=_TrustBearingAdapter()):
                    with TestClient(create_app(config=local_config)) as local_client:
                        local_payload = exercise_client(local_client, simulation_id)

            s3_config = build_config(
                audit_storage_backend="s3",
                audit_s3_bucket="test-audit-bucket",
                audit_s3_prefix="test-audit-prefix",
            )
            real_s3_constructor = app_module.S3AuditTrail

            def construct_s3(**kwargs: object):
                return real_s3_constructor(client=_FakeS3Client(), **kwargs)

            with mock.patch.object(app_module, "build_adapter", return_value=_TrustBearingAdapter()):
                with mock.patch.object(app_module, "S3AuditTrail", side_effect=construct_s3):
                    with TestClient(create_app(config=s3_config)) as s3_client:
                        s3_payload = exercise_client(s3_client, simulation_id)

        self.assertEqual(
            local_payload["trustSurfaceContract"],
            s3_payload["trustSurfaceContract"],
        )
        self.assertEqual(
            self._normalize_signoff_paths(local_payload),
            self._normalize_signoff_paths(s3_payload),
        )


if __name__ == "__main__":
    unittest.main()
