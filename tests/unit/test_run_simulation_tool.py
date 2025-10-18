"""Unit tests for the run_simulation MCP tool."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from mcp.session_registry import registry
from mcp.tools.run_simulation import (
    RunSimulationRequest,
    RunSimulationValidationError,
    run_simulation,
)
from mcp_bridge.adapter.errors import AdapterError, AdapterErrorCode
from mcp_bridge.adapter.schema import SimulationHandle, SimulationResult
from mcp_bridge.services.job_service import JobService, JobStatus


@dataclass
class FakeAdapter:
    def run_simulation_sync(
        self,
        simulation_id: str,
        *,
        run_id: str | None = None,
    ) -> SimulationResult:
        return SimulationResult(
            results_id=f"{simulation_id}-{run_id or 'default'}",
            simulation_id=simulation_id,
            generated_at="2024-01-01T00:00:00Z",
            series=[],
        )


class FailingAdapter(FakeAdapter):
    def run_simulation_sync(
        self,
        simulation_id: str,
        *,
        run_id: str | None = None,
    ) -> SimulationResult:
        raise AdapterError(AdapterErrorCode.INTEROP_ERROR, "failure")


def _register_simulation(simulation_id: str = "sim-unit") -> None:
    handle = SimulationHandle(simulation_id=simulation_id, file_path="/tmp/model.pkml")
    registry.register(handle)


def _reset_registry() -> None:
    registry.clear()


def test_run_simulation_submits_job_successfully() -> None:
    _reset_registry()
    _register_simulation()
    adapter = FakeAdapter()
    service = JobService(max_workers=1, default_timeout=5.0)
    try:
        payload = RunSimulationRequest(simulationId="sim-unit")
        response = run_simulation(adapter, service, payload)
        record = service.wait_for_completion(response.job_id, timeout=2.0)
        assert record.status is JobStatus.SUCCEEDED
        assert record.result_id == "sim-unit-default"
    finally:
        service.shutdown()
        _reset_registry()


def test_run_simulation_validates_simulation_exists() -> None:
    _reset_registry()
    adapter = FakeAdapter()
    service = JobService()
    payload = RunSimulationRequest(simulationId="missing")
    with pytest.raises(RunSimulationValidationError):
        run_simulation(adapter, service, payload)
    service.shutdown()


def test_run_simulation_propagates_adapter_errors_after_retries() -> None:
    _reset_registry()
    _register_simulation("sim-fail")
    adapter = FailingAdapter()
    service = JobService(max_workers=1, default_timeout=0.1, max_retries=1)
    try:
        payload = RunSimulationRequest(simulationId="sim-fail")
        response = run_simulation(adapter, service, payload)
        record = service.wait_for_completion(response.job_id, timeout=2.0)
        assert record.status is JobStatus.FAILED
    finally:
        service.shutdown()
        _reset_registry()
