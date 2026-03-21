from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = WORKSPACE_ROOT / "scripts" / "ospsuite_bridge.R"
CISPLATIN_MODEL_PATH = WORKSPACE_ROOT / "cisplatin_models" / "cisplatin_population_rxode2_model.R"


def has_r_package(package_name: str) -> bool:
    if not shutil.which("Rscript"):
        return False
    completed = subprocess.run(
        ["Rscript", "-e", f"quit(status = if (requireNamespace('{package_name}', quietly = TRUE)) 0 else 1)"],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def run_r_json(r_body: str):
    script = textwrap.dedent(
        f"""
        source({json.dumps(str(BRIDGE_PATH))})
        payload <- local({{
        {textwrap.indent(r_body.strip(), "  ")}
        }})
        cat(jsonlite::toJSON(payload, auto_unbox = TRUE, null = "null"))
        """
    )
    completed = subprocess.run(
        ["Rscript", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout.strip() or "null")


@unittest.skipUnless(shutil.which("Rscript"), "Rscript is required for bridge-level R tests")
class OecdBridgeTests(unittest.TestCase):
    def test_normalize_model_profile_coerces_scalar_sections(self) -> None:
        payload = run_r_json(
            """
            normalize_model_profile(
              list(
                contextOfUse = "Research-only summary",
                applicabilityDomain = "Adult human IV use",
                modelPerformance = "No bundled predictivity dossier",
                parameterProvenance = "Parameter table declared in module",
                uncertainty = "Uncertainty dossier pending",
                implementationVerification = "Smoke tests only",
                platformQualification = "rxode2 runtime documented; no formal software qualification dossier",
                peerReview = "No external peer review",
                profileSource = "workspace-model"
              ),
              "rxode2",
              "/tmp/example_model.R"
            )
            """
        )

        self.assertEqual(payload["contextOfUse"]["summary"], "Research-only summary")
        self.assertEqual(payload["applicabilityDomain"]["summary"], "Adult human IV use")
        self.assertEqual(payload["modelPerformance"]["summary"], "No bundled predictivity dossier")
        self.assertEqual(payload["parameterProvenance"]["summary"], "Parameter table declared in module")
        self.assertEqual(payload["uncertainty"]["summary"], "Uncertainty dossier pending")
        self.assertEqual(payload["implementationVerification"]["summary"], "Smoke tests only")
        self.assertEqual(payload["platformQualification"]["summary"], "rxode2 runtime documented; no formal software qualification dossier")
        self.assertEqual(payload["peerReview"]["summary"], "No external peer review")
        self.assertEqual(payload["profileSource"]["summary"], "workspace-model")

    def test_normalize_model_profile_canonicalizes_peer_review_traceability(self) -> None:
        payload = run_r_json(
            """
            normalize_model_profile(
              list(
                peerReview = list(
                  status = "declared",
                  reviews = list(
                    list(
                      reviewer = "Independent reviewer",
                      reviewType = "expert-review",
                      reviewDate = "2026-03-01",
                      reviewOutcome = "accepted-with-notes"
                    )
                  ),
                  priorUse = list(
                    list(
                      jurisdiction = "OECD",
                      context = "consumer safety"
                    )
                  ),
                  changeHistory = list(
                    list(
                      version = "1.1",
                      date = "2026-03-10",
                      summary = "Updated transporter scaling notes"
                    )
                  ),
                  changeStatus = "actively-maintained"
                )
              ),
              "rxode2",
              "/tmp/example_model.R"
            )
            """
        )

        self.assertEqual(payload["peerReview"]["reviewRecordCount"], 1)
        self.assertEqual(payload["peerReview"]["priorUseCount"], 1)
        self.assertEqual(payload["peerReview"]["revisionEntryCount"], 1)
        self.assertTrue(payload["peerReview"]["coverage"]["hasRevisionStatus"])
        self.assertEqual(payload["peerReview"]["revisionStatus"], "actively-maintained")
        self.assertEqual(len(payload["peerReview"]["reviewRecords"]), 1)
        self.assertEqual(len(payload["peerReview"]["priorRegulatoryUse"]), 1)
        self.assertEqual(len(payload["peerReview"]["revisionHistory"]), 1)

    def test_normalize_model_profile_canonicalizes_performance_traceability(self) -> None:
        payload = run_r_json(
            """
            normalize_model_profile(
              list(
                modelPerformance = list(
                  status = "declared",
                  goodnessOfFit = list(
                    status = "declared",
                    metrics = list("Cmax"),
                    datasets = list("adult-iv-study"),
                    records = list(
                      list(dataset = "adult-iv-study", matrix = "plasma")
                    ),
                    criteria = list("Relative error <= 20% for plasma Cmax")
                  ),
                  predictiveChecks = list(
                    status = "declared",
                    benchmarkDatasets = list(
                      list(dataset = "external-benchmark", route = "iv")
                    ),
                    acceptanceCriterion = "GMFE within 2-fold across the benchmark set"
                  )
                )
              ),
              "rxode2",
              "/tmp/example_model.R"
            )
            """
        )

        coverage = payload["modelPerformance"]["coverage"]
        self.assertEqual(coverage["goodnessOfFitMetricCount"], 1)
        self.assertEqual(coverage["goodnessOfFitDatasetCount"], 1)
        self.assertEqual(coverage["goodnessOfFitDatasetRecordCount"], 1)
        self.assertEqual(coverage["predictiveDatasetRecordCount"], 1)
        self.assertEqual(coverage["acceptanceCriterionCount"], 2)
        self.assertTrue(coverage["hasExplicitAcceptanceCriteria"])
        self.assertEqual(payload["modelPerformance"]["acceptanceCriterionCount"], 2)
        self.assertEqual(payload["modelPerformance"]["predictiveDatasetRecordCount"], 1)

    def test_profile_request_mismatch_accepts_scalar_context_without_crashing(self) -> None:
        payload = run_r_json(
            """
            profile <- normalize_model_profile(
              list(
                contextOfUse = list(
                  scientificPurpose = "Kidney PBPK research",
                  decisionContext = "Exploratory use",
                  regulatoryUse = "research-only"
                ),
                applicabilityDomain = list(
                  type = "declared-with-runtime-guardrails",
                  qualificationLevel = "research-use",
                  species = "human",
                  routes = "iv-infusion"
                ),
                profileSource = list(type = "module-self-declared", path = "example_model.R")
              ),
              "rxode2",
              "/tmp/example_model.R"
            )
            profile_request_mismatch_errors(
              profile,
              list(contextOfUse = "research-only", route = "iv-infusion", species = "human")
            )
            """
        )

        self.assertEqual(payload, [])

    def test_profile_request_mismatch_reports_scalar_context_and_route_errors(self) -> None:
        payload = run_r_json(
            """
            profile <- normalize_model_profile(
              list(
                contextOfUse = list(
                  scientificPurpose = "Kidney PBPK research",
                  decisionContext = "Exploratory use",
                  regulatoryUse = "research-only"
                ),
                applicabilityDomain = list(
                  type = "declared-with-runtime-guardrails",
                  qualificationLevel = "research-use",
                  species = "human",
                  routes = "iv-infusion"
                ),
                profileSource = list(type = "module-self-declared", path = "example_model.R")
              ),
              "rxode2",
              "/tmp/example_model.R"
            )
            profile_request_mismatch_errors(
              profile,
              list(contextOfUse = "regulatory-use", route = "oral", species = "human")
            )
            """
        )

        codes = {entry["code"] for entry in payload}
        self.assertIn("unsupported_route", codes)
        self.assertIn("context_of_use_mismatch", codes)

    def test_with_profile_assessment_emits_oecd_checklist_and_score(self) -> None:
        payload = run_r_json(
            """
            profile <- normalize_model_profile(
              list(
                contextOfUse = list(
                  scientificPurpose = "Kidney PBPK research",
                  decisionContext = "Exploratory use",
                  regulatoryUse = "research-only"
                ),
                applicabilityDomain = list(
                  type = "declared-with-runtime-guardrails",
                  qualificationLevel = "research-use",
                  species = "human",
                  routes = "iv-infusion"
                ),
                modelPerformance = list(
                  status = "limited-internal-evaluation",
                  goodnessOfFit = list(status = "not-bundled", summary = "No formal fit metrics"),
                  predictiveChecks = list(status = "smoke-only", summary = "Smoke tests only"),
                  targetOutputs = list("Plasma|Cisplatin|Concentration")
                ),
                parameterProvenance = list(
                  status = "partially-declared",
                  sourceTable = "pbpk_parameter_table",
                  coverage = "Named runtime parameters",
                  provenanceMethod = "module annotations"
                ),
                uncertainty = list(
                  status = "partially-characterized",
                  sensitivityAnalysis = list(status = "not-encoded"),
                  residualUncertainty = "Residual transport uncertainty"
                ),
                implementationVerification = list(
                  status = "basic-internal-checks",
                  solver = "rxode2::rxSolve",
                  verifiedChecks = list("syntax", "smoke test")
                ),
                platformQualification = list(
                  status = "runtime-platform-documented",
                  softwareName = "rxode2",
                  runtime = "R",
                  runtimeVersion = "R 4.4.0",
                  qualificationBasis = "Runtime version is recorded for traceability; no formal platform qualification dossier is bundled."
                ),
                peerReview = list(status = "not-reported"),
                profileSource = list(
                  type = "module-self-declared",
                  path = "example_model.R",
                  sourceToolHint = "rxode2"
                )
              ),
              "rxode2",
              "/tmp/example_model.R"
            )
            with_profile_assessment(
              list(ok = TRUE, errors = list(), warnings = list()),
              profile,
              list(scientificProfile = TRUE)
            )
            """
        )

        assessment = payload["assessment"]
        checklist = assessment["oecdChecklist"]

        self.assertAlmostEqual(assessment["oecdChecklistScore"], 7.5 / 9, places=3)
        self.assertEqual(checklist["contextOfUse"]["status"], "declared")
        self.assertEqual(checklist["applicabilityDomain"]["status"], "declared")
        self.assertEqual(checklist["modelPerformanceAndPredictivity"]["status"], "partial")
        self.assertEqual(checklist["parameterizationAndProvenance"]["status"], "declared")
        self.assertEqual(checklist["uncertaintyAndSensitivity"]["status"], "declared")
        self.assertEqual(checklist["implementationVerification"]["status"], "declared")
        self.assertEqual(checklist["softwarePlatformQualification"]["status"], "declared")
        self.assertEqual(checklist["peerReviewAndPriorUse"]["status"], "missing")
        self.assertEqual(checklist["reportingAndTraceability"]["status"], "declared")
        self.assertEqual(assessment["qualificationState"]["state"], "research-use")
        self.assertFalse(assessment["qualificationState"]["riskAssessmentReady"])

    def test_with_profile_assessment_promotes_structured_peer_review_traceability(self) -> None:
        payload = run_r_json(
            """
            profile <- normalize_model_profile(
              list(
                contextOfUse = list(
                  scientificPurpose = "Kidney PBPK research",
                  decisionContext = "Exploratory use",
                  regulatoryUse = "research-only"
                ),
                applicabilityDomain = list(
                  type = "declared-with-runtime-guardrails",
                  qualificationLevel = "research-use",
                  species = "human",
                  routes = "iv-infusion"
                ),
                modelPerformance = list(
                  status = "limited-internal-evaluation",
                  goodnessOfFit = list(status = "not-bundled", summary = "No formal fit metrics"),
                  predictiveChecks = list(status = "smoke-only", summary = "Smoke tests only"),
                  targetOutputs = list("Plasma|Cisplatin|Concentration")
                ),
                parameterProvenance = list(
                  status = "partially-declared",
                  sourceTable = "pbpk_parameter_table",
                  coverage = "Named runtime parameters",
                  provenanceMethod = "module annotations"
                ),
                uncertainty = list(
                  status = "partially-characterized",
                  sensitivityAnalysis = list(status = "not-encoded"),
                  residualUncertainty = "Residual transport uncertainty"
                ),
                implementationVerification = list(
                  status = "basic-internal-checks",
                  solver = "rxode2::rxSolve",
                  verifiedChecks = list("syntax", "smoke test")
                ),
                platformQualification = list(
                  status = "runtime-platform-documented",
                  softwareName = "rxode2",
                  runtime = "R",
                  runtimeVersion = "R 4.4.0",
                  qualificationBasis = "Runtime version is recorded for traceability; no formal platform qualification dossier is bundled."
                ),
                peerReview = list(
                  status = "declared",
                  reviewRecords = list(
                    list(
                      reviewer = "Independent reviewer",
                      reviewType = "expert-review",
                      reviewDate = "2026-03-01",
                      reviewOutcome = "accepted-with-notes"
                    )
                  ),
                  priorRegulatoryUse = list(
                    list(
                      jurisdiction = "OECD",
                      context = "consumer safety"
                    )
                  ),
                  revisionHistory = list(
                    list(
                      version = "1.1",
                      date = "2026-03-10",
                      summary = "Updated transporter scaling notes"
                    )
                  ),
                  revisionStatus = "actively-maintained"
                ),
                profileSource = list(
                  type = "module-self-declared",
                  path = "example_model.R",
                  sourceToolHint = "rxode2"
                )
              ),
              "rxode2",
              "/tmp/example_model.R"
            )
            with_profile_assessment(
              list(ok = TRUE, errors = list(), warnings = list()),
              profile,
              list(scientificProfile = TRUE)
            )
            """
        )

        assessment = payload["assessment"]
        checklist = assessment["oecdChecklist"]
        warning_codes = {entry["code"] for entry in payload["warnings"]}

        self.assertAlmostEqual(assessment["oecdChecklistScore"], 8.5 / 9, places=3)
        self.assertEqual(checklist["peerReviewAndPriorUse"]["status"], "declared")
        self.assertNotIn("peer_review_traceability_limited", warning_codes)

    def test_with_profile_assessment_warns_for_sparse_peer_review_traceability(self) -> None:
        payload = run_r_json(
            """
            profile <- normalize_model_profile(
              list(
                contextOfUse = list(
                  scientificPurpose = "Kidney PBPK research",
                  decisionContext = "Exploratory use",
                  regulatoryUse = "research-only"
                ),
                applicabilityDomain = list(
                  type = "declared-with-runtime-guardrails",
                  qualificationLevel = "research-use",
                  species = "human",
                  routes = "iv-infusion"
                ),
                modelPerformance = list(status = "limited-internal-evaluation"),
                parameterProvenance = list(status = "partially-declared", sourceTable = "pbpk_parameter_table"),
                uncertainty = list(status = "partially-characterized"),
                implementationVerification = list(status = "basic-internal-checks", verifiedChecks = list("smoke test")),
                platformQualification = list(
                  status = "runtime-platform-documented",
                  softwareName = "rxode2",
                  runtime = "R",
                  qualificationBasis = "Runtime only"
                ),
                peerReview = list(
                  status = "declared",
                  summary = "Internal discussion completed"
                ),
                profileSource = list(type = "module-self-declared", path = "example_model.R")
              ),
              "rxode2",
              "/tmp/example_model.R"
            )
            with_profile_assessment(
              list(ok = TRUE, errors = list(), warnings = list()),
              profile,
              list(scientificProfile = TRUE)
            )
            """
        )

        assessment = payload["assessment"]
        checklist = assessment["oecdChecklist"]
        warning_codes = {entry["code"] for entry in payload["warnings"]}
        missing_evidence = set(assessment["missingEvidence"])

        self.assertEqual(checklist["peerReviewAndPriorUse"]["status"], "partial")
        self.assertIn("peer_review_traceability_limited", warning_codes)
        self.assertIn("Structured peer-review records", missing_evidence)
        self.assertIn("Prior regulatory or external use traceability", missing_evidence)
        self.assertIn("Revision or change history", missing_evidence)

    def test_with_profile_assessment_promotes_structured_performance_traceability(self) -> None:
        payload = run_r_json(
            """
            profile <- normalize_model_profile(
              list(
                contextOfUse = list(
                  scientificPurpose = "Kidney PBPK research",
                  decisionContext = "Exploratory use",
                  regulatoryUse = "research-only"
                ),
                applicabilityDomain = list(
                  type = "declared-with-runtime-guardrails",
                  qualificationLevel = "research-use",
                  species = "human",
                  routes = "iv-infusion"
                ),
                modelPerformance = list(
                  status = "declared",
                  goodnessOfFit = list(
                    status = "declared",
                    metrics = list("Cmax"),
                    datasetRecords = list(
                      list(dataset = "adult-iv-study", matrix = "plasma")
                    ),
                    acceptanceCriteria = list("Relative error <= 20% for plasma Cmax")
                  ),
                  predictiveChecks = list(
                    status = "declared",
                    datasetRecords = list(
                      list(dataset = "external-benchmark", route = "iv")
                    ),
                    acceptanceCriterion = "GMFE within 2-fold across the benchmark set"
                  ),
                  targetOutputs = list("Plasma|Cisplatin|Concentration")
                ),
                parameterProvenance = list(
                  status = "partially-declared",
                  sourceTable = "pbpk_parameter_table",
                  coverage = "Named runtime parameters",
                  provenanceMethod = "module annotations"
                ),
                uncertainty = list(status = "partially-characterized"),
                implementationVerification = list(status = "basic-internal-checks", verifiedChecks = list("smoke test")),
                platformQualification = list(
                  status = "runtime-platform-documented",
                  softwareName = "rxode2",
                  runtime = "R",
                  runtimeVersion = "R 4.4.0",
                  qualificationBasis = "Runtime version is recorded for traceability; no formal platform qualification dossier is bundled."
                ),
                peerReview = list(status = "not-reported"),
                profileSource = list(type = "module-self-declared", path = "example_model.R")
              ),
              "rxode2",
              "/tmp/example_model.R"
            )
            with_profile_assessment(
              list(ok = TRUE, errors = list(), warnings = list()),
              profile,
              list(scientificProfile = TRUE)
            )
            """
        )

        assessment = payload["assessment"]
        checklist = assessment["oecdChecklist"]
        warning_codes = {entry["code"] for entry in payload["warnings"]}
        missing_evidence = set(assessment["missingEvidence"])

        self.assertEqual(checklist["modelPerformanceAndPredictivity"]["status"], "declared")
        self.assertNotIn("model_performance_evidence_limited", warning_codes)
        self.assertNotIn("Explicit performance acceptance criteria", missing_evidence)

    def test_normalize_parameter_catalog_preserves_provenance_fields(self) -> None:
        payload = run_r_json(
            """
            normalize_parameter_catalog(
              list("Dose|DosePerSquareMeter" = 80),
              list(
                list(
                  path = "Dose|DosePerSquareMeter",
                  display_name = "Dose per square meter",
                  unit = "mg/m2",
                  category = "Dose",
                  sourceType = "study-design-input",
                  source = "Protocol input",
                  evidenceType = "scenario definition",
                  rationale = "User-controlled dose definition"
                )
              )
            )
            """
        )

        row = payload["Dose|DosePerSquareMeter"]
        self.assertEqual(row["sourceType"], "study-design-input")
        self.assertEqual(row["source"], "Protocol input")
        self.assertEqual(row["evidenceType"], "scenario definition")
        self.assertEqual(row["provenance_status"], "declared")

    def test_record_parameter_table_reads_companion_sidecar_and_reports_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "example_model.R"
            model_path.write_text("# example model", encoding="utf-8")
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
                                "sourceCitation": "Doe et al. 2026",
                                "distribution": "lognormal",
                                "mean": 70,
                                "sd": 10,
                                "experimentalConditions": ["adult healthy volunteers"],
                                "rationale": "Default adult physiology prior",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = run_r_json(
                f"""
                parameters <- list("Physiology|BodyWeight" = 70)
                catalog <- normalize_parameter_catalog(
                  parameters,
                  list(
                    list(
                      path = "Physiology|BodyWeight",
                      display_name = "Body weight",
                      unit = "kg",
                      category = "Physiology"
                    )
                  )
                )
                record <- list(
                  backend = "rxode2",
                  simulation_id = "example-model",
                  file_path = {json.dumps(str(model_path))},
                  metadata = list(name = "Example model"),
                  capabilities = list(scientificProfile = FALSE),
                  profile = list(),
                  parameters = parameters,
                  parameter_catalog = catalog
                )
                record_parameter_table(record, limit = 10L)
                """
            )

        self.assertEqual(payload["source"], "combined")
        self.assertEqual(payload["sidecarPath"], str(model_path.with_suffix(".parameters.json")))
        self.assertEqual(payload["bundleMetadata"]["bundleVersion"], "pbpk-parameter-table.v1")
        self.assertEqual(payload["coverage"]["rowsWithSources"], 1)
        self.assertEqual(payload["coverage"]["rowsWithDistributions"], 1)
        self.assertEqual(payload["coverage"]["rowsWithExperimentalConditions"], 1)
        self.assertEqual(payload["coverage"]["rowsWithRationale"], 1)
        self.assertEqual(payload["issueCount"], 0)
        row = payload["rows"][0]
        self.assertEqual(row["distribution"], "lognormal")
        self.assertEqual(row["mean"], 70)
        self.assertEqual(row["sd"], 10)
        self.assertEqual(row["sourceCitation"], "Doe et al. 2026")
        self.assertEqual(row["experimentalConditions"], ["adult healthy volunteers"])

    def test_with_profile_assessment_handles_unreported_parameter_count(self) -> None:
        payload = run_r_json(
            """
            profile <- normalize_model_profile(
              list(),
              "ospsuite",
              "/tmp/example_model.pkml"
            )
            with_profile_assessment(
              list(ok = TRUE, errors = list(), warnings = list()),
              profile,
              list(scientificProfile = FALSE)
            )
            """
        )

        checklist = payload["assessment"]["oecdChecklist"]
        self.assertEqual(checklist["parameterizationAndProvenance"]["status"], "missing")
        self.assertEqual(payload["assessment"]["qualificationState"]["state"], "exploratory")

    def test_ospsuite_profile_marks_sidecar_source(self) -> None:
        example_model = (
            WORKSPACE_ROOT
            / "var"
            / "models"
            / "esqlabs"
            / "pregnancy-neonates-batch-run"
            / "Pregnant_simulation_PKSim.pkml"
        )
        payload = run_r_json(
            f"""
            profile <- ospsuite_profile(
              {json.dumps(str(example_model))},
              list()
            )
            profile$profileSource
            """
        )

        self.assertEqual(payload["type"], "sidecar")

    def test_build_oecd_report_includes_parameter_table(self) -> None:
        payload = run_r_json(
            """
            parameters <- list(
              "Physiology|BodyWeight" = 70,
              "Dose|DosePerSquareMeter" = 80
            )
            catalog <- normalize_parameter_catalog(
              parameters,
              list(
                list(
                  path = "Physiology|BodyWeight",
                  display_name = "Body weight",
                  unit = "kg",
                  category = "Physiology",
                  sourceType = "adult-human-physiology-default",
                  source = "Workspace physiology defaults",
                  evidenceType = "literature-informed default"
                ),
                list(
                  path = "Dose|DosePerSquareMeter",
                  display_name = "Dose per square meter",
                  unit = "mg/m2",
                  category = "Dose",
                  sourceType = "study-design-input",
                  source = "Protocol input",
                  evidenceType = "scenario definition"
                )
              )
            )
            profile <- normalize_model_profile(
              list(
                contextOfUse = list(
                  scientificPurpose = "Kidney PBPK research",
                  decisionContext = "Exploratory use",
                  regulatoryUse = "research-only"
                ),
                applicabilityDomain = list(
                  type = "declared-with-runtime-guardrails",
                  qualificationLevel = "research-use",
                  species = "human",
                  routes = "iv-infusion"
                ),
                modelPerformance = list(
                  status = "limited-internal-evaluation",
                  goodnessOfFit = list(status = "not-bundled", summary = "No formal fit metrics"),
                  predictiveChecks = list(status = "smoke-only", summary = "Smoke tests only"),
                  targetOutputs = list("Plasma|Cisplatin|Concentration")
                ),
                parameterProvenance = list(
                  status = "partially-declared",
                  sourceTable = "pbpk_parameter_table",
                  coverage = "Named runtime parameters",
                  provenanceMethod = "module annotations"
                ),
                uncertainty = list(
                  status = "partially-characterized",
                  sensitivityAnalysis = list(status = "not-encoded"),
                  residualUncertainty = "Residual transport uncertainty"
                ),
                implementationVerification = list(
                  status = "basic-internal-checks",
                  solver = "rxode2::rxSolve",
                  verifiedChecks = list("syntax", "smoke test")
                ),
                platformQualification = list(
                  status = "runtime-platform-documented",
                  softwareName = "rxode2",
                  runtime = "R",
                  runtimeVersion = "R 4.4.0",
                  qualificationBasis = "Runtime version is recorded for traceability; no formal platform qualification dossier is bundled."
                ),
                peerReview = list(status = "not-reported"),
                profileSource = list(
                  type = "module-self-declared",
                  path = "example_model.R",
                  sourceToolHint = "rxode2"
                )
              ),
              "rxode2",
              "/tmp/example_model.R"
            )
            validation <- with_profile_assessment(
              list(ok = TRUE, errors = list(), warnings = list()),
              profile,
              list(scientificProfile = TRUE)
            )
            record <- list(
              backend = "rxode2",
              simulation_id = "example-model",
              file_path = "/tmp/example_model.R",
              metadata = list(
                name = "Example model",
                modelVersion = "1.0",
                createdBy = "test",
                createdAt = "2026-03-19T00:00:00Z",
                latestResultsId = "example-results",
                verification = list(
                  generatedAt = "2026-03-20T10:00:00Z",
                  status = "passed",
                  summary = "All executable verification checks passed.",
                  requestedPopulationSmoke = FALSE,
                  qualificationState = list(state = "research-use"),
                  checkCount = 2,
                  passedCount = 2,
                  failedCount = 0,
                  warningCount = 0,
                  skippedCount = 0,
                  checks = list(
                    list(id = "mass-balance", status = "passed", summary = "Tracked amount stayed within tolerance."),
                    list(id = "solver-stability", status = "passed", summary = "Refined sampling remained stable.")
                  ),
                  artifacts = list(deterministicResultsId = "example-results")
                )
              ),
              capabilities = list(scientificProfile = TRUE),
              profile = profile,
              parameters = parameters,
              parameter_catalog = catalog
            )
            assign(
              "example-results",
              list(
                results_id = "example-results",
                simulation_id = "example-model",
                generated_at = "2026-03-20T10:05:00Z",
                metadata = list(engine = "rxode2"),
                series = list(
                  list(
                    parameter = "Plasma|Cisplatin|Concentration",
                    unit = "mg/L",
                    values = list(
                      list(time = 0, value = 0),
                      list(time = 1, value = 2),
                      list(time = 2, value = 1)
                    )
                  )
                )
              ),
              envir = results_store
            )
            build_oecd_report(
              record,
              request = list(contextOfUse = "research-only"),
              validation = validation,
              include_parameter_table = TRUE,
              parameter_limit = 10
            )
            """
        )

        self.assertEqual(payload["reportVersion"], "pbpk-oecd-report.v1")
        self.assertEqual(payload["oecdChecklist"]["modelPerformanceAndPredictivity"]["status"], "partial")
        self.assertEqual(payload["qualificationState"]["state"], "research-use")
        self.assertIn("oecdCoverage", payload)
        self.assertEqual(payload["oecdCoverage"]["coverageVersion"], "pbpk-oecd-coverage.v1")
        self.assertFalse(payload["oecdCoverage"]["affectsChecklistScore"])
        self.assertFalse(payload["oecdCoverage"]["affectsQualificationState"])
        self.assertEqual(
            payload["oecdCoverage"]["reportingTemplate"]["sections"]["modelPerformance"]["status"],
            "partial",
        )
        self.assertEqual(
            payload["oecdCoverage"]["reportingTemplate"]["sections"]["modelConceptualisation"]["status"],
            "missing",
        )
        self.assertEqual(
            payload["oecdCoverage"]["evaluationChecklist"]["sections"]["regulatoryPurpose"]["status"],
            "partial",
        )
        self.assertEqual(
            payload["oecdCoverage"]["evaluationChecklist"]["sections"]["theoreticalBasisOfModelEquations"]["status"],
            "missing",
        )
        self.assertEqual(payload["performanceEvidence"]["included"], True)
        self.assertEqual(payload["performanceEvidence"]["returnedRows"], 0)
        self.assertEqual(payload["performanceEvidence"]["strongestEvidenceClass"], "none")
        self.assertEqual(
            payload["performanceEvidence"]["qualificationBoundary"],
            "no-bundled-performance-evidence",
        )
        self.assertFalse(payload["performanceEvidence"]["supportsObservedVsPredictedEvidence"])
        self.assertFalse(payload["performanceEvidence"]["supportsPredictiveDatasetEvidence"])
        self.assertFalse(payload["performanceEvidence"]["supportsExternalQualificationEvidence"])
        self.assertFalse(payload["performanceEvidence"]["limitedToRuntimeOrInternalEvidence"])
        self.assertEqual(payload["uncertaintyEvidence"]["included"], True)
        self.assertGreaterEqual(payload["uncertaintyEvidence"]["returnedRows"], 2)
        self.assertEqual(payload["verificationEvidence"]["included"], True)
        self.assertGreaterEqual(payload["verificationEvidence"]["returnedRows"], 1)
        self.assertEqual(payload["executableVerification"]["included"], True)
        self.assertEqual(payload["executableVerification"]["status"], "passed")
        self.assertEqual(payload["executableVerification"]["passedCount"], 2)
        self.assertEqual(payload["executableVerification"]["checks"][0]["id"], "mass-balance")
        self.assertEqual(payload["platformQualificationEvidence"]["included"], True)
        self.assertGreaterEqual(payload["platformQualificationEvidence"]["returnedRows"], 1)
        self.assertIn("ngraObjects", payload)
        self.assertEqual(payload["ngraObjects"]["assessmentContext"]["objectType"], "assessmentContext.v1")
        self.assertEqual(
            payload["ngraObjects"]["pbpkQualificationSummary"]["state"],
            "research-use",
        )
        self.assertEqual(
            payload["ngraObjects"]["pbpkQualificationSummary"]["assessmentBoundary"],
            "pbpk-execution-and-qualification-substrate-only",
        )
        self.assertFalse(
            payload["ngraObjects"]["pbpkQualificationSummary"]["supports"]["regulatoryDecision"],
        )
        self.assertIn(
            "higher-level NGRA decision policy or orchestrator outside PBPK MCP",
            payload["ngraObjects"]["pbpkQualificationSummary"]["requiredExternalInputs"],
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintySummary"]["status"],
            "partially-characterized",
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintySummary"]["decisionBoundary"],
            "no-ngra-decision-policy",
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintySummary"]["semanticCoverage"]["overallQuantificationStatus"],
            "declared-without-complete-quantification",
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintySummary"]["semanticCoverage"]["quantifiedRowCount"],
            0,
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintySummary"]["semanticCoverage"]["declaredOnlyRowCount"],
            2,
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintySummary"]["semanticCoverage"]["variabilityType"],
            "unreported",
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintySummary"]["semanticCoverage"]["sensitivityType"],
            "parameter-influence-analysis",
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintySummary"]["semanticCoverage"]["residualUncertaintyType"],
            "epistemic-or-unresolved-uncertainty",
        )
        self.assertIn(
            "sensitivity-analysis",
            payload["ngraObjects"]["uncertaintySummary"]["semanticCoverage"]["declaredOnlyComponents"],
        )
        self.assertIn(
            "residual-uncertainty",
            payload["ngraObjects"]["uncertaintySummary"]["semanticCoverage"]["declaredOnlyComponents"],
        )
        self.assertIn(
            "variability",
            payload["ngraObjects"]["uncertaintySummary"]["semanticCoverage"]["missingComponents"],
        )
        self.assertFalse(
            payload["ngraObjects"]["uncertaintySummary"]["supports"]["crossDomainUncertaintyRegister"],
        )
        self.assertTrue(
            payload["ngraObjects"]["uncertaintySummary"]["supports"]["typedUncertaintySemantics"],
        )
        self.assertFalse(
            payload["ngraObjects"]["uncertaintySummary"]["supports"]["quantifiedVariability"],
        )
        self.assertFalse(
            payload["ngraObjects"]["uncertaintySummary"]["supports"]["quantifiedSensitivity"],
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
            payload["ngraObjects"]["uncertaintyHandoff"]["supports"]["pbpkQualificationAttached"],
        )
        self.assertTrue(
            payload["ngraObjects"]["uncertaintyHandoff"]["supports"]["pbpkUncertaintySummaryAttached"],
        )
        self.assertTrue(
            payload["ngraObjects"]["uncertaintyHandoff"]["supports"]["typedUncertaintySemanticsAttached"],
        )
        self.assertFalse(
            payload["ngraObjects"]["uncertaintyHandoff"]["supports"]["quantifiedPbpkVariability"],
        )
        self.assertFalse(
            payload["ngraObjects"]["uncertaintyHandoff"]["supports"]["quantifiedPbpkSensitivity"],
        )
        self.assertFalse(
            payload["ngraObjects"]["uncertaintyHandoff"]["supports"]["uncertaintyRegisterReferenceAttached"],
        )
        self.assertEqual(
            payload["ngraObjects"]["uncertaintyRegisterReference"]["status"],
            "not-attached",
        )
        self.assertIn(
            "PoD or NAM uncertainty outside PBPK MCP",
            payload["ngraObjects"]["uncertaintyHandoff"]["requiredExternalInputs"],
        )
        self.assertIn(
            "external cross-domain uncertainty register reference",
            payload["ngraObjects"]["uncertaintyHandoff"]["requiredExternalInputs"],
        )
        self.assertEqual(
            payload["ngraObjects"]["internalExposureEstimate"]["status"],
            "available",
        )
        self.assertEqual(
            payload["ngraObjects"]["internalExposureEstimate"]["assessmentBoundary"],
            "pbpk-side-internal-exposure-estimate-only",
        )
        self.assertTrue(
            payload["ngraObjects"]["internalExposureEstimate"]["supports"]["externalBerHandoff"],
        )
        self.assertEqual(
            payload["ngraObjects"]["internalExposureEstimate"]["selectionStatus"],
            "only-series",
        )
        self.assertEqual(
            payload["ngraObjects"]["internalExposureEstimate"]["selectedOutput"]["cmax"],
            2,
        )
        self.assertEqual(
            payload["ngraObjects"]["pointOfDepartureReference"]["status"],
            "not-attached",
        )
        self.assertEqual(
            payload["ngraObjects"]["pointOfDepartureReference"]["decisionOwner"],
            "external-orchestrator",
        )
        self.assertEqual(
            payload["ngraObjects"]["berInputBundle"]["status"],
            "incomplete",
        )
        self.assertEqual(
            payload["ngraObjects"]["berInputBundle"]["decisionOwner"],
            "external-orchestrator",
        )
        self.assertIn(
            "external point-of-departure reference",
            payload["ngraObjects"]["berInputBundle"]["requiredExternalInputs"],
        )
        self.assertEqual(payload["parameterTable"]["source"], "parameter_catalog")
        self.assertEqual(payload["parameterTable"]["returnedRows"], 2)
        self.assertEqual(
            payload["parameterTable"]["rows"][0]["provenance_status"],
            "declared",
        )

    def test_build_oecd_report_marks_ber_bundle_ready_with_pod_ref_and_target_output(self) -> None:
        payload = run_r_json(
            """
            parameters <- list("Dose|DosePerSquareMeter" = 80)
            profile <- normalize_model_profile(
              list(
                contextOfUse = list(
                  scientificPurpose = "Tier 1 PBPK support",
                  decisionContext = "BER-ready handoff",
                  regulatoryUse = "research-only"
                ),
                applicabilityDomain = list(
                  type = "declared-with-runtime-guardrails",
                  qualificationLevel = "research-use",
                  species = "human",
                  routes = "iv-infusion"
                ),
                uncertainty = list(status = "partially-characterized"),
                profileSource = list(
                  type = "module-self-declared",
                  path = "example_model.R",
                  sourceToolHint = "rxode2"
                )
              ),
              "rxode2",
              "/tmp/example_model.R"
            )
            validation <- with_profile_assessment(
              list(ok = TRUE, errors = list(), warnings = list()),
              profile,
              list(scientificProfile = TRUE)
            )
            record <- list(
              backend = "rxode2",
              simulation_id = "ber-ready-model",
              file_path = "/tmp/example_model.R",
              metadata = list(
                name = "BER ready model",
                latestResultsId = "ber-ready-results"
              ),
              capabilities = list(scientificProfile = TRUE),
              profile = profile,
              parameters = parameters,
              parameter_catalog = normalize_parameter_catalog(parameters, list())
            )
            assign(
              "ber-ready-results",
              list(
                results_id = "ber-ready-results",
                simulation_id = "ber-ready-model",
                generated_at = "2026-03-21T10:00:00Z",
                metadata = list(engine = "rxode2"),
                series = list(
                  list(
                    parameter = "Plasma|Parent|Concentration",
                    unit = "uM",
                    values = list(
                      list(time = 0, value = 0),
                      list(time = 1, value = 5),
                      list(time = 2, value = 2)
                    )
                  )
                )
              ),
              envir = results_store
            )
            report <- build_oecd_report(
              record,
              request = list(
                contextOfUse = "research-only",
                targetOutput = "Plasma|Parent|Concentration",
                comparisonMetric = "cmax",
                podRef = "pod-123",
                pod = list(
                  source = "httr-benchmark",
                  metric = "cmax",
                  unit = "uM",
                  basis = "true-dose-adjusted"
                ),
                trueDose = list(
                  applied = TRUE,
                  basis = "free-concentration",
                  summary = "PoD normalized to free concentration"
                ),
                uncertaintyRegister = list(
                  ref = "unc-reg-123",
                  source = "assessment-workbench",
                  scope = "tier-1-systemic"
                )
              ),
              validation = validation,
              include_parameter_table = FALSE
            )
            list(
              ber = report$ngraObjects$berInputBundle,
              register = report$ngraObjects$uncertaintyRegisterReference,
              handoff = report$ngraObjects$uncertaintyHandoff
            )
            """
        )

        ber_payload = payload["ber"]
        register_payload = payload["register"]
        handoff_payload = payload["handoff"]

        self.assertEqual(ber_payload["status"], "ready-for-external-ber-calculation")
        self.assertEqual(ber_payload["assessmentBoundary"], "external-ber-calculation-only")
        self.assertEqual(
            ber_payload["decisionOwner"],
            "external-orchestrator",
        )
        self.assertEqual(
            ber_payload["pointOfDepartureReferenceRef"],
            "ber-ready-model-point-of-departure-reference",
        )
        self.assertEqual(ber_payload["comparisonMetric"], "cmax")
        self.assertEqual(ber_payload["podRef"], "pod-123")
        self.assertEqual(ber_payload["podMetadata"]["source"], "httr-benchmark")
        self.assertEqual(ber_payload["internalExposureMetric"]["metric"], "cmax")
        self.assertEqual(ber_payload["internalExposureMetric"]["value"], 5)
        self.assertEqual(ber_payload["internalExposureMetric"]["unit"], "uM")
        self.assertTrue(ber_payload["trueDoseAdjustmentApplied"])
        self.assertEqual(ber_payload["trueDoseAdjustment"]["basis"], "free-concentration")
        self.assertEqual(ber_payload["blockingReasons"], [])
        self.assertTrue(ber_payload["supports"]["externalBerCalculation"])
        self.assertIn(
            "BER calculation and decision policy outside PBPK MCP",
            ber_payload["requiredExternalInputs"],
        )
        self.assertEqual(register_payload["status"], "attached-external-reference")
        self.assertEqual(register_payload["registerRef"], "unc-reg-123")
        self.assertEqual(handoff_payload["status"], "ready-for-cross-domain-uncertainty-synthesis")
        self.assertEqual(
            handoff_payload["uncertaintyRegisterReferenceRef"],
            "ber-ready-model-uncertainty-register-reference",
        )
        self.assertTrue(
            handoff_payload["supports"]["uncertaintyRegisterReferenceAttached"],
        )

    def test_performance_evidence_summary_distinguishes_runtime_internal_rows(self) -> None:
        payload = run_r_json(
            """
            rows <- normalize_performance_evidence_rows(
              list(
                list(
                  id = "runtime-smoke-row",
                  kind = "runtime-smoke-test",
                  status = "passed",
                  evidenceLevel = "runtime-only"
                ),
                list(
                  id = "internal-reference-row",
                  kind = "regression-baseline",
                  status = "passed",
                  evidenceLevel = "internal-reference"
                )
              )
            )
            performance_evidence_summary(rows)
            """
        )

        self.assertEqual(payload["strongestEvidenceClass"], "internal-reference")
        self.assertEqual(
            payload["qualificationBoundary"],
            "runtime-or-internal-evidence-only",
        )
        self.assertTrue(payload["limitedToRuntimeOrInternalEvidence"])
        self.assertFalse(payload["supportsObservedVsPredictedEvidence"])
        self.assertFalse(payload["supportsPredictiveDatasetEvidence"])
        self.assertFalse(payload["supportsExternalQualificationEvidence"])
        self.assertEqual(payload["evidenceClassCounts"]["runtime-smoke"], 1)
        self.assertEqual(payload["evidenceClassCounts"]["internal-reference"], 1)

    def test_record_performance_evidence_reads_companion_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "example_model.R"
            model_path.write_text("# example model", encoding="utf-8")
            (root / "example_model.performance.json").write_text(
                json.dumps(
                    {
                        "metadata": {
                            "bundleVersion": "pbpk-performance-evidence.v1",
                            "summary": "Example benchmark bundle",
                        },
                        "rows": [
                            {
                                "id": "obs-vs-pred-cmax",
                                "kind": "observed-vs-predicted",
                                "status": "declared",
                                "metric": "Cmax",
                                "observedValue": 1.0,
                                "predictedValue": 1.1,
                                "dataset": "example-benchmark",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = run_r_json(
                f"""
                record <- list(
                  backend = "rxode2",
                  simulation_id = "example-sidecar",
                  file_path = {json.dumps(str(model_path))},
                  metadata = list(name = "Example model"),
                  profile = list(modelPerformance = list(status = "limited-internal-evaluation")),
                  capabilities = list(scientificProfile = TRUE),
                  parameters = list(),
                  parameter_catalog = list()
                )
                record_performance_evidence(record, limit = 10)
                """
            )

        self.assertEqual(payload["source"], "performance-evidence-sidecar")
        self.assertEqual(payload["returnedRows"], 1)
        self.assertEqual(payload["strongestEvidenceClass"], "observed-vs-predicted")
        self.assertTrue(payload["supportsObservedVsPredictedEvidence"])
        self.assertFalse(payload["supportsPredictiveDatasetEvidence"])
        self.assertFalse(payload["supportsExternalQualificationEvidence"])
        self.assertEqual(
            payload["qualificationBoundary"],
            "predictive-supporting-evidence-without-external-qualification",
        )
        self.assertEqual(payload["bundleMetadata"]["bundleVersion"], "pbpk-performance-evidence.v1")
        self.assertTrue(str(payload["sidecarPath"]).endswith("example_model.performance.json"))

    def test_record_performance_evidence_merges_sidecar_profile_supplement(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "example_model.R"
            model_path.write_text("# example model", encoding="utf-8")
            (root / "example_model.performance.json").write_text(
                json.dumps(
                    {
                        "metadata": {
                            "bundleVersion": "pbpk-performance-evidence.v1",
                            "summary": "Example benchmark bundle",
                        },
                        "profileSupplement": {
                            "goodnessOfFit": {
                                "metrics": ["Cmax"],
                                "datasetRecords": [
                                    {"dataset": "adult-iv-study", "matrix": "plasma"}
                                ],
                                "acceptanceCriteria": [
                                    "Relative error <= 20% for plasma Cmax"
                                ],
                            },
                            "predictiveChecks": {
                                "datasetRecords": [
                                    {"dataset": "external-benchmark", "route": "iv"}
                                ],
                                "acceptanceCriteria": [
                                    "GMFE within 2-fold across the benchmark set"
                                ],
                            },
                            "targetOutputs": ["Plasma|Compound|Concentration"],
                        },
                        "rows": [
                            {
                                "id": "obs-vs-pred-cmax",
                                "kind": "observed-vs-predicted",
                                "status": "declared",
                                "metric": "Cmax",
                                "targetOutput": "Plasma|Compound|Concentration",
                                "observedValue": 1.0,
                                "predictedValue": 1.1,
                                "dataset": "adult-iv-study",
                                "acceptanceCriterion": "Relative error <= 20% for plasma Cmax",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = run_r_json(
                f"""
                record <- list(
                  backend = "rxode2",
                  simulation_id = "example-sidecar-supplement",
                  file_path = {json.dumps(str(model_path))},
                  metadata = list(name = "Example model"),
                  profile = list(modelPerformance = list(status = "limited-internal-evaluation")),
                  capabilities = list(scientificProfile = TRUE),
                  parameters = list(),
                  parameter_catalog = list()
                )
                record_performance_evidence(record, limit = 10)
                """
            )

        self.assertTrue(payload["traceability"]["profileSupplementAttached"])
        self.assertEqual(payload["traceability"]["goodnessOfFitDatasetRecordCount"], 1)
        self.assertEqual(payload["traceability"]["predictiveDatasetRecordCount"], 1)
        self.assertEqual(payload["predictiveDatasetSummary"]["datasetCount"], 2)
        self.assertEqual(payload["predictiveDatasetSummary"]["metricCount"], 1)
        self.assertEqual(payload["predictiveDatasetSummary"]["acceptanceCriterionCount"], 2)
        self.assertIn("adult-iv-study", payload["predictiveDatasetSummary"]["datasets"])
        self.assertIn("external-benchmark", payload["predictiveDatasetSummary"]["datasets"])
        self.assertEqual(
            payload["traceabilityConsistency"]["datasetReferenceMatchedRowCount"],
            1,
        )
        self.assertEqual(
            payload["traceabilityConsistency"]["datasetReferenceUnmatchedRowCount"],
            0,
        )
        self.assertEqual(
            payload["traceabilityConsistency"]["acceptanceCriterionMatchedRowCount"],
            1,
        )
        self.assertEqual(
            payload["traceabilityConsistency"]["targetOutputMatchedRowCount"],
            1,
        )
        self.assertIn(
            "Plasma|Compound|Concentration",
            payload["predictiveDatasetSummary"]["targetOutputs"],
        )
        self.assertEqual(
            payload["profileSupplement"]["predictiveChecks"]["datasetRecords"][0]["dataset"],
            "external-benchmark",
        )

    def test_record_performance_evidence_warns_for_traceability_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "example_model.R"
            model_path.write_text("# example model", encoding="utf-8")
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

            payload = run_r_json(
                f"""
                record <- list(
                  backend = "rxode2",
                  simulation_id = "example-traceability-mismatch",
                  file_path = {json.dumps(str(model_path))},
                  metadata = list(name = "Example model"),
                  profile = list(modelPerformance = list(status = "limited-internal-evaluation")),
                  capabilities = list(scientificProfile = TRUE),
                  parameters = list(),
                  parameter_catalog = list()
                )
                record_performance_evidence(record, limit = 10)
                """
            )

        issue_codes = {entry["code"] for entry in payload["issues"]}
        self.assertIn("performance_row_dataset_traceability_missing", issue_codes)
        self.assertIn("performance_row_target_output_traceability_missing", issue_codes)
        self.assertIn("performance_row_acceptance_traceability_missing", issue_codes)
        self.assertEqual(
            payload["traceabilityConsistency"]["datasetReferenceUnmatchedRowCount"],
            1,
        )
        self.assertEqual(
            payload["traceabilityConsistency"]["targetOutputUnmatchedRowCount"],
            1,
        )
        self.assertEqual(
            payload["traceabilityConsistency"]["acceptanceCriterionUnmatchedRowCount"],
            1,
        )

    def test_record_performance_evidence_reports_profile_traceability(self) -> None:
        payload = run_r_json(
            """
            record <- list(
              backend = "rxode2",
              simulation_id = "example-traceability",
              file_path = "/tmp/example_model.R",
              metadata = list(name = "Example model"),
              profile = list(
                modelPerformance = list(
                  status = "declared",
                  goodnessOfFit = list(
                    status = "declared",
                    metrics = list("Cmax"),
                    datasets = list("adult-iv-study"),
                    datasetRecords = list(
                      list(dataset = "adult-iv-study", matrix = "plasma")
                    ),
                    acceptanceCriteria = list("Relative error <= 20% for plasma Cmax")
                  ),
                  predictiveChecks = list(
                    status = "declared",
                    datasetRecords = list(
                      list(dataset = "external-benchmark", route = "iv")
                    ),
                    acceptanceCriterion = "GMFE within 2-fold across the benchmark set"
                  )
                )
              ),
              capabilities = list(scientificProfile = TRUE),
              parameters = list(),
              parameter_catalog = list()
            )
            record_performance_evidence(record, limit = 20)
            """
        )

        self.assertEqual(payload["traceability"]["goodnessOfFitDatasetRecordCount"], 1)
        self.assertEqual(payload["traceability"]["predictiveDatasetRecordCount"], 1)
        self.assertEqual(payload["traceability"]["acceptanceCriterionCount"], 2)
        self.assertTrue(payload["traceability"]["hasExplicitAcceptanceCriteria"])
        self.assertTrue(
            any(
                row.get("acceptanceCriterion") == "Relative error <= 20% for plasma Cmax"
                for row in payload["rows"]
            )
        )

    def test_record_performance_evidence_reports_semantic_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "example_model.R"
            model_path.write_text("# example model", encoding="utf-8")
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

            payload = run_r_json(
                f"""
                record <- list(
                  backend = "rxode2",
                  simulation_id = "example-sidecar",
                  file_path = {json.dumps(str(model_path))},
                  metadata = list(name = "Example model"),
                  profile = list(modelPerformance = list(status = "limited-internal-evaluation")),
                  capabilities = list(scientificProfile = TRUE),
                  parameters = list(),
                  parameter_catalog = list()
                )
                record_performance_evidence(record, limit = 10)
                """
            )

        issue_codes = {entry["code"] for entry in payload["issues"]}
        self.assertIn("performance_bundle_version_missing", issue_codes)
        self.assertIn("performance_bundle_summary_missing", issue_codes)
        self.assertIn("performance_row_observed_missing", issue_codes)
        self.assertIn("performance_row_predicted_missing", issue_codes)
        self.assertIn("performance_row_dataset_missing", issue_codes)
        self.assertIn("performance_row_acceptance_missing", issue_codes)
        self.assertGreaterEqual(payload["issueCount"], 6)

    def test_record_uncertainty_evidence_passes_runtime_parameter_context(self) -> None:
        payload = run_r_json(
            """
            module_env <- new.env(parent = emptyenv())
            module_env$pbpk_uncertainty_evidence <- function(parameters = NULL, parameter_catalog = NULL, parameter_table = NULL, ...) {
              list(
                list(
                  id = "param-aware-uncertainty",
                  kind = "sensitivity-analysis",
                  status = if (!is.null(parameters) && !is.null(parameter_catalog) && !is.null(parameter_table)) "declared" else "failed",
                  value = as.numeric(parameters[["Dose|Value"]] %||% NA_real_),
                  lowerBound = length(parameter_catalog %||% list()),
                  upperBound = length((parameter_table$rows %||% list())),
                  summary = "Hook received current runtime parameter context."
                )
              )
            }
            record <- list(
              backend = "rxode2",
              simulation_id = "uncertainty-test",
              file_path = "/tmp/example_model.R",
              metadata = list(name = "Example uncertainty model", backend = "rxode2"),
              profile = list(
                uncertainty = list(status = "partially-characterized")
              ),
              capabilities = list(scientificProfile = TRUE),
              module_env = module_env,
              parameters = list("Dose|Value" = 42),
              parameter_catalog = list(
                list(path = "Dose|Value", unit = "mg", display_name = "Dose"),
                list(path = "Simulation|EndTime", unit = "h", display_name = "End time")
              )
            )
            record_uncertainty_evidence(record, limit = 10)
            """
        )

        self.assertEqual(payload["source"], "pbpk_uncertainty_evidence")
        self.assertEqual(payload["returnedRows"], 1)
        self.assertEqual(payload["rows"][0]["id"], "param-aware-uncertainty")
        self.assertEqual(payload["rows"][0]["status"], "declared")
        self.assertEqual(payload["rows"][0]["value"], 42)
        self.assertEqual(payload["rows"][0]["lowerBound"], 2)
        self.assertEqual(payload["rows"][0]["upperBound"], 2)

    def test_record_uncertainty_evidence_reads_companion_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "example_model.R"
            model_path.write_text("# example model", encoding="utf-8")
            (root / "example_model.uncertainty.json").write_text(
                json.dumps(
                    {
                        "metadata": {
                            "bundleVersion": "pbpk-uncertainty-evidence.v1",
                            "summary": "Example uncertainty bundle",
                        },
                        "rows": [
                            {
                                "id": "variability-summary",
                                "kind": "variability-propagation",
                                "status": "declared",
                                "method": "bounded sampling",
                                "metric": "AUC0-tlast",
                                "lowerBound": 9.2,
                                "upperBound": 12.4,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = run_r_json(
                f"""
                record <- list(
                  backend = "rxode2",
                  simulation_id = "example-sidecar",
                  file_path = {json.dumps(str(model_path))},
                  metadata = list(name = "Example model"),
                  profile = list(uncertainty = list(status = "partially-characterized")),
                  capabilities = list(scientificProfile = TRUE),
                  parameters = list(),
                  parameter_catalog = list()
                )
                record_uncertainty_evidence(record, limit = 10)
                """
            )

        self.assertEqual(payload["source"], "uncertainty-evidence-sidecar")
        self.assertEqual(payload["returnedRows"], 1)
        self.assertEqual(payload["rows"][0]["id"], "variability-summary")
        self.assertEqual(payload["bundleMetadata"]["bundleVersion"], "pbpk-uncertainty-evidence.v1")
        self.assertEqual(payload["issueCount"], 0)

    def test_record_uncertainty_evidence_reports_semantic_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "example_model.R"
            model_path.write_text("# example model", encoding="utf-8")
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

            payload = run_r_json(
                f"""
                record <- list(
                  backend = "rxode2",
                  simulation_id = "example-sidecar",
                  file_path = {json.dumps(str(model_path))},
                  metadata = list(name = "Example model"),
                  profile = list(uncertainty = list(status = "partially-characterized")),
                  capabilities = list(scientificProfile = TRUE),
                  parameters = list(),
                  parameter_catalog = list()
                )
                record_uncertainty_evidence(record, limit = 10)
                """
            )

        issue_codes = {entry["code"] for entry in payload["issues"]}
        self.assertIn("uncertainty_bundle_version_missing", issue_codes)
        self.assertIn("uncertainty_bundle_summary_missing", issue_codes)
        self.assertIn("uncertainty_row_summary_missing", issue_codes)
        self.assertIn("uncertainty_row_scope_missing", issue_codes)
        self.assertGreaterEqual(payload["issueCount"], 4)

    def test_record_uncertainty_evidence_warns_for_unquantified_variability_propagation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "example_model.R"
            model_path.write_text("# example model", encoding="utf-8")
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

            payload = run_r_json(
                f"""
                record <- list(
                  backend = "rxode2",
                  simulation_id = "example-sidecar-quant-gap",
                  file_path = {json.dumps(str(model_path))},
                  metadata = list(name = "Example model"),
                  profile = list(uncertainty = list(status = "partially-characterized")),
                  capabilities = list(scientificProfile = TRUE),
                  parameters = list(),
                  parameter_catalog = list()
                )
                evidence <- record_uncertainty_evidence(record, limit = 10)
                summary <- uncertainty_summary_from_record(record, evidence)
                list(
                  issues = evidence$issues,
                  semanticCoverage = summary$semanticCoverage
                )
                """
            )

        issue_codes = {entry["code"] for entry in payload["issues"]}
        self.assertIn("uncertainty_row_quantitative_signal_missing", issue_codes)
        self.assertEqual(
            payload["semanticCoverage"]["overallQuantificationStatus"],
            "declared-without-complete-quantification",
        )
        self.assertEqual(payload["semanticCoverage"]["quantifiedRowCount"], 0)
        self.assertEqual(payload["semanticCoverage"]["declaredOnlyRowCount"], 1)

    def test_cisplatin_uncertainty_evidence_includes_variability_propagation(self) -> None:
        if not has_r_package("rxode2"):
            self.skipTest("rxode2 is required for the cisplatin uncertainty hook test")
        payload = run_r_json(
            f"""
            source({json.dumps(str(CISPLATIN_MODEL_PATH))})
            pbpk_uncertainty_evidence(parameters = pbpk_default_parameters())
            """
        )

        row_ids = {entry["id"] for entry in payload}
        self.assertIn("bounded-variability-propagation-summary", row_ids)
        self.assertIn("local-sensitivity-screen-summary", row_ids)
        self.assertTrue(
            any(entry.startswith("bounded-variability-propagation-") for entry in row_ids)
        )
        self.assertTrue(
            any(entry.startswith("local-sensitivity-") for entry in row_ids)
        )

    def test_build_verification_summary_runs_smoke_checks(self) -> None:
        payload = run_r_json(
            """
            module_env <- new.env(parent = emptyenv())
            module_env$pbpk_run_simulation <- function(parameters, simulation_id = NULL, run_id = NULL, request = list()) {
              list(
                metadata = list(engine = "rxode2"),
                series = list(
                  list(
                    parameter = "Plasma|Test|Concentration",
                    unit = "mg/L",
                    values = list(
                      list(time = 0, value = 1),
                      list(time = 1, value = 0.5)
                    )
                  )
                )
              )
            }
            module_env$pbpk_run_population <- function(parameters, simulation_id = NULL, cohort = list(), outputs = list(), request = list()) {
              list(
                aggregates = list(meanCmax = 1.2, meanAUC = 3.4),
                chunks = list(
                  list(
                    chunkId = "chunk-001",
                    subjectRange = c(1, cohort$size %||% 1),
                    timeRange = c(0, 24)
                  )
                ),
                metadata = list(engine = "rxode2")
              )
            }
            module_env$pbpk_run_verification_checks <- function(parameters = NULL, request = list(), parameter_catalog = NULL, parameter_table = NULL, ...) {
              list(
                list(
                  id = "parameter-unit-consistency",
                  kind = "unit-consistency",
                  status = if (!is.null(parameter_catalog) && !is.null(parameter_table) && length(parameter_table$rows %||% list()) > 0) "passed" else "failed",
                  summary = "Parameter table snapshot was available to the model-specific runtime verification hook."
                ),
                list(
                  id = "mass-balance",
                  kind = "mass-balance",
                  status = "passed",
                  summary = "Tracked amount stayed within tolerance.",
                  value = 1e-08
                ),
                list(
                  id = "solver-stability",
                  kind = "solver-stability",
                  status = "passed",
                  summary = "Refined sampling grid remained numerically stable.",
                  value = 5e-06
                )
              )
            }
            profile <- normalize_model_profile(
              list(
                contextOfUse = list(
                  scientificPurpose = "Verification test",
                  decisionContext = "Smoke validation",
                  regulatoryUse = "research-only"
                ),
                applicabilityDomain = list(
                  type = "declared-with-runtime-guardrails",
                  qualificationLevel = "research-use",
                  species = "human",
                  routes = "iv-infusion"
                ),
                modelPerformance = list(status = "limited-internal-evaluation"),
                parameterProvenance = list(
                  status = "partially-declared",
                  sourceTable = "pbpk_parameter_table",
                  coverage = "Named runtime parameters",
                  provenanceMethod = "module annotations"
                ),
                uncertainty = list(status = "partially-characterized"),
                implementationVerification = list(
                  status = "basic-internal-checks",
                  solver = "rxode2::rxSolve",
                  verifiedChecks = list("smoke test"),
                  evidence = list(
                    list(
                      id = "smoke-check",
                      status = "passed",
                      summary = "Deterministic smoke test completed"
                    )
                  )
                ),
                peerReview = list(status = "not-reported"),
                profileSource = list(
                  type = "module-self-declared",
                  path = "example_model.R"
                )
              ),
              "rxode2",
              "/tmp/example_model.R"
            )
            capabilities <- list(
              backend = "rxode2",
              deterministicSimulation = TRUE,
              populationSimulation = TRUE,
              scientificProfile = TRUE,
              applicabilityDomain = profile$applicabilityDomain
            )
            record <- list(
              backend = "rxode2",
              simulation_id = "verify-test",
              file_path = "/tmp/example_model.R",
              metadata = list(
                name = "Example verification model",
                backend = "rxode2",
                capabilities = capabilities,
                profile = profile
              ),
              profile = profile,
              capabilities = capabilities,
              module_env = module_env,
              parameters = list("Dose|Value" = 1),
              parameter_catalog = list(
                "Dose|Value" = list(
                  path = "Dose|Value",
                  unit = "mg",
                  display_name = "Dose"
                )
              )
            )
            assign("verify-test", record, envir = simulations)
            validation <- with_profile_assessment(
              list(
                ok = TRUE,
                summary = "Request is consistent with the declared profile",
                errors = list(),
                warnings = list()
              ),
              profile,
              capabilities
            )
            build_verification_summary(
              simulation_record("verify-test"),
              request = list(route = "iv-infusion", contextOfUse = "research-only"),
              validation = validation,
              include_population_smoke = TRUE,
              population_cohort = list(size = 5, seed = 42),
              population_outputs = list(aggregates = list("meanCmax"))
            )
            """
        )

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["requestedPopulationSmoke"])
        self.assertEqual(payload["qualificationState"]["state"], "research-use")

        checks = {entry["id"]: entry for entry in payload["checks"]}
        self.assertEqual(checks["preflight-validation"]["status"], "passed")
        self.assertEqual(checks["parameter-catalog"]["status"], "passed")
        self.assertEqual(checks["verification-evidence"]["status"], "passed")
        self.assertEqual(checks["deterministic-smoke"]["status"], "passed")
        self.assertEqual(checks["deterministic-integrity"]["status"], "passed")
        self.assertEqual(checks["deterministic-reproducibility"]["status"], "passed")
        self.assertEqual(checks["parameter-unit-consistency"]["status"], "passed")
        self.assertEqual(checks["mass-balance"]["status"], "passed")
        self.assertEqual(checks["solver-stability"]["status"], "passed")
        self.assertEqual(checks["population-smoke"]["status"], "passed")
        self.assertEqual(checks["deterministic-smoke"]["seriesCount"], 1)
        self.assertEqual(checks["population-smoke"]["cohortSize"], 5)
        self.assertTrue(payload["artifacts"]["deterministicResultsId"])
        self.assertTrue(payload["artifacts"]["deterministicRepeatResultsId"])
        self.assertTrue(payload["artifacts"]["populationResultsId"])

    def test_result_integrity_check_detects_decreasing_time(self) -> None:
        payload = run_r_json(
            """
            result_integrity_check(
              list(
                series = list(
                  list(
                    parameter = "Plasma|Test|Concentration",
                    unit = "mg/L",
                    values = list(
                      list(time = 0, value = 1),
                      list(time = 2, value = 0.5),
                      list(time = 1, value = 0.4)
                    )
                  )
                )
              )
            )
            """
        )

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["decreasingSeriesCount"], 1)


if __name__ == "__main__":
    unittest.main()
