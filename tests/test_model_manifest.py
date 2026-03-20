from __future__ import annotations

import json
import importlib.util
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
PATCH_ROOT = WORKSPACE_ROOT / "patches"
MODEL_MANIFEST_PATH = PATCH_ROOT / "mcp_bridge" / "model_manifest.py"
spec = importlib.util.spec_from_file_location("pbpk_patch_model_manifest", MODEL_MANIFEST_PATH)
if spec is None or spec.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Unable to load patch module from {MODEL_MANIFEST_PATH}")
module = importlib.util.module_from_spec(spec)
sys.modules.setdefault("pbpk_patch_model_manifest", module)
spec.loader.exec_module(module)
validate_model_manifest = module.validate_model_manifest


class ModelManifestTests(unittest.TestCase):
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

    def test_pkml_without_sidecar_is_marked_exploratory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "example.pkml"
            model_path.write_text("<Simulation />", encoding="utf-8")

            payload = validate_model_manifest(model_path)

        manifest = payload["manifest"]
        self.assertEqual(manifest["manifestStatus"], "missing")
        self.assertEqual(manifest["qualificationState"]["state"], "exploratory")
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
