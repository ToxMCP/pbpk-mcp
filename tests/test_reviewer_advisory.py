from __future__ import annotations

import sys
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_bridge.reviewer_advisory import build_dossier_improvement_signals  # noqa: E402


class ReviewerAdvisoryTests(unittest.TestCase):
    def test_builds_benchmark_advisory_from_reference_model_manifest(self) -> None:
        model_path = WORKSPACE_ROOT / "reference_models" / "reference_compound_population_rxode2_model.R"

        advisory = build_dossier_improvement_signals(file_path=str(model_path))

        self.assertIsNotNone(advisory)
        self.assertTrue(advisory["advisoryOnly"])
        self.assertEqual(advisory["source"], "curationSummary.regulatoryBenchmarkReadiness")
        self.assertTrue(advisory["prioritizedSignals"])
        self.assertTrue(advisory["recommendedNextArtifacts"])


if __name__ == "__main__":
    unittest.main()
