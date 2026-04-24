"""MCP tool for calculating PK parameters from simulation results."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Iterable, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mcp_bridge.adapter import AdapterError
from mcp_bridge.adapter.interface import OspsuiteAdapter
from mcp_bridge.adapter.schema import SimulationResult, SimulationResultSeries
from mcp_bridge.services.job_service import BaseJobService


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
    model_config = ConfigDict(populate_by_name=True)

    parameter: str
    unit: Optional[str] = None
    cmax: Optional[float] = None
    tmax: Optional[float] = None
    auc: Optional[float] = None
    auc0_inf: Optional[float] = Field(default=None, alias="auc0Inf")
    lambda_z: Optional[float] = Field(default=None, alias="lambdaZ")
    half_life: Optional[float] = Field(default=None, alias="halfLife")
    auc_extrapolated_percent: Optional[float] = Field(default=None, alias="aucExtrapolatedPercent")
    terminal_phase_point_count: Optional[int] = Field(default=None, alias="terminalPhasePointCount")
    nca_status: Optional[str] = Field(default=None, alias="ncaStatus")
    nca_warnings: List[str] = Field(default_factory=list, alias="ncaWarnings")
    clearance: Optional[float] = None
    volume_distribution: Optional[float] = Field(default=None, alias="volumeDistribution")


class CalculatePkParametersResponse(BaseModel):
    results_id: str = Field(alias="resultsId")
    simulation_id: str = Field(alias="simulationId")
    metrics: List[PkMetricGroup]


@dataclass(frozen=True)
class _TerminalPhaseFit:
    lambda_z: float
    half_life: float
    auc0_inf: float
    auc_extrapolated_percent: float
    terminal_phase_point_count: int
    warnings: tuple[str, ...] = ()


MIN_TERMINAL_PHASE_POINTS = 3
MAX_TERMINAL_PHASE_POINTS = 5
MIN_TERMINAL_PHASE_R_SQUARED = 0.98
MAX_ACCEPTABLE_AUC_EXTRAPOLATION_PERCENT = 20.0


def calculate_pk_parameters(
    adapter: OspsuiteAdapter,
    job_service: BaseJobService | CalculatePkParametersRequest | None,
    payload: CalculatePkParametersRequest | None = None,
) -> CalculatePkParametersResponse:
    if payload is None:
        payload = job_service  # type: ignore[assignment]
        job_service = None
    if not isinstance(payload, CalculatePkParametersRequest):
        raise CalculatePkParametersValidationError("PK parameter payload is required")

    result = None

    # Try fetching from job registry first (persisted results)
    if job_service is not None:
        stored_payload = job_service.get_stored_simulation_result(payload.results_id)
        if stored_payload:
            try:
                result = SimulationResult.model_validate(stored_payload)
            except ValueError:
                pass  # Malformed stored result, fallback to adapter

    # Fallback to adapter memory/backend (e.g. inmemory backend or direct R bridge)
    if result is None:
        try:
            result = adapter.get_results(payload.results_id)
        except AdapterError as exc:
            raise CalculatePkParametersValidationError(str(exc)) from exc

    series = _filter_series(result.series, payload.output_path)
    if not series:
        raise CalculatePkParametersValidationError("No matching result series found")

    metrics = [_compute_metrics(entry, result.metadata) for entry in series if entry.values]
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


def _safe_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _safe_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _series_points(series: SimulationResultSeries) -> tuple[list[float], list[float]]:
    values = sorted(
        series.values,
        key=lambda item: _safe_float(item.get("time")) if _safe_float(item.get("time")) is not None else -math.inf,
    )
    times: list[float] = []
    concentrations: list[float] = []
    for entry in values:
        time_value = _safe_float(entry.get("time"))
        concentration_value = _safe_float(entry.get("value"))
        if time_value is None or concentration_value is None:
            continue
        times.append(time_value)
        concentrations.append(concentration_value)
    return times, concentrations


def _compute_metrics(
    series: SimulationResultSeries,
    metadata: Mapping[str, object] | None = None,
) -> PkMetricGroup:
    times, concentrations = _series_points(series)

    if not concentrations:
        return PkMetricGroup(
            parameter=series.parameter,
            unit=series.unit,
            ncaStatus="not-evaluable",
            ncaWarnings=["No finite numeric concentration-time pairs were available."],
        )

    cmax = max(concentrations)
    cmax_index = concentrations.index(cmax)
    tmax = times[cmax_index] if cmax_index < len(times) else None
    auc = _trapezoidal_rule(times, concentrations)
    terminal_fit, fit_warnings = _derive_terminal_phase_fit(times, concentrations, auc)
    clearance, volume_distribution, dose_warnings = _derive_clearance_metrics(
        series.parameter,
        metadata,
        auc0_inf=terminal_fit.auc0_inf if terminal_fit else None,
        lambda_z=terminal_fit.lambda_z if terminal_fit else None,
    )
    warnings = [*fit_warnings, *dose_warnings]

    if terminal_fit is None:
        nca_status = "suppressed"
    elif warnings:
        nca_status = "warning"
    else:
        nca_status = "derived"

    return PkMetricGroup(
        parameter=series.parameter,
        unit=series.unit,
        cmax=cmax,
        tmax=tmax,
        auc=auc,
        auc0Inf=terminal_fit.auc0_inf if terminal_fit else None,
        lambdaZ=terminal_fit.lambda_z if terminal_fit else None,
        halfLife=terminal_fit.half_life if terminal_fit else None,
        aucExtrapolatedPercent=terminal_fit.auc_extrapolated_percent if terminal_fit else None,
        terminalPhasePointCount=terminal_fit.terminal_phase_point_count if terminal_fit else None,
        ncaStatus=nca_status,
        ncaWarnings=warnings,
        clearance=clearance,
        volumeDistribution=volume_distribution,
    )


def _trapezoidal_rule(times: List[float], values: List[float]) -> float:
    auc = 0.0
    for idx in range(1, len(times)):
        delta_t = times[idx] - times[idx - 1]
        if delta_t < 0:
            continue
        auc += delta_t * (values[idx] + values[idx - 1]) / 2.0
    return auc


def _is_non_increasing(values: list[float]) -> bool:
    return all(values[index] <= values[index - 1] + 1e-12 for index in range(1, len(values)))


def _log_linear_fit(times: list[float], concentrations: list[float]) -> tuple[float, float] | None:
    if len(times) != len(concentrations) or len(times) < MIN_TERMINAL_PHASE_POINTS:
        return None
    if len(set(times)) != len(times):
        return None
    log_values = [math.log(value) for value in concentrations]
    mean_time = sum(times) / len(times)
    mean_log = sum(log_values) / len(log_values)
    centered_time = [time - mean_time for time in times]
    centered_log = [value - mean_log for value in log_values]
    denominator = sum(value * value for value in centered_time)
    if math.isclose(denominator, 0.0, abs_tol=1e-12):
        return None
    slope = sum(delta_t * delta_y for delta_t, delta_y in zip(centered_time, centered_log)) / denominator
    intercept = mean_log - slope * mean_time
    fitted = [intercept + slope * time for time in times]
    residual = sum((actual - predicted) ** 2 for actual, predicted in zip(log_values, fitted))
    total = sum((actual - mean_log) ** 2 for actual in log_values)
    r_squared = 1.0 if math.isclose(total, 0.0, abs_tol=1e-12) else max(0.0, 1.0 - residual / total)
    return slope, r_squared


def _derive_terminal_phase_fit(
    times: list[float],
    concentrations: list[float],
    auc: float,
) -> tuple[_TerminalPhaseFit | None, list[str]]:
    positive_pairs = [(time, value) for time, value in zip(times, concentrations) if value > 0.0]
    if len(positive_pairs) < MIN_TERMINAL_PHASE_POINTS:
        return None, ["Terminal-phase fit suppressed: fewer than three positive tail points were available."]

    positive_times = [time for time, _ in positive_pairs]
    positive_values = [value for _, value in positive_pairs]
    candidate_sizes = range(
        MIN_TERMINAL_PHASE_POINTS,
        min(MAX_TERMINAL_PHASE_POINTS, len(positive_pairs)) + 1,
    )
    best_fit: _TerminalPhaseFit | None = None
    best_r_squared = -math.inf

    for point_count in candidate_sizes:
        tail_times = positive_times[-point_count:]
        tail_values = positive_values[-point_count:]
        if any(delta <= 0 for delta in (tail_times[idx] - tail_times[idx - 1] for idx in range(1, len(tail_times)))):
            continue
        if not _is_non_increasing(tail_values):
            continue
        fit = _log_linear_fit(tail_times, tail_values)
        if fit is None:
            continue
        slope, r_squared = fit
        if slope >= 0 or r_squared < MIN_TERMINAL_PHASE_R_SQUARED:
            continue

        lambda_z = -slope
        last_concentration = tail_values[-1]
        auc_extrapolated = last_concentration / lambda_z
        auc0_inf = auc + auc_extrapolated
        if auc0_inf <= 0:
            continue
        auc_extrapolated_percent = auc_extrapolated / auc0_inf * 100.0
        warnings: list[str] = []
        if auc_extrapolated_percent > MAX_ACCEPTABLE_AUC_EXTRAPOLATION_PERCENT:
            warnings.append(
                "AUC extrapolation exceeds 20% of AUC0Inf; treat terminal-phase estimates as screening-level only."
            )

        candidate = _TerminalPhaseFit(
            lambda_z=lambda_z,
            half_life=math.log(2.0) / lambda_z,
            auc0_inf=auc0_inf,
            auc_extrapolated_percent=auc_extrapolated_percent,
            terminal_phase_point_count=point_count,
            warnings=tuple(warnings),
        )
        if r_squared > best_r_squared or (
            math.isclose(r_squared, best_r_squared, rel_tol=1e-9, abs_tol=1e-9)
            and best_fit is not None
            and point_count > best_fit.terminal_phase_point_count
        ):
            best_fit = candidate
            best_r_squared = r_squared

    if best_fit is None:
        return None, [
            "Terminal-phase fit suppressed: the positive tail did not satisfy the monotonic log-linear screening rules."
        ]
    return best_fit, list(best_fit.warnings)


def _extract_dose_context(metadata: Mapping[str, object] | None) -> Mapping[str, object]:
    if not isinstance(metadata, Mapping):
        return {}
    for key in ("ncaDoseContext", "doseScenario", "dose", "administeredDose"):
        candidate = metadata.get(key)
        if isinstance(candidate, Mapping):
            return candidate
    return {}


def _matches_output_path(parameter: str, context: Mapping[str, object]) -> bool:
    explicit_paths = context.get("compatibleOutputPaths")
    if isinstance(explicit_paths, (list, tuple)):
        normalized_paths = {_safe_text(item) for item in explicit_paths}
        return parameter in normalized_paths or not normalized_paths
    output_path = _safe_text(context.get("outputPath"))
    return output_path is None or output_path == parameter


def _derive_clearance_metrics(
    parameter: str,
    metadata: Mapping[str, object] | None,
    *,
    auc0_inf: float | None,
    lambda_z: float | None,
) -> tuple[float | None, float | None, list[str]]:
    if auc0_inf is None or auc0_inf <= 0:
        return None, None, []

    context = _extract_dose_context(metadata)
    if not context or not _matches_output_path(parameter, context):
        return None, None, []

    dose_amount = _safe_float(
        context.get("doseAmount")
        or context.get("amount")
        or context.get("value")
    )
    if dose_amount is None or dose_amount <= 0:
        return None, None, ["Dose context was declared but did not provide a usable positive dose amount."]

    dose_unit_basis = _safe_text(context.get("doseUnitBasis"))
    if dose_unit_basis is None:
        return None, None, [
            "Dose context was declared without an explicit doseUnitBasis; clearance and volume distribution were withheld."
        ]

    clearance = dose_amount / auc0_inf
    volume_distribution = None
    if lambda_z is not None and lambda_z > 0:
        volume_distribution = clearance / lambda_z
    return clearance, volume_distribution, []


__all__ = [
    "CalculatePkParametersRequest",
    "CalculatePkParametersResponse",
    "CalculatePkParametersValidationError",
    "calculate_pk_parameters",
]
