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
                uncertainty={"status": "declared", "summary": "Imported uncertainty summary"},
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
            payload["ngraObjects"]["internalExposureEstimate"]["status"],
            "available",
        )
        self.assertEqual(
            payload["ngraObjects"]["berInputBundle"]["status"],
            "ready-for-external-ber-calculation",
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
        self.assertIn(
            "No external point-of-departure reference is attached.",
            payload["ngraObjects"]["berInputBundle"]["blockingReasons"],
        )


if __name__ == "__main__":
    unittest.main()
