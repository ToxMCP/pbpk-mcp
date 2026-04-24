"""Streamable HTTP JSON-RPC transport exposing MCP tools and resources."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Literal, Optional, Union

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ValidationError

from ..adapter import AdapterError
from ..config import AppConfig
from ..errors import DetailedHTTPException, ErrorCode, validation_exception
from ..routes import mcp as rest_mcp
from ..routes import resources_base as resource_routes
from ..security.auth import AuthContext, auth_dependency
from ..util.concurrency import maybe_to_thread

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/mcp", tags=["mcp-jsonrpc"])


class JSONRPCRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    method: str
    params: Optional[Union[Dict[str, Any], list[Any]]] = None
    id: Union[str, int]


class ListToolsResult(BaseModel):
    tools: list[dict[str, Any]]


class ListPromptsResult(BaseModel):
    prompts: list[dict[str, Any]]


class JSONRPCDispatchError(Exception):
    def __init__(
        self,
        code: int,
        message: str,
        *,
        data: Optional[Any] = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.data = data
        self.http_status = http_status


PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

UNAUTHORIZED = -32000
FORBIDDEN = -32001
TOOL_EXECUTION_ERROR = -32002


LATEST_MCP_PROTOCOL_VERSION = "2025-11-25"
LEGACY_MCP_PROTOCOL_VERSION = "2025-03-26"
SUPPORTED_MCP_PROTOCOL_VERSIONS = {
    LATEST_MCP_PROTOCOL_VERSION,
    LEGACY_MCP_PROTOCOL_VERSION,
}
PUBLIC_RESOURCE_URIS = {
    "pbpk://schemas/catalog",
    "pbpk://capability-matrix",
    "pbpk://contract-manifest",
    "pbpk://release-bundle-manifest",
}


def _create_error_response(
    code: int,
    message: str,
    request_id: Optional[Union[str, int]],
    *,
    data: Optional[Any] = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    payload: dict[str, Any] = {"jsonrpc": "2.0", "error": error}
    if request_id is not None:
        payload["id"] = request_id
    return payload


def _create_success_response(result: Any, request_id: Union[str, int]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


@router.get("")
async def jsonrpc_get_endpoint() -> Response:
    """Return 405 because this transport does not expose an SSE stream."""

    return Response(status_code=status.HTTP_405_METHOD_NOT_ALLOWED)


@router.post("")
@router.post("/jsonrpc")
async def jsonrpc_endpoint(request: Request, response: Response) -> Any:
    body: Any = None
    request_id: str | int | None = None
    if request.url.path.endswith("/jsonrpc"):
        logger.warning("jsonrpc.legacy_endpoint path=%s (prefer /mcp)", request.url.path)

    try:
        _validate_transport_headers(request)
    except JSONRPCDispatchError as exc:
        response.status_code = exc.http_status or status.HTTP_400_BAD_REQUEST
        return _create_error_response(exc.code, str(exc), None, data=exc.data)

    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001
        logger.error("jsonrpc.invalid_json", exc_info=exc)
        response.status_code = status.HTTP_400_BAD_REQUEST
        return _create_error_response(PARSE_ERROR, "Invalid JSON payload", None)

    if isinstance(body, list):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return _create_error_response(INVALID_REQUEST, "Batch requests are not supported", None)

    if not isinstance(body, dict):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return _create_error_response(INVALID_REQUEST, "JSON-RPC request must be an object", None)

    raw_id = body.get("id")
    if "id" in body and raw_id is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return _create_error_response(INVALID_REQUEST, "JSON-RPC id must not be null", None)
    request_id = raw_id if isinstance(raw_id, (str, int)) and not isinstance(raw_id, bool) else None

    if body.get("jsonrpc") != "2.0":
        response.status_code = status.HTTP_400_BAD_REQUEST
        return _create_error_response(
            INVALID_REQUEST,
            "JSON-RPC version must be '2.0'",
            request_id,
        )

    if "method" not in body and ("result" in body or "error" in body):
        return _handle_client_response(body, request_id, response)

    is_notification = "id" not in body
    if is_notification:
        return _handle_notification(body, response)
    if request_id is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return _create_error_response(
            INVALID_REQUEST,
            "JSON-RPC id must be a string or integer",
            None,
        )

    try:
        rpc_request = JSONRPCRequest.model_validate(body)
    except ValidationError as exc:
        logger.error("jsonrpc.invalid_request", exc_info=exc)
        response.status_code = status.HTTP_400_BAD_REQUEST
        return _create_error_response(
            INVALID_REQUEST,
            "Invalid JSON-RPC request",
            request_id,
            data=exc.errors(),
        )

    try:
        result = await _dispatch_jsonrpc(request, rpc_request)
    except JSONRPCDispatchError as exc:
        logger.debug("jsonrpc.dispatch_error", extra={"method": rpc_request.method})
        response.status_code = status.HTTP_200_OK
        return _create_error_response(exc.code, str(exc), request_id, data=exc.data)
    except Exception as exc:  # noqa: BLE001
        logger.exception("jsonrpc.unhandled_exception")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return _create_error_response(INTERNAL_ERROR, "Internal error", request_id, data=str(exc))

    response.status_code = status.HTTP_200_OK
    return _create_success_response(result, request_id)


def _handle_notification(body: dict[str, Any], response: Response) -> Response | dict[str, Any]:
    method = body.get("method")
    if not isinstance(method, str):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return _create_error_response(INVALID_REQUEST, "Notification method is required", None)
    if method == "initialized" or method.startswith("notifications/"):
        response.status_code = status.HTTP_202_ACCEPTED
        return Response(status_code=status.HTTP_202_ACCEPTED)
    response.status_code = status.HTTP_400_BAD_REQUEST
    return _create_error_response(
        METHOD_NOT_FOUND,
        f"Notification not accepted: {method}",
        None,
    )


def _handle_client_response(
    body: dict[str, Any],
    request_id: str | int | None,
    response: Response,
) -> Response | dict[str, Any]:
    if request_id is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return _create_error_response(
            INVALID_REQUEST,
            "JSON-RPC response id must be a string or integer",
            None,
        )
    if "result" in body and "error" in body:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return _create_error_response(
            INVALID_REQUEST,
            "JSON-RPC response cannot contain both result and error",
            request_id,
        )
    response.status_code = status.HTTP_202_ACCEPTED
    return Response(status_code=status.HTTP_202_ACCEPTED)


def _validate_transport_headers(request: Request) -> None:
    config: AppConfig = request.app.state.config
    origin = request.headers.get("origin")
    allowed_origins = tuple(getattr(config, "mcp_allowed_origins", ()) or ())
    if origin and allowed_origins and origin not in allowed_origins:
        raise JSONRPCDispatchError(
            FORBIDDEN,
            "Origin is not allowed",
            data={"origin": origin},
            http_status=status.HTTP_403_FORBIDDEN,
        )

    strict = bool(getattr(config, "mcp_strict_transport", False))
    accept = request.headers.get("accept", "")
    if strict:
        accepted = {item.split(";", 1)[0].strip().lower() for item in accept.split(",")}
        if not {"application/json", "text/event-stream"}.issubset(accepted):
            raise JSONRPCDispatchError(
                INVALID_REQUEST,
                "MCP strict transport requires Accept: application/json, text/event-stream",
            )

    protocol_version = request.headers.get("mcp-protocol-version")
    if protocol_version and protocol_version not in SUPPORTED_MCP_PROTOCOL_VERSIONS:
        raise JSONRPCDispatchError(
            INVALID_PARAMS,
            "Unsupported MCP protocol version",
            data={
                "requested": protocol_version,
                "supported": sorted(SUPPORTED_MCP_PROTOCOL_VERSIONS),
            },
        )
    if strict and not protocol_version:
        raise JSONRPCDispatchError(
            INVALID_REQUEST,
            "MCP strict transport requires MCP-Protocol-Version",
        )


async def _dispatch_jsonrpc(request: Request, rpc_request: JSONRPCRequest) -> Any:
    method = rpc_request.method
    params = rpc_request.params or {}

    if isinstance(params, list):
        raise JSONRPCDispatchError(INVALID_PARAMS, "Positional parameters are not supported")

    if method == "initialize":
        return _handle_initialize(request, params)
    if method == "shutdown":
        return {}

    if method in {"resources/list", "resources/read", "resources/templates/list"}:
        auth_context = await _optional_auth_dependency(request)
        if method == "resources/list":
            return await _handle_list_resources(request, auth_context)
        if method == "resources/read":
            return await _handle_read_resource(request, params, auth_context)
        return _handle_resource_templates()

    auth_context = await auth_dependency(request)

    if method in {"mcp/tool/list", "tools/list"}:
        return _handle_list_tools(auth_context)
    if method in {"mcp/tool/call", "tools/call"}:
        return await _handle_call_tool(request, params, auth_context)
    if method == "prompts/list":
        return ListPromptsResult(prompts=[]).model_dump()
    if method == "prompts/get":
        raise JSONRPCDispatchError(METHOD_NOT_FOUND, "Prompt catalog is empty")

    raise JSONRPCDispatchError(METHOD_NOT_FOUND, f"Method not found: {method}")


def _handle_initialize(request: Request, params: dict[str, Any]) -> dict[str, Any]:
    config: AppConfig = request.app.state.config
    requested = str(params.get("protocolVersion") or "").strip()
    protocol_version = (
        requested if requested in SUPPORTED_MCP_PROTOCOL_VERSIONS else LATEST_MCP_PROTOCOL_VERSION
    )
    server_info = {
        "name": getattr(config, "service_name", "mcp-bridge"),
        "title": "PBPK MCP Server",
        "version": getattr(config, "service_version", "unknown"),
        "description": "PBPK model discovery, simulation, qualification, and reporting server.",
    }
    capabilities = {
        "tools": {"listChanged": False},
        "resources": {"listChanged": False},
    }
    return {
        "protocolVersion": protocol_version,
        "serverInfo": server_info,
        "capabilities": capabilities,
        "instructions": (
            "Use tools for PBPK workflows. Published artifacts and live catalogs are also "
            "available as MCP resources using pbpk:// URIs; legacy REST helper endpoints remain available."
        ),
    }


def _handle_list_tools(auth: AuthContext) -> dict[str, Any]:
    registry = rest_mcp.get_tool_registry()
    tools: list[dict[str, Any]] = []
    for descriptor in registry.values():
        if descriptor.roles and not set(auth.roles).intersection(descriptor.roles):
            continue
        tool: dict[str, Any] = {
            "name": descriptor.name,
            "title": _title_from_name(descriptor.name),
            "description": descriptor.description,
            "inputSchema": descriptor.input_schema(),
            "annotations": rest_mcp._tool_annotations(descriptor),  # type: ignore[attr-defined]
        }
        output_schema = descriptor.output_schema()
        if output_schema is not None:
            tool["outputSchema"] = output_schema
        tools.append(tool)
    return ListToolsResult(tools=tools).model_dump()


async def _handle_call_tool(request: Request, params: dict[str, Any], auth: AuthContext) -> Any:
    if not isinstance(params, dict):
        raise JSONRPCDispatchError(INVALID_PARAMS, "Tool call parameters must be an object")

    tool_name = params.get("name") or params.get("tool")
    if not tool_name or not isinstance(tool_name, str):
        raise JSONRPCDispatchError(INVALID_PARAMS, "Tool 'name' is required")

    arguments = _normalize_tool_arguments(params)
    if not isinstance(arguments, dict):
        raise JSONRPCDispatchError(INVALID_PARAMS, "Tool arguments must be an object")

    call_payload = {
        "tool": tool_name,
        "arguments": arguments,
        "idempotencyKey": params.get("idempotencyKey") or params.get("idempotency_key"),
        "critical": params.get("critical"),
    }

    try:
        request_model = rest_mcp.CallToolRequest.model_validate(call_payload)
    except ValidationError as exc:
        raise JSONRPCDispatchError(INVALID_PARAMS, "Invalid tool invocation payload", data=exc.errors()) from exc

    try:
        result: rest_mcp.CallToolResponse = await rest_mcp.call_tool(  # type: ignore[call-arg]
            http_request=request,
            request=request_model,
            adapter=request.app.state.adapter,
            job_service=request.app.state.jobs,
            population_store=request.app.state.population_store,
            audit_trail=request.app.state.audit,
            snapshot_store=request.app.state.snapshot_store,
            auth=auth,
        )
    except DetailedHTTPException as exc:
        if _is_tool_execution_error(exc):
            return _tool_execution_error_payload(exc)
        raise _map_http_exception(exc) from exc
    except ValidationError as exc:
        return _tool_execution_error_payload(validation_exception(exc))

    content_list = [
        item.model_dump(by_alias=True) if isinstance(item, BaseModel) else item
        for item in result.content
    ]
    payload: dict[str, Any] = {
        "content": content_list,
        "isError": result.isError,
        "structuredContent": result.structured_content,
    }
    if result.annotations:
        payload["annotations"] = result.annotations
    return payload


def _is_tool_execution_error(exc: DetailedHTTPException) -> bool:
    return exc.status_code == status.HTTP_400_BAD_REQUEST and exc.error_code == ErrorCode.INVALID_INPUT


def _tool_execution_error_payload(exc: DetailedHTTPException) -> dict[str, Any]:
    details = [_detail_to_dict(detail) for detail in exc.error_details]
    structured = {
        "error": {
            "code": (exc.error_code or ErrorCode.INVALID_INPUT).value,
            "message": str(exc.detail),
            "details": details,
        }
    }
    return {
        "content": [{"type": "text", "text": json.dumps(structured, indent=2)}],
        "isError": True,
        "structuredContent": structured,
    }


async def _optional_auth_dependency(request: Request) -> AuthContext | None:
    try:
        return await auth_dependency(request)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise _map_http_exception_from_http(exc) from exc


def _resource_auth_allowed(auth: AuthContext | None) -> bool:
    if auth is None:
        return False
    return bool(set(auth.roles).intersection({"viewer", "operator", "admin"}))


def _ensure_resource_auth(auth: AuthContext | None) -> None:
    if _resource_auth_allowed(auth):
        return
    raise JSONRPCDispatchError(UNAUTHORIZED, "Authentication required for this resource")


async def _handle_list_resources(request: Request, auth: AuthContext | None) -> dict[str, Any]:
    resources = _base_resource_descriptors()
    try:
        schema_items = resource_routes._schema_index()  # type: ignore[attr-defined]
    except Exception:
        schema_items = []
    for item in schema_items:
        resources.append(
            {
                "uri": f"pbpk://schemas/{item['schemaId']}",
                "name": f"schema:{item['schemaId']}",
                "title": item.get("title") or item["schemaId"],
                "description": item.get("description") or "Published PBPK-side JSON Schema.",
                "mimeType": "application/json",
            }
        )

    if _resource_auth_allowed(auth):
        resources.extend(_protected_resource_descriptors())
    return {"resources": resources}


def _handle_resource_templates() -> dict[str, Any]:
    return {
        "resourceTemplates": [
            {
                "uriTemplate": "pbpk://schemas/{schemaId}",
                "name": "pbpk-schema",
                "title": "PBPK Schema",
                "description": "Read a published PBPK-side schema and its example payload.",
                "mimeType": "application/json",
            },
            {
                "uriTemplate": "pbpk://parameters/{simulationId}",
                "name": "simulation-parameters",
                "title": "Simulation Parameters",
                "description": "Read parameter metadata for a loaded simulation.",
                "mimeType": "application/json",
            },
        ]
    }


async def _handle_read_resource(
    request: Request,
    params: dict[str, Any],
    auth: AuthContext | None,
) -> dict[str, Any]:
    uri = params.get("uri")
    if not uri or not isinstance(uri, str):
        raise JSONRPCDispatchError(INVALID_PARAMS, "Resource 'uri' is required")
    if uri not in PUBLIC_RESOURCE_URIS and not uri.startswith("pbpk://schemas/"):
        _ensure_resource_auth(auth)

    payload = await _read_resource_payload(request, uri)
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": "application/json",
                "text": json.dumps(payload, indent=2, sort_keys=True, default=str),
            }
        ]
    }


async def _read_resource_payload(request: Request, uri: str) -> Any:
    if uri == "pbpk://schemas/catalog":
        return _schema_catalog_payload()
    if uri.startswith("pbpk://schemas/"):
        schema_id = uri.removeprefix("pbpk://schemas/")
        return _schema_document_payload(schema_id)
    if uri == "pbpk://capability-matrix":
        matrix, sha256, _ = resource_routes._capability_matrix_document()  # type: ignore[attr-defined]
        return {"sha256": sha256, "matrix": matrix}
    if uri == "pbpk://contract-manifest":
        manifest, sha256, _ = resource_routes._contract_manifest_document()  # type: ignore[attr-defined]
        return {"sha256": sha256, "manifest": manifest}
    if uri == "pbpk://release-bundle-manifest":
        manifest, sha256, _ = resource_routes._release_bundle_manifest_document()  # type: ignore[attr-defined]
        return {"sha256": sha256, "manifest": manifest}
    if uri == "pbpk://models":
        snapshot = await maybe_to_thread(
            _should_offload(request), request.app.state.session_registry.snapshot
        )
        return {
            "items": await maybe_to_thread(
                _should_offload(request),
                resource_routes.discover_model_entries,  # type: ignore[attr-defined]
                loaded_records=snapshot,
            )
        }
    if uri == "pbpk://simulations":
        records = await maybe_to_thread(
            _should_offload(request), request.app.state.session_registry.snapshot
        )
        return {
            "items": [
                {
                    "id": record.handle.simulation_id,
                    "simulationId": record.handle.simulation_id,
                    "filePath": record.handle.file_path,
                    "metadata": dict(record.metadata or {}),
                    "createdAt": resource_routes._isoformat(record.created_at),  # type: ignore[attr-defined]
                    "lastAccessedAt": resource_routes._isoformat(record.last_accessed),  # type: ignore[attr-defined]
                }
                for record in records
            ]
        }
    if uri.startswith("pbpk://parameters/"):
        simulation_id = uri.removeprefix("pbpk://parameters/")
        try:
            summaries = await maybe_to_thread(
                _should_offload(request),
                request.app.state.adapter.list_parameters,
                simulation_id,
                None,
            )
        except AdapterError as exc:
            raise JSONRPCDispatchError(TOOL_EXECUTION_ERROR, str(exc)) from exc
        return {
            "simulationId": simulation_id,
            "items": [
                {
                    "id": f"{simulation_id}:{summary.path}",
                    "simulationId": simulation_id,
                    "path": summary.path,
                    "displayName": summary.display_name,
                    "unit": summary.unit,
                    "category": summary.category,
                    "isEditable": summary.is_editable,
                }
                for summary in summaries
            ],
        }
    raise JSONRPCDispatchError(METHOD_NOT_FOUND, f"Resource not found: {uri}")


def _schema_catalog_payload() -> dict[str, Any]:
    return {
        "items": [
            {key: value for key, value in item.items() if not key.startswith("_") and key not in {"schema", "example"}}
            for item in resource_routes._schema_index()  # type: ignore[attr-defined]
        ]
    }


def _schema_document_payload(schema_id: str) -> dict[str, Any]:
    normalized_id = schema_id.removesuffix(".json")
    match = next(
        (
            item
            for item in resource_routes._schema_index()  # type: ignore[attr-defined]
            if item["schemaId"] == normalized_id
        ),
        None,
    )
    if match is None:
        raise JSONRPCDispatchError(METHOD_NOT_FOUND, f"Schema resource not found: {schema_id}")
    return {key: value for key, value in match.items() if not key.startswith("_")}


def _base_resource_descriptors() -> list[dict[str, Any]]:
    return [
        {
            "uri": "pbpk://schemas/catalog",
            "name": "schema-catalog",
            "title": "PBPK Schema Catalog",
            "description": "Published PBPK-side object schema catalog.",
            "mimeType": "application/json",
        },
        {
            "uri": "pbpk://capability-matrix",
            "name": "capability-matrix",
            "title": "PBPK Capability Matrix",
            "description": "Machine-readable PBPK runtime support matrix.",
            "mimeType": "application/json",
        },
        {
            "uri": "pbpk://contract-manifest",
            "name": "contract-manifest",
            "title": "PBPK Contract Manifest",
            "description": "Published PBPK MCP contract manifest.",
            "mimeType": "application/json",
        },
        {
            "uri": "pbpk://release-bundle-manifest",
            "name": "release-bundle-manifest",
            "title": "PBPK Release Bundle Manifest",
            "description": "Release bundle artifact inventory and hashes.",
            "mimeType": "application/json",
        },
    ]


def _protected_resource_descriptors() -> list[dict[str, Any]]:
    return [
        {
            "uri": "pbpk://models",
            "name": "models",
            "title": "Discoverable PBPK Models",
            "description": "Filesystem-backed PBPK model catalog.",
            "mimeType": "application/json",
        },
        {
            "uri": "pbpk://simulations",
            "name": "simulations",
            "title": "Loaded PBPK Simulations",
            "description": "Loaded simulation session registry.",
            "mimeType": "application/json",
        },
    ]


def _map_http_exception(exc: DetailedHTTPException) -> JSONRPCDispatchError:
    status_code = exc.status_code
    error_code = exc.error_code or ErrorCode.INTERNAL_ERROR

    if status_code == status.HTTP_401_UNAUTHORIZED:
        return JSONRPCDispatchError(UNAUTHORIZED, str(exc.detail))
    if status_code == status.HTTP_403_FORBIDDEN:
        return JSONRPCDispatchError(FORBIDDEN, str(exc.detail))
    if status_code == status.HTTP_428_PRECONDITION_REQUIRED:
        return JSONRPCDispatchError(TOOL_EXECUTION_ERROR, str(exc.detail))
    if status_code == status.HTTP_404_NOT_FOUND:
        return JSONRPCDispatchError(METHOD_NOT_FOUND, str(exc.detail))
    if status_code == status.HTTP_409_CONFLICT:
        return JSONRPCDispatchError(TOOL_EXECUTION_ERROR, str(exc.detail))
    if status_code == status.HTTP_400_BAD_REQUEST or error_code == ErrorCode.INVALID_INPUT:
        data = [_detail_to_dict(detail) for detail in exc.error_details]
        return JSONRPCDispatchError(INVALID_PARAMS, str(exc.detail), data=data or None)

    return JSONRPCDispatchError(TOOL_EXECUTION_ERROR, str(exc.detail))


def _map_http_exception_from_http(exc: HTTPException) -> JSONRPCDispatchError:
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        return JSONRPCDispatchError(UNAUTHORIZED, str(exc.detail))
    if exc.status_code == status.HTTP_403_FORBIDDEN:
        return JSONRPCDispatchError(FORBIDDEN, str(exc.detail))
    return JSONRPCDispatchError(TOOL_EXECUTION_ERROR, str(exc.detail))


def _detail_to_dict(detail: Any) -> dict[str, Any]:
    if hasattr(detail, "to_dict"):
        return detail.to_dict()
    if isinstance(detail, dict):
        return detail
    return {"issue": str(detail)}


def _normalize_tool_arguments(params: dict[str, Any]) -> dict[str, Any]:
    """Normalize tool arguments across Codex/Gemini and MCP shapes."""

    arguments = params.get("arguments")
    if isinstance(arguments, dict):
        return arguments

    parameters = params.get("parameters")
    if isinstance(parameters, dict):
        return parameters

    fallback = {
        key: value
        for key, value in params.items()
        if key
        not in {
            "name",
            "tool",
            "arguments",
            "parameters",
            "idempotencyKey",
            "idempotency_key",
            "critical",
        }
    }
    return fallback


def _title_from_name(name: str) -> str:
    return " ".join(token.capitalize() for token in name.split("_"))


def _should_offload(request: Request) -> bool:
    return bool(getattr(request.app.state, "adapter_offload", True))


__all__ = ["router"]
