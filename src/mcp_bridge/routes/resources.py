"""Read-only MCP resource endpoints for simulations and parameters."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Sequence

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from mcp.session_registry import SessionRecord, SessionRegistry

from ..adapter import AdapterError
from ..adapter.interface import OspsuiteAdapter
from ..dependencies import get_adapter, get_session_registry
from ..errors import DetailedHTTPException, ErrorCode, adapter_error_to_http, error_detail
from ..util.concurrency import maybe_to_thread

router = APIRouter(prefix="/mcp/resources", tags=["mcp-resources"])


def _should_offload(request: Request) -> bool:
    return bool(getattr(request.app.state, "adapter_offload", True))


def _to_camel(string: str) -> str:
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        frozen=True,
        protected_namespaces=(),
    )


class PaginationModel(CamelModel):
    page: int
    limit: int
    total: int


class SimulationResource(CamelModel):
    id: str
    simulation_id: str = Field(alias="simulationId")
    display_name: Optional[str] = Field(default=None, alias="displayName")
    model_version: Optional[str] = Field(default=None, alias="modelVersion")
    created_at: str = Field(alias="createdAt")
    last_accessed_at: str = Field(alias="lastAccessedAt")
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulationResourcePage(CamelModel):
    items: list[SimulationResource]
    page: int
    limit: int
    total: int


class ParameterResource(CamelModel):
    id: str
    simulation_id: str = Field(alias="simulationId")
    path: str
    display_name: Optional[str] = Field(default=None, alias="displayName")
    unit: Optional[str] = None
    category: Optional[str] = None
    is_editable: Optional[bool] = Field(default=None, alias="isEditable")


class ParameterResourcePage(CamelModel):
    items: list[ParameterResource]
    page: int
    limit: int
    total: int


def _isoformat(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _weak_etag(tokens: Sequence[str]) -> str:
    payload = "|".join(tokens) if tokens else "empty"
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()
    return f'W/"{digest}"'


def _fingerprint_metadata(metadata: dict[str, Any]) -> str:
    if not metadata:
        return "meta:none"
    try:
        serialised = json.dumps(metadata, sort_keys=True, default=str)
    except TypeError:
        serialised = str(sorted(metadata.items()))
    return hashlib.sha1(serialised.encode("utf-8")).hexdigest()


def _paginate(items: Sequence[Any], *, page: int, limit: int) -> Sequence[Any]:
    start = (page - 1) * limit
    if start >= len(items):
        return ()
    return items[start : start + limit]


def _sort_records(records: Iterable[SessionRecord]) -> list[SessionRecord]:
    return sorted(records, key=lambda record: record.handle.simulation_id.lower())


def _http_error(
    *,
    status_code: int,
    message: str,
    code: ErrorCode,
    field: Optional[str] = None,
    hint: Optional[str] = None,
) -> DetailedHTTPException:
    details = [error_detail(issue=message, field=field, hint=hint)] if field or hint else []
    return DetailedHTTPException(
        status_code=status_code, message=message, code=code, details=details
    )


@router.get("/simulations", response_model=SimulationResourcePage)
async def list_simulation_resources(
    request: Request,
    response: Response,
    session_store: SessionRegistry = Depends(get_session_registry),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    search: Optional[str] = Query(default=None),
) -> SimulationResourcePage:
    snapshot = await maybe_to_thread(_should_offload(request), session_store.snapshot)
    records = _sort_records(snapshot)

    if search:
        lowered = search.lower()
        records = [
            record
            for record in records
            if lowered in record.handle.simulation_id.lower()
            or lowered in json.dumps(record.metadata or {}).lower()
        ]

    total = len(records)
    page_items = list(_paginate(records, page=page, limit=limit))

    items: list[SimulationResource] = []
    fingerprints: list[str] = []
    last_modified_candidates: list[float] = []

    for record in page_items:
        sim_id = record.handle.simulation_id
        created_at = _isoformat(record.created_at)
        last_accessed_at = _isoformat(record.last_accessed)
        display_name = None
        model_version = None
        metadata = dict(record.metadata or {})
        if metadata:
            display_name = str(metadata.get("name") or metadata.get("displayName") or "")
            model_version = str(metadata.get("modelVersion") or "")
        resource = SimulationResource(
            id=sim_id,
            simulationId=sim_id,
            displayName=display_name or None,
            modelVersion=model_version or None,
            createdAt=created_at,
            lastAccessedAt=last_accessed_at,
            metadata=metadata,
        )
        items.append(resource)
        fingerprints.append(
            f"{sim_id}:{created_at}:{last_accessed_at}:{_fingerprint_metadata(metadata)}"
        )
        last_modified_candidates.extend([record.created_at, record.last_accessed])

    etag = _weak_etag(fingerprints)
    if_none_match = request.headers.get("if-none-match")
    headers = {"ETag": etag}

    if last_modified_candidates:
        last_modified = max(last_modified_candidates)
        headers["Last-Modified"] = _isoformat(last_modified)

    if if_none_match and if_none_match == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    response.headers.update(headers)
    return SimulationResourcePage(items=items, page=page, limit=limit, total=total)


@router.get("/parameters", response_model=ParameterResourcePage)
async def list_parameter_resources(
    request: Request,
    response: Response,
    adapter: OspsuiteAdapter = Depends(get_adapter),
    session_store: SessionRegistry = Depends(get_session_registry),
    simulation_id: str = Query(..., alias="simulationId", min_length=1, max_length=64),
    filter_pattern: Optional[str] = Query(default=None, alias="filter"),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000),
) -> ParameterResourcePage:
    offload = _should_offload(request)
    snapshot = await maybe_to_thread(offload, session_store.snapshot)
    record_map = {record.handle.simulation_id: record for record in snapshot}
    record = record_map.get(simulation_id)
    if not record:
        raise _http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"Simulation '{simulation_id}' is not registered",
            code=ErrorCode.NOT_FOUND,
            field="simulationId",
            hint="Load the simulation before inspecting parameter resources.",
        )

    pattern = filter_pattern.strip() if filter_pattern else None
    try:
        summaries = await maybe_to_thread(
            offload, adapter.list_parameters, simulation_id, pattern or None
        )
    except AdapterError as exc:
        raise adapter_error_to_http(exc) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise _http_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Unexpected error listing parameters",
            code=ErrorCode.INTERNAL_ERROR,
        ) from exc

    summaries = sorted(summaries, key=lambda summary: summary.path.lower())
    total = len(summaries)
    page_summaries = list(_paginate(summaries, page=page, limit=limit))

    items: list[ParameterResource] = []
    fingerprints: list[str] = []
    metadata_fingerprint = _fingerprint_metadata(record.metadata or {})
    sim_created_at = _isoformat(record.created_at)
    sim_last_accessed = _isoformat(record.last_accessed)

    for summary in page_summaries:
        items.append(
            ParameterResource(
                id=f"{simulation_id}:{summary.path}",
                simulationId=simulation_id,
                path=summary.path,
                displayName=summary.display_name,
                unit=summary.unit,
                category=summary.category,
                isEditable=summary.is_editable,
            )
        )
        fingerprints.append(
            f"{simulation_id}:{summary.path}:{summary.unit or ''}:"
            f"{summary.display_name or ''}:{summary.category or ''}:"
            f"{summary.is_editable}"
        )

    etag = _weak_etag(fingerprints)
    headers = {"ETag": etag, "Last-Modified": sim_last_accessed}
    if_none_match = request.headers.get("if-none-match")

    if if_none_match and if_none_match == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    response.headers.update(headers)
    response.headers["MCP-Simulation-Created-At"] = sim_created_at
    response.headers["MCP-Simulation-Fingerprint"] = metadata_fingerprint
    return ParameterResourcePage(items=items, page=page, limit=limit, total=total)
