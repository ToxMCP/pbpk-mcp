"""Parity validation suite for reference PBPK models."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from mcp.session_registry import registry
from mcp.tools.calculate_pk_parameters import (
    CalculatePkParametersRequest,
    CalculatePkParametersResponse,
    PkMetricGroup,
    calculate_pk_parameters,
)
from mcp.tools.load_simulation import LoadSimulationRequest, load_simulation

from ..config import AppConfig
from ..runtime.factory import build_adapter, build_population_store


class ParitySuiteError(RuntimeError):
    """Raised when parity validation fails."""


@dataclass(frozen=True)
class ExpectedMetric:
    parameter: str
    unit: str | None = None
    cmax: float | None = None
    tmax: float | None = None
    auc: float | None = None


@dataclass(frozen=True)
class ParityCase:
    case_id: str
    name: str
    model_path: Path
    sha256: str
    expected: tuple[ExpectedMetric, ...]


@dataclass
class MetricFailure:
    parameter: str
    field: str
    expected: float | None
    actual: float | None
    delta_percent: float | None


@dataclass
class ParityCaseResult:
    case: ParityCase
    iterations: int
    max_delta_percent: float
    failures: list[MetricFailure] = field(default_factory=list)
    sample_metrics: dict[str, dict[str, float | None]] | None = None

    @property
    def ok(self) -> bool:
        return not self.failures

    def to_dict(self) -> dict[str, object]:
        try:
            relative_model_path = self.case.model_path.relative_to(Path.cwd())
        except ValueError:
            relative_model_path = self.case.model_path
        return {
            "caseId": self.case.case_id,
            "name": self.case.name,
            "modelPath": str(relative_model_path),
            "sha256": self.case.sha256,
            "iterations": self.iterations,
            "maxDeltaPercent": round(self.max_delta_percent, 6),
            "failures": [
                {
                    "parameter": failure.parameter,
                    "field": failure.field,
                    "expected": failure.expected,
                    "actual": failure.actual,
                    "deltaPercent": failure.delta_percent,
                }
                for failure in self.failures
            ],
            "sampleMetrics": self.sample_metrics or {},
        }


@dataclass
class ParitySuiteResult:
    tolerance_percent: float
    iterations: int
    cases: list[ParityCaseResult]

    @property
    def ok(self) -> bool:
        return all(case.ok for case in self.cases)

    @property
    def max_delta_percent(self) -> float:
        if not self.cases:
            return 0.0
        return max(case.max_delta_percent for case in self.cases)

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iterations": self.iterations,
            "tolerancePercent": self.tolerance_percent,
            "maxDeltaPercent": round(self.max_delta_percent, 6),
            "cases": [case.to_dict() for case in self.cases],
        }


def run_parity_suite(
    *,
    iterations: int = 10,
    cases_path: Path | None = None,
    adapter_config: AppConfig | None = None,
) -> ParitySuiteResult:
    """Execute the parity suite against the configured adapter."""

    cases_path = cases_path or Path("reference/parity/expected_metrics.json")
    config = json.loads(cases_path.read_text(encoding="utf-8"))
    tolerance_percent = float(config.get("tolerancePercent", 1.0))
    cases = tuple(_parse_cases(config.get("cases", []), cases_path.parent))

    app_config = adapter_config or AppConfig()
    population_store = build_population_store(app_config)
    adapter = build_adapter(app_config, population_store=population_store)
    adapter.init()

    results: list[ParityCaseResult] = []
    try:
        for case in cases:
            case_result = _run_case(adapter, case, iterations, tolerance_percent)
            results.append(case_result)
    finally:
        adapter.shutdown()
        registry.clear()

    suite_result = ParitySuiteResult(
        tolerance_percent=tolerance_percent,
        iterations=iterations,
        cases=results,
    )
    if not suite_result.ok:
        raise ParitySuiteError("Parity suite failed")
    return suite_result


def _parse_cases(raw_cases: Sequence[dict[str, object]], base_dir: Path) -> Iterable[ParityCase]:
    repo_root = base_dir.parent.parent if base_dir.parent else base_dir
    for entry in raw_cases:
        case_id = str(entry["id"])
        name = str(entry.get("name", case_id))
        model_path = Path(entry["modelPath"])
        if not model_path.is_absolute():
            candidate = (base_dir / model_path).resolve()
            if candidate.exists():
                model_path = candidate
            else:
                model_path = (repo_root / model_path).resolve()
        sha256 = str(entry.get("sha256", "")).lower()
        expected_metrics: list[ExpectedMetric] = []
        for metric in entry.get("expectedMetrics", []):
            expected_metrics.append(
                ExpectedMetric(
                    parameter=str(metric.get("parameter")),
                    unit=metric.get("unit"),
                    cmax=_coerce_float(metric.get("cmax")),
                    tmax=_coerce_float(metric.get("tmax")),
                    auc=_coerce_float(metric.get("auc")),
                )
            )
        yield ParityCase(
            case_id=case_id,
            name=name,
            model_path=model_path,
            sha256=sha256,
            expected=tuple(expected_metrics),
        )


def _run_case(
    adapter,
    case: ParityCase,
    iterations: int,
    tolerance_percent: float,
) -> ParityCaseResult:
    tolerance = tolerance_percent / 100.0
    expected_by_parameter = {metric.parameter: metric for metric in case.expected}
    failures: list[MetricFailure] = []
    max_delta = 0.0
    sample_metrics: dict[str, dict[str, float | None]] | None = None

    if not case.model_path.is_file():
        raise ParitySuiteError(f"Model file missing: {case.model_path}")

    file_hash = hashlib.sha256(case.model_path.read_bytes()).hexdigest()
    if case.sha256 and file_hash.lower() != case.sha256.lower():
        raise ParitySuiteError(
            f"Hash mismatch for {case.case_id}: expected {case.sha256} got {file_hash}"
        )

    for iteration in range(iterations):
        registry.clear()
        request = LoadSimulationRequest(filePath=str(case.model_path), simulationId=case.case_id)
        load_simulation(adapter, request, allowed_roots=[case.model_path.parent])
        result = adapter.run_simulation_sync(case.case_id, run_id=f"{case.case_id}-run-{iteration}")
        response: CalculatePkParametersResponse = calculate_pk_parameters(
            adapter,
            CalculatePkParametersRequest(resultsId=result.results_id),
        )

        actual_by_parameter = {metric.parameter: metric for metric in response.metrics}
        sample_metrics = {
            parameter: _metric_payload(metric)
            for parameter, metric in actual_by_parameter.items()
        }

        for parameter, expected_metric in expected_by_parameter.items():
            actual_metric = actual_by_parameter.get(parameter)
            if actual_metric is None:
                failures.append(
                    MetricFailure(
                        parameter=parameter,
                        field="metric",
                        expected=None,
                        actual=None,
                        delta_percent=None,
                    )
                )
                continue

            for field_name in ("cmax", "tmax", "auc"):
                expected_value = getattr(expected_metric, field_name)
                if expected_value is None:
                    continue
                actual_value = getattr(actual_metric, field_name)
                if actual_value is None:
                    failures.append(
                        MetricFailure(
                            parameter=parameter,
                            field=field_name,
                            expected=expected_value,
                            actual=None,
                            delta_percent=None,
                        )
                    )
                    continue
                delta = _relative_delta(expected_value, actual_value)
                max_delta = max(max_delta, delta)
                if delta > tolerance:
                    failures.append(
                        MetricFailure(
                            parameter=parameter,
                            field=field_name,
                            expected=expected_value,
                            actual=actual_value,
                            delta_percent=delta * 100.0,
                        )
                    )

    return ParityCaseResult(
        case=case,
        iterations=iterations,
        max_delta_percent=max_delta * 100.0,
        failures=failures,
        sample_metrics=sample_metrics,
    )


def _metric_payload(metric: PkMetricGroup) -> dict[str, float | None]:
    return {
        "unit": metric.unit,
        "cmax": metric.cmax,
        "tmax": metric.tmax,
        "auc": metric.auc,
    }


def _relative_delta(expected: float, actual: float) -> float:
    if expected == 0:
        return abs(actual)
    return abs(actual - expected) / abs(expected)


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _default_output_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("reports/parity") / f"{timestamp}.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the PBPK parity validation suite.")
    parser.add_argument("--iterations", type=int, default=10, help="Number of runs per model")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("reference/parity/expected_metrics.json"),
        help="Path to the parity case definition JSON file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the parity results JSON (default: reports/parity/<timestamp>.json)",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Skip writing the parity results to disk",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        result = run_parity_suite(iterations=args.iterations, cases_path=args.cases)
    except ParitySuiteError as exc:
        print(f"[parity] FAILED: {exc}")
        return 1

    if not args.no_write:
        output_path = args.output or _default_output_path()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        print(f"[parity] results written to {output_path}")

    print(
        f"[parity] all {len(result.cases)} cases passed with max delta "
        f"{result.max_delta_percent:.4f}% (tolerance {result.tolerance_percent}%)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
