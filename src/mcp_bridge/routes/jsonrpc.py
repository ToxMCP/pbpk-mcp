"""JSON-RPC transport exposing the MCP tool registry."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Union

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, Field, ValidationError

from ..config import AppConfig
from ..errors import DetailedHTTPException, ErrorCode, validation_exception
from ..routes import mcp as rest_mcp
from ..security.auth import AuthContext, auth_dependency

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/mcp", tags=["mcp-jsonrpc"])


class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Union[Dict[str, Any], list[Any]]] = None
    id: Optional[Union[str, int]] = None


class JSONRPCError(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None


class JSONRPCResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[JSONRPCError] = None
    id: Optional[Union[str, int]] = None

    model_config = {"exclude_none": True}


class FeatureSupport(BaseModel):
    enabled: bool


class InitializeResult(BaseModel):
    protocolVersion: str = Field(..., alias="protocolVersion")
    serverInfo: Dict[str, Optional[str]] = Field(..., alias="serverInfo")
    capabilities: Dict[str, FeatureSupport]


class ListToolsResult(BaseModel):
    tools: list[dict[str, Any]]


class ListPromptsResult(BaseModel):
    prompts: list[dict[str, Any]]


class JSONRPCDispatchError(Exception):
    def __init__(self, code: int, message: str, *, data: Optional[Any] = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

UNAUTHORIZED = -32000
FORBIDDEN = -32001
TOOL_EXECUTION_ERROR = -32002


MCP_PROTOCOL_VERSION = "2025-03-26"


def _create_error_response(
    code: int,
    message: str,
    request_id: Optional[Union[str, int]],
    *,
    data: Optional[Any] = None,
) -> dict[str, Any]:
    payload = JSONRPCResponse(
        id=request_id,
        error=JSONRPCError(code=code, message=message, data=data),
    )
    return payload.model_dump()


def _create_success_response(result: Any, request_id: Optional[Union[str, int]]) -> dict[str, Any]:
    payload = JSONRPCResponse(id=request_id, result=result)
    return payload.model_dump()


@router.post("")
@router.post("/jsonrpc")
async def jsonrpc_endpoint(request: Request, response: Response) -> Any:
    body: Any = None
    if request.url.path.endswith("/jsonrpc"):
        logger.warning("jsonrpc.legacy_endpoint path=%s (prefer /mcp)", request.url.path)
    try:
        try:
            body = await request.json()
        except Exception as exc:  # noqa: BLE001
            logger.error("jsonrpc.invalid_json", exc_info=exc)
            response.status_code = status.HTTP_400_BAD_REQUEST
            return _create_error_response(PARSE_ERROR, "Invalid JSON payload", None)

        if isinstance(body, list):
            response.status_code = status.HTTP_400_BAD_REQUEST
            return _create_error_response(
                INVALID_REQUEST,
                "Batch requests are not supported",
                None,
            )

        try:
            rpc_request = JSONRPCRequest.model_validate(body)
        except ValidationError as exc:
            logger.error("jsonrpc.invalid_request", exc_info=exc)
            response.status_code = status.HTTP_400_BAD_REQUEST
            request_id = body.get("id") if isinstance(body, dict) else None
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
            return _create_error_response(
                exc.code,
                str(exc),
                rpc_request.id,
                data=exc.data,
            )

        if rpc_request.id is None:
            response.status_code = status.HTTP_204_NO_CONTENT
            return None

        response.status_code = status.HTTP_200_OK
        return _create_success_response(result, rpc_request.id)

    except Exception as exc:  # noqa: BLE001
        logger.exception("jsonrpc.unhandled_exception")
        request_id = None
        if isinstance(body, dict):
            request_id = body.get("id")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return _create_error_response(INTERNAL_ERROR, "Internal error", request_id, data=str(exc))


async def _dispatch_jsonrpc(request: Request, rpc_request: JSONRPCRequest) -> Any:
    method = rpc_request.method
    params = rpc_request.params or {}

    if isinstance(params, list):
        raise JSONRPCDispatchError(INVALID_PARAMS, "Positional parameters are not supported")

    if method == "initialize":
        return _handle_initialize(request)
    if method in {"initialized", "notifications/initialized"}:
        return {}
    if method == "shutdown":
        return None

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


def _handle_initialize(request: Request) -> dict[str, Any]:
    config: AppConfig = request.app.state.config
    server_info = {
        "name": getattr(config, "service_name", "mcp-bridge"),
        "version": getattr(config, "service_version", "unknown"),
    }
    capabilities = {
        "tools": FeatureSupport(enabled=True),
        "prompts": FeatureSupport(enabled=False),
        "resources": FeatureSupport(enabled=False),
    }
    payload = InitializeResult(
        protocolVersion=MCP_PROTOCOL_VERSION,
        serverInfo=server_info,
        capabilities=capabilities,
    )
    return payload.model_dump(by_alias=True)


def _handle_list_tools(auth: AuthContext) -> dict[str, Any]:
    registry = rest_mcp.get_tool_registry()
    tools: list[dict[str, Any]] = []
    for descriptor in registry.values():
        if auth.roles and descriptor.roles:
            if not set(auth.roles).intersection(descriptor.roles):
                continue
        tools.append(
            {
                "name": descriptor.name,
                "description": descriptor.description,
                "inputSchema": descriptor.input_schema(),
                "annotations": rest_mcp._tool_annotations(descriptor),  # type: ignore[attr-defined]
            }
        )
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

    adapter = request.app.state.adapter
    job_service = request.app.state.jobs
    population_store = request.app.state.population_store
    audit = request.app.state.audit

    try:
        result: rest_mcp.CallToolResponse = await rest_mcp.call_tool(  # type: ignore[call-arg]
            http_request=request,
            request=request_model,
            adapter=adapter,
            job_service=job_service,
            population_store=population_store,
            audit_trail=audit,
            auth=auth,
        )
    except DetailedHTTPException as exc:
        raise _map_http_exception(exc) from exc
    except ValidationError as exc:
        mapped = validation_exception(exc)
        raise _map_http_exception(mapped) from exc

    # Use the content directly from the CallToolResponse which is now standard MCP format
    # Ensure items in content are dicts (they should be if model_dump was called, but let's be safe)
    content_list = []
    for item in result.content:
        if isinstance(item, BaseModel):
            content_list.append(item.model_dump(by_alias=True))
        else:
            content_list.append(item)

    payload: dict[str, Any] = {
        "content": content_list,
        "isError": result.isError
    }
    
    if result.annotations:
        payload["annotations"] = result.annotations
        
    return payload


def _map_http_exception(exc: DetailedHTTPException) -> JSONRPCDispatchError:
    status_code = exc.status_code
    error_code = exc.error_code or ErrorCode.INTERNAL_ERROR

    if status_code == status.HTTP_401_UNAUTHORIZED:
        return JSONRPCDispatchError(UNAUTHORIZED, str(exc.detail))
    if status_code == status.HTTP_403_FORBIDDEN:
        return JSONRPCDispatchError(FORBIDDEN, str(exc.detail))
    if status_code == status.HTTP_404_NOT_FOUND:
        return JSONRPCDispatchError(METHOD_NOT_FOUND, str(exc.detail))
    if status_code == status.HTTP_409_CONFLICT:
        return JSONRPCDispatchError(TOOL_EXECUTION_ERROR, str(exc.detail))
    if status_code == status.HTTP_400_BAD_REQUEST or error_code == ErrorCode.INVALID_INPUT:
        data = [_detail_to_dict(detail) for detail in exc.error_details]
        return JSONRPCDispatchError(INVALID_PARAMS, str(exc.detail), data=data or None)

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


__all__ = ["router"]
