"""MCP tool for submitting asynchronous simulation runs."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mcp.session_registry import SessionRegistryError, registry
from mcp_bridge.adapter.interface import OspsuiteAdapter
from mcp_bridge.services.job_service import JobRecord, JobService


class RunSimulationValidationError(ValueError):
    """Raised when run_simulation validation fails."""


class RunSimulationRequest(BaseModel):
    """Payload accepted by the ``run_simulation`` MCP tool."""

    model_config = ConfigDict(populate_by_name=True)

    simulation_id: str = Field(alias="simulationId", min_length=1, max_length=64)
    run_id: Optional[str] = Field(default=None, alias="runId", min_length=1, max_length=128)
    timeout_seconds: Optional[float] = Field(default=None, alias="timeoutSeconds", ge=1.0)
    max_retries: Optional[int] = Field(default=None, alias="maxRetries", ge=0)

    @field_validator("run_id")
    @classmethod
    def _trim_run_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("run_id cannot be empty when provided")
        return trimmed


class RunSimulationResponse(BaseModel):
    job_id: str = Field(alias="jobId")
    status: str
    queued_at: float = Field(alias="queuedAt")
    attempts: int = 0
    max_retries: int = Field(alias="maxRetries", default=0)
    timeout_seconds: float = Field(alias="timeoutSeconds")

    @classmethod
    def from_record(cls, record: JobRecord) -> RunSimulationResponse:
        return cls(
            jobId=record.job_id,
            status=record.status.value,
            queuedAt=record.submitted_at,
            attempts=record.attempts,
            maxRetries=record.max_retries,
            timeoutSeconds=record.timeout_seconds,
        )


def run_simulation(
    adapter: OspsuiteAdapter,
    job_service: JobService,
    payload: RunSimulationRequest,
) -> RunSimulationResponse:
    """Submit an asynchronous simulation job."""

    try:
        registry.get(payload.simulation_id)
    except SessionRegistryError as exc:
        raise RunSimulationValidationError(str(exc)) from exc

    record = job_service.submit_simulation_job(
        adapter,
        payload.simulation_id,
        run_id=payload.run_id,
        timeout_seconds=payload.timeout_seconds,
        max_retries=payload.max_retries,
    )
    return RunSimulationResponse.from_record(record)


__all__ = [
    "RunSimulationRequest",
    "RunSimulationResponse",
    "RunSimulationValidationError",
    "run_simulation",
]
