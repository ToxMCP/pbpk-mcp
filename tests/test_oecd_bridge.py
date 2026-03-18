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

        self.assertAlmostEqual(assessment["oecdChecklistScore"], 5 / 6, places=3)
        self.assertEqual(checklist["contextOfUse"]["status"], "declared")
        self.assertEqual(checklist["applicabilityDomain"]["status"], "declared")
        self.assertEqual(checklist["uncertaintyAndSensitivity"]["status"], "declared")
        self.assertEqual(checklist["implementationVerification"]["status"], "declared")
        self.assertEqual(checklist["peerReviewAndPriorUse"]["status"], "missing")
        self.assertEqual(checklist["reportingAndTraceability"]["status"], "declared")


if __name__ == "__main__":
    unittest.main()
