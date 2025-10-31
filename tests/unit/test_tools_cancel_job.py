"""Unit tests for the cancel_job MCP tool."""

from __future__ import annotations

import pytest

from mcp.tools.cancel_job import (
    CancelJobRequest,
    CancelJobValidationError,
    cancel_job,
)
from mcp_bridge.services.job_service import JobRecord, JobStatus


class _StubJobService:
    def __init__(self, record: JobRecord | None = None) -> None:
        self._record = record
        self.cancel_calls: list[str] = []

    def cancel_job(self, job_id: str) -> JobRecord:
        self.cancel_calls.append(job_id)
        if self._record is None or self._record.job_id != job_id:
            raise KeyError(job_id)
        return self._record


def _make_record(job_id: str) -> JobRecord:
    return JobRecord(
        job_id=job_id,
        simulation_id="sim-1",
        submitted_at=0.0,
        status=JobStatus.CANCELLED,
    )


def test_cancel_job_success() -> None:
    record = _make_record("job-123")
    service = _StubJobService(record=record)
    request = CancelJobRequest(jobId=record.job_id)

    response = cancel_job(service, request)

    assert response.job_id == record.job_id
    assert response.status == JobStatus.CANCELLED.value
    assert service.cancel_calls == [record.job_id]


def test_cancel_job_missing() -> None:
    service = _StubJobService(record=None)
    request = CancelJobRequest(jobId="missing")

    with pytest.raises(CancelJobValidationError):
        cancel_job(service, request)
