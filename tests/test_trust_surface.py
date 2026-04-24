from __future__ import annotations

import sys
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_bridge.trust_surface import build_trust_surface_contract  # noqa: E402


class TrustSurfaceTests(unittest.TestCase):
    def test_builds_curation_contract_for_validate_model_manifest(self) -> None:
        payload = {
            "curationSummary": {
                "reviewLabel": "Research use",
                "humanSummary": "Research-use only.",
                "regulatoryBenchmarkReadiness": {
                    "overallStatus": "below-benchmark-bar",
                    "advisoryOnly": True,
                },
                "cautionSummary": {"highestSeverity": "high"},
                "summaryTransportRisk": {"riskLevel": "high"},
                "misreadRiskSummary": {"plainLanguageSummary": "Do not overread."},
                "exportBlockPolicy": {
                    "blockReasons": [
                        {"code": "detached-summary-blocked"},
                        {"code": "decision-readiness-overclaim-blocked"},
                    ]
                },
                "renderingGuardrails": {"allowBareReviewLabel": False},
            }
        }

        contract = build_trust_surface_contract(payload, tool_name="validate_model_manifest")

        self.assertIsNotNone(contract)
        self.assertEqual(contract["tool"], "validate_model_manifest")
        self.assertEqual(contract["surfaceCount"], 1)
        surface = contract["surfaces"][0]
        self.assertEqual(surface["surfacePath"], "curationSummary")
        self.assertIn(
            "curationSummary.regulatoryBenchmarkReadiness",
            surface["requiredAdjacentPaths"],
        )
        self.assertIn(
            "curationSummary.regulatoryBenchmarkReadiness.prioritizedGaps",
            surface["requiredAdjacentPaths"],
        )
        self.assertIn("curationSummary.cautionSummary", surface["requiredAdjacentPaths"])
        self.assertIn("detached-summary-blocked", surface["primaryBlockReasonCodes"])

    def test_builds_report_contract_for_export(self) -> None:
        payload = {
            "report": {
                "humanReviewSummary": {
                    "exportBlockPolicy": {
                        "blockReasons": [
                            {"code": "detached-summary-blocked"},
                        ]
                    },
                    "summaryTransportRisk": {"plainLanguageSummary": "Detached summaries can overread."},
                },
                "missingEvidence": ["Predictive dataset not attached."],
                "dossierImprovementSignals": {"advisoryOnly": True},
                "performanceEvidence": {"objectiveMetrics": {"rowCount": 1}},
                "ngraObjects": {
                    "pbpkQualificationSummary": {
                        "exportBlockPolicy": {
                            "blockReasons": [
                                {"code": "direct-regulatory-dose-derivation-blocked"},
                            ]
                        }
                    }
                },
            }
        }

        contract = build_trust_surface_contract(payload, tool_name="export_oecd_report")

        self.assertIsNotNone(contract)
        self.assertEqual(contract["surfaceCount"], 2)
        surface_paths = {surface["surfacePath"] for surface in contract["surfaces"]}
        self.assertIn("report.humanReviewSummary", surface_paths)
        self.assertIn("report.ngraObjects.pbpkQualificationSummary", surface_paths)
        human_surface = next(surface for surface in contract["surfaces"] if surface["surfacePath"] == "report.humanReviewSummary")
        self.assertIn("report.dossierImprovementSignals", human_surface["requiredAdjacentPaths"])
        self.assertIn("report.performanceEvidence.objectiveMetrics", human_surface["requiredAdjacentPaths"])

    def test_builds_verification_contract_for_runtime_checks(self) -> None:
        payload = {
            "qualificationState": {
                "state": "research-use",
                "reviewStatus": {"status": "not-declared"},
            },
            "profile": {
                "workflowRole": {"role": "exposure-led-support"},
                "populationSupport": {"supportedSpecies": "human"},
                "evidenceBasis": {"basisType": "nam-ivive-only"},
                "workflowClaimBoundaries": {
                    "directRegulatoryDoseDerivation": "not-supported",
                },
            },
            "evidenceBasis": {"basisType": "ivive-linked"},
            "workflowClaimBoundaries": {"directRegulatoryDoseDerivation": "not-supported"},
            "missingEvidence": ["Predictive evaluation dataset not attached."],
            "dossierImprovementSignals": {"advisoryOnly": True},
            "warnings": ["Human review required."],
            "operatorReviewSignoff": {"status": "not-recorded"},
            "operatorReviewGovernance": {"supportsOverride": False},
        }

        contract = build_trust_surface_contract(payload, tool_name="run_verification_checks")

        self.assertIsNotNone(contract)
        self.assertEqual(contract["tool"], "run_verification_checks")
        self.assertEqual(contract["surfaceCount"], 1)
        surface = contract["surfaces"][0]
        self.assertEqual(surface["surfacePath"], "qualificationState")
        self.assertIn("evidenceBasis", surface["requiredAdjacentPaths"])
        self.assertIn("workflowClaimBoundaries", surface["requiredAdjacentPaths"])
        self.assertIn("missingEvidence", surface["requiredAdjacentPaths"])
        self.assertIn("dossierImprovementSignals", surface["requiredAdjacentPaths"])
        self.assertIn("profile.workflowRole", surface["requiredAdjacentPaths"])
        self.assertIn("operatorReviewSignoff", surface["requiredAdjacentPaths"])
        self.assertIn("operatorReviewGovernance", surface["requiredAdjacentPaths"])
        self.assertEqual(surface["operatorReviewGovernancePath"], "operatorReviewGovernance")

    def test_builds_validation_contract_with_missing_evidence_and_advisory_signals(self) -> None:
        payload = {
            "qualificationState": {"state": "research-use"},
            "evidenceBasis": {"basisType": "ivive-linked"},
            "workflowClaimBoundaries": {"directRegulatoryDoseDerivation": "not-supported"},
            "cautionSummary": {"highestSeverity": "high"},
            "missingEvidence": ["Predictive dataset not attached."],
            "dossierImprovementSignals": {"advisoryOnly": True},
            "warnings": ["Keep context attached."],
            "operatorReviewSignoff": {"status": "not-recorded"},
            "operatorReviewGovernance": {"supportsOverride": False},
            "ngraObjects": {
                "pbpkQualificationSummary": {
                    "reviewStatus": {"status": "not-declared"},
                    "evidenceBasis": {"basisType": "ivive-linked"},
                    "workflowClaimBoundaries": {"directRegulatoryDoseDerivation": "not-supported"},
                    "cautionSummary": {"highestSeverity": "high"},
                    "exportBlockPolicy": {"blockReasons": [{"code": "detached-summary-blocked"}]},
                }
            },
        }

        contract = build_trust_surface_contract(payload, tool_name="validate_simulation_request")

        self.assertIsNotNone(contract)
        surface = contract["surfaces"][0]
        self.assertEqual(surface["surfacePath"], "ngraObjects.pbpkQualificationSummary")
        self.assertIn("evidenceBasis", surface["requiredAdjacentPaths"])
        self.assertIn("workflowClaimBoundaries", surface["requiredAdjacentPaths"])
        self.assertIn("missingEvidence", surface["requiredAdjacentPaths"])
        self.assertIn("warnings", surface["requiredAdjacentPaths"])
        self.assertIn("dossierImprovementSignals", surface["requiredAdjacentPaths"])


if __name__ == "__main__":
    unittest.main()
