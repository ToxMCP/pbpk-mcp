"""MCP tool for calculating basic PK parameters from simulation results."""

from __future__ import annotations

from typing import Iterable, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mcp_bridge.adapter import AdapterError
from mcp_bridge.adapter.interface import OspsuiteAdapter
from mcp_bridge.adapter.schema import SimulationResultSeries


class CalculatePkParametersValidationError(ValueError):
    """Raised when PK parameter calculation fails."""


class CalculatePkParametersRequest(BaseModel):
    """Payload accepted by the ``calculate_pk_parameters`` tool."""

    model_config = ConfigDict(populate_by_name=True)

    results_id: str = Field(alias="resultsId", min_length=1, max_length=128)
    output_path: Optional[str] = Field(default=None, alias="outputPath", min_length=1)

    @field_validator("output_path")
    @classmethod
    def _trim_output_path(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("output_path cannot be empty when provided")
        return trimmed


class PkMetricGroup(BaseModel):
    parameter: str
    unit: Optional[str] = None
    cmax: Optional[float] = None
    tmax: Optional[float] = None
    auc: Optional[float] = None


class CalculatePkParametersResponse(BaseModel):
    results_id: str = Field(alias="resultsId")
    simulation_id: str = Field(alias="simulationId")
    metrics: List[PkMetricGroup]


def calculate_pk_parameters(
    adapter: OspsuiteAdapter,
    payload: CalculatePkParametersRequest,
) -> CalculatePkParametersResponse:
    try:
        result = adapter.get_results(payload.results_id)
    except AdapterError as exc:
        raise CalculatePkParametersValidationError(str(exc)) from exc

    series = _filter_series(result.series, payload.output_path)
    if not series:
        raise CalculatePkParametersValidationError("No matching result series found")

    metrics = [_compute_metrics(entry) for entry in series if entry.values]
    if not metrics:
        raise CalculatePkParametersValidationError("No numeric values available for analysis")

    return CalculatePkParametersResponse(
        resultsId=result.results_id,
        simulationId=result.simulation_id,
        metrics=metrics,
    )


def _filter_series(
    series: Iterable[SimulationResultSeries],
    output_path: Optional[str],
) -> List[SimulationResultSeries]:
    if output_path is None:
        return list(series)
    return [entry for entry in series if entry.parameter == output_path]


def _compute_metrics(series: SimulationResultSeries) -> PkMetricGroup:
    values = sorted(series.values, key=lambda item: float(item.get("time", 0.0)))
    concentrations = [float(item.get("value", 0.0)) for item in values]
    times = [float(item.get("time", 0.0)) for item in values]

    if not concentrations:
        return PkMetricGroup(parameter=series.parameter, unit=series.unit)

    cmax = max(concentrations)
    cmax_index = concentrations.index(cmax)
    tmax = times[cmax_index] if cmax_index < len(times) else None
    auc = _trapezoidal_rule(times, concentrations)

    return PkMetricGroup(
        parameter=series.parameter,
        unit=series.unit,
        cmax=cmax,
        tmax=tmax,
        auc=auc,
    )


def _trapezoidal_rule(times: List[float], values: List[float]) -> float:
    auc = 0.0
    for idx in range(1, len(times)):
        delta_t = times[idx] - times[idx - 1]
        if delta_t < 0:
            continue
        auc += delta_t * (values[idx] + values[idx - 1]) / 2.0
    return auc


__all__ = [
    "CalculatePkParametersRequest",
    "CalculatePkParametersResponse",
    "CalculatePkParametersValidationError",
    "calculate_pk_parameters",
]
