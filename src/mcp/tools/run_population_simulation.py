"""MCP tool for submitting population simulation runs."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from mcp.session_registry import SessionRegistry, SessionRegistryError, registry
from mcp.tools.load_simulation import resolve_model_path
from mcp_bridge.adapter import AdapterError
from mcp_bridge.adapter.interface import OspsuiteAdapter
from mcp_bridge.adapter.schema import PopulationCohortConfig, PopulationOutputsConfig, PopulationSimulationConfig
from mcp_bridge.services.job_service import JobRecord, JobService


class RunPopulationSimulationValidationError(ValueError):
    """Raised when population simulation validation fails."""


class CohortSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    size: int = Field(..., ge=1)
    sampling: Optional[str] = None
    seed: Optional[int] = None
    covariates: list[dict[str, Any]] = Field(default_factory=list)


class OutputsSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    timeSeries: list[dict[str, Any]] = Field(default_factory=list)
    aggregates: list[str] = Field(default_factory=list)


class RunPopulationSimulationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    model_path: str = Field(alias="modelPath")
    simulation_id: str = Field(alias="simulationId", min_length=1, max_length=64)
    cohort: CohortSpec
    outputs: OutputsSpec = Field(default_factory=OutputsSpec)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: Optional[float] = Field(default=None, alias="timeoutSeconds", ge=1.0)
    max_retries: Optional[int] = Field(default=None, alias="maxRetries", ge=0)


class RunPopulationSimulationResponse(BaseModel):
    job_id: str = Field(alias="jobId")
    simulation_id: str = Field(alias="simulationId")
    status: str
    queued_at: float = Field(alias="queuedAt")
    timeout_seconds: float = Field(alias="timeoutSeconds")
    max_retries: int = Field(alias="maxRetries")

    @classmethod
    def from_record(cls, record: JobRecord, simulation_id: str) -> "RunPopulationSimulationResponse":
        return cls(
            jobId=record.job_id,
            simulationId=simulation_id,
            status=record.status.value,
            queuedAt=record.submitted_at,
            timeoutSeconds=record.timeout_seconds,
            maxRetries=record.max_retries,
        )


def run_population_simulation(
    adapter: OspsuiteAdapter,
    job_service: JobService,
    payload: RunPopulationSimulationRequest,
    *,
    session_store: SessionRegistry = registry,
    allowed_roots: Optional[list[str]] = None,
) -> RunPopulationSimulationResponse:
    """Submit a population simulation job and return queued metadata."""

    try:
        resolved_path = resolve_model_path(payload.model_path, allowed_roots=allowed_roots)
    except ValueError as exc:  # pragma: no cover - delegated validation
        raise RunPopulationSimulationValidationError(str(exc)) from exc

    handle = None
    if not session_store.contains(payload.simulation_id):
        try:
            handle = adapter.load_simulation(str(resolved_path), simulation_id=payload.simulation_id)
        except AdapterError as exc:
            raise RunPopulationSimulationValidationError(str(exc)) from exc
    else:
        try:
            handle = adapter.load_simulation(str(resolved_path), simulation_id=payload.simulation_id)
        except AdapterError:
            handle = None  # Already loaded; ignore duplicates.

    if handle is not None:
        try:
            session_store.register(handle, metadata=handle.metadata, allow_replace=True)
        except SessionRegistryError as exc:
            raise RunPopulationSimulationValidationError(str(exc)) from exc

    config = PopulationSimulationConfig(
        model_path=str(resolved_path),
        simulation_id=payload.simulation_id,
        cohort=PopulationCohortConfig.model_validate(payload.cohort.model_dump(by_alias=True)),
        outputs=PopulationOutputsConfig.model_validate(payload.outputs.model_dump(by_alias=True)),
        metadata=payload.metadata,
    )

    record = job_service.submit_population_job(
        adapter,
        config,
        timeout_seconds=payload.timeout_seconds,
        max_retries=payload.max_retries,
    )

    return RunPopulationSimulationResponse.from_record(record, payload.simulation_id)


__all__ = [
    "RunPopulationSimulationRequest",
    "RunPopulationSimulationResponse",
    "RunPopulationSimulationValidationError",
    "run_population_simulation",
]
