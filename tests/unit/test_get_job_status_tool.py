"""Unit tests for the get_job_status MCP tool."""

from __future__ import annotations

import pytest

from mcp.tools.get_job_status import (
    GetJobStatusRequest,
    GetJobStatusValidationError,
    get_job_status,
)
from mcp_bridge.adapter.schema import SimulationResult
from mcp_bridge.services.job_service import JobService, JobStatus


def test_get_job_status_returns_payload() -> None:
    service = JobService()
    try:
        record = service.submit_simulation_job(adapter=_NullAdapter(), simulation_id="sim-1")
        service.wait_for_completion(record.job_id, timeout=1.0)
        response = get_job_status(service, GetJobStatusRequest(jobId=record.job_id))
        assert response.job.job_id == record.job_id
        assert response.job.status in {status.value for status in JobStatus}
    finally:
        service.shutdown()


def test_get_job_status_missing_job_raises() -> None:
    service = JobService()
    try:
        with pytest.raises(GetJobStatusValidationError):
            get_job_status(service, GetJobStatusRequest(jobId="missing"))
    finally:
        service.shutdown()


class _NullAdapter:
    def run_simulation_sync(
        self,
        simulation_id: str,
        *,
        run_id: str | None = None,
    ) -> SimulationResult:
        return SimulationResult(
            results_id=f"{simulation_id}-result",
            simulation_id=simulation_id,
            generated_at="2024-01-01T00:00:00Z",
            series=[],
        )
