"""MCP tool for orchestrating multi-parameter sensitivity analyses."""

from __future__ import annotations

import base64
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mcp_bridge.agent.sensitivity import (
    ScenarioMetrics,
    SensitivityAnalysisReport,
    SensitivityConfig,
    SensitivityParameterSpec,
    run_sensitivity_analysis,
)
from mcp_bridge.services.job_service import BaseJobService

from .load_simulation import LoadSimulationValidationError, resolve_model_path


class RunSensitivityAnalysisValidationError(ValueError):
    """Raised when sensitivity analysis inputs fail validation."""


class SensitivityParameterModel(BaseModel):
    """Input schema describing a single sensitivity parameter."""

    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    path: str
    deltas: List[float] = Field(..., min_length=1)
    unit: Optional[str] = None
    bounds: Optional[tuple[float, float]] = None
    baseline_value: Optional[float] = Field(default=None, alias="baselineValue")

    @field_validator("path")
    @classmethod
    def _normalize_path(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Parameter path cannot be empty")
        return trimmed

    @field_validator("deltas")
    @classmethod
    def _validate_deltas(cls, values: Iterable[float]) -> List[float]:
        normalized: List[float] = []
        for item in values:
            if not isinstance(item, (int, float)):
                raise ValueError("Sensitivity deltas must be numeric")
            normalized.append(float(item))
        if not normalized:
            raise ValueError("At least one delta must be provided")
        return normalized


class RunSensitivityAnalysisRequest(BaseModel):
    """Payload accepted by the ``run_sensitivity_analysis`` MCP tool."""

    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    model_path: str = Field(alias="modelPath")
    simulation_id: str = Field(alias="simulationId", min_length=1, max_length=64)
    parameters: List[SensitivityParameterModel] = Field(min_length=1)
    include_baseline: bool = Field(default=True, alias="includeBaseline")
    poll_interval_seconds: float = Field(default=0.25, alias="pollIntervalSeconds", ge=0.05, le=5.0)
    job_timeout_seconds: Optional[float] = Field(default=None, alias="jobTimeoutSeconds", gt=0)
    metrics: Optional[List[str]] = None

    @field_validator("model_path")
    @classmethod
    def _validate_model_path(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("modelPath must be provided")
        return trimmed


class CsvAttachment(BaseModel):
    """Metadata describing the generated CSV attachment."""

    filename: str
    contentType: str = Field(default="text/csv")
    data: str = Field(description="Base64-encoded CSV payload")
    path: str = Field(description="Filesystem location of the generated CSV artefact")


class RunSensitivityAnalysisResponse(BaseModel):
    """Structured MCP response for the sensitivity analysis tool."""

    report: Dict[str, object]
    csv: CsvAttachment


@dataclass
class _CsvRow:
    scenario_id: str
    parameter_path: Optional[str]
    percent_change: Optional[float]
    absolute_value: Optional[float]
    job_status: str
    error: Optional[str]
    metric: str
    unit: Optional[str]
    cmax: Optional[float]
    tmax: Optional[float]
    auc: Optional[float]
    delta_cmax_percent: Optional[float]
    delta_tmax_percent: Optional[float]
    delta_auc_percent: Optional[float]


def _build_parameter_specs(
    parameters: Iterable[SensitivityParameterModel],
) -> List[SensitivityParameterSpec]:
    specs: List[SensitivityParameterSpec] = []
    for item in parameters:
        specs.append(
            SensitivityParameterSpec(
                path=item.path,
                deltas=item.deltas,
                unit=item.unit,
                bounds=item.bounds,
                baseline_value=item.baseline_value,
            )
        )
    return specs


def _metric_lookup(metrics: List[ScenarioMetrics]) -> Dict[str, ScenarioMetrics]:
    return {metric.parameter: metric for metric in metrics}


def _format_csv(report: SensitivityAnalysisReport, *, filename_hint: str) -> tuple[str, Path]:
    rows: List[_CsvRow] = []

    for scenario in report.scenarios:
        metric_lookup = _metric_lookup(scenario.metrics)
        for parameter, metric in metric_lookup.items():
            delta_map = scenario.delta_percent.get(parameter, {})
            rows.append(
                _CsvRow(
                    scenario_id=scenario.scenario_id,
                    parameter_path=scenario.parameter_path,
                    percent_change=scenario.percent_change,
                    absolute_value=scenario.absolute_value,
                    job_status=scenario.job_status,
                    error=scenario.error,
                    metric=parameter,
                    unit=metric.unit,
                    cmax=metric.cmax,
                    tmax=metric.tmax,
                    auc=metric.auc,
                    delta_cmax_percent=delta_map.get("cmax"),
                    delta_tmax_percent=delta_map.get("tmax"),
                    delta_auc_percent=delta_map.get("auc"),
                )
            )

        # Emit an empty row when no metrics were produced so failures remain visible.
        if not metric_lookup:
            rows.append(
                _CsvRow(
                    scenario_id=scenario.scenario_id,
                    parameter_path=scenario.parameter_path,
                    percent_change=scenario.percent_change,
                    absolute_value=scenario.absolute_value,
                    job_status=scenario.job_status,
                    error=scenario.error,
                    metric="",
                    unit=None,
                    cmax=None,
                    tmax=None,
                    auc=None,
                    delta_cmax_percent=None,
                    delta_tmax_percent=None,
                    delta_auc_percent=None,
                )
            )

    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "scenario_id",
            "parameter_path",
            "percent_change",
            "absolute_value",
            "job_status",
            "error",
            "metric",
            "unit",
            "cmax",
            "tmax",
            "auc",
            "delta_cmax_percent",
            "delta_tmax_percent",
            "delta_auc_percent",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(asdict(row))

    csv_text = buffer.getvalue()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    reports_dir = Path("reports") / "sensitivity"
    reports_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{filename_hint}-{timestamp}.csv"
    output_path = reports_dir / filename
    output_path.write_text(csv_text, encoding="utf-8")
    return csv_text, output_path


def run_sensitivity_analysis_tool(
    adapter,
    job_service: BaseJobService,
    payload: RunSensitivityAnalysisRequest,
) -> RunSensitivityAnalysisResponse:
    """Execute the sensitivity analysis MCP tool."""

    try:
        resolved_path = resolve_model_path(payload.model_path)
    except LoadSimulationValidationError as exc:
        raise RunSensitivityAnalysisValidationError(str(exc)) from exc

    parameters = _build_parameter_specs(payload.parameters)
    config = SensitivityConfig(
        model_path=resolved_path,
        base_simulation_id=payload.simulation_id,
        parameters=parameters,
        include_baseline=payload.include_baseline,
        poll_interval_seconds=payload.poll_interval_seconds,
        job_timeout_seconds=payload.job_timeout_seconds,
        metrics=payload.metrics,
    )

    if not config.parameters:
        raise RunSensitivityAnalysisValidationError(
            "Sensitivity configuration must include parameters"
        )

    report = run_sensitivity_analysis(adapter, job_service, config)
    csv_text, csv_path = _format_csv(report, filename_hint=payload.simulation_id)
    csv_data = base64.b64encode(csv_text.encode("utf-8")).decode("ascii")

    return RunSensitivityAnalysisResponse(
        report=report.model_dump(mode="json"),
        csv=CsvAttachment(
            filename=csv_path.name,
            data=csv_data,
            path=str(csv_path.resolve()),
        ),
    )


__all__ = [
    "CsvAttachment",
    "RunSensitivityAnalysisRequest",
    "RunSensitivityAnalysisResponse",
    "RunSensitivityAnalysisValidationError",
    "run_sensitivity_analysis_tool",
]
