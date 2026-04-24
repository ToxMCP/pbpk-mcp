"""MCP tool definition for cancelling asynchronous jobs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from mcp_bridge.services.job_service import BaseJobService, JobRecord


class CancelJobValidationError(ValueError):
    """Raised when the requested job cannot be cancelled."""


class CancelJobRequest(BaseModel):
    """Payload for the ``cancel_job`` MCP tool."""

    model_config = ConfigDict(populate_by_name=True)

    job_id: str = Field(alias="jobId", min_length=1, max_length=64)


class CancelJobResponse(BaseModel):
    """Response returned after issuing a cancellation request."""

    job_id: str = Field(alias="jobId")
    status: str

    @classmethod
    def from_record(cls, record: JobRecord) -> CancelJobResponse:
        status = record.status.value if hasattr(record.status, "value") else str(record.status)
        return cls(jobId=record.job_id, status=status)


def cancel_job(job_service: BaseJobService, payload: CancelJobRequest) -> CancelJobResponse:
    """Request cancellation of a queued or running job via the job service."""

    try:
        record = job_service.cancel_job(payload.job_id)
    except KeyError as exc:
        raise CancelJobValidationError("Job not found or already terminal") from exc

    return CancelJobResponse.from_record(record)


__all__ = [
    "CancelJobRequest",
    "CancelJobResponse",
    "CancelJobValidationError",
    "cancel_job",
]
