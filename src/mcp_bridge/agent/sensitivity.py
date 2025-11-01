"""Utilities for running parameter sensitivity analyses via MCP tools."""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field

from mcp import (
    CalculatePkParametersRequest,
    GetJobStatusRequest,
    GetParameterValueRequest,
    RunSimulationRequest,
    SetParameterValueRequest,
    calculate_pk_parameters,
    get_job_status,
    get_parameter_value,
    run_simulation,
    set_parameter_value,
)
from mcp.session_registry import registry
from mcp.tools.get_parameter_value import GetParameterValueValidationError
from mcp.tools.load_simulation import LoadSimulationRequest, load_simulation
from mcp_bridge.services.job_service import BaseJobService, JobStatus


class SensitivityAnalysisError(RuntimeError):
    """Raised when the sensitivity workflow cannot complete."""


class SensitivityParameterSpec(BaseModel):
    """Configuration describing a single sensitivity parameter."""

    path: str
    deltas: Sequence[float] = Field(..., description="Percentage deltas (e.g. 0.25 = +25%).")
    unit: Optional[str] = None
    bounds: Optional[Tuple[float, float]] = None
    baseline_value: Optional[float] = Field(
        default=None,
        description="Optional baseline value when the adapter cannot provide one.",
    )


class SensitivityConfig(BaseModel):
    """Top-level configuration for a sensitivity analysis run."""

    model_config = ConfigDict(protected_namespaces=())

    model_path: Path
    base_simulation_id: str = Field(..., min_length=1, max_length=64)
    parameters: Sequence[SensitivityParameterSpec]
    include_baseline: bool = True
    poll_interval_seconds: float = 0.25
    job_timeout_seconds: Optional[float] = None
    metrics: Optional[Sequence[str]] = None


class ScenarioMetrics(BaseModel):
    """PK metrics captured for a single parameter output."""

    parameter: str
    unit: Optional[str] = None
    cmax: Optional[float] = None
    tmax: Optional[float] = None
    auc: Optional[float] = None


class ScenarioReport(BaseModel):
    """Summary of a single sensitivity scenario run."""

    model_config = ConfigDict(protected_namespaces=())

    scenario_id: str
    simulation_id: str
    parameter_path: Optional[str]
    percent_change: float
    absolute_value: Optional[float]
    job_id: str
    job_status: str
    run_id: Optional[str] = None
    results_id: Optional[str] = None
    error: Optional[str] = None
    metrics: List[ScenarioMetrics] = Field(default_factory=list)
    delta_percent: Dict[str, Dict[str, Optional[float]]] = Field(default_factory=dict)


class SensitivityAnalysisReport(BaseModel):
    """Aggregated report for an entire sensitivity analysis run."""

    model_config = ConfigDict(protected_namespaces=())

    simulation_id: str
    model_path: Path
    baseline_metrics: List[ScenarioMetrics] = Field(default_factory=list)
    scenarios: List[ScenarioReport]
    failures: List[str] = Field(default_factory=list)


class _Scenario(BaseModel):
    scenario_id: str
    simulation_id: str
    parameter_path: Optional[str]
    percent_change: float
    absolute_value: Optional[float]
    run_id: Optional[str]
    job_id: Optional[str] = None
    job_status: Optional[str] = None
    results_id: Optional[str] = None
    error: Optional[str] = None


def _slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)


def _clamp(value: float, bounds: Optional[Tuple[float, float]]) -> float:
    if not bounds:
        return value
    lower, upper = bounds
    return max(lower, min(upper, value))


def _metric_map(metrics: List[ScenarioMetrics]) -> Dict[str, ScenarioMetrics]:
    return {metric.parameter: metric for metric in metrics}


def _calculate_pk(adapter, results_id: str, output_path: Optional[str]) -> List[ScenarioMetrics]:
    payload = CalculatePkParametersRequest(resultsId=results_id, outputPath=output_path)
    response = calculate_pk_parameters(adapter, payload)
    summaries = []
    for metric in response.metrics:
        summaries.append(
            ScenarioMetrics(
                parameter=metric.parameter,
                unit=getattr(metric, "unit", None),
                cmax=getattr(metric, "cmax", None),
                tmax=getattr(metric, "tmax", None),
                auc=getattr(metric, "auc", None),
            )
        )
    return summaries


def _percentage_change(baseline: Optional[float], current: Optional[float]) -> Optional[float]:
    if baseline is None or current is None:
        return None
    if math.isclose(baseline, 0.0, abs_tol=1e-12):
        return None
    return (current - baseline) / baseline * 100.0


def _ensure_simulation_loaded(adapter, model_path: Path, simulation_id: str) -> None:
    if registry.contains(simulation_id):
        return
    load_simulation(
        adapter,
        LoadSimulationRequest(filePath=str(model_path), simulationId=simulation_id),
    )


def generate_scenarios(
    adapter,
    config: SensitivityConfig,
) -> Tuple[List[_Scenario], Dict[str, float], Dict[str, str]]:
    """Prepare scenarios and baseline metadata.

    Returns a tuple containing scenarios, baseline values, and baseline units.
    """

    _ensure_simulation_loaded(adapter, config.model_path, config.base_simulation_id)

    baseline_values: Dict[str, float] = {}
    baseline_units: Dict[str, str] = {}
    for spec in config.parameters:
        try:
            response = get_parameter_value(
                adapter,
                GetParameterValueRequest(
                    simulationId=config.base_simulation_id,
                    parameterPath=spec.path,
                ),
            )
            baseline_values[spec.path] = response.parameter.value
            baseline_units[spec.path] = response.parameter.unit
        except GetParameterValueValidationError as exc:
            if spec.baseline_value is None:
                raise SensitivityAnalysisError(
                    f"Baseline value unavailable for parameter '{spec.path}'"
                ) from exc
            baseline_values[spec.path] = spec.baseline_value
            baseline_units[spec.path] = spec.unit or ""

    scenarios: List[_Scenario] = []
    counter = 0

    if config.include_baseline:
        scenarios.append(
            _Scenario(
                scenario_id="baseline",
                simulation_id=config.base_simulation_id,
                parameter_path=None,
                percent_change=0.0,
                absolute_value=None,
                run_id=f"sens-baseline-{_slugify(config.base_simulation_id)}",
            )
        )

    for spec in config.parameters:
        base_value = baseline_values[spec.path]
        for delta in spec.deltas:
            counter += 1
            absolute = base_value * (1.0 + delta)
            absolute = _clamp(absolute, spec.bounds)
            scenario_id = f"{_slugify(spec.path)}_{int(delta*1000)}"
            simulation_id = f"{config.base_simulation_id}__sens_{counter}"
            _ensure_simulation_loaded(adapter, config.model_path, simulation_id)
            scenarios.append(
                _Scenario(
                    scenario_id=scenario_id,
                    simulation_id=simulation_id,
                    parameter_path=spec.path,
                    percent_change=delta,
                    absolute_value=absolute,
                    run_id=f"sens-{scenario_id}",
                )
            )

    return scenarios, baseline_values, baseline_units


def run_sensitivity_analysis(
    adapter,
    job_service: BaseJobService,
    config: SensitivityConfig,
) -> SensitivityAnalysisReport:
    """Execute the sensitivity analysis workflow and return a structured report."""

    if not config.parameters:
        raise SensitivityAnalysisError(
            "Sensitivity configuration must include at least one parameter"
        )

    scenarios, baseline_values, baseline_units = generate_scenarios(adapter, config)

    job_to_scenario: Dict[str, _Scenario] = {}

    for scenario in scenarios:
        if scenario.parameter_path and scenario.absolute_value is not None:
            set_parameter_value(
                adapter,
                SetParameterValueRequest(
                    simulationId=scenario.simulation_id,
                    parameterPath=scenario.parameter_path,
                    value=scenario.absolute_value,
                    unit=baseline_units.get(scenario.parameter_path),
                ),
            )

        response = run_simulation(
            adapter,
            job_service,
            RunSimulationRequest(
                simulationId=scenario.simulation_id,
                runId=scenario.run_id,
            ),
        )
        scenario.job_id = response.job_id
        scenario.job_status = response.status
        job_to_scenario[response.job_id] = scenario

    pending = set(job_to_scenario.keys())
    deadline = time.time() + config.job_timeout_seconds if config.job_timeout_seconds else None

    while pending:
        for job_id in list(pending):
            status = get_job_status(job_service, GetJobStatusRequest(jobId=job_id)).job
            scenario = job_to_scenario[job_id]
            scenario.job_status = status.status
            scenario.results_id = status.result_id
            scenario.error = (status.error or {}).get("message") if status.error else None
            if status.status not in {JobStatus.QUEUED.value, JobStatus.RUNNING.value}:
                pending.remove(job_id)

        if pending:
            if deadline and time.time() >= deadline:
                raise SensitivityAnalysisError(
                    "Sensitivity analysis timed out waiting for jobs: " + ", ".join(sorted(pending))
                )
            time.sleep(max(0.05, config.poll_interval_seconds))

    baseline_metrics: List[ScenarioMetrics] = []
    baseline_metric_map: Dict[str, ScenarioMetrics] = {}
    reports: List[ScenarioReport] = []
    failures: List[str] = []

    for scenario in scenarios:
        metrics: List[ScenarioMetrics] = []
        if scenario.results_id and scenario.job_status == JobStatus.SUCCEEDED.value:
            metrics = _calculate_pk(adapter, scenario.results_id, None)
        elif scenario.job_status != JobStatus.SUCCEEDED.value:
            failures.append(
                f"{scenario.scenario_id}:{scenario.job_status}:{scenario.error or 'unknown'}"
            )

        if scenario.scenario_id == "baseline":
            baseline_metrics = metrics
            baseline_metric_map = _metric_map(metrics)

        reports.append(
            ScenarioReport(
                scenario_id=scenario.scenario_id,
                simulation_id=scenario.simulation_id,
                parameter_path=scenario.parameter_path,
                percent_change=scenario.percent_change,
                absolute_value=scenario.absolute_value,
                job_id=scenario.job_id or "",
                job_status=scenario.job_status or JobStatus.FAILED.value,
                run_id=scenario.run_id,
                results_id=scenario.results_id,
                error=scenario.error,
                metrics=metrics,
                delta_percent={},
            )
        )

    for report in reports:
        if not baseline_metrics or not report.metrics:
            continue
        deltas_for_report: Dict[str, Dict[str, Optional[float]]] = {}
        for metric in report.metrics:
            baseline_metric = baseline_metric_map.get(metric.parameter)
            if not baseline_metric:
                continue
            deltas_for_report[metric.parameter] = {
                "cmax": _percentage_change(baseline_metric.cmax, metric.cmax),
                "tmax": _percentage_change(baseline_metric.tmax, metric.tmax),
                "auc": _percentage_change(baseline_metric.auc, metric.auc),
            }
        report.delta_percent = deltas_for_report

    return SensitivityAnalysisReport(
        simulation_id=config.base_simulation_id,
        model_path=config.model_path,
        baseline_metrics=baseline_metrics,
        scenarios=reports,
        failures=failures,
    )


__all__ = [
    "SensitivityAnalysisError",
    "SensitivityAnalysisReport",
    "SensitivityConfig",
    "SensitivityParameterSpec",
    "ScenarioReport",
    "generate_scenarios",
    "run_sensitivity_analysis",
]
