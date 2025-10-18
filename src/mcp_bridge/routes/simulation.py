# ruff: noqa: UP006,UP007,UP035
"""Simulation-related API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
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
from mcp.tools.run_simulation import (
    RunSimulationRequest as ToolRunSimulationRequest,
)
from mcp.tools.run_simulation import (
    RunSimulationValidationError,
)
from mcp.tools.run_simulation import (
    run_simulation as execute_run_simulation,
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
from mcp.tools.set_parameter_value import (
    SetParameterValueRequest as ToolSetParameterValueRequest,
)
from mcp.tools.set_parameter_value import (
    SetParameterValueValidationError,
)
from mcp.tools.set_parameter_value import (
    set_parameter_value as execute_set_parameter_value,
)

from ..adapter import AdapterError, AdapterErrorCode, OspsuiteAdapter
from ..dependencies import get_adapter, get_job_service, get_population_store
from ..logging import get_logger
from ..services.job_service import JobService
from ..storage.population_store import (
    PopulationChunkNotFoundError,
    PopulationResultStore,
    PopulationStorageError,
)
from ..security.auth import AuthContext, require_roles

router = APIRouter()
logger = get_logger(__name__)


def _to_camel(string: str) -> str:
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


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


def _map_adapter_error(exc: AdapterError) -> HTTPException:
    status_map = {
        AdapterErrorCode.INVALID_INPUT: status.HTTP_400_BAD_REQUEST,
        AdapterErrorCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
        AdapterErrorCode.ENVIRONMENT_MISSING: status.HTTP_503_SERVICE_UNAVAILABLE,
        AdapterErrorCode.INTEROP_ERROR: status.HTTP_502_BAD_GATEWAY,
        AdapterErrorCode.TIMEOUT: status.HTTP_504_GATEWAY_TIMEOUT,
    }
    status_code = status_map.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR)
    return HTTPException(status_code=status_code, detail=str(exc))


@router.post(
    "/load_simulation", response_model=LoadSimulationResponse, status_code=status.HTTP_201_CREATED
)
async def load_simulation(
    payload: LoadSimulationRequest,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    _auth: AuthContext = Depends(require_roles("operator", "admin")),
) -> LoadSimulationResponse:
    try:
        tool_payload = ToolLoadSimulationRequest.model_validate(payload.model_dump(by_alias=True))
        tool_response = execute_load_simulation(adapter, tool_payload)
    except DuplicateSimulationError as exc:
        logger.warning(
            "simulation.duplicate",
            simulationId=payload.simulation_id or payload.file_path,
            detail=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except LoadSimulationValidationError as exc:
        logger.warning(
            "simulation.invalid",
            simulationId=payload.simulation_id or "<generated>",
            detail=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AdapterError as exc:
        raise _map_adapter_error(exc) from exc

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
    adapter: OspsuiteAdapter = Depends(get_adapter),
    _auth: AuthContext = Depends(require_roles("viewer", "operator", "admin")),
) -> ListParametersResponse:
    try:
        tool_payload = ToolListParametersRequest.model_validate(payload.model_dump(by_alias=True))
    except ValidationError as exc:
        detail = exc.errors()[0]["msg"] if exc.errors() else str(exc)
        logger.warning(
            "simulation.parameters.invalid",
            simulationId=payload.simulation_id,
            pattern=payload.search_pattern,
            detail=detail,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    try:
        tool_response = execute_list_parameters(adapter, tool_payload)
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
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except AdapterError as exc:
        raise _map_adapter_error(exc) from exc

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
    adapter: OspsuiteAdapter = Depends(get_adapter),
    _auth: AuthContext = Depends(require_roles("viewer", "operator", "admin")),
) -> ParameterValueResponse:
    try:
        tool_payload = ToolGetParameterValueRequest.model_validate(
            payload.model_dump(by_alias=True)
        )
    except ValidationError as exc:
        detail = exc.errors()[0]["msg"] if exc.errors() else str(exc)
        logger.warning(
            "simulation.parameter.invalid",
            simulationId=payload.simulation_id,
            parameterPath=payload.parameter_path,
            detail=detail,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc

    try:
        tool_response = execute_get_parameter_value(adapter, tool_payload)
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
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except AdapterError as exc:
        raise _map_adapter_error(exc) from exc

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
    adapter: OspsuiteAdapter = Depends(get_adapter),
    _auth: AuthContext = Depends(require_roles("operator", "admin")),
) -> ParameterValueResponse:
    try:
        tool_payload = ToolSetParameterValueRequest.model_validate(
            payload.model_dump(by_alias=True)
        )
    except ValidationError as exc:
        detail = exc.errors()[0]["msg"] if exc.errors() else str(exc)
        logger.warning(
            "simulation.parameter.invalid",
            simulationId=payload.simulation_id,
            parameterPath=payload.parameter_path,
            detail=detail,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc

    try:
        tool_response = execute_set_parameter_value(adapter, tool_payload)
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
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except AdapterError as exc:
        raise _map_adapter_error(exc) from exc

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
    adapter: OspsuiteAdapter = Depends(get_adapter),
    job_service: JobService = Depends(get_job_service),
    _auth: AuthContext = Depends(require_roles("operator", "admin")),
) -> RunSimulationResponse:
    try:
        tool_payload = ToolRunSimulationRequest.model_validate(payload.model_dump(by_alias=True))
        job_response = execute_run_simulation(adapter, job_service, tool_payload)
    except RunSimulationValidationError as exc:
        logger.warning(
            "simulation.run.invalid",
            simulationId=payload.simulation_id,
            detail=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AdapterError as exc:
        raise _map_adapter_error(exc) from exc

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
    adapter: OspsuiteAdapter = Depends(get_adapter),
    job_service: JobService = Depends(get_job_service),
    _auth: AuthContext = Depends(require_roles("operator", "admin")),
) -> RunPopulationSimulationResponse:
    try:
        tool_payload = ToolRunPopulationSimulationRequest.model_validate(
            payload.model_dump(by_alias=True)
        )
        tool_response = execute_run_population_simulation(adapter, job_service, tool_payload)
    except (RunPopulationSimulationValidationError, LoadSimulationValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AdapterError as exc:
        raise _map_adapter_error(exc) from exc

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
    job_service: JobService = Depends(get_job_service),
    _auth: AuthContext = Depends(require_roles("viewer", "operator", "admin")),
) -> JobStatusResponse:
    try:
        tool_payload = ToolGetJobStatusRequest.model_validate(payload.model_dump(by_alias=True))
        tool_response = execute_get_job_status(job_service, tool_payload)
    except GetJobStatusValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

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
    )


@router.post("/get_simulation_results", response_model=GetSimulationResultsResponse)
async def get_simulation_results(
    payload: GetSimulationResultsRequest,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    _auth: AuthContext = Depends(require_roles("viewer", "operator", "admin")),
) -> GetSimulationResultsResponse:
    try:
        results = adapter.get_results(payload.results_id)
    except AdapterError as exc:
        raise _map_adapter_error(exc) from exc

    series_models = [
        ResultSeriesModel(parameter=s.parameter, unit=s.unit, values=s.values)
        for s in results.series
    ]
    return GetSimulationResultsResponse(
        resultsId=results.results_id,
        generatedAt=results.generated_at,
        series=series_models,
    )


@router.post("/get_population_results", response_model=PopulationResultsResponse)
async def get_population_results(
    payload: GetPopulationResultsRequest,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    _auth: AuthContext = Depends(require_roles("viewer", "operator", "admin")),
) -> PopulationResultsResponse:
    try:
        results = adapter.get_population_results(payload.results_id)
    except AdapterError as exc:
        raise _map_adapter_error(exc) from exc

    return PopulationResultsResponse(
        resultsId=results.results_id,
        simulationId=results.simulation_id,
        generatedAt=results.generated_at,
        cohort=results.cohort.model_dump(),
        aggregates=results.aggregates,
        chunks=[PopulationChunkModel.model_validate(chunk.model_dump()) for chunk in results.chunk_handles],
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PopulationStorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    stream = store.open_chunk(metadata.results_id, metadata.chunk_id)
    response = StreamingResponse(stream, media_type=metadata.content_type)
    response.headers["Content-Length"] = str(metadata.size_bytes)
    response.headers["Content-Disposition"] = (
        f"attachment; filename=\"{metadata.chunk_id}.json\""
    )
    return response


@router.post("/calculate_pk_parameters", response_model=CalculatePkParametersResponseBody)
async def calculate_pk_parameters(
    payload: CalculatePkParametersRequestBody,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    _auth: AuthContext = Depends(require_roles("viewer", "operator", "admin")),
) -> CalculatePkParametersResponseBody:
    try:
        tool_payload = ToolCalculatePkParametersRequest.model_validate(
            payload.model_dump(by_alias=True)
        )
        tool_response = execute_calculate_pk_parameters(adapter, tool_payload)
    except ValidationError as exc:
        detail = exc.errors()[0]["msg"] if exc.errors() else str(exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    except CalculatePkParametersValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AdapterError as exc:
        raise _map_adapter_error(exc) from exc

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
    job_service: JobService = Depends(get_job_service),
    _auth: AuthContext = Depends(require_roles("operator", "admin")),
) -> CancelJobResponse:
    try:
        record = job_service.cancel_job(payload.job_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc
    return CancelJobResponse(jobId=record.job_id, status=record.status.value)
