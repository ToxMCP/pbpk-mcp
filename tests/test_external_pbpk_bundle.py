from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
PATCH_ROOT = WORKSPACE_ROOT / "patches"
TOOL_PATH = PATCH_ROOT / "mcp" / "tools" / "ingest_external_pbpk_bundle.py"
HAS_PYDANTIC = importlib.util.find_spec("pydantic") is not None

if HAS_PYDANTIC:
    spec = importlib.util.spec_from_file_location("pbpk_patch_external_bundle", TOOL_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - import guard
        raise RuntimeError(f"Unable to load patch module from {TOOL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("pbpk_patch_external_bundle", module)
    spec.loader.exec_module(module)
    IngestExternalPbpkBundleRequest = module.IngestExternalPbpkBundleRequest
    ingest_external_pbpk_bundle = module.ingest_external_pbpk_bundle


@unittest.skipUnless(HAS_PYDANTIC, "pydantic is required for external PBPK bundle tool tests")
class ExternalPbpkBundleTests(unittest.TestCase):
    def test_ingest_external_pbpk_bundle_returns_ready_ber_handoff(self) -> None:
        payload = ingest_external_pbpk_bundle(
            IngestExternalPbpkBundleRequest(
                sourcePlatform="GastroPlus",
                sourceVersion="10.1",
                modelName="Example external PBPK",
                assessmentContext={
                    "contextOfUse": {"regulatoryUse": "research-only"},
                    "scientificPurpose": "Tier 1 internal exposure screening",
                    "decisionContext": "BER handoff",
                    "domain": {"species": "human", "route": "oral", "population": "adult"},
                    "targetOutput": "Plasma|Parent|Concentration",
                },
                internalExposure={
                    "targetOutput": "Plasma|Parent|Concentration",
                    "species": "human",
                    "route": "oral",
                    "population": "adult",
                    "metrics": {
                        "cmax": {"value": 3.2, "unit": "uM"},
                        "tmax": {"value": 1.5},
                        "auc0Tlast": {"value": 10.5, "unit": "uM*h"},
                    },
                },
                qualification={
                    "evidenceLevel": "L2",
                    "verificationStatus": "checked",
                    "platformClass": "commercial",
                },
                uncertainty={
                    "status": "declared",
                    "summary": "Imported uncertainty summary",
                    "evidenceRows": [
                        {
                            "kind": "variability-propagation",
                            "status": "declared",
                            "method": "population simulation",
                            "metric": "cmax",
                            "targetOutput": "Plasma|Parent|Concentration",
                            "lowerBound": 2.7,
                            "upperBound": 3.8,
                        },
                        {
                            "kind": "residual-uncertainty",
                            "status": "declared",
                            "summary": "Residual external-dose mapping uncertainty",
                        },
                    ],
                },
                uncertaintyRegister={
                    "ref": "unc-reg-001",
                    "source": "assessment-workbench",
                    "scope": "tier-1-systemic",
                },
                pod={
                    "ref": "pod-001",
                    "source": "httr-benchmark",
                    "metric": "cmax",
                    "unit": "uM",
                    "basis": "true-dose-adjusted",
                },
                trueDoseAdjustment={
                    "applied": True,
                    "basis": "free-concentration",
                    "summary": "Normalized to free concentration",
                },
                comparisonMetric="cmax",
            )
        ).model_dump(by_alias=True)

        self.assertEqual(payload["tool"], "ingest_external_pbpk_bundle")
        self.assertEqual(payload["contractVersion"], "pbpk-mcp.v1")
        self.assertEqual(payload["externalRun"]["sourcePlatform"], "GastroPlus")
        self.assertEqual(
            payload["ngraObjects"]["assessmentContext"]["contextOfUse"]["regulatoryUse"]["effective"],
            "research-only",
        )
        self.assertEqual(
            payload["ngraObjects"]["pbpkQualificationSummary"]["state"],
            "research-use",
        )
        self.assertEqual(
            payload["ngraObjects"]["pbpkQualificationSummary"]["assessmentBoundary"],
            "external-pbpk-normalization-only",
        )
        self.assertTrue(
            payload["ngraObjects"]["pbpkQualificationSummary"]["supports"]["externalImportNormalization"],
        )
        self.assertEqual(
            payload["ngraObjects"]["internalExposureEstimate"]["status"],
            "available",
        )
        self.assertEqual(
            payload["ngraObjects"]["pointOfDepartureReference"]["status"],
            "attached-external-reference",
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintySummary"]["decisionBoundary"],
            "no-ngra-decision-policy",
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintySummary"]["semanticCoverage"]["overallQuantificationStatus"],
            "partially-quantified",
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintySummary"]["semanticCoverage"]["quantifiedRowCount"],
            1,
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintySummary"]["semanticCoverage"]["declaredOnlyRowCount"],
            1,
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintySummary"]["semanticCoverage"]["variabilityType"],
            "aleatoric-or-population-variability",
        )
        self.assertIn(
            "variability",
            payload["ngraObjects"]["uncertaintySummary"]["semanticCoverage"]["quantifiedComponents"],
        )
        self.assertIn(
            "residual-uncertainty",
            payload["ngraObjects"]["uncertaintySummary"]["semanticCoverage"]["declaredOnlyComponents"],
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintyHandoff"]["status"],
            "ready-for-cross-domain-uncertainty-synthesis",
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintyHandoff"]["decisionOwner"],
            "external-orchestrator",
        )
        self.assertTrue(
            payload["ngraObjects"]["uncertaintyHandoff"]["supports"]["pbpkUncertaintySummaryAttached"],
        )
        self.assertTrue(
            payload["ngraObjects"]["uncertaintyHandoff"]["supports"]["typedUncertaintySemanticsAttached"],
        )
        self.assertTrue(
            payload["ngraObjects"]["uncertaintyHandoff"]["supports"]["quantifiedPbpkVariability"],
        )
        self.assertFalse(
            payload["ngraObjects"]["uncertaintyHandoff"]["supports"]["quantifiedPbpkResidualUncertainty"],
        )
        self.assertTrue(
            payload["ngraObjects"]["uncertaintyHandoff"]["supports"]["uncertaintyRegisterReferenceAttached"],
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintyRegisterReference"]["status"],
            "attached-external-reference",
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintyHandoff"]["uncertaintyRegisterReferenceRef"],
            "gastroplus-uncertainty-register-reference",
        )
        self.assertEqual(
            payload["ngraObjects"]["berInputBundle"]["status"],
            "ready-for-external-ber-calculation",
        )
        self.assertEqual(
            payload["ngraObjects"]["berInputBundle"]["pointOfDepartureReferenceRef"],
            "gastroplus-point-of-departure-reference",
        )
        self.assertEqual(
            payload["ngraObjects"]["berInputBundle"]["decisionOwner"],
            "external-orchestrator",
        )
        self.assertEqual(
            payload["ngraObjects"]["berInputBundle"]["internalExposureMetric"]["value"],
            3.2,
        )
        self.assertEqual(payload["ngraObjects"]["berInputBundle"]["blockingReasons"], [])

    def test_ingest_external_pbpk_bundle_stays_incomplete_without_pod(self) -> None:
        payload = ingest_external_pbpk_bundle(
            IngestExternalPbpkBundleRequest(
                sourcePlatform="Simcyp",
                internalExposure={
                    "metrics": {"cmax": {"value": 1.2, "unit": "uM"}},
                },
            )
        ).model_dump(by_alias=True)

        self.assertEqual(
            payload["ngraObjects"]["internalExposureEstimate"]["status"],
            "available",
        )
        self.assertEqual(
            payload["ngraObjects"]["berInputBundle"]["status"],
            "incomplete",
        )
        self.assertEqual(
            payload["ngraObjects"]["pointOfDepartureReference"]["status"],
            "not-attached",
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintyHandoff"]["status"],
            "partial-pbpk-uncertainty-handoff",
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintySummary"]["semanticCoverage"]["overallQuantificationStatus"],
            "unreported",
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintySummary"]["semanticCoverage"]["quantifiedRowCount"],
            0,
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintyRegisterReference"]["status"],
            "not-attached",
        )
        self.assertIn(
            "No structured PBPK uncertainty summary is attached.",
            payload["ngraObjects"]["uncertaintyHandoff"]["blockingReasons"],
        )
        self.assertIn(
            "external cross-domain uncertainty register reference",
            payload["ngraObjects"]["uncertaintyHandoff"]["requiredExternalInputs"],
        )
        self.assertIn(
            "BER calculation and decision policy outside PBPK MCP",
            payload["ngraObjects"]["berInputBundle"]["requiredExternalInputs"],
        )
        self.assertIn(
            "No external point-of-departure reference is attached.",
            payload["ngraObjects"]["berInputBundle"]["blockingReasons"],
        )


if __name__ == "__main__":
    unittest.main()
