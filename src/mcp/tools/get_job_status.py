"""MCP tool for retrieving asynchronous job status information."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from mcp_bridge.services.job_service import JobRecord, JobService


class GetJobStatusValidationError(ValueError):
    """Raised when job status lookup fails."""


class GetJobStatusRequest(BaseModel):
    """Payload accepted by the ``get_job_status`` MCP tool."""

    model_config = ConfigDict(populate_by_name=True)

    job_id: str = Field(alias="jobId", min_length=1, max_length=64)


class JobStatusPayload(BaseModel):
    job_id: str = Field(alias="jobId")
    status: str
    submitted_at: Optional[float] = Field(default=None, alias="submittedAt")
    started_at: Optional[float] = Field(default=None, alias="startedAt")
    finished_at: Optional[float] = Field(default=None, alias="finishedAt")
    attempts: int = 0
    max_retries: int = Field(alias="maxRetries", default=0)
    timeout_seconds: Optional[float] = Field(default=None, alias="timeoutSeconds")
    cancel_requested: bool = Field(default=False, alias="cancelRequested")
    result_id: Optional[str] = Field(default=None, alias="resultId")
    error: Optional[dict[str, object]] = None

    @classmethod
    def from_record(cls, record: JobRecord) -> JobStatusPayload:
        return cls(
            jobId=record.job_id,
            status=record.status.value,
            submittedAt=record.submitted_at,
            startedAt=record.started_at,
            finishedAt=record.finished_at,
            attempts=record.attempts,
            maxRetries=record.max_retries,
            timeoutSeconds=record.timeout_seconds,
            cancelRequested=record.cancel_requested,
            resultId=record.result_id,
            error=record.error,
        )


class GetJobStatusResponse(BaseModel):
    job: JobStatusPayload


def get_job_status(
    job_service: JobService,
    payload: GetJobStatusRequest,
) -> GetJobStatusResponse:
    try:
        record = job_service.get_job(payload.job_id)
    except KeyError as exc:
        raise GetJobStatusValidationError("Job not found") from exc

    return GetJobStatusResponse(job=JobStatusPayload.from_record(record))


__all__ = [
    "GetJobStatusRequest",
    "GetJobStatusResponse",
    "GetJobStatusValidationError",
    "get_job_status",
]
