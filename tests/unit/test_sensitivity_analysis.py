"""Tests for the sensitivity analysis workflow."""

from __future__ import annotations

from pathlib import Path

from mcp_bridge.adapter.errors import AdapterError, AdapterErrorCode
from mcp_bridge.adapter.mock import InMemoryAdapter
from mcp_bridge.agent import (
    SensitivityConfig,
    SensitivityParameterSpec,
    run_sensitivity_analysis,
)
from mcp_bridge.agent.sensitivity import SensitivityAnalysisError
from mcp_bridge.services.job_service import JobService

FIXTURE_MODEL = Path("tests/fixtures/demo.pkml").resolve()


class FailingAdapter(InMemoryAdapter):
    def run_simulation_sync(self, simulation_id: str, *, run_id: str | None = None):
        if run_id and "fail" in run_id.lower() and "baseline" not in run_id.lower():
            raise AdapterError(AdapterErrorCode.INTEROP_ERROR, "boom")
        return super().run_simulation_sync(simulation_id, run_id=run_id)


def test_run_sensitivity_analysis_success() -> None:
    adapter = InMemoryAdapter()
    adapter.init()
    job_service = JobService()

    config = SensitivityConfig(
        model_path=FIXTURE_MODEL,
        base_simulation_id="sens-base",
        parameters=[
            SensitivityParameterSpec(
                path="Organ.Liver.Weight",
                deltas=[-0.1, 0.1],
                baseline_value=75.0,
            )
        ],
    )

    try:
        report = run_sensitivity_analysis(adapter, job_service, config)
        assert len(report.scenarios) == 3
        assert not report.failures
        statuses = {scenario.job_status for scenario in report.scenarios}
        assert statuses == {"succeeded"}
        assert report.baseline_metrics, "Baseline metrics should be captured"
    finally:
        job_service.shutdown()
        adapter.shutdown()


def test_run_sensitivity_analysis_records_failures() -> None:
    adapter = FailingAdapter()
    adapter.init()
    job_service = JobService(max_workers=1)

    config = SensitivityConfig(
        model_path=FIXTURE_MODEL,
        base_simulation_id="sens-failure",
        parameters=[
            SensitivityParameterSpec(
                path="Failure.Parameter",
                deltas=[0.2],
                baseline_value=1.0,
            )
        ],
    )

    try:
        report = run_sensitivity_analysis(adapter, job_service, config)
        assert any(
            scenario.job_status == "failed"
            for scenario in report.scenarios
            if scenario.scenario_id != "baseline"
        )
        assert report.failures, "Failures list should record errors"
    finally:
        job_service.shutdown()
        adapter.shutdown()


def test_run_sensitivity_requires_parameters() -> None:
    adapter = InMemoryAdapter()
    adapter.init()
    job_service = JobService()

    config = SensitivityConfig(
        model_path=FIXTURE_MODEL,
        base_simulation_id="sens-empty",
        parameters=[],
    )

    try:
        try:
            run_sensitivity_analysis(adapter, job_service, config)
        except SensitivityAnalysisError:
            pass
        else:
            raise AssertionError("Expected SensitivityAnalysisError for missing parameters")
    finally:
        job_service.shutdown()
        adapter.shutdown()
