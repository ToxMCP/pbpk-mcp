from __future__ import annotations

import json
import subprocess
import textwrap
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = WORKSPACE_ROOT / "scripts" / "ospsuite_bridge.R"


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
        self.assertEqual(payload["peerReview"]["summary"], "No external peer review")
        self.assertEqual(payload["profileSource"]["summary"], "workspace-model")

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

        self.assertAlmostEqual(assessment["oecdChecklistScore"], 6.5 / 8, places=3)
        self.assertEqual(checklist["contextOfUse"]["status"], "declared")
        self.assertEqual(checklist["applicabilityDomain"]["status"], "declared")
        self.assertEqual(checklist["modelPerformanceAndPredictivity"]["status"], "partial")
        self.assertEqual(checklist["parameterizationAndProvenance"]["status"], "declared")
        self.assertEqual(checklist["uncertaintyAndSensitivity"]["status"], "declared")
        self.assertEqual(checklist["implementationVerification"]["status"], "declared")
        self.assertEqual(checklist["peerReviewAndPriorUse"]["status"], "missing")
        self.assertEqual(checklist["reportingAndTraceability"]["status"], "declared")

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
                createdAt = "2026-03-19T00:00:00Z"
              ),
              capabilities = list(scientificProfile = TRUE),
              profile = profile,
              parameters = parameters,
              parameter_catalog = catalog
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
        self.assertEqual(payload["performanceEvidence"]["included"], True)
        self.assertEqual(payload["performanceEvidence"]["returnedRows"], 0)
        self.assertEqual(payload["parameterTable"]["source"], "parameter_catalog")
        self.assertEqual(payload["parameterTable"]["returnedRows"], 2)
        self.assertEqual(
            payload["parameterTable"]["rows"][0]["provenance_status"],
            "declared",
        )


if __name__ == "__main__":
    unittest.main()
