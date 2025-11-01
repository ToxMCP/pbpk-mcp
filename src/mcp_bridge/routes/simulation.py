# ruff: noqa: UP006,UP007,UP035
"""Simulation-related API routes."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from mcp.tools.calculate_pk_parameters import (
    CalculatePkParametersRequest as ToolCalculatePkParametersRequest,
)
from mcp.tools.calculate_pk_parameters import (
    CalculatePkParametersValidationError,
)
from mcp.tools.calculate_pk_parameters import (
    calculate_pk_parameters as execute_calculate_pk_parameters,
)
from mcp.tools.cancel_job import (
    CancelJobRequest as ToolCancelJobRequest,
)
from mcp.tools.cancel_job import (
    CancelJobResponse as ToolCancelJobResponse,
)
from mcp.tools.cancel_job import (
    CancelJobValidationError,
)
from mcp.tools.cancel_job import (
    cancel_job as execute_cancel_job,
)
from mcp.tools.get_job_status import (
    GetJobStatusRequest as ToolGetJobStatusRequest,
)
from mcp.tools.get_job_status import (
    GetJobStatusValidationError,
)
from mcp.tools.get_job_status import (
    get_job_status as execute_get_job_status,
)
from mcp.tools.get_parameter_value import (
    GetParameterValueRequest as ToolGetParameterValueRequest,
)
from mcp.tools.get_parameter_value import (
    GetParameterValueValidationError,
)
from mcp.tools.get_parameter_value import (
    get_parameter_value as execute_get_parameter_value,
)
from mcp.tools.list_parameters import (
    ListParametersRequest as ToolListParametersRequest,
)
from mcp.tools.list_parameters import (
    ListParametersValidationError,
)
from mcp.tools.list_parameters import (
    list_parameters as execute_list_parameters,
)
from mcp.tools.load_simulation import (
    DuplicateSimulationError,
    LoadSimulationValidationError,
)
from mcp.tools.load_simulation import (
    LoadSimulationRequest as ToolLoadSimulationRequest,
)
from mcp.tools.load_simulation import (
    load_simulation as execute_load_simulation,
)
from mcp.tools.run_population_simulation import (
    RunPopulationSimulationRequest as ToolRunPopulationSimulationRequest,
)
from mcp.tools.run_population_simulation import (
    RunPopulationSimulationValidationError,
)
from mcp.tools.run_population_simulation import (
    run_population_simulation as execute_run_population_simulation,
)
from mcp.tools.run_simulation import (
    RunSimulationRequest as ToolRunSimulationRequest,
)
from mcp.tools.run_simulation import (
    RunSimulationValidationError,
)
from mcp.tools.run_simulation import (
    run_simulation as execute_run_simulation,
)
from mcp.tools.set_parameter_value import (
    SetParameterValueRequest as ToolSetParameterValueRequest,
)
from mcp.tools.set_parameter_value import (
    SetParameterValueValidationError,
)
from mcp.tools.set_parameter_value import (
    set_parameter_value as execute_set_parameter_value,
)

from ..adapter import AdapterError, OspsuiteAdapter
from ..adapter.schema import SimulationResult
from ..audit import AuditTrail
from ..dependencies import (
    get_adapter,
    get_audit_trail,
    get_job_service,
    get_population_store,
    get_session_registry,
    get_snapshot_store,
)
from ..errors import (
    ErrorCode,
    adapter_error_to_http,
    http_error,
    validation_exception,
)
from ..logging import get_logger
from ..security import require_confirmation
from ..security.auth import AuthContext, require_roles
from ..services.job_service import BaseJobService, JobStatus
from ..services.snapshot_service import capture_snapshot, restore_snapshot
from ..storage.population_store import (
    PopulationChunkNotFoundError,
    PopulationResultStore,
    PopulationStorageError,
)
from ..storage.snapshot_store import SimulationSnapshotStore
from ..util.concurrency import maybe_to_thread

router = APIRouter()
logger = get_logger(__name__)


def _should_offload(request: Request) -> bool:
    return bool(getattr(request.app.state, "adapter_offload", True))


def _to_camel(string: str) -> str:
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


def _format_snapshot_metadata(record) -> SnapshotMetadataModel:
    timestamp = record.created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return SnapshotMetadataModel(
        snapshotId=record.snapshot_id,
        simulationId=record.simulation_id,
        createdAt=timestamp,
        hash=record.hash,
    )


class LoadSimulationRequest(CamelModel):
    file_path: str = Field(alias="filePath")
    simulation_id: Optional[str] = Field(default=None, alias="simulationId")


class SimulationMetadata(CamelModel):
    name: Optional[str] = None
    model_version: Optional[str] = Field(default=None, alias="modelVersion")
    created_by: Optional[str] = Field(default=None, alias="createdBy")
    created_at: Optional[str] = Field(default=None, alias="createdAt")


class LoadSimulationResponse(CamelModel):
    simulation_id: str = Field(alias="simulationId")
    metadata: SimulationMetadata = SimulationMetadata()
    warnings: List[str] = Field(default_factory=list)


class ListParametersRequest(CamelModel):
    simulation_id: str = Field(alias="simulationId")
    search_pattern: Optional[str] = Field(default=None, alias="searchPattern")


class ListParametersResponse(CamelModel):
    parameters: List[str]


class GetParameterValueRequest(CamelModel):
    simulation_id: str = Field(alias="simulationId")
    parameter_path: str = Field(alias="parameterPath")


class ParameterValueModel(CamelModel):
    path: str
    value: float
    unit: str
    display_name: Optional[str] = Field(default=None, alias="displayName")
    last_updated_at: Optional[str] = Field(default=None, alias="lastUpdatedAt")
    source: Optional[str] = None


class ParameterValueResponse(CamelModel):
    parameter: ParameterValueModel


class SetParameterValueRequest(GetParameterValueRequest):
    value: float
    unit: Optional[str] = None
    update_mode: Optional[str] = Field(default="absolute", alias="updateMode")
    comment: Optional[str] = None


class RunSimulationRequest(CamelModel):
    simulation_id: str = Field(alias="simulationId")
    run_id: Optional[str] = Field(default=None, alias="runId")


class RunSimulationResponse(CamelModel):
    job_id: str = Field(alias="jobId")
    queued_at: str = Field(alias="queuedAt")
    estimated_duration_seconds: Optional[float] = Field(
        default=None, alias="estimatedDurationSeconds"
    )
    expires_at: Optional[str] = Field(default=None, alias="expiresAt")


class GetJobStatusRequest(CamelModel):
    job_id: str = Field(alias="jobId")


class JobProgressModel(CamelModel):
    percentage: Optional[float] = None
    message: Optional[str] = None


class JobStatusResponse(CamelModel):
    job_id: str = Field(alias="jobId")
    status: str
    progress: Optional[JobProgressModel] = None
    submitted_at: Optional[str] = Field(default=None, alias="submittedAt")
    started_at: Optional[str] = Field(default=None, alias="startedAt")
    finished_at: Optional[str] = Field(default=None, alias="finishedAt")
    attempts: int = 0
    max_retries: int = Field(default=0, alias="maxRetries")
    timeout_seconds: Optional[float] = Field(default=None, alias="timeoutSeconds")
    result_handle: Optional[dict[str, Any]] = Field(default=None, alias="resultHandle")
    error: Optional[dict[str, Any]] = None
    cancel_requested: Optional[bool] = Field(default=None, alias="cancelRequested")
    external_job_id: Optional[str] = Field(default=None, alias="externalJobId")


class SnapshotSimulationRequest(CamelModel):
    simulation_id: str = Field(alias="simulationId")


class SnapshotMetadataModel(CamelModel):
    snapshot_id: str = Field(alias="snapshotId")
    simulation_id: str = Field(alias="simulationId")
    created_at: str = Field(alias="createdAt")
    hash: str


class SnapshotSimulationResponse(CamelModel):
    snapshot: SnapshotMetadataModel


class RestoreSimulationRequest(CamelModel):
    simulation_id: str = Field(alias="simulationId")
    snapshot_id: Optional[str] = Field(default=None, alias="snapshotId")


class RestoreSimulationResponse(CamelModel):
    snapshot: SnapshotMetadataModel


class SnapshotListResponse(CamelModel):
    snapshots: List[SnapshotMetadataModel]
    latest_snapshot: Optional[SnapshotMetadataModel] = Field(default=None, alias="latestSnapshot")


class GetSimulationResultsRequest(CamelModel):
    results_id: str = Field(alias="resultsId")


class ResultSeriesModel(CamelModel):
    parameter: str
    unit: str
    values: List[dict[str, float]]


class GetSimulationResultsResponse(CamelModel):
    results_id: str = Field(alias="resultsId")
    generated_at: str = Field(alias="generatedAt")
    simulation_metadata: SimulationMetadata = Field(
        default_factory=SimulationMetadata, alias="simulationMetadata"
    )
    series: List[ResultSeriesModel]


class CalculatePkParametersRequestBody(CamelModel):
    results_id: str = Field(alias="resultsId")
    output_path: Optional[str] = Field(default=None, alias="outputPath")


class PkMetricModel(CamelModel):
    parameter: str
    unit: Optional[str] = None
    cmax: Optional[float] = Field(default=None, alias="cmax")
    tmax: Optional[float] = Field(default=None, alias="tmax")
    auc: Optional[float] = Field(default=None, alias="auc")


class CalculatePkParametersResponseBody(CamelModel):
    results_id: str = Field(alias="resultsId")
    simulation_id: str = Field(alias="simulationId")
    metrics: List[PkMetricModel]


class CohortConfig(CamelModel):
    size: int = Field(..., ge=1)
    sampling: Optional[str] = None
    seed: Optional[int] = None
    covariates: List[dict[str, Any]] = Field(default_factory=list)


class OutputsConfig(CamelModel):
    time_series: List[dict[str, Any]] = Field(default_factory=list, alias="timeSeries")
    aggregates: List[str] = Field(default_factory=list)


class RunPopulationSimulationRequest(CamelModel):
    model_config = ConfigDict(protected_namespaces=())

    model_path: str = Field(alias="modelPath")
    simulation_id: str = Field(alias="simulationId", min_length=1, max_length=64)
    cohort: CohortConfig
    outputs: OutputsConfig = Field(default_factory=OutputsConfig)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: Optional[float] = Field(default=None, alias="timeoutSeconds", ge=1.0)
    max_retries: Optional[int] = Field(default=None, alias="maxRetries", ge=0)


class RunPopulationSimulationResponse(CamelModel):
    job_id: str = Field(alias="jobId")
    simulation_id: str = Field(alias="simulationId")
    status: str
    queued_at: str = Field(alias="queuedAt")
    timeout_seconds: float = Field(alias="timeoutSeconds")
    max_retries: int = Field(alias="maxRetries")


class PopulationChunkModel(CamelModel):
    chunk_id: str = Field(alias="chunkId")
    uri: Optional[str] = None
    content_type: Optional[str] = Field(default=None, alias="contentType")
    size_bytes: Optional[int] = Field(default=None, alias="sizeBytes")
    subject_range: Optional[tuple[int, int]] = Field(default=None, alias="subjectRange")
    time_range: Optional[tuple[float, float]] = Field(default=None, alias="timeRange")
    preview: Optional[dict[str, Any]] = None


class GetPopulationResultsRequest(CamelModel):
    results_id: str = Field(alias="resultsId")


class PopulationResultsResponse(CamelModel):
    results_id: str = Field(alias="resultsId")
    simulation_id: str = Field(alias="simulationId")
    generated_at: str = Field(alias="generatedAt")
    cohort: Dict[str, Any]
    aggregates: Dict[str, float]
    chunks: List[PopulationChunkModel] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CancelJobRequest(CamelModel):
    job_id: str = Field(alias="jobId")


class CancelJobResponse(CamelModel):
    job_id: str = Field(alias="jobId")
    status: str


def _iso_timestamp(epoch: Optional[float]) -> Optional[str]:
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


async def _job_event_stream(
    job_id: str,
    job_service: BaseJobService,
    poll_interval: float = 0.25,
) -> AsyncGenerator[bytes, None]:
    last_status: Optional[str] = None
    terminal_statuses = {
        JobStatus.SUCCEEDED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value,
        JobStatus.TIMEOUT.value,
    }

    while True:
        record = job_service.get_job(job_id)
        status_value = (
            record.status.value if isinstance(record.status, JobStatus) else str(record.status)
        )
        payload = {
            "jobId": record.job_id,
            "status": status_value,
            "attempts": record.attempts,
            "maxRetries": record.max_retries,
            "timeoutSeconds": record.timeout_seconds,
            "submittedAt": _iso_timestamp(record.submitted_at),
            "startedAt": _iso_timestamp(record.started_at),
            "finishedAt": _iso_timestamp(record.finished_at),
            "resultId": record.result_id,
            "error": record.error,
        }
        if status_value != last_status:
            yield f"data: {json.dumps(payload)}\n\n".encode()
            last_status = status_value

        if status_value in terminal_statuses:
            break
        await asyncio.sleep(poll_interval)


@router.post(
    "/load_simulation", response_model=LoadSimulationResponse, status_code=status.HTTP_201_CREATED
)
async def load_simulation(
    payload: LoadSimulationRequest,
    request: Request,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    _auth: AuthContext = Depends(require_roles("operator", "admin")),
) -> LoadSimulationResponse:
    require_confirmation(request)
    try:
        tool_payload = ToolLoadSimulationRequest.model_validate(payload.model_dump(by_alias=True))
        session_store = request.app.state.session_registry
        tool_response = await maybe_to_thread(
            _should_offload(request),
            execute_load_simulation,
            adapter,
            tool_payload,
            session_store=session_store,
        )
    except DuplicateSimulationError as exc:
        logger.warning(
            "simulation.duplicate",
            simulationId=payload.simulation_id or payload.file_path,
            detail=str(exc),
        )
        raise http_error(
            status_code=status.HTTP_409_CONFLICT,
            message=str(exc),
            code=ErrorCode.CONFLICT,
            field="simulationId",
            hint="Choose a unique simulationId or omit it to let the server generate one.",
        ) from exc
    except LoadSimulationValidationError as exc:
        message = str(exc)
        key = "simulation" if "simulation" in message.lower() else "file"
        field = "simulationId" if key == "simulation" else "filePath"
        hint = (
            "Ensure the simulation is not already loaded and the identifier is unique."
            if field == "simulationId"
            else "Provide an absolute .pkml path within MCP_MODEL_SEARCH_PATHS."
        )
        logger.warning(
            "simulation.invalid",
            simulationId=payload.simulation_id or "<generated>",
            detail=message,
        )
        raise http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=message,
            code=ErrorCode.INVALID_INPUT,
            field=field,
            hint=hint,
        ) from exc
    except AdapterError as exc:
        raise adapter_error_to_http(exc) from exc

    metadata = SimulationMetadata(
        name=tool_response.metadata.name,
        modelVersion=tool_response.metadata.model_version,
        createdBy=tool_response.metadata.created_by,
        createdAt=tool_response.metadata.created_at,
    )

    logger.info(
        "simulation.loaded",
        simulationId=tool_response.simulation_id,
        filePath=payload.file_path,
    )

    return LoadSimulationResponse(
        simulationId=tool_response.simulation_id,
        metadata=metadata,
        warnings=tool_response.warnings,
    )


@router.post("/list_parameters", response_model=ListParametersResponse)
async def list_parameters(
    payload: ListParametersRequest,
    request: Request,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    _auth: AuthContext = Depends(require_roles("viewer", "operator", "admin")),
) -> ListParametersResponse:
    try:
        tool_payload = ToolListParametersRequest.model_validate(payload.model_dump(by_alias=True))
    except ValidationError as exc:
        detail_exception = validation_exception(exc, status_code=status.HTTP_400_BAD_REQUEST)
        detail = detail_exception.detail
        logger.warning(
            "simulation.parameters.invalid",
            simulationId=payload.simulation_id,
            pattern=payload.search_pattern,
            detail=detail,
        )
        raise detail_exception from exc
    offload = _should_offload(request)
    try:
        tool_response = await maybe_to_thread(
            offload,
            execute_list_parameters,
            adapter,
            tool_payload,
        )
    except ListParametersValidationError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in detail.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        logger.warning(
            "simulation.parameters.invalid",
            simulationId=payload.simulation_id,
            pattern=payload.search_pattern,
            detail=detail,
        )
        field = "simulationId" if status_code == status.HTTP_404_NOT_FOUND else "searchPattern"
        hint = (
            "Load the simulation before listing parameters."
            if status_code == status.HTTP_404_NOT_FOUND
            else "Use a glob pattern like '*Weight*' without newline characters."
        )
        code = (
            ErrorCode.NOT_FOUND
            if status_code == status.HTTP_404_NOT_FOUND
            else ErrorCode.INVALID_INPUT
        )
        raise http_error(
            status_code=status_code,
            message=detail,
            code=code,
            field=field,
            hint=hint,
        ) from exc
    except AdapterError as exc:
        raise adapter_error_to_http(exc) from exc

    logger.info(
        "simulation.parameters.listed",
        simulationId=payload.simulation_id,
        pattern=payload.search_pattern or "*",
        count=len(tool_response.parameters),
    )
    return ListParametersResponse(parameters=tool_response.parameters)


@router.post("/get_parameter_value", response_model=ParameterValueResponse)
async def get_parameter_value(
    payload: GetParameterValueRequest,
    request: Request,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    _auth: AuthContext = Depends(require_roles("viewer", "operator", "admin")),
) -> ParameterValueResponse:
    try:
        tool_payload = ToolGetParameterValueRequest.model_validate(
            payload.model_dump(by_alias=True)
        )
    except ValidationError as exc:
        detail_exception = validation_exception(exc, status_code=status.HTTP_400_BAD_REQUEST)
        detail = detail_exception.detail
        logger.warning(
            "simulation.parameter.invalid",
            simulationId=payload.simulation_id,
            parameterPath=payload.parameter_path,
            detail=detail,
        )
        raise detail_exception from exc

    try:
        tool_response = await maybe_to_thread(
            _should_offload(request),
            execute_get_parameter_value,
            adapter,
            tool_payload,
        )
    except GetParameterValueValidationError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in detail.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        logger.warning(
            "simulation.parameter.error",
            simulationId=payload.simulation_id,
            parameterPath=payload.parameter_path,
            detail=detail,
        )
        hint = (
            "Confirm the parameter path exists in the loaded simulation."
            if status_code == status.HTTP_404_NOT_FOUND
            else "Verify the parameter path uses '|' separators and valid characters."
        )
        code = (
            ErrorCode.NOT_FOUND
            if status_code == status.HTTP_404_NOT_FOUND
            else ErrorCode.INVALID_INPUT
        )
        raise http_error(
            status_code=status_code,
            message=detail,
            code=code,
            field="parameterPath",
            hint=hint,
        ) from exc
    except AdapterError as exc:
        raise adapter_error_to_http(exc) from exc

    value = tool_response.parameter
    model = ParameterValueModel(
        path=value.path,
        value=value.value,
        unit=value.unit,
        displayName=value.display_name,
        lastUpdatedAt=value.last_updated_at,
        source=value.source,
    )
    logger.info(
        "simulation.parameter.read",
        simulationId=payload.simulation_id,
        parameterPath=payload.parameter_path,
        unit=value.unit,
    )
    return ParameterValueResponse(parameter=model)


@router.post("/set_parameter_value", response_model=ParameterValueResponse)
async def set_parameter_value(
    payload: SetParameterValueRequest,
    request: Request,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    _auth: AuthContext = Depends(require_roles("operator", "admin")),
) -> ParameterValueResponse:
    require_confirmation(request)
    try:
        tool_payload = ToolSetParameterValueRequest.model_validate(
            payload.model_dump(by_alias=True)
        )
    except ValidationError as exc:
        detail_exception = validation_exception(exc, status_code=status.HTTP_400_BAD_REQUEST)
        detail = detail_exception.detail
        logger.warning(
            "simulation.parameter.invalid",
            simulationId=payload.simulation_id,
            parameterPath=payload.parameter_path,
            detail=detail,
        )
        raise detail_exception from exc

    try:
        tool_response = await maybe_to_thread(
            _should_offload(request),
            execute_set_parameter_value,
            adapter,
            tool_payload,
        )
    except SetParameterValueValidationError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in detail.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        logger.warning(
            "simulation.parameter.update.error",
            simulationId=payload.simulation_id,
            parameterPath=payload.parameter_path,
            detail=detail,
        )
        hint = (
            "Load the simulation and ensure the parameter exists before updating."
            if status_code == status.HTTP_404_NOT_FOUND
            else "Verify the value is numeric and within acceptable bounds."
        )
        code = (
            ErrorCode.NOT_FOUND
            if status_code == status.HTTP_404_NOT_FOUND
            else ErrorCode.INVALID_INPUT
        )
        raise http_error(
            status_code=status_code,
            message=detail,
            code=code,
            field="parameterPath",
            hint=hint,
        ) from exc
    except AdapterError as exc:
        raise adapter_error_to_http(exc) from exc

    value = tool_response.parameter
    model = ParameterValueModel(
        path=value.path,
        value=value.value,
        unit=value.unit,
        displayName=value.display_name,
        lastUpdatedAt=value.last_updated_at,
        source=value.source,
    )
    logger.info(
        "simulation.parameter.updated",
        simulationId=payload.simulation_id,
        parameterPath=payload.parameter_path,
        unit=value.unit,
    )
    return ParameterValueResponse(parameter=model)


@router.post(
    "/run_simulation", response_model=RunSimulationResponse, status_code=status.HTTP_202_ACCEPTED
)
async def run_simulation(
    payload: RunSimulationRequest,
    request: Request,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    job_service: BaseJobService = Depends(get_job_service),
    _auth: AuthContext = Depends(require_roles("operator", "admin")),
) -> RunSimulationResponse:
    require_confirmation(request)
    try:
        tool_payload = ToolRunSimulationRequest.model_validate(payload.model_dump(by_alias=True))
        job_response = await maybe_to_thread(
            _should_offload(request),
            execute_run_simulation,
            adapter,
            job_service,
            tool_payload,
        )
    except RunSimulationValidationError as exc:
        detail = str(exc)
        is_not_found = "not found" in detail.lower()
        status_code = status.HTTP_404_NOT_FOUND if is_not_found else status.HTTP_400_BAD_REQUEST
        hint = (
            "Load the simulation before running it."
            if is_not_found
            else "Check the simulationId and optional runId parameters."
        )
        logger.warning(
            "simulation.run.invalid",
            simulationId=payload.simulation_id,
            detail=detail,
        )
        code = ErrorCode.NOT_FOUND if is_not_found else ErrorCode.INVALID_INPUT
        raise http_error(
            status_code=status_code,
            message=detail,
            code=code,
            field="simulationId",
            hint=hint,
        ) from exc
    except AdapterError as exc:
        raise adapter_error_to_http(exc) from exc

    queued_at = _iso_timestamp(job_response.queued_at)
    assert queued_at is not None
    return RunSimulationResponse(
        jobId=job_response.job_id,
        queuedAt=queued_at,
        estimatedDurationSeconds=None,
        expiresAt=None,
    )


@router.post(
    "/run_population_simulation",
    response_model=RunPopulationSimulationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_population_simulation(
    payload: RunPopulationSimulationRequest,
    request: Request,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    job_service: BaseJobService = Depends(get_job_service),
    _auth: AuthContext = Depends(require_roles("operator", "admin")),
) -> RunPopulationSimulationResponse:
    require_confirmation(request)
    try:
        tool_payload = ToolRunPopulationSimulationRequest.model_validate(
            payload.model_dump(by_alias=True)
        )
        tool_response = await maybe_to_thread(
            _should_offload(request),
            execute_run_population_simulation,
            adapter,
            job_service,
            tool_payload,
        )
    except (RunPopulationSimulationValidationError, LoadSimulationValidationError) as exc:
        detail = str(exc)
        is_not_found = "not found" in detail.lower()
        status_code = status.HTTP_404_NOT_FOUND if is_not_found else status.HTTP_400_BAD_REQUEST
        code = ErrorCode.NOT_FOUND if is_not_found else ErrorCode.INVALID_INPUT
        hint = (
            "Load the simulation and ensure cohort definitions are valid."
            if is_not_found
            else "Validate population configuration and model path inputs."
        )
        raise http_error(
            status_code=status_code,
            message=detail,
            code=code,
            field="simulationId",
            hint=hint,
        ) from exc
    except AdapterError as exc:
        raise adapter_error_to_http(exc) from exc

    queued_at = _iso_timestamp(tool_response.queued_at)
    assert queued_at is not None
    return RunPopulationSimulationResponse(
        jobId=tool_response.job_id,
        simulationId=tool_response.simulation_id,
        status=tool_response.status,
        queuedAt=queued_at,
        timeoutSeconds=tool_response.timeout_seconds,
        maxRetries=tool_response.max_retries,
    )


@router.post("/get_job_status", response_model=JobStatusResponse)
async def get_job_status(
    payload: GetJobStatusRequest,
    job_service: BaseJobService = Depends(get_job_service),
    _auth: AuthContext = Depends(require_roles("viewer", "operator", "admin")),
) -> JobStatusResponse:
    try:
        tool_payload = ToolGetJobStatusRequest.model_validate(payload.model_dump(by_alias=True))
        tool_response = execute_get_job_status(job_service, tool_payload)
    except GetJobStatusValidationError as exc:
        detail = str(exc)
        raise http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            message=detail,
            code=ErrorCode.NOT_FOUND,
            field="jobId",
            hint="Verify the job identifier is correct and the job is still retained.",
        ) from exc

    job = tool_response.job
    return JobStatusResponse(
        jobId=job.job_id,
        status=job.status,
        submittedAt=_iso_timestamp(job.submitted_at),
        startedAt=_iso_timestamp(job.started_at),
        finishedAt=_iso_timestamp(job.finished_at),
        attempts=job.attempts,
        maxRetries=job.max_retries,
        timeoutSeconds=job.timeout_seconds,
        resultHandle={"resultsId": job.result_id} if job.result_id else None,
        error=job.error,
        cancelRequested=job.cancel_requested,
        externalJobId=job.external_job_id,
    )


@router.post(
    "/snapshot_simulation",
    response_model=SnapshotSimulationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def snapshot_simulation(
    payload: SnapshotSimulationRequest,
    request: Request,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    snapshot_store: SimulationSnapshotStore = Depends(get_snapshot_store),
    session_store=Depends(get_session_registry),
    audit: AuditTrail = Depends(get_audit_trail),
    _auth: AuthContext = Depends(require_roles("operator", "admin")),
) -> SnapshotSimulationResponse:
    if not session_store.contains(payload.simulation_id):
        raise http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"Simulation '{payload.simulation_id}' is not loaded",
            code=ErrorCode.NOT_FOUND,
            field="simulationId",
            hint="Load the simulation before capturing a baseline snapshot.",
        )

    offload = _should_offload(request)
    try:
        record = await maybe_to_thread(
            offload,
            capture_snapshot,
            adapter,
            snapshot_store,
            payload.simulation_id,
        )
    except AdapterError as exc:
        raise adapter_error_to_http(exc) from exc

    metadata = _format_snapshot_metadata(record)
    audit.record_event(
        "simulation.snapshot.created",
        {
            "simulationId": metadata.simulation_id,
            "snapshotId": metadata.snapshot_id,
            "hash": metadata.hash,
            "createdAt": metadata.created_at,
        },
    )
    logger.info(
        "simulation.snapshot.created",
        simulationId=metadata.simulation_id,
        snapshotId=metadata.snapshot_id,
    )
    return SnapshotSimulationResponse(snapshot=metadata)


@router.post("/restore_simulation", response_model=RestoreSimulationResponse)
async def restore_simulation(
    payload: RestoreSimulationRequest,
    request: Request,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    snapshot_store: SimulationSnapshotStore = Depends(get_snapshot_store),
    session_store=Depends(get_session_registry),
    audit: AuditTrail = Depends(get_audit_trail),
    _auth: AuthContext = Depends(require_roles("operator", "admin")),
) -> RestoreSimulationResponse:
    if not session_store.contains(payload.simulation_id):
        raise http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"Simulation '{payload.simulation_id}' is not loaded",
            code=ErrorCode.NOT_FOUND,
            field="simulationId",
            hint="Load the simulation before restoring a baseline snapshot.",
        )

    offload = _should_offload(request)
    try:
        record = await maybe_to_thread(
            offload,
            restore_snapshot,
            adapter,
            snapshot_store,
            payload.simulation_id,
            payload.snapshot_id,
        )
    except FileNotFoundError as exc:
        raise http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            message=str(exc),
            code=ErrorCode.NOT_FOUND,
            field="snapshotId",
            hint="Capture a snapshot before requesting a restore.",
        ) from exc
    except AdapterError as exc:
        raise adapter_error_to_http(exc) from exc

    metadata = _format_snapshot_metadata(record)
    restored_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    audit.record_event(
        "simulation.snapshot.restored",
        {
            "simulationId": metadata.simulation_id,
            "snapshotId": metadata.snapshot_id,
            "hash": metadata.hash,
            "restoredAt": restored_at,
        },
    )
    logger.info(
        "simulation.snapshot.restored",
        simulationId=metadata.simulation_id,
        snapshotId=metadata.snapshot_id,
    )
    return RestoreSimulationResponse(snapshot=metadata)


@router.get("/get_simulation_snapshot", response_model=SnapshotListResponse)
async def get_simulation_snapshot(
    simulation_id: str = Query(..., alias="simulationId", min_length=1, max_length=64),
    snapshot_store: SimulationSnapshotStore = Depends(get_snapshot_store),
    _auth: AuthContext = Depends(require_roles("viewer", "operator", "admin")),
) -> SnapshotListResponse:
    records = snapshot_store.list(simulation_id)
    snapshots = [_format_snapshot_metadata(record) for record in records]
    latest = snapshots[0] if snapshots else None
    return SnapshotListResponse(snapshots=snapshots, latestSnapshot=latest)


@router.get("/jobs/{job_id}/events")
async def stream_job_events(
    job_id: str,
    job_service: BaseJobService = Depends(get_job_service),
    _auth: AuthContext = Depends(require_roles("viewer", "operator", "admin")),
) -> StreamingResponse:
    stream = _job_event_stream(job_id, job_service)
    return StreamingResponse(stream, media_type="text/event-stream")


@router.post("/get_simulation_results", response_model=GetSimulationResultsResponse)
async def get_simulation_results(
    payload: GetSimulationResultsRequest,
    request: Request,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    job_service: BaseJobService = Depends(get_job_service),
    _auth: AuthContext = Depends(require_roles("viewer", "operator", "admin")),
) -> GetSimulationResultsResponse:
    def _format_result(result: SimulationResult) -> GetSimulationResultsResponse:
        series_models = [
            ResultSeriesModel(parameter=s.parameter, unit=s.unit, values=s.values)
            for s in result.series
        ]
        return GetSimulationResultsResponse(
            resultsId=result.results_id,
            generatedAt=result.generated_at,
            series=series_models,
        )

    try:
        results = await maybe_to_thread(
            _should_offload(request), adapter.get_results, payload.results_id
        )
        return _format_result(results)
    except AdapterError as exc:
        stored = job_service.get_stored_simulation_result(payload.results_id)
        if stored:
            return _format_result(SimulationResult.model_validate(stored))
        raise adapter_error_to_http(exc) from exc


@router.post("/get_population_results", response_model=PopulationResultsResponse)
async def get_population_results(
    payload: GetPopulationResultsRequest,
    request: Request,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    _auth: AuthContext = Depends(require_roles("viewer", "operator", "admin")),
) -> PopulationResultsResponse:
    try:
        results = await maybe_to_thread(
            _should_offload(request), adapter.get_population_results, payload.results_id
        )
    except AdapterError as exc:
        raise adapter_error_to_http(exc) from exc

    return PopulationResultsResponse(
        resultsId=results.results_id,
        simulationId=results.simulation_id,
        generatedAt=results.generated_at,
        cohort=results.cohort.model_dump(),
        aggregates=results.aggregates,
        chunks=[
            PopulationChunkModel.model_validate(chunk.model_dump())
            for chunk in results.chunk_handles
        ],
        metadata=results.metadata,
    )


@router.get(
    "/population_results/{results_id}/chunks/{chunk_id}",
    response_class=StreamingResponse,
)
async def download_population_chunk(
    results_id: str,
    chunk_id: str,
    store: PopulationResultStore = Depends(get_population_store),
    _auth: AuthContext = Depends(require_roles("viewer", "operator", "admin")),
) -> StreamingResponse:
    try:
        metadata = store.get_metadata(results_id, chunk_id)
    except PopulationChunkNotFoundError as exc:
        raise http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            message=str(exc),
            code=ErrorCode.NOT_FOUND,
            field="chunkId",
            hint="Ensure the population results are still retained on disk.",
        ) from exc
    except PopulationStorageError as exc:
        raise http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(exc),
            code=ErrorCode.INVALID_INPUT,
            field="chunkId",
            hint="Check storage permissions and chunk metadata.",
        ) from exc

    stream = store.open_chunk(metadata.results_id, metadata.chunk_id)
    response = StreamingResponse(stream, media_type=metadata.content_type)
    response.headers["Content-Length"] = str(metadata.size_bytes)
    response.headers["Content-Disposition"] = f'attachment; filename="{metadata.chunk_id}.json"'
    return response


@router.post("/calculate_pk_parameters", response_model=CalculatePkParametersResponseBody)
async def calculate_pk_parameters(
    payload: CalculatePkParametersRequestBody,
    request: Request,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    _auth: AuthContext = Depends(require_roles("viewer", "operator", "admin")),
) -> CalculatePkParametersResponseBody:
    try:
        tool_payload = ToolCalculatePkParametersRequest.model_validate(
            payload.model_dump(by_alias=True)
        )
        tool_response = await maybe_to_thread(
            _should_offload(request),
            execute_calculate_pk_parameters,
            adapter,
            tool_payload,
        )
    except ValidationError as exc:
        raise validation_exception(exc, status_code=status.HTTP_400_BAD_REQUEST) from exc
    except CalculatePkParametersValidationError as exc:
        raise http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(exc),
            code=ErrorCode.INVALID_INPUT,
            field="resultsId",
            hint="Provide a resultsId generated by run_simulation before requesting PK metrics.",
        ) from exc
    except AdapterError as exc:
        raise adapter_error_to_http(exc) from exc

    metrics_models = [
        PkMetricModel(
            parameter=item.parameter,
            unit=item.unit,
            cmax=item.cmax,
            tmax=item.tmax,
            auc=item.auc,
        )
        for item in tool_response.metrics
    ]
    return CalculatePkParametersResponseBody(
        resultsId=tool_response.results_id,
        simulationId=tool_response.simulation_id,
        metrics=metrics_models,
    )


@router.post("/cancel_job", response_model=CancelJobResponse)
async def cancel_job(
    payload: CancelJobRequest,
    job_service: BaseJobService = Depends(get_job_service),
    _auth: AuthContext = Depends(require_roles("operator", "admin")),
) -> CancelJobResponse:
    try:
        tool_payload = ToolCancelJobRequest.model_validate(payload.model_dump(by_alias=True))
        tool_response: ToolCancelJobResponse = execute_cancel_job(job_service, tool_payload)
    except CancelJobValidationError as exc:
        raise http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            message=str(exc),
            code=ErrorCode.NOT_FOUND,
            field="jobId",
            hint="Ensure the job is still queued or running before cancelling.",
        ) from exc
    return CancelJobResponse.model_validate(tool_response.model_dump(by_alias=True))
