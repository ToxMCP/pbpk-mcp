"""MCP tool for retrieving asynchronous job status information."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from mcp_bridge.services.job_service import BaseJobService, JobRecord

TOOL_NAME = "get_job_status"
CONTRACT_VERSION = "pbpk-mcp.v1"


class GetJobStatusValidationError(ValueError):
    """Raised when job status lookup fails."""


class GetJobStatusRequest(BaseModel):
    """Payload accepted by the ``get_job_status`` MCP tool."""

    model_config = ConfigDict(populate_by_name=True)

    job_id: str = Field(alias="jobId", min_length=1, max_length=64)


class ResultHandlePayload(BaseModel):
    """Normalized handle for a completed asynchronous simulation result."""

    results_id: str = Field(alias="resultsId")


class JobStatusPayload(BaseModel):
    """Backward-compatible nested job payload."""

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
    external_job_id: Optional[str] = Field(default=None, alias="externalJobId")

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
            externalJobId=record.external_job_id,
        )


class GetJobStatusResponse(BaseModel):
    """Normalized MCP response for async job status lookups."""

    tool: str = TOOL_NAME
    contract_version: str = Field(default=CONTRACT_VERSION, alias="contractVersion")
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
    result_handle: Optional[ResultHandlePayload] = Field(default=None, alias="resultHandle")
    error: Optional[dict[str, object]] = None
    external_job_id: Optional[str] = Field(default=None, alias="externalJobId")
    job: JobStatusPayload

    @classmethod
    def from_record(cls, record: JobRecord) -> GetJobStatusResponse:
        nested_job = JobStatusPayload.from_record(record)
        result_handle = (
            ResultHandlePayload(resultsId=record.result_id) if record.result_id else None
        )
        return cls(
            tool=TOOL_NAME,
            contractVersion=CONTRACT_VERSION,
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
            resultHandle=result_handle,
            error=record.error,
            externalJobId=record.external_job_id,
            job=nested_job,
        )


def get_job_status(
    job_service: BaseJobService,
    payload: GetJobStatusRequest,
) -> GetJobStatusResponse:
    try:
        record = job_service.get_job(payload.job_id)
    except KeyError as exc:
        raise GetJobStatusValidationError("Job not found") from exc

    return GetJobStatusResponse.from_record(record)


__all__ = [
    "GetJobStatusRequest",
    "GetJobStatusResponse",
    "GetJobStatusValidationError",
    "JobStatusPayload",
    "ResultHandlePayload",
    "get_job_status",
]
