from __future__ import annotations

import json
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_MATRIX_PATH = WORKSPACE_ROOT / "docs" / "architecture" / "capability_matrix.json"
ALLOWED_STATUS_VALUES = {"yes", "conditional", "no"}


class CapabilityMatrixTests(unittest.TestCase):
    def test_capability_matrix_has_expected_entries(self) -> None:
        payload = json.loads(CAPABILITY_MATRIX_PATH.read_text(encoding="utf-8"))

        self.assertEqual(payload["contractVersion"], "pbpk-mcp.v1")
        entries = {entry["id"]: entry for entry in payload["entries"]}

        self.assertEqual(
            set(entries),
            {
                "pkml-transfer-file",
                "contract-complete-r-model",
                "discoverable-incomplete-r-model",
                "pksim5-project",
                "berkeley-madonna-source",
            },
        )

    def test_capability_matrix_status_values_are_controlled(self) -> None:
        payload = json.loads(CAPABILITY_MATRIX_PATH.read_text(encoding="utf-8"))
        status_fields = [
            "catalogDiscovery",
            "staticManifestValidation",
            "loadIntoSession",
            "requestValidation",
            "verification",
            "deterministicExecution",
            "populationExecution",
            "deterministicResults",
            "populationResults",
            "oecdDossierExport",
        ]

        for entry in payload["entries"]:
            for field in status_fields:
                self.assertIn(
                    entry[field],
                    ALLOWED_STATUS_VALUES,
                    f"{entry['id']} has invalid status {entry[field]!r} for {field}",
                )

    def test_runtime_supported_rows_match_expected_boundaries(self) -> None:
        payload = json.loads(CAPABILITY_MATRIX_PATH.read_text(encoding="utf-8"))
        entries = {entry["id"]: entry for entry in payload["entries"]}

        pkml = entries["pkml-transfer-file"]
        self.assertEqual(pkml["backend"], "ospsuite")
        self.assertEqual(pkml["catalogDiscovery"], "yes")
        self.assertEqual(pkml["populationExecution"], "no")
        self.assertEqual(pkml["oecdDossierExport"], "yes")

        runtime_r = entries["contract-complete-r-model"]
        self.assertEqual(runtime_r["backend"], "rxode2")
        self.assertEqual(runtime_r["catalogDiscovery"], "yes")
        self.assertEqual(runtime_r["populationExecution"], "conditional")
        self.assertEqual(runtime_r["oecdDossierExport"], "yes")

        incomplete_r = entries["discoverable-incomplete-r-model"]
        self.assertEqual(incomplete_r["catalogDiscovery"], "yes")
        self.assertEqual(incomplete_r["loadIntoSession"], "no")
        self.assertEqual(incomplete_r["oecdDossierExport"], "no")

    def test_conversion_only_rows_are_not_runtime_supported(self) -> None:
        payload = json.loads(CAPABILITY_MATRIX_PATH.read_text(encoding="utf-8"))
        entries = {entry["id"]: entry for entry in payload["entries"]}

        for entry_id in ("pksim5-project", "berkeley-madonna-source"):
            entry = entries[entry_id]
            self.assertEqual(entry["policy"], "conversion-only")
            self.assertIsNone(entry["backend"])
            self.assertEqual(entry["catalogDiscovery"], "no")
            self.assertEqual(entry["loadIntoSession"], "no")
            self.assertEqual(entry["deterministicExecution"], "no")
            self.assertEqual(entry["oecdDossierExport"], "no")


if __name__ == "__main__":
    unittest.main()
