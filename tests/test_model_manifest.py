from __future__ import annotations

import json
import importlib.util
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
MODEL_MANIFEST_PATH = SRC_ROOT / "mcp_bridge" / "model_manifest.py"
REFERENCE_WORKSPACE_MODEL = (
    WORKSPACE_ROOT / "var" / "models" / "rxode2" / "reference_compound" / "reference_compound_population_rxode2_model.R"
)
spec = importlib.util.spec_from_file_location("pbpk_packaged_model_manifest", MODEL_MANIFEST_PATH)
if spec is None or spec.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Unable to load packaged module from {MODEL_MANIFEST_PATH}")
module = importlib.util.module_from_spec(spec)
sys.modules.setdefault("pbpk_packaged_model_manifest", module)
spec.loader.exec_module(module)
validate_model_manifest = module.validate_model_manifest


class ModelManifestTests(unittest.TestCase):
    def test_workspace_reference_model_manifest_declares_ngra_fields(self) -> None:
        payload = validate_model_manifest(REFERENCE_WORKSPACE_MODEL)

        manifest = payload["manifest"]
        self.assertEqual(manifest["manifestStatus"], "valid")
        self.assertTrue(payload["curationSummary"]["ngraDeclarationsExplicit"])
        self.assertEqual(payload["curationSummary"]["manifestStatus"], "valid")
        self.assertIn("complete static curation", payload["curationSummary"]["reviewLabel"].lower())
        self.assertIn("misreadRiskSummary", payload["curationSummary"])
        self.assertTrue(payload["curationSummary"]["misreadRiskSummary"]["requiredReading"])
        self.assertIn(
            "static manifest completeness",
            payload["curationSummary"]["misreadRiskSummary"]["riskStatements"][0]["message"].lower(),
        )
        self.assertIn("renderingGuardrails", payload["curationSummary"])
        self.assertFalse(payload["curationSummary"]["renderingGuardrails"]["allowBareReviewLabel"])
        self.assertTrue(payload["curationSummary"]["renderingGuardrails"]["requiresInlineMisreadGuidance"])
        self.assertEqual(
            payload["curationSummary"]["renderingGuardrails"]["actionIfRequiredFieldsMissing"],
            "refuse-rendering",
        )
        self.assertIn("summaryTransportRisk", payload["curationSummary"])
        self.assertEqual(payload["curationSummary"]["summaryTransportRisk"]["riskLevel"], "high")
        self.assertTrue(payload["curationSummary"]["summaryTransportRisk"]["detachedSummaryUnsafe"])
        self.assertIn("regulatoryBenchmarkReadiness", payload["curationSummary"])
        self.assertTrue(payload["curationSummary"]["regulatoryBenchmarkReadiness"]["advisoryOnly"])
        self.assertEqual(
            payload["curationSummary"]["regulatoryBenchmarkReadiness"]["modelResemblance"],
            "research-example",
        )
        self.assertEqual(
            payload["curationSummary"]["regulatoryBenchmarkReadiness"]["overallStatus"],
            "below-benchmark-bar",
        )
        benchmark_readiness = payload["curationSummary"]["regulatoryBenchmarkReadiness"]
        benchmark_source = benchmark_readiness["benchmarkBarSource"]
        self.assertTrue(benchmark_source["sourceManifestSha256"])
        self.assertTrue(benchmark_source["fetchedLockSha256"])
        self.assertIn(
            benchmark_source["sourceResolution"],
            {"direct-lock-files", "audit-manifest-fallback", "packaged-contract-fallback"},
        )
        self.assertTrue(benchmark_readiness["recommendedNextArtifacts"])
        provenance_status = next(
            item
            for item in benchmark_readiness["dimensionStatuses"]
            if item["id"] == "parameterProvenanceDepth"
        )
        self.assertIn("profile.parameterProvenance", provenance_status["evaluatedFrom"])
        self.assertTrue(provenance_status["recommendedNextArtifacts"])
        self.assertIn("tce_tsca_package", provenance_status["benchmarkExampleIds"])
        self.assertTrue(provenance_status["observedManifestFields"])
        self.assertIn("cautionSummary", payload["curationSummary"])
        self.assertEqual(payload["curationSummary"]["cautionSummary"]["highestSeverity"], "high")
        self.assertTrue(payload["curationSummary"]["cautionSummary"]["blockingRecommended"])
        self.assertIn(
            "detached-summary-overread",
            {entry["code"] for entry in payload["curationSummary"]["cautionSummary"]["cautions"]},
        )
        self.assertIn("exportBlockPolicy", payload["curationSummary"])
        self.assertEqual(
            payload["curationSummary"]["exportBlockPolicy"]["defaultAction"],
            "block-lossy-or-decision-leaning-exports",
        )
        self.assertIn(
            "bare-review-label-blocked",
            {entry["code"] for entry in payload["curationSummary"]["exportBlockPolicy"]["blockReasons"]},
        )
        self.assertIn(
            "summaryTransportRisk.plainLanguageSummary",
            payload["curationSummary"]["renderingGuardrails"]["requiredFields"],
        )
        self.assertTrue(manifest["ngraCoverage"]["allExplicitlyDeclared"])
        self.assertEqual(manifest["ngraCoverage"]["declaredCount"], 4)
        self.assertEqual(manifest["ngraCoverage"]["missingDeclarations"], [])
        self.assertEqual(
            manifest["ngraCoverage"]["workflowRole"]["declaredField"],
            "profile.workflowRole",
        )
        codes = {issue["code"] for issue in manifest["issues"]}
        self.assertNotIn("ngra_workflow_role_missing", codes)
        self.assertNotIn("ngra_population_support_missing", codes)
        self.assertNotIn("ngra_evidence_basis_missing", codes)
        self.assertNotIn("ngra_workflow_claim_boundaries_missing", codes)

    def test_pkml_sidecar_manifest_can_reach_qualified_within_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "example.pkml"
            model_path.write_text("<Simulation />", encoding="utf-8")
            sidecar_path = root / "example.profile.json"
            sidecar_path.write_text(
                json.dumps(
                    {
                        "profile": {
                            "contextOfUse": {
                                "scientificPurpose": "Risk assessment",
                                "decisionContext": "Regulatory submission",
                                "regulatoryUse": "regulatory-use",
                            },
                            "applicabilityDomain": {
                                "type": "declared-with-evidence",
                                "qualificationLevel": "regulatory-qualified",
                            },
                            "modelPerformance": {"status": "declared"},
                            "parameterProvenance": {"status": "declared"},
                            "uncertainty": {"status": "declared"},
                            "implementationVerification": {"status": "declared"},
                            "platformQualification": {"status": "declared"},
                            "peerReview": {"status": "declared"},
                        }
                    }
                ),
                encoding="utf-8",
            )

            payload = validate_model_manifest(model_path)

        manifest = payload["manifest"]
        self.assertEqual(manifest["manifestStatus"], "valid")
        self.assertEqual(manifest["profileSource"], "sidecar")
        self.assertEqual(manifest["qualificationState"]["state"], "qualified-within-context")
        self.assertTrue(manifest["qualificationState"]["riskAssessmentReady"])

    def test_pkml_sidecar_manifest_warns_for_missing_ngra_declarations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "example.pkml"
            model_path.write_text("<Simulation />", encoding="utf-8")
            (root / "example.profile.json").write_text(
                json.dumps(
                    {
                        "profile": {
                            "contextOfUse": {
                                "scientificPurpose": "Example PBPK research",
                                "decisionContext": "Internal prioritization",
                                "regulatoryUse": "research-only",
                            },
                            "applicabilityDomain": {
                                "type": "declared-with-runtime-guardrails",
                                "qualificationLevel": "research-use",
                                "species": ["human"],
                                "lifeStage": ["adult"],
                            },
                            "modelPerformance": {"status": "declared"},
                            "parameterProvenance": {"status": "declared"},
                            "uncertainty": {"status": "declared"},
                            "implementationVerification": {"status": "declared"},
                            "platformQualification": {"status": "declared"},
                            "peerReview": {"status": "declared"},
                        }
                    }
                ),
                encoding="utf-8",
            )

            payload = validate_model_manifest(model_path)

        manifest = payload["manifest"]
        self.assertFalse(manifest["ngraCoverage"]["allExplicitlyDeclared"])
        self.assertEqual(manifest["ngraCoverage"]["missingCount"], 4)
        self.assertEqual(
            manifest["ngraCoverage"]["populationSupport"]["scopeHintFields"],
            ["species", "lifeStage"],
        )
        codes = {issue["code"] for issue in manifest["issues"]}
        self.assertIn("ngra_workflow_role_missing", codes)
        self.assertIn("ngra_population_support_missing", codes)
        self.assertIn("ngra_evidence_basis_missing", codes)
        self.assertIn("ngra_workflow_claim_boundaries_missing", codes)

    def test_pkml_without_sidecar_is_marked_exploratory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "example.pkml"
            model_path.write_text("<Simulation />", encoding="utf-8")

            payload = validate_model_manifest(model_path)

        manifest = payload["manifest"]
        self.assertEqual(manifest["manifestStatus"], "missing")
        self.assertEqual(manifest["qualificationState"]["state"], "exploratory")
        self.assertFalse(payload["curationSummary"]["ngraDeclarationsExplicit"])
        self.assertIn(
            "without model-specific static curation",
            payload["curationSummary"]["reviewLabel"].lower(),
        )
        self.assertTrue(payload["curationSummary"]["misreadRiskSummary"]["requiredReading"])
        risk_codes = {
            entry["code"] for entry in payload["curationSummary"]["misreadRiskSummary"]["riskStatements"]
        }
        self.assertIn("implicit-ngra-boundaries", risk_codes)
        self.assertIn("not-risk-assessment-ready", risk_codes)
        self.assertIn("detached-summary-overread", risk_codes)
        self.assertFalse(payload["curationSummary"]["renderingGuardrails"]["allowBareReviewLabel"])
        self.assertEqual(payload["curationSummary"]["renderingGuardrails"]["severity"], "warning")
        self.assertEqual(payload["curationSummary"]["summaryTransportRisk"]["riskLevel"], "high")
        codes = {issue["code"] for issue in manifest["issues"]}
        self.assertIn("sidecar_missing", codes)

    def test_r_manifest_detects_research_use_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "example_model.R"
            model_path.write_text(
                textwrap.dedent(
                    """
                    pbpk_model_profile <- function(...) {
                      list(
                        contextOfUse = list(
                          scientificPurpose = "Kidney PBPK research",
                          decisionContext = "Internal decision support",
                          regulatoryUse = "research-only"
                        ),
                        applicabilityDomain = list(
                          type = "declared-with-runtime-guardrails",
                          qualificationLevel = "research-use"
                        ),
                        modelPerformance = list(status = "limited-internal-evaluation"),
                        parameterProvenance = list(status = "partially-declared"),
                        uncertainty = list(status = "partially-characterized"),
                        implementationVerification = list(status = "basic-internal-checks"),
                        platformQualification = list(status = "runtime-platform-documented"),
                        peerReview = list(status = "not-reported")
                      )
                    }
                    pbpk_validate_request <- function(...) list(ok = TRUE)
                    pbpk_run_simulation <- function(...) list()
                    pbpk_run_population <- function(...) list()
                    pbpk_parameter_table <- function(...) list()
                    pbpk_performance_evidence <- function(...) list()
                    pbpk_uncertainty_evidence <- function(...) list()
                    pbpk_verification_evidence <- function(...) list()
                    pbpk_platform_qualification_evidence <- function(...) list()
                    pbpk_run_verification_checks <- function(...) list()
                    """
                ),
                encoding="utf-8",
            )

            payload = validate_model_manifest(model_path)

        manifest = payload["manifest"]
        self.assertEqual(manifest["manifestStatus"], "valid")
        self.assertEqual(manifest["qualificationLevel"], "research-use")
        self.assertEqual(manifest["qualificationState"]["state"], "research-use")
        self.assertTrue(manifest["hooks"]["validationHook"])
        self.assertTrue(manifest["hooks"]["parameterTable"])
        self.assertTrue(manifest["hooks"]["performanceEvidence"])
        self.assertTrue(manifest["hooks"]["uncertaintyEvidence"])
        self.assertTrue(manifest["hooks"]["verificationEvidence"])
        self.assertTrue(manifest["hooks"]["platformQualificationEvidence"])
        self.assertTrue(manifest["hooks"]["runtimeVerificationHook"])

    def test_r_manifest_detects_explicit_ngra_declarations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "example_model.R"
            model_path.write_text(
                textwrap.dedent(
                    """
                    pbpk_model_profile <- function(...) {
                      list(
                        contextOfUse = list(
                          scientificPurpose = "Kidney PBPK research",
                          decisionContext = "Internal decision support",
                          regulatoryUse = "research-only"
                        ),
                        applicabilityDomain = list(
                          type = "declared-with-runtime-guardrails",
                          qualificationLevel = "research-use"
                        ),
                        modelPerformance = list(status = "limited-internal-evaluation"),
                        parameterProvenance = list(status = "partially-declared"),
                        uncertainty = list(status = "partially-characterized"),
                        implementationVerification = list(status = "basic-internal-checks"),
                        platformQualification = list(status = "runtime-platform-documented"),
                        peerReview = list(status = "not-reported"),
                        workflowRole = list(workflow = "exposure-led-ngra"),
                        populationSupport = list(
                          supportedSpecies = c("human"),
                          extrapolationPolicy = "outside-declared-population-context-requires-human-review"
                        ),
                        evidenceBasis = list(inVivoSupportStatus = "not-declared"),
                        workflowClaimBoundaries = list(
                          directRegulatoryDoseDerivation = "not-supported"
                        )
                      )
                    }
                    pbpk_validate_request <- function(...) list(ok = TRUE)
                    pbpk_run_simulation <- function(...) list()
                    pbpk_run_population <- function(...) list()
                    pbpk_parameter_table <- function(...) list()
                    pbpk_performance_evidence <- function(...) list()
                    pbpk_uncertainty_evidence <- function(...) list()
                    pbpk_verification_evidence <- function(...) list()
                    pbpk_platform_qualification_evidence <- function(...) list()
                    pbpk_run_verification_checks <- function(...) list()
                    """
                ),
                encoding="utf-8",
            )

            payload = validate_model_manifest(model_path)

        manifest = payload["manifest"]
        self.assertTrue(manifest["ngraCoverage"]["allExplicitlyDeclared"])
        self.assertEqual(
            manifest["ngraCoverage"]["workflowRole"]["declaredField"],
            "profile.workflowRole",
        )
        self.assertEqual(
            manifest["ngraCoverage"]["workflowClaimBoundaries"]["declaredField"],
            "profile.workflowClaimBoundaries",
        )
        codes = {issue["code"] for issue in manifest["issues"]}
        self.assertNotIn("ngra_workflow_role_missing", codes)
        self.assertNotIn("ngra_population_support_missing", codes)
        self.assertNotIn("ngra_evidence_basis_missing", codes)
        self.assertNotIn("ngra_workflow_claim_boundaries_missing", codes)

    def test_r_manifest_accepts_performance_sidecar_without_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "example_model.R"
            model_path.write_text(
                textwrap.dedent(
                    """
                    pbpk_model_profile <- function(...) {
                      list(
                        contextOfUse = list(
                          scientificPurpose = "Kidney PBPK research",
                          decisionContext = "Internal decision support",
                          regulatoryUse = "research-only"
                        ),
                        applicabilityDomain = list(
                          type = "declared-with-runtime-guardrails",
                          qualificationLevel = "research-use"
                        ),
                        modelPerformance = list(status = "limited-internal-evaluation"),
                        parameterProvenance = list(status = "partially-declared"),
                        uncertainty = list(status = "partially-characterized"),
                        implementationVerification = list(status = "basic-internal-checks"),
                        platformQualification = list(status = "runtime-platform-documented"),
                        peerReview = list(status = "not-reported")
                      )
                    }
                    pbpk_validate_request <- function(...) list(ok = TRUE)
                    pbpk_run_simulation <- function(...) list()
                    pbpk_run_population <- function(...) list()
                    pbpk_parameter_table <- function(...) list()
                    pbpk_uncertainty_evidence <- function(...) list()
                    pbpk_verification_evidence <- function(...) list()
                    pbpk_platform_qualification_evidence <- function(...) list()
                    pbpk_run_verification_checks <- function(...) list()
                    """
                ),
                encoding="utf-8",
            )
            (root / "example_model.performance.json").write_text(
                json.dumps(
                    {
                        "metadata": {
                            "bundleVersion": "pbpk-performance-evidence.v1",
                            "summary": "Example companion performance bundle",
                        },
                        "profileSupplement": {
                            "predictiveChecks": {
                                "datasetRecords": [
                                    {"dataset": "external-benchmark", "route": "iv"}
                                ],
                                "acceptanceCriteria": [
                                    "GMFE within 2-fold across the benchmark set"
                                ]
                            }
                        },
                        "rows": [
                            {
                                "id": "observed-predicted-cmax",
                                "kind": "observed-vs-predicted",
                                "status": "declared",
                                "observedValue": 1.0,
                                "predictedValue": 1.1,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = validate_model_manifest(model_path)

        manifest = payload["manifest"]
        self.assertEqual(manifest["manifestStatus"], "valid")
        self.assertEqual(manifest["qualificationState"]["state"], "research-use")
        self.assertFalse(manifest["hooks"]["performanceEvidence"])
        self.assertTrue(manifest["hooks"]["performanceEvidenceSidecar"])
        self.assertEqual(
            manifest["supplementalEvidence"]["performanceEvidenceRowCount"],
            1,
        )
        self.assertEqual(
            manifest["supplementalEvidence"]["performanceEvidenceBundleMetadata"]["bundleVersion"],
            "pbpk-performance-evidence.v1",
        )
        self.assertEqual(
            manifest["supplementalEvidence"]["performanceEvidenceProfileSupplementCoverage"]["predictiveDatasetRecordCount"],
            1,
        )
        self.assertEqual(
            manifest["supplementalEvidence"]["performanceEvidenceProfileSupplementCoverage"]["acceptanceCriterionCount"],
            1,
        )
        codes = {issue["code"] for issue in manifest["issues"]}
        self.assertNotIn("performance_evidence_hook_missing", codes)

    def test_r_manifest_accepts_parameter_table_sidecar_without_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "example_model.R"
            model_path.write_text(
                textwrap.dedent(
                    """
                    pbpk_model_profile <- function(...) {
                      list(
                        contextOfUse = list(
                          scientificPurpose = "Kidney PBPK research",
                          decisionContext = "Internal decision support",
                          regulatoryUse = "research-only"
                        ),
                        applicabilityDomain = list(
                          type = "declared-with-runtime-guardrails",
                          qualificationLevel = "research-use"
                        ),
                        modelPerformance = list(status = "limited-internal-evaluation"),
                        parameterProvenance = list(status = "partially-declared"),
                        uncertainty = list(status = "partially-characterized"),
                        implementationVerification = list(status = "basic-internal-checks"),
                        platformQualification = list(status = "runtime-platform-documented"),
                        peerReview = list(status = "not-reported")
                      )
                    }
                    pbpk_validate_request <- function(...) list(ok = TRUE)
                    pbpk_run_simulation <- function(...) list()
                    pbpk_run_population <- function(...) list()
                    pbpk_performance_evidence <- function(...) list()
                    pbpk_uncertainty_evidence <- function(...) list()
                    pbpk_verification_evidence <- function(...) list()
                    pbpk_platform_qualification_evidence <- function(...) list()
                    pbpk_run_verification_checks <- function(...) list()
                    """
                ),
                encoding="utf-8",
            )
            (root / "example_model.parameters.json").write_text(
                json.dumps(
                    {
                        "metadata": {
                            "bundleVersion": "pbpk-parameter-table.v1",
                            "summary": "Example companion parameter table",
                        },
                        "rows": [
                            {
                                "path": "Physiology|BodyWeight",
                                "unit": "kg",
                                "source": "Example physiology defaults",
                                "sourceCitation": "Doe et al. 2024",
                                "distribution": "lognormal",
                                "mean": 70,
                                "sd": 10,
                                "experimentalConditions": ["adult healthy volunteers"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = validate_model_manifest(model_path)

        manifest = payload["manifest"]
        self.assertEqual(manifest["manifestStatus"], "valid")
        self.assertEqual(manifest["qualificationState"]["state"], "research-use")
        self.assertFalse(manifest["hooks"]["parameterTable"])
        self.assertTrue(manifest["hooks"]["parameterTableSidecar"])
        self.assertEqual(
            manifest["supplementalEvidence"]["parameterTableRowCount"],
            1,
        )
        self.assertEqual(
            manifest["supplementalEvidence"]["parameterTableBundleMetadata"]["bundleVersion"],
            "pbpk-parameter-table.v1",
        )
        codes = {issue["code"] for issue in manifest["issues"]}
        self.assertNotIn("parameter_table_hook_missing", codes)

    def test_r_manifest_warns_for_malformed_parameter_table_sidecar_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "example_model.R"
            model_path.write_text(
                textwrap.dedent(
                    """
                    pbpk_model_profile <- function(...) {
                      list(
                        contextOfUse = list(
                          scientificPurpose = "Kidney PBPK research",
                          decisionContext = "Internal decision support",
                          regulatoryUse = "research-only"
                        ),
                        applicabilityDomain = list(
                          type = "declared-with-runtime-guardrails",
                          qualificationLevel = "research-use"
                        ),
                        modelPerformance = list(status = "limited-internal-evaluation"),
                        parameterProvenance = list(status = "partially-declared"),
                        uncertainty = list(status = "partially-characterized"),
                        implementationVerification = list(status = "basic-internal-checks"),
                        platformQualification = list(status = "runtime-platform-documented"),
                        peerReview = list(status = "not-reported")
                      )
                    }
                    pbpk_validate_request <- function(...) list(ok = TRUE)
                    pbpk_run_simulation <- function(...) list()
                    pbpk_run_population <- function(...) list()
                    pbpk_performance_evidence <- function(...) list()
                    pbpk_uncertainty_evidence <- function(...) list()
                    pbpk_verification_evidence <- function(...) list()
                    pbpk_platform_qualification_evidence <- function(...) list()
                    pbpk_run_verification_checks <- function(...) list()
                    """
                ),
                encoding="utf-8",
            )
            (root / "example_model.parameters.json").write_text(
                json.dumps(
                    {
                        "metadata": {},
                        "rows": [
                            {
                                "path": "Physiology|BodyWeight",
                                "distribution": "lognormal",
                                "sourceType": "in-vitro-estimate",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = validate_model_manifest(model_path)

        manifest = payload["manifest"]
        codes = {issue["code"] for issue in manifest["issues"]}
        self.assertIn("parameter_table_bundle_version_missing", codes)
        self.assertIn("parameter_table_bundle_summary_missing", codes)
        self.assertIn("parameter_row_source_missing", codes)
        self.assertIn("parameter_row_distribution_details_missing", codes)
        self.assertIn("parameter_row_conditions_missing", codes)

    def test_r_manifest_warns_for_malformed_performance_sidecar_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "example_model.R"
            model_path.write_text(
                textwrap.dedent(
                    """
                    pbpk_model_profile <- function(...) {
                      list(
                        contextOfUse = list(
                          scientificPurpose = "Kidney PBPK research",
                          decisionContext = "Internal decision support",
                          regulatoryUse = "research-only"
                        ),
                        applicabilityDomain = list(
                          type = "declared-with-runtime-guardrails",
                          qualificationLevel = "research-use"
                        ),
                        modelPerformance = list(status = "limited-internal-evaluation"),
                        parameterProvenance = list(status = "partially-declared"),
                        uncertainty = list(status = "partially-characterized"),
                        implementationVerification = list(status = "basic-internal-checks"),
                        platformQualification = list(status = "runtime-platform-documented"),
                        peerReview = list(status = "not-reported")
                      )
                    }
                    pbpk_validate_request <- function(...) list(ok = TRUE)
                    pbpk_run_simulation <- function(...) list()
                    pbpk_run_population <- function(...) list()
                    pbpk_parameter_table <- function(...) list()
                    pbpk_uncertainty_evidence <- function(...) list()
                    pbpk_verification_evidence <- function(...) list()
                    pbpk_platform_qualification_evidence <- function(...) list()
                    pbpk_run_verification_checks <- function(...) list()
                    """
                ),
                encoding="utf-8",
            )
            (root / "example_model.performance.json").write_text(
                json.dumps(
                    {
                        "metadata": {},
                        "rows": [
                            {
                                "id": "bad-obs-pred-row",
                                "evidenceClass": "observed-vs-predicted",
                                "status": "declared"
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = validate_model_manifest(model_path)

        manifest = payload["manifest"]
        codes = {issue["code"] for issue in manifest["issues"]}
        self.assertIn("performance_bundle_version_missing", codes)
        self.assertIn("performance_bundle_summary_missing", codes)
        self.assertIn("performance_row_observed_missing", codes)
        self.assertIn("performance_row_predicted_missing", codes)
        self.assertIn("performance_row_dataset_missing", codes)
        self.assertIn("performance_row_acceptance_missing", codes)

    def test_r_manifest_warns_for_performance_traceability_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "example_model.R"
            model_path.write_text(
                textwrap.dedent(
                    """
                    pbpk_model_profile <- function(...) {
                      list(
                        contextOfUse = list(
                          scientificPurpose = "Kidney PBPK research",
                          decisionContext = "Internal decision support",
                          regulatoryUse = "research-only"
                        ),
                        applicabilityDomain = list(
                          type = "declared-with-runtime-guardrails",
                          qualificationLevel = "research-use"
                        ),
                        modelPerformance = list(status = "limited-internal-evaluation"),
                        parameterProvenance = list(status = "partially-declared"),
                        uncertainty = list(status = "partially-characterized"),
                        implementationVerification = list(status = "basic-internal-checks"),
                        platformQualification = list(status = "runtime-platform-documented"),
                        peerReview = list(status = "not-reported")
                      )
                    }
                    pbpk_validate_request <- function(...) list(ok = TRUE)
                    pbpk_run_simulation <- function(...) list()
                    pbpk_run_population <- function(...) list()
                    pbpk_parameter_table <- function(...) list()
                    pbpk_uncertainty_evidence <- function(...) list()
                    pbpk_verification_evidence <- function(...) list()
                    pbpk_platform_qualification_evidence <- function(...) list()
                    pbpk_run_verification_checks <- function(...) list()
                    """
                ),
                encoding="utf-8",
            )
            (root / "example_model.performance.json").write_text(
                json.dumps(
                    {
                        "metadata": {
                            "bundleVersion": "pbpk-performance-evidence.v1",
                            "summary": "Traceability mismatch bundle",
                        },
                        "profileSupplement": {
                            "predictiveChecks": {
                                "datasetRecords": [
                                    {"dataset": "declared-benchmark", "route": "iv"}
                                ],
                                "acceptanceCriteria": [
                                    "GMFE within 2-fold across the benchmark set"
                                ],
                            },
                            "targetOutputs": ["Plasma|Compound|Concentration"],
                        },
                        "rows": [
                            {
                                "id": "mismatched-predictive-row",
                                "kind": "predictive-dataset",
                                "status": "declared",
                                "dataset": "undeclared-benchmark",
                                "targetOutput": "Kidney|Compound|Concentration",
                                "acceptanceCriterion": "AUC within 10% of observed benchmark",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = validate_model_manifest(model_path)

        codes = {issue["code"] for issue in payload["manifest"]["issues"]}
        self.assertIn("performance_row_dataset_traceability_missing", codes)
        self.assertIn("performance_row_target_output_traceability_missing", codes)
        self.assertIn("performance_row_acceptance_traceability_missing", codes)

    def test_r_manifest_accepts_uncertainty_sidecar_without_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "example_model.R"
            model_path.write_text(
                textwrap.dedent(
                    """
                    pbpk_model_profile <- function(...) {
                      list(
                        contextOfUse = list(
                          scientificPurpose = "Kidney PBPK research",
                          decisionContext = "Internal decision support",
                          regulatoryUse = "research-only"
                        ),
                        applicabilityDomain = list(
                          type = "declared-with-runtime-guardrails",
                          qualificationLevel = "research-use"
                        ),
                        modelPerformance = list(status = "limited-internal-evaluation"),
                        parameterProvenance = list(status = "partially-declared"),
                        uncertainty = list(status = "partially-characterized"),
                        implementationVerification = list(status = "basic-internal-checks"),
                        platformQualification = list(status = "runtime-platform-documented"),
                        peerReview = list(status = "not-reported")
                      )
                    }
                    pbpk_validate_request <- function(...) list(ok = TRUE)
                    pbpk_run_simulation <- function(...) list()
                    pbpk_run_population <- function(...) list()
                    pbpk_parameter_table <- function(...) list()
                    pbpk_performance_evidence <- function(...) list()
                    pbpk_verification_evidence <- function(...) list()
                    pbpk_platform_qualification_evidence <- function(...) list()
                    pbpk_run_verification_checks <- function(...) list()
                    """
                ),
                encoding="utf-8",
            )
            (root / "example_model.uncertainty.json").write_text(
                json.dumps(
                    {
                        "metadata": {
                            "bundleVersion": "pbpk-uncertainty-evidence.v1",
                            "summary": "Example companion uncertainty bundle",
                        },
                        "rows": [
                            {
                                "id": "local-sensitivity-summary",
                                "kind": "sensitivity-analysis",
                                "status": "declared",
                                "method": "one-at-a-time",
                                "metric": "Cmax",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = validate_model_manifest(model_path)

        manifest = payload["manifest"]
        self.assertEqual(manifest["manifestStatus"], "valid")
        self.assertEqual(manifest["qualificationState"]["state"], "research-use")
        self.assertFalse(manifest["hooks"]["uncertaintyEvidence"])
        self.assertTrue(manifest["hooks"]["uncertaintyEvidenceSidecar"])
        self.assertEqual(
            manifest["supplementalEvidence"]["uncertaintyEvidenceRowCount"],
            1,
        )
        self.assertEqual(
            manifest["supplementalEvidence"]["uncertaintyEvidenceBundleMetadata"]["bundleVersion"],
            "pbpk-uncertainty-evidence.v1",
        )
        codes = {issue["code"] for issue in manifest["issues"]}
        self.assertNotIn("uncertainty_evidence_hook_missing", codes)

    def test_r_manifest_warns_for_malformed_uncertainty_sidecar_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "example_model.R"
            model_path.write_text(
                textwrap.dedent(
                    """
                    pbpk_model_profile <- function(...) {
                      list(
                        contextOfUse = list(
                          scientificPurpose = "Kidney PBPK research",
                          decisionContext = "Internal decision support",
                          regulatoryUse = "research-only"
                        ),
                        applicabilityDomain = list(
                          type = "declared-with-runtime-guardrails",
                          qualificationLevel = "research-use"
                        ),
                        modelPerformance = list(status = "limited-internal-evaluation"),
                        parameterProvenance = list(status = "partially-declared"),
                        uncertainty = list(status = "partially-characterized"),
                        implementationVerification = list(status = "basic-internal-checks"),
                        platformQualification = list(status = "runtime-platform-documented"),
                        peerReview = list(status = "not-reported")
                      )
                    }
                    pbpk_validate_request <- function(...) list(ok = TRUE)
                    pbpk_run_simulation <- function(...) list()
                    pbpk_run_population <- function(...) list()
                    pbpk_parameter_table <- function(...) list()
                    pbpk_performance_evidence <- function(...) list()
                    pbpk_verification_evidence <- function(...) list()
                    pbpk_platform_qualification_evidence <- function(...) list()
                    pbpk_run_verification_checks <- function(...) list()
                    """
                ),
                encoding="utf-8",
            )
            (root / "example_model.uncertainty.json").write_text(
                json.dumps(
                    {
                        "metadata": {},
                        "rows": [
                            {
                                "id": "bad-sensitivity-row",
                                "kind": "sensitivity-analysis",
                                "status": "declared"
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = validate_model_manifest(model_path)

        manifest = payload["manifest"]
        codes = {issue["code"] for issue in manifest["issues"]}
        self.assertIn("uncertainty_bundle_version_missing", codes)
        self.assertIn("uncertainty_bundle_summary_missing", codes)
        self.assertIn("uncertainty_row_summary_missing", codes)
        self.assertIn("uncertainty_row_scope_missing", codes)

    def test_r_manifest_warns_for_unquantified_variability_propagation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "example_model.R"
            model_path.write_text(
                textwrap.dedent(
                    """
                    pbpk_model_profile <- function(...) {
                      list(
                        contextOfUse = list(
                          scientificPurpose = "Kidney PBPK research",
                          decisionContext = "Internal decision support",
                          regulatoryUse = "research-only"
                        ),
                        applicabilityDomain = list(
                          type = "declared-with-runtime-guardrails",
                          qualificationLevel = "research-use"
                        ),
                        modelPerformance = list(status = "limited-internal-evaluation"),
                        parameterProvenance = list(status = "partially-declared"),
                        uncertainty = list(status = "partially-characterized"),
                        implementationVerification = list(status = "basic-internal-checks"),
                        platformQualification = list(status = "runtime-platform-documented"),
                        peerReview = list(status = "not-reported")
                      )
                    }
                    pbpk_validate_request <- function(...) list(ok = TRUE)
                    pbpk_run_simulation <- function(...) list()
                    pbpk_run_population <- function(...) list()
                    pbpk_parameter_table <- function(...) list()
                    pbpk_performance_evidence <- function(...) list()
                    pbpk_verification_evidence <- function(...) list()
                    pbpk_platform_qualification_evidence <- function(...) list()
                    pbpk_run_verification_checks <- function(...) list()
                    """
                ),
                encoding="utf-8",
            )
            (root / "example_model.uncertainty.json").write_text(
                json.dumps(
                    {
                        "metadata": {
                            "bundleVersion": "pbpk-uncertainty-evidence.v1",
                            "summary": "Unquantified variability propagation",
                        },
                        "rows": [
                            {
                                "id": "bad-variability-propagation-row",
                                "kind": "variability-propagation",
                                "status": "declared",
                                "method": "population simulation",
                                "metric": "cmax",
                                "targetOutput": "Plasma|Compound|Concentration",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = validate_model_manifest(model_path)

        codes = {issue["code"] for issue in payload["manifest"]["issues"]}
        self.assertIn("uncertainty_row_quantitative_signal_missing", codes)

    def test_r_without_profile_hook_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "broken_model.R"
            model_path.write_text("pbpk_run_simulation <- function(...) list()", encoding="utf-8")

            payload = validate_model_manifest(model_path)

        manifest = payload["manifest"]
        self.assertEqual(manifest["manifestStatus"], "missing")
        self.assertEqual(manifest["qualificationState"]["state"], "exploratory")
        codes = {issue["code"] for issue in manifest["issues"]}
        self.assertIn("profile_hook_missing", codes)


if __name__ == "__main__":
    unittest.main()
