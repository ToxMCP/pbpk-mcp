from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ValidateModelManifestsScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.script = self.repo_root / "scripts" / "validate_model_manifests.py"

    def _run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.script), *args],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

    def _base_profile(self) -> dict[str, object]:
        return {
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

    def test_require_explicit_ngra_rejects_valid_manifest_with_implicit_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "implicit-example.pkml"
            model_path.write_text("<Simulation />", encoding="utf-8")
            (root / "implicit-example.profile.json").write_text(
                json.dumps(self._base_profile()),
                encoding="utf-8",
            )

            completed = self._run_script(
                "--path",
                str(model_path),
                "--require-explicit-ngra",
            )

        self.assertEqual(completed.returncode, 1, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["summary"]["valid"], 1)
        self.assertEqual(payload["summary"]["explicitNgraDeclarations"], 0)
        self.assertTrue(payload["gating"]["failed"])
        self.assertEqual(payload["gating"]["failureCount"], 1)
        failure = payload["gating"]["failures"][0]
        self.assertEqual(failure["manifestStatus"], "valid")
        self.assertEqual(failure["failureCodes"], ["implicit_ngra_boundaries"])
        self.assertEqual(
            failure["missingNgraDeclarations"],
            ["workflowRole", "populationSupport", "evidenceBasis", "workflowClaimBoundaries"],
        )

    def test_require_explicit_ngra_accepts_explicit_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "explicit-example.pkml"
            model_path.write_text("<Simulation />", encoding="utf-8")
            profile = self._base_profile()
            profile["profile"].update(
                {
                    "workflowRole": {
                        "role": "pbpk-substrate",
                        "supports": ["exposure-translation"],
                    },
                    "populationSupport": {
                        "species": ["human"],
                        "lifeStage": ["adult"],
                        "variabilityRepresentation": "defaulted",
                    },
                    "evidenceBasis": {
                        "directInVivoSupport": "not-declared",
                        "iviveLinkage": "not-declared",
                    },
                    "workflowClaimBoundaries": {
                        "supportsReverseDosimetry": False,
                        "supportsForwardDosimetry": False,
                    },
                }
            )
            (root / "explicit-example.profile.json").write_text(
                json.dumps(profile),
                encoding="utf-8",
            )

            completed = self._run_script(
                "--path",
                str(model_path),
                "--require-explicit-ngra",
            )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["summary"]["valid"], 1)
        self.assertEqual(payload["summary"]["explicitNgraDeclarations"], 1)
        self.assertFalse(payload["gating"]["failed"])
        self.assertEqual(payload["gating"]["failures"], [])

    def test_curated_publication_set_passes_for_bundled_models(self) -> None:
        completed = self._run_script(
            "--strict",
            "--require-explicit-ngra",
            "--curated-publication-set",
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["summary"]["valid"], 1)
        self.assertEqual(payload["summary"]["explicitNgraDeclarations"], 1)
        self.assertFalse(payload["gating"]["failed"])

    def test_strict_and_explicit_ngra_report_multiple_failure_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "missing-sidecar.pkml"
            model_path.write_text("<Simulation />", encoding="utf-8")

            completed = self._run_script(
                "--path",
                str(model_path),
                "--strict",
                "--require-explicit-ngra",
            )

        self.assertEqual(completed.returncode, 1, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["gating"]["failed"])
        self.assertEqual(
            payload["gating"]["appliedChecks"],
            ["manifestStatus=valid", "curationSummary.ngraDeclarationsExplicit=true"],
        )
        failure = payload["gating"]["failures"][0]
        self.assertEqual(failure["manifestStatus"], "missing")
        self.assertEqual(
            failure["failureCodes"],
            ["manifest_status_invalid", "implicit_ngra_boundaries"],
        )


if __name__ == "__main__":
    unittest.main()
