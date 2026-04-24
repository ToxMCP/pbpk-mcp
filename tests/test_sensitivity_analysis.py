from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import mcp_bridge.agent.sensitivity as sensitivity_module  # noqa: E402


class SensitivityAnalysisReportTests(unittest.TestCase):
    def test_report_carries_baseline_capture_provenance_and_failure_categories(self) -> None:
        config = sensitivity_module.SensitivityConfig(
            model_path=WORKSPACE_ROOT / "reference_models" / "reference_compound_population_rxode2_model.R",
            base_simulation_id="sens-base",
            parameters=[
                sensitivity_module.SensitivityParameterSpec(
                    path="Kidney|Volume",
                    deltas=[0.1],
                    unit="L",
                    bounds=(4.0, 6.0),
                )
            ],
        )

        baseline_scenario = sensitivity_module._Scenario(
            scenario_id="baseline",
            simulation_id="sens-base",
            parameter_path=None,
            percent_change=0.0,
            absolute_value=None,
            requested_absolute_value=None,
            bounded_by_input=False,
            run_id="sens-baseline",
        )
        perturbed_scenario = sensitivity_module._Scenario(
            scenario_id="Kidney_Volume_100",
            simulation_id="sens-base__sens_1",
            parameter_path="Kidney|Volume",
            percent_change=0.1,
            absolute_value=6.0,
            requested_absolute_value=6.6,
            bounded_by_input=True,
            run_id="sens-Kidney_Volume_100",
        )

        def fake_run_simulation(_adapter, _job_service, payload):
            if payload.simulation_id == "sens-base":
                return SimpleNamespace(job_id="job-baseline", status="queued")
            return SimpleNamespace(job_id="job-perturbed", status="queued")

        def fake_get_job_status(_job_service, request):
            if request.job_id == "job-baseline":
                return SimpleNamespace(
                    job=SimpleNamespace(
                        status="succeeded",
                        result_id="res-baseline",
                        error=None,
                    )
                )
            return SimpleNamespace(
                job=SimpleNamespace(
                    status="failed",
                    result_id=None,
                    error={"message": "solver timeout in adapter"},
                )
            )

        baseline_metrics = [
            sensitivity_module.ScenarioMetrics(
                parameter="Central|Concentration",
                unit="unitless",
                cmax=10.0,
                tmax=0.0,
                auc=14.0,
                auc0_inf=15.0,
                nca_status="derived",
            )
        ]

        with (
            patch.object(
                sensitivity_module,
                "generate_scenarios",
                return_value=(
                    [baseline_scenario, perturbed_scenario],
                    {"Kidney|Volume": 6.0},
                    {"Kidney|Volume": "L"},
                    {"Kidney|Volume": "adapter"},
                ),
            ),
            patch.object(sensitivity_module, "run_simulation", side_effect=fake_run_simulation),
            patch.object(sensitivity_module, "get_job_status", side_effect=fake_get_job_status),
            patch.object(sensitivity_module, "_calculate_pk", return_value=baseline_metrics),
            patch.object(sensitivity_module, "set_parameter_value", return_value=None),
            patch.object(sensitivity_module.time, "sleep", return_value=None),
        ):
            report = sensitivity_module.run_sensitivity_analysis(
                adapter=object(),
                job_service=object(),
                config=config,
            )

        self.assertEqual(report.baseline_parameters[0]["path"], "Kidney|Volume")
        self.assertEqual(report.baseline_parameters[0]["source"], "adapter")
        self.assertEqual(report.scientific_framing["analysis_type"], "local-oat-screen")
        self.assertEqual(report.scenarios[1].failure_category, "timeout")
        self.assertTrue(report.scenarios[1].scenario_provenance["bounded_by_input"])
        self.assertEqual(report.failure_details[0]["category"], "timeout")
        self.assertEqual(report.failures[0], "Kidney_Volume_100:failed:solver timeout in adapter")


if __name__ == "__main__":
    unittest.main()
