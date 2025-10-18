"""Unit tests for calculate_pk_parameters tool."""

from __future__ import annotations

import pytest

from mcp.tools.calculate_pk_parameters import (
    CalculatePkParametersRequest,
    CalculatePkParametersValidationError,
    calculate_pk_parameters,
)
from mcp_bridge.adapter.schema import SimulationResult, SimulationResultSeries


class AdapterStub:
    def __init__(self, result: SimulationResult) -> None:
        self._result = result

    def get_results(self, results_id: str) -> SimulationResult:
        if results_id != self._result.results_id:
            raise ValueError("Unknown results")
        return self._result


def _result_fixture() -> SimulationResult:
    return SimulationResult(
        results_id="res-1",
        simulation_id="sim-1",
        generated_at="2024-01-01T00:00:00Z",
        series=[
            SimulationResultSeries(
                parameter="Organ.Liver.Concentration",
                unit="mg/L",
                values=[
                    {"time": 0.0, "value": 0.0},
                    {"time": 1.0, "value": 1.0},
                    {"time": 2.0, "value": 0.5},
                ],
            ),
            SimulationResultSeries(
                parameter="Plasma.Concentration",
                unit="mg/L",
                values=[
                    {"time": 0.0, "value": 0.2},
                    {"time": 1.0, "value": 1.5},
                    {"time": 2.0, "value": 1.2},
                ],
            ),
        ],
    )


def test_calculate_pk_parameters_all_series() -> None:
    adapter = AdapterStub(_result_fixture())
    payload = CalculatePkParametersRequest(resultsId="res-1")
    response = calculate_pk_parameters(adapter, payload)
    assert response.results_id == "res-1"
    assert len(response.metrics) == 2
    liver_metrics = next(
        item for item in response.metrics if item.parameter == "Organ.Liver.Concentration"
    )
    assert liver_metrics.cmax == 1.0
    assert liver_metrics.tmax == 1.0
    assert liver_metrics.auc > 0


def test_calculate_pk_parameters_filtered_series() -> None:
    adapter = AdapterStub(_result_fixture())
    payload = CalculatePkParametersRequest(
        resultsId="res-1",
        outputPath="Plasma.Concentration",
    )
    response = calculate_pk_parameters(adapter, payload)
    assert len(response.metrics) == 1
    metric = response.metrics[0]
    assert metric.parameter == "Plasma.Concentration"
    assert metric.cmax == 1.5


def test_calculate_pk_parameters_missing_series_raises() -> None:
    adapter = AdapterStub(_result_fixture())
    payload = CalculatePkParametersRequest(
        resultsId="res-1",
        outputPath="Nonexistent",
    )
    with pytest.raises(CalculatePkParametersValidationError):
        calculate_pk_parameters(adapter, payload)
