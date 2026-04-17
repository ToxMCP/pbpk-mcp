from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp.tools.calculate_pk_parameters import (  # noqa: E402
    CalculatePkParametersRequest,
    calculate_pk_parameters,
)
from mcp_bridge.adapter.schema import SimulationResult  # noqa: E402


class _AdapterStub:
    def __init__(self, result: SimulationResult) -> None:
        self._result = result

    def get_results(self, _results_id: str) -> SimulationResult:
        return self._result


class CalculatePkParametersTests(unittest.TestCase):
    def _build_result(self, *, values: list[tuple[float, float]], metadata: dict[str, object] | None = None) -> SimulationResult:
        return SimulationResult.model_validate(
            {
                "results_id": "res-1",
                "simulation_id": "sim-1",
                "generated_at": "2026-04-11T00:00:00Z",
                "metadata": metadata or {},
                "series": [
                    {
                        "parameter": "Central|Concentration",
                        "unit": "unitless",
                        "values": [{"time": time, "value": value} for time, value in values],
                    }
                ],
            }
        )

    def test_calculate_pk_parameters_supports_existing_two_argument_call_pattern(self) -> None:
        result = self._build_result(values=[(0.0, 10.0), (1.0, 5.0), (2.0, 2.5), (3.0, 1.25), (4.0, 0.625)])
        response = calculate_pk_parameters(
            _AdapterStub(result),
            CalculatePkParametersRequest(resultsId="res-1"),
        )

        self.assertEqual(response.results_id, "res-1")
        self.assertEqual(len(response.metrics), 1)

    def test_log_linear_tail_emits_richer_nca_metrics(self) -> None:
        result = self._build_result(
            values=[(0.0, 10.0), (1.0, 5.0), (2.0, 2.5), (3.0, 1.25), (4.0, 0.625)],
            metadata={
                "ncaDoseContext": {
                    "doseAmount": 100.0,
                    "doseUnitBasis": "unitless",
                    "outputPath": "Central|Concentration",
                }
            },
        )
        response = calculate_pk_parameters(
            _AdapterStub(result),
            CalculatePkParametersRequest(resultsId="res-1"),
        )
        metric = response.metrics[0]

        self.assertAlmostEqual(metric.auc, 14.0625, places=6)
        self.assertAlmostEqual(metric.lambda_z or 0.0, math.log(2.0), places=6)
        self.assertAlmostEqual(metric.half_life or 0.0, 1.0, places=6)
        self.assertAlmostEqual(metric.auc0_inf or 0.0, 14.964184, places=5)
        self.assertAlmostEqual(metric.auc_extrapolated_percent or 0.0, 6.025617, places=5)
        self.assertEqual(metric.terminal_phase_point_count, 5)
        self.assertEqual(metric.nca_status, "derived")
        self.assertEqual(metric.nca_warnings, [])
        self.assertAlmostEqual(metric.clearance or 0.0, 100.0 / (metric.auc0_inf or 1.0), places=6)
        self.assertAlmostEqual(
            metric.volume_distribution or 0.0,
            (metric.clearance or 0.0) / (metric.lambda_z or 1.0),
            places=6,
        )

    def test_non_monotonic_tail_suppresses_terminal_phase_metrics(self) -> None:
        result = self._build_result(values=[(0.0, 10.0), (1.0, 6.0), (2.0, 4.0), (3.0, 4.3), (4.0, 4.1)])
        response = calculate_pk_parameters(
            _AdapterStub(result),
            CalculatePkParametersRequest(resultsId="res-1"),
        )
        metric = response.metrics[0]

        self.assertIsNone(metric.auc0_inf)
        self.assertIsNone(metric.lambda_z)
        self.assertEqual(metric.nca_status, "suppressed")
        self.assertTrue(any("Terminal-phase fit suppressed" in warning for warning in metric.nca_warnings))

    def test_unsorted_points_are_sorted_before_auc_and_tmax(self) -> None:
        result = self._build_result(values=[(3.0, 1.25), (0.0, 10.0), (2.0, 2.5), (1.0, 5.0)])
        response = calculate_pk_parameters(
            _AdapterStub(result),
            CalculatePkParametersRequest(resultsId="res-1"),
        )
        metric = response.metrics[0]

        self.assertEqual(metric.tmax, 0.0)
        self.assertAlmostEqual(metric.auc, 13.125, places=6)

    def test_terminal_phase_requires_three_positive_points(self) -> None:
        result = self._build_result(values=[(0.0, 10.0), (1.0, 5.0)])
        response = calculate_pk_parameters(
            _AdapterStub(result),
            CalculatePkParametersRequest(resultsId="res-1"),
        )
        metric = response.metrics[0]

        self.assertIsNone(metric.auc0_inf)
        self.assertEqual(metric.nca_status, "suppressed")
        self.assertTrue(any("fewer than three positive tail points" in warning for warning in metric.nca_warnings))


if __name__ == "__main__":
    unittest.main()
