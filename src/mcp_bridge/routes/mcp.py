"""MCP protocol endpoints: tool discovery, invocation, and capabilities."""

from __future__ import annotations

import hashlib
import inspect
import json
import time
from typing import Any, Dict, Iterable, Optional

from fastapi import APIRouter, Depends, Request, status
from prometheus_client import Counter, Gauge, Histogram
from pydantic import BaseModel, Field, ValidationError

from mcp.tools.calculate_pk_parameters import CalculatePkParametersValidationError
from mcp.tools.cancel_job import CancelJobValidationError
from mcp.tools.get_job_status import GetJobStatusValidationError
from mcp.tools.get_parameter_value import GetParameterValueValidationError
from mcp.tools.list_parameters import ListParametersValidationError
from mcp.tools.load_simulation import DuplicateSimulationError, LoadSimulationValidationError
from mcp.tools.run_population_simulation import RunPopulationSimulationValidationError
from mcp.tools.run_sensitivity_analysis import RunSensitivityAnalysisValidationError
from mcp.tools.run_simulation import RunSimulationValidationError
from mcp.tools.set_parameter_value import SetParameterValueValidationError

from ..adapter import AdapterError
from ..adapter.interface import OspsuiteAdapter
from ..dependencies import get_adapter, get_audit_trail, get_job_service, get_population_store
from ..errors import (
    DetailedHTTPException,
    ErrorCode,
    adapter_error_to_http,
    http_error,
    validation_exception,
)
from ..security import require_confirmation
from ..security.auth import AuthContext, auth_dependency
from ..services.job_service import BaseJobService, IdempotencyConflictError
from ..storage.population_store import PopulationResultStore
from ..tools.registry import ToolDescriptor, get_tool_registry
from ..util.concurrency import maybe_to_thread

router = APIRouter(prefix="/mcp", tags=["mcp"])


_TOOL_IN_PROGRESS = Gauge(
    "mcp_tool_invocations_in_progress",
    "Number of MCP tool invocations currently in progress.",
    ("tool",),
)
_TOOL_COUNT = Counter(
    "mcp_tool_invocations_total",
    "Total MCP tool invocations labelled by tool and outcome.",
    ("tool", "status"),
)
_TOOL_LATENCY = Histogram(
    "mcp_tool_duration_seconds",
    "Latency of MCP tool invocations labelled by tool and outcome.",
    ("tool", "status"),
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.0,
        5.0,
        10.0,
        30.0,
        60.0,
    ),
)


class ToolDescription(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any] = Field(alias="inputSchema")
    output_schema: Optional[Dict[str, Any]] = Field(default=None, alias="outputSchema")
    annotations: Dict[str, Any] = Field(default_factory=dict)


class ListToolsResponse(BaseModel):
    tools: list[ToolDescription]


class CallToolRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(default=None, alias="idempotencyKey")
    critical: Optional[bool] = None


class CallToolResponse(BaseModel):
    type: str = Field(default="tool_result", alias="type")
    tool: str
    structured_content: Dict[str, Any] = Field(alias="structuredContent")
    annotations: Dict[str, Any] = Field(default_factory=dict)


class AdapterCapabilities(BaseModel):
    name: str
    populationSupported: bool
    health: Dict[str, Any]


class CapabilitiesResponse(BaseModel):
    transports: list[str]
    adapter: AdapterCapabilities
    maxPayloadKb: int = Field(alias="maxPayloadKb")
    timeouts: Dict[str, Any]
    annotations: Dict[str, Any] = Field(default_factory=dict)


def _normalize_result(payload: Any) -> Dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, BaseModel):
        return payload.model_dump(by_alias=True)
    if hasattr(payload, "model_dump"):
        return payload.model_dump(by_alias=True)  # type: ignore[attr-defined]
    if isinstance(payload, dict):
        return payload
    return dict(payload) if isinstance(payload, Iterable) else {"value": payload}


def _tool_annotations(descriptor: ToolDescriptor) -> Dict[str, Any]:
    return {
        "critical": descriptor.critical,
        "requiresConfirmation": descriptor.requires_confirmation,
        "roles": list(descriptor.roles),
    }


def _fingerprint_payload(model: BaseModel) -> str:
    data = model.model_dump(mode="json", by_alias=True)
    payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _digest_object(obj: Dict[str, Any]) -> str:
    try:
        data = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    except TypeError:
        data = json.dumps(str(obj), sort_keys=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _tool_result_summary(content: Dict[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for key in ("jobId", "status", "simulationId", "resultsId"):
        if key in content:
            summary[key] = content[key]
    return summary


def _record_tool_audit(
    audit: Any,
    descriptor: ToolDescriptor,
    auth: AuthContext | None,
    arguments_fingerprint: str,
    arguments_keys: list[str],
    duration_ms: float,
    status_label: str,
    idempotency_key: str | None,
    result_content: Dict[str, Any],
    service_version: str,
    error: str | None = None,
) -> None:
    if audit is None or not getattr(audit, "enabled", False):
        return

    identity = None
    if auth is not None:
        identity = {
            "subject": auth.subject,
            "roles": auth.roles,
            "tokenId": auth.token_id,
            "isServiceAccount": auth.is_service_account,
        }

    event_payload = {
        "identity": identity,
        "tool": {
            "name": descriptor.name,
            "argumentsDigest": arguments_fingerprint,
            "argumentKeys": arguments_keys,
            "idempotencyKey": idempotency_key,
            "resultDigest": _digest_object(result_content) if result_content else None,
            "resultSummary": _tool_result_summary(result_content),
            "status": status_label,
            "durationMs": duration_ms,
            "serviceVersion": service_version,
        },
    }
    if error:
        event_payload["error"] = error

    audit.record_event(f"tool.{descriptor.name}", event_payload)


def _ensure_tool_roles(descriptor: ToolDescriptor, context: AuthContext) -> None:
    if not descriptor.roles:
        return
    have = {role.lower() for role in context.roles}
    need = {role.lower() for role in descriptor.roles}
    if have.intersection(need):
        return
    raise http_error(
        status_code=status.HTTP_403_FORBIDDEN,
        message="Insufficient permissions",
        code=ErrorCode.FORBIDDEN,
        hint=f"Required roles: {', '.join(descriptor.roles)}",
    )


def _handle_tool_specific_errors(tool: str, exc: Exception) -> DetailedHTTPException:
    if isinstance(exc, DetailedHTTPException):
        return exc
    if isinstance(exc, ValidationError):
        return validation_exception(exc)
    if isinstance(exc, AdapterError):
        return adapter_error_to_http(exc)

    message = str(exc)

    if tool == "load_simulation":
        if isinstance(exc, DuplicateSimulationError):
            return http_error(
                status_code=status.HTTP_409_CONFLICT,
                message=message,
                code=ErrorCode.CONFLICT,
                field="simulationId",
                hint="Choose a unique simulationId or omit it to let the server generate one.",
            )
        if isinstance(exc, LoadSimulationValidationError):
            key = "simulation" if "simulation" in message.lower() else "file"
            field = "simulationId" if key == "simulation" else "filePath"
            hint = (
                "Ensure the simulation is not already loaded and the identifier is unique."
                if field == "simulationId"
                else "Provide an absolute .pkml path within MCP_MODEL_SEARCH_PATHS."
            )
            return http_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=message,
                code=ErrorCode.INVALID_INPUT,
                field=field,
                hint=hint,
            )

    if tool == "list_parameters" and isinstance(exc, ListParametersValidationError):
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in message.lower()
            else status.HTTP_400_BAD_REQUEST
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
        return http_error(
            status_code=status_code,
            message=message,
            code=code,
            field=field,
            hint=hint,
        )

    if tool == "get_parameter_value" and isinstance(exc, GetParameterValueValidationError):
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in message.lower()
            else status.HTTP_400_BAD_REQUEST
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
        return http_error(
            status_code=status_code,
            message=message,
            code=code,
            field="parameterPath",
            hint=hint,
        )

    if tool == "set_parameter_value" and isinstance(exc, SetParameterValueValidationError):
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in message.lower()
            else status.HTTP_400_BAD_REQUEST
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
        return http_error(
            status_code=status_code,
            message=message,
            code=code,
            field="parameterPath",
            hint=hint,
        )

    if tool == "run_sensitivity_analysis" and isinstance(
        exc, RunSensitivityAnalysisValidationError
    ):
        field = (
            "modelPath" if "path" in message.lower() or "file" in message.lower() else "parameters"
        )
        return http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=message,
            code=ErrorCode.INVALID_INPUT,
            field=field,
            hint=(
                "Confirm the model path is within MCP_MODEL_SEARCH_PATHS and "
                "each parameter includes at least one delta."
            ),
        )

    if isinstance(exc, IdempotencyConflictError):
        return http_error(
            status_code=status.HTTP_409_CONFLICT,
            message=str(exc),
            code=ErrorCode.CONFLICT,
            field="Idempotency-Key",
            hint="Reuse the same payload for this key or choose a new idempotency key.",
        )

    if tool == "run_simulation" and isinstance(exc, RunSimulationValidationError):
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in message.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        hint = (
            "Load the simulation before running it."
            if status_code == status.HTTP_404_NOT_FOUND
            else "Check the simulationId and optional runId parameters."
        )
        code = (
            ErrorCode.NOT_FOUND
            if status_code == status.HTTP_404_NOT_FOUND
            else ErrorCode.INVALID_INPUT
        )
        return http_error(
            status_code=status_code,
            message=message,
            code=code,
            field="simulationId",
            hint=hint,
        )

    if tool == "get_job_status" and isinstance(exc, GetJobStatusValidationError):
        return http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            message=message,
            code=ErrorCode.NOT_FOUND,
            field="jobId",
            hint="Verify the job identifier is correct and the job is still retained.",
        )

    if tool == "calculate_pk_parameters" and isinstance(exc, CalculatePkParametersValidationError):
        return http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=message,
            code=ErrorCode.INVALID_INPUT,
            field="resultsId",
            hint="Provide a resultsId generated by run_simulation before requesting PK metrics.",
        )

    if tool == "run_population_simulation" and isinstance(
        exc, (RunPopulationSimulationValidationError, LoadSimulationValidationError)
    ):
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in message.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        hint = (
            "Load the simulation and ensure cohort definitions are valid."
            if status_code == status.HTTP_404_NOT_FOUND
            else "Validate population configuration and model path inputs."
        )
        code = (
            ErrorCode.NOT_FOUND
            if status_code == status.HTTP_404_NOT_FOUND
            else ErrorCode.INVALID_INPUT
        )
        return http_error(
            status_code=status_code,
            message=message,
            code=code,
            field="simulationId",
            hint=hint,
        )

    if tool == "cancel_job" and isinstance(exc, CancelJobValidationError):
        return http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            message=message,
            code=ErrorCode.NOT_FOUND,
            field="jobId",
            hint="Verify the job is still queued or running before cancelling.",
        )

    if isinstance(exc, AdapterError):
        return adapter_error_to_http(exc)

    raise exc


@router.get("/list_tools", response_model=ListToolsResponse)
def list_tools(_auth: AuthContext = Depends(auth_dependency)) -> ListToolsResponse:
    registry = get_tool_registry()
    items = []
    for descriptor in registry.values():
        items.append(
            ToolDescription(
                name=descriptor.name,
                description=descriptor.description,
                inputSchema=descriptor.input_schema(),
                outputSchema=descriptor.output_schema(),
                annotations=_tool_annotations(descriptor),
            )
        )
    return ListToolsResponse(tools=items)


@router.post("/call_tool", response_model=CallToolResponse)
async def call_tool(
    http_request: Request,
    request: CallToolRequest,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    job_service: BaseJobService = Depends(get_job_service),
    population_store: PopulationResultStore = Depends(get_population_store),
    audit_trail: Any = Depends(get_audit_trail),
    auth: AuthContext = Depends(auth_dependency),
) -> CallToolResponse:
    registry = get_tool_registry()
    descriptor = registry.get(request.tool)
    if descriptor is None:
        raise http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"Tool '{request.tool}' is not registered",
            code=ErrorCode.NOT_FOUND,
            field="tool",
        )

    _ensure_tool_roles(descriptor, auth)

    if descriptor.requires_confirmation:
        if request.critical is not True:
            raise http_error(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                message="Critical tools must be invoked with critical=true.",
                code=ErrorCode.CONFIRMATION_REQUIRED,
                hint="Set 'critical': true in the request payload before calling this tool.",
            )
        require_confirmation(http_request)

    try:
        tool_request = descriptor.request_model.model_validate(request.arguments)
    except ValidationError as exc:
        raise validation_exception(exc) from exc

    dependency_map = {
        "adapter": adapter,
        "job_service": job_service,
        "population_store": population_store,
    }
    call_kwargs = {name: dependency_map[name] for name in descriptor.dependencies}
    call_kwargs["payload"] = tool_request

    if request.idempotency_key and descriptor.name in {
        "run_simulation",
        "run_population_simulation",
    }:
        call_kwargs["idempotency_key"] = request.idempotency_key
        call_kwargs["idempotency_fingerprint"] = _fingerprint_payload(tool_request)

    status_label = "success"
    start_time = time.perf_counter()
    _TOOL_IN_PROGRESS.labels(descriptor.name).inc()
    auth_context = getattr(http_request.state, "auth", None)
    service_version = getattr(http_request.app.state, "config", None)
    service_version = getattr(service_version, "service_version", "unknown")
    arguments_model = tool_request.model_dump(mode="json", by_alias=True)
    arguments_fingerprint = _fingerprint_payload(tool_request)
    handler = descriptor.handler
    result_content: Dict[str, Any] = {}
    try:
        if inspect.iscoroutinefunction(handler):
            result = await handler(**call_kwargs)
        else:
            offload = bool(getattr(http_request.app.state, "adapter_offload", True))
            result = await maybe_to_thread(offload, handler, **call_kwargs)
        result_content = _normalize_result(result)
    except Exception as exc:  # noqa: BLE001 - mapped below
        status_label = "error"
        detailed = _handle_tool_specific_errors(descriptor.name, exc)
        if audit_trail is not None:
            _record_tool_audit(
                audit_trail,
                descriptor,
                auth_context,
                arguments_fingerprint,
                list(arguments_model.keys()),
                (time.perf_counter() - start_time) * 1000,
                status_label,
                request.idempotency_key,
                result_content,
                service_version,
                error=str(detailed.detail if hasattr(detailed, "detail") else detailed),
            )
        raise detailed from exc
    finally:
        duration = time.perf_counter() - start_time
        _TOOL_IN_PROGRESS.labels(descriptor.name).dec()
        _TOOL_COUNT.labels(descriptor.name, status_label).inc()
        _TOOL_LATENCY.labels(descriptor.name, status_label).observe(duration)

    annotations = _tool_annotations(descriptor)
    if request.idempotency_key:
        annotations["idempotencyKey"] = request.idempotency_key

    if audit_trail is not None:
        _record_tool_audit(
            audit_trail,
            descriptor,
            auth_context,
            arguments_fingerprint,
            list(arguments_model.keys()),
            duration * 1000,
            status_label,
            request.idempotency_key,
            result_content,
            service_version,
        )

    return CallToolResponse(
        tool=descriptor.name,
        structuredContent=result_content,
        annotations=annotations,
    )


@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities(
    fastapi_request: Request,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    population_store: PopulationResultStore = Depends(get_population_store),
) -> CapabilitiesResponse:
    config = fastapi_request.app.state.config
    health = adapter.health() if hasattr(adapter, "health") else {}
    adapter_cap = AdapterCapabilities(
        name=config.adapter_backend,
        populationSupported=population_store is not None,
        health=health,
    )
    annotations = {
        "service": config.service_name,
        "environment": config.environment,
    }
    timeouts = {
        "defaultMs": int(config.job_timeout_seconds * 1000),
        "adapterTimeoutMs": config.adapter_timeout_ms,
    }
    transports = ["http-streamable"]
    return CapabilitiesResponse(
        transports=transports,
        adapter=adapter_cap,
        maxPayloadKb=512,
        timeouts=timeouts,
        annotations=annotations,
    )


__all__ = ["router"]
