#!/usr/bin/env python3
"""Export OpenAPI spec and tool JSON Schemas for documentation bundles."""

from __future__ import annotations

import argparse
import json
import sys
import types
from pathlib import Path
from typing import Iterable

try:
    import prometheus_client  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - documentation environments only
    class _NoopMetric:
        def __init__(self, *args, **kwargs) -> None:  # noqa: D401
            pass

        def labels(self, *args, **kwargs):  # noqa: D401
            return self

        def inc(self, *args, **kwargs) -> None:  # noqa: D401
            return None

        def dec(self, *args, **kwargs) -> None:  # noqa: D401
            return None

    class _NoopHistogram(_NoopMetric):
        def observe(self, *args, **kwargs) -> None:  # noqa: D401
            return None

    def _generate_latest() -> bytes:
        return b""

    stub = types.SimpleNamespace(
        Counter=_NoopMetric,
        Gauge=_NoopMetric,
        Histogram=_NoopHistogram,
        CONTENT_TYPE_LATEST="text/plain; version=0.0.4; charset=utf-8",
        generate_latest=_generate_latest,
    )
    sys.modules["prometheus_client"] = stub


def _ensure_stub_module(name: str, attrs: dict[str, object]) -> None:
    if name in sys.modules:
        return
    parts = name.split(".")
    for idx in range(1, len(parts)):
        pkg_name = ".".join(parts[:idx])
        if pkg_name not in sys.modules:
            pkg = types.ModuleType(pkg_name)
            pkg.__path__ = []  # type: ignore[attr-defined]
            sys.modules[pkg_name] = pkg
    module = types.ModuleType(name)
    for attr, value in attrs.items():
        setattr(module, attr, value)
    sys.modules[name] = module


try:
    import langchain_core.messages  # noqa: F401
    import langchain_core.pydantic_v1  # noqa: F401
    import langchain_core.tools  # noqa: F401
    import langchain_core.utils.function_calling  # noqa: F401
    import langgraph.checkpoint.memory  # noqa: F401
    import langgraph.checkpoint.sqlite  # noqa: F401
    import langgraph.checkpoint.base  # noqa: F401
    import langgraph.constants  # noqa: F401
    import langgraph.graph  # noqa: F401
    import langgraph.pregel  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - documentation environments only
    class _StubMessage:
        def __init__(self, content: str | None = None, **kwargs) -> None:
            self.content = content
            self.kwargs = kwargs

    class _StubStructuredTool:
        def __init__(self, *_, name: str | None = None, description: str | None = None, func=None, args_schema=None, **__) -> None:  # noqa: ANN001
            self.name = name or getattr(func, "__name__", "tool")
            self.description = description
            self.func = func
            self.args_schema = args_schema

        def __call__(self, *args, **kwargs):
            if self.func is not None:
                return self.func(*args, **kwargs)
            raise NotImplementedError("StructuredTool stub cannot execute without an underlying function.")

    def _stub_convert_to_openai_function(function: object, **_) -> dict[str, str]:
        name = getattr(function, "__name__", "tool")
        return {"name": name}

    from collections import namedtuple

    _CheckpointTuple = namedtuple(
        "CheckpointTuple",
        ["config", "checkpoint", "metadata", "parent_config", "pending_writes"],
    )

    class _StubMemorySaver:
        def __init__(self, *_, **__):
            self._store: dict[str, object] = {}

        def put(self, config, checkpoint, metadata, new_versions=None):  # noqa: ANN001
            key = repr(config)
            self._store[key] = types.SimpleNamespace(
                config=config,
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=None,
                pending_writes=[],
            )
            return self._store[key]

        def put_writes(self, *_args, **_kwargs):
            return None

        def get_tuple(self, config):  # noqa: ANN001
            return self._store.get(repr(config))

    class _StubSqliteSaver(_StubMemorySaver):
        def __init__(self, *_, **__):
            super().__init__()

        def setup(self) -> None:
            return None

    class _StubStateGraph:
        def __init__(self, *_args, **_kwargs):
            self._nodes: dict[str, object] = {}

        def add_node(self, name: str, func) -> None:
            self._nodes[name] = func

        def add_edge(self, *_args, **_kwargs) -> None:
            return None

        def add_conditional_edges(self, *_args, **_kwargs) -> None:
            return None

        def set_entry_point(self, *_args, **_kwargs) -> None:
            return None

        def compile(self, **_kwargs):
            return object()

    def _stub_empty_checkpoint() -> dict:
        return {}

    from pydantic import BaseModel as _PydanticBaseModel
    from pydantic import Field as _PydanticField
    try:
        from pydantic import validator as _pydantic_validator
    except ImportError:  # pragma: no cover
        from pydantic.class_validators import validator as _pydantic_validator  # type: ignore

    _ensure_stub_module(
        "langchain_core.messages",
        {
            "AIMessage": type("AIMessage", (_StubMessage,), {}),
            "HumanMessage": type("HumanMessage", (_StubMessage,), {}),
            "BaseMessage": type("BaseMessage", (_StubMessage,), {}),
        },
    )
    _ensure_stub_module(
        "langchain_core.pydantic_v1",
        {
            "BaseModel": _PydanticBaseModel,
            "Field": _PydanticField,
            "validator": _pydantic_validator,
        },
    )
    _ensure_stub_module(
        "langchain_core.tools",
        {
            "StructuredTool": _StubStructuredTool,
        },
    )
    _ensure_stub_module("langchain_core.utils", {})
    _ensure_stub_module(
        "langchain_core.utils.function_calling",
        {"convert_to_openai_function": _stub_convert_to_openai_function},
    )
    _ensure_stub_module("langgraph", {})
    _ensure_stub_module("langgraph.checkpoint", {})
    _ensure_stub_module(
        "langgraph.checkpoint.memory",
        {"MemorySaver": _StubMemorySaver},
    )
    _ensure_stub_module(
        "langgraph.checkpoint.sqlite",
        {"SqliteSaver": _StubSqliteSaver},
    )
    _ensure_stub_module(
        "langgraph.checkpoint.base",
        {"CheckpointTuple": _CheckpointTuple},
    )
    _ensure_stub_module(
        "langgraph.constants",
        {"INTERRUPT": "__interrupt__"},
    )
    _ensure_stub_module(
        "langgraph.graph",
        {
            "END": "__end__",
            "StateGraph": _StubStateGraph,
        },
    )
    _ensure_stub_module(
        "langgraph.pregel",
        {"empty_checkpoint": _stub_empty_checkpoint},
    )

from mcp_bridge.app import create_app
from mcp_bridge.config import AppConfig
from mcp_bridge.tools.registry import get_tool_registry
from pydantic import BaseModel as _PydanticBaseModel


def _dump_json(path: Path, payload: object, indent: int) -> None:
    path.write_text(json.dumps(payload, indent=indent, sort_keys=True) + "\n")


def _export_openapi(app, contracts_dir: Path, indent: int) -> Path:
    contracts_dir.mkdir(parents=True, exist_ok=True)
    openapi = app.openapi()
    output = contracts_dir / "openapi.json"
    _dump_json(output, openapi, indent)
    return output


def _export_tool_schemas(
    schemas_dir: Path,
    indent: int,
) -> Iterable[Path]:
    schemas_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    registry = get_tool_registry()
    for tool_name, descriptor in registry.items():
        # Request schema reflects fields accepted by the tool.
        request_schema = descriptor.request_model.model_json_schema()
        request_path = schemas_dir / f"{tool_name}-request.json"
        _dump_json(request_path, request_schema, indent)
        paths.append(request_path)

        # Response schema is optional for fire-and-forget tools.
        if descriptor.response_model is not None:
            response_schema = descriptor.response_model.model_json_schema()
            response_path = schemas_dir / f"{tool_name}-response.json"
            _dump_json(response_path, response_schema, indent)
            paths.append(response_path)
    return paths


def _build_config(source: str) -> AppConfig:
    if source == "env":
        return AppConfig.from_env()
    return AppConfig()


def _rebuild_known_models() -> None:
    """Ensure Pydantic models with forward references are ready for schema export."""

    try:
        from mcp_bridge.routes import mcp as mcp_routes
        from mcp_bridge.routes import resources as resource_routes
        from mcp_bridge.routes import simulation as simulation_routes
    except ModuleNotFoundError:  # pragma: no cover - defensive
        return

    for module in (mcp_routes, resource_routes, simulation_routes):
        for name in dir(module):
            obj = getattr(module, name, None)
            if (
                isinstance(obj, type)
                and issubclass(obj, _PydanticBaseModel)
                and getattr(obj, "model_rebuild", None)
            ):
                try:
                    obj.model_rebuild(recursive=True)
                except Exception:
                    continue


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export OpenAPI and MCP tool schemas for the documentation bundle.",
    )
    parser.add_argument(
        "--contracts-dir",
        type=Path,
        default=Path("docs/mcp-bridge/contracts"),
        help="Directory to write OpenAPI specifications to (default: %(default)s)",
    )
    parser.add_argument(
        "--schemas-dir",
        type=Path,
        default=Path("docs/mcp-bridge/reference/schemas"),
        help="Directory to write tool JSON schemas to (default: %(default)s)",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation level for exported files (default: %(default)s)",
    )
    parser.add_argument(
        "--config-source",
        choices=("default", "env"),
        default="default",
        help="Load application configuration from defaults or environment variables.",
    )
    parser.add_argument(
        "--skip-schemas",
        action="store_true",
        help="Skip exporting per-tool JSON schemas (OpenAPI only).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    config = _build_config(args.config_source)
    app = create_app(config)
    _rebuild_known_models()
    try:
        openapi_path = _export_openapi(app, args.contracts_dir, args.indent)
        schema_paths: list[Path] = []
        if not args.skip_schemas:
            schema_paths = list(_export_tool_schemas(args.schemas_dir, args.indent))
    finally:
        adapter = getattr(app.state, "adapter", None)
        if adapter is not None:
            adapter.shutdown()
        job_service = getattr(app.state, "jobs", None)
        if job_service is not None:
            job_service.shutdown()
        audit = getattr(app.state, "audit", None)
        if audit is not None:
            audit.close()

    rendered_count = len(schema_paths)
    print(f"Exported OpenAPI spec to {openapi_path}")
    if rendered_count:
        print(f"Exported {rendered_count} tool schemas to {args.schemas_dir}")


if __name__ == "__main__":
    main()
