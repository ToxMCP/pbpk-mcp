from __future__ import annotations

from mcp.server.caching import CacheHint
from mcp.server.context import ServerRequestContext
from mcp.server.lowlevel import Server
from mcp_types import (
    CallToolRequestParams,
    CallToolResult,
    GetPromptRequestParams,
    ListPromptsResult,
    ListResourcesResult,
    ListResourceTemplatesResult,
    ListToolsResult,
    GetPromptResult,
    PaginatedRequestParams,
    ReadResourceRequestParams,
    ReadResourceResult,
    Tool,
    ToolAnnotations,
)

from . import __version__
from .backend import Backend

TOOL_POLICY_KEY = "org.toxmcp/toolPolicy"
RESULT_ANNOTATIONS_KEY = "org.toxmcp/resultAnnotations"
INVOCATION_KEY = "org.toxmcp/invocation"


def create_server(backend: Backend) -> Server:
    def raw_params(context):
        params = dict(context.params or {})
        params.pop("_meta", None)
        return params

    async def tools(context: ServerRequestContext, params: PaginatedRequestParams | None):
        result = await backend.invoke("tools/list", raw_params(context), context.request)
        tools = []
        for original in result["tools"]:
            item = dict(original)
            annotations = item.get("annotations", {})
            extra = {
                key: value
                for key, value in annotations.items()
                if key
                not in {
                    "title",
                    "readOnlyHint",
                    "destructiveHint",
                    "idempotentHint",
                    "openWorldHint",
                }
            }
            item["annotations"] = ToolAnnotations.model_validate(
                {key: value for key, value in annotations.items() if key not in extra}
            )
            if extra:
                item["_meta"] = {**item.get("_meta", {}), TOOL_POLICY_KEY: extra}
            tools.append(Tool.model_validate(item))
        return ListToolsResult(tools=tools, next_cursor=result.get("nextCursor"))

    async def call(context: ServerRequestContext, params: CallToolRequestParams):
        raw = raw_params(context)
        raw.update(name=params.name, arguments=params.arguments or {})
        metadata = dict((context.params or {}).get("_meta", {}))
        invocation = metadata.get(INVOCATION_KEY, {})
        if isinstance(invocation, dict):
            for key in ["critical", "idempotencyKey"]:
                if key in invocation:
                    raw[key] = invocation[key]
        result = dict(await backend.invoke("tools/call", raw, context.request))
        annotations = result.pop("annotations", None)
        if annotations is not None:
            result["_meta"] = {**result.get("_meta", {}), RESULT_ANNOTATIONS_KEY: annotations}
        return CallToolResult.model_validate(result)

    async def resources(context: ServerRequestContext, params: PaginatedRequestParams | None):
        return ListResourcesResult.model_validate(
            await backend.invoke("resources/list", raw_params(context), context.request)
        )

    async def templates(context: ServerRequestContext, params: PaginatedRequestParams | None):
        return ListResourceTemplatesResult.model_validate(
            await backend.invoke("resources/templates/list", raw_params(context), context.request)
        )

    async def read(context: ServerRequestContext, params: ReadResourceRequestParams):
        raw = raw_params(context)
        raw["uri"] = str(params.uri)
        return ReadResourceResult.model_validate(
            await backend.invoke("resources/read", raw, context.request)
        )

    async def prompts(context: ServerRequestContext, params: PaginatedRequestParams | None):
        return ListPromptsResult.model_validate(
            await backend.invoke("prompts/list", raw_params(context), context.request)
        )

    async def get_prompt(context: ServerRequestContext, params: GetPromptRequestParams):
        return GetPromptResult.model_validate(
            await backend.invoke("prompts/get", raw_params(context), context.request)
        )

    return Server(
        "pbpk-mcp-sdk2",
        version=__version__,
        title="PBPK MCP SDK2 transport",
        on_list_tools=tools,
        on_call_tool=call,
        on_list_resources=resources,
        on_read_resource=read,
        on_list_resource_templates=templates,
        on_list_prompts=prompts,
        on_get_prompt=get_prompt,
        cache_hints={
            method: CacheHint(ttl_ms=0, scope="private")
            for method in [
                "tools/list",
                "resources/list",
                "resources/templates/list",
                "prompts/list",
            ]
        },
    )
