"""Read-only MCP resource endpoints for simulations, models, and parameters."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from mcp.session_registry import SessionRecord, SessionRegistry
try:  # pragma: no cover - fallback depends on installed package contents
    from mcp_bridge.contract import (
        capability_matrix_document as packaged_capability_matrix_document,
    )
    from mcp_bridge.contract import contract_manifest_document as packaged_contract_manifest_document
    from mcp_bridge.contract import schema_documents as packaged_schema_documents
    from mcp_bridge.contract import schema_examples as packaged_schema_examples
except Exception:  # pragma: no cover - runtime fallback when packaged artifacts are unavailable
    packaged_capability_matrix_document = None
    packaged_contract_manifest_document = None
    packaged_schema_documents = None
    packaged_schema_examples = None

from ..adapter import AdapterError
from ..adapter.interface import OspsuiteAdapter
from ..dependencies import get_adapter, get_session_registry
from ..errors import DetailedHTTPException, ErrorCode, adapter_error_to_http, error_detail
from ..model_catalog import discover_models as discover_model_entries
from ..model_catalog import model_catalog_fingerprint
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


class ModelResource(CamelModel):
    id: str
    model_id: str = Field(alias="modelId")
    suggested_simulation_id: str = Field(alias="suggestedSimulationId")
    file_path: str = Field(alias="filePath")
    relative_path: str = Field(alias="relativePath")
    root_path: str = Field(alias="rootPath")
    backend: str
    runtime_format: str = Field(alias="runtimeFormat")
    display_name: Optional[str] = Field(default=None, alias="displayName")
    model_version: Optional[str] = Field(default=None, alias="modelVersion")
    scientific_profile: Optional[bool] = Field(default=None, alias="scientificProfile")
    profile_source: Optional[str] = Field(default=None, alias="profileSource")
    population_simulation: Optional[bool] = Field(default=None, alias="populationSimulation")
    validation_hook: Optional[bool] = Field(default=None, alias="validationHook")
    discovery_state: str = Field(alias="discoveryState")
    is_loaded: bool = Field(alias="isLoaded")
    loaded_simulation_ids: list[str] = Field(default_factory=list, alias="loadedSimulationIds")
    modified_at: str = Field(alias="modifiedAt")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelResourcePage(CamelModel):
    items: list[ModelResource]
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


class SchemaResource(CamelModel):
    id: str
    schema_id: str = Field(alias="schemaId")
    version: str
    title: Optional[str] = None
    description: Optional[str] = None
    sha256: Optional[str] = None
    relative_path: str = Field(alias="relativePath")
    example_sha256: Optional[str] = Field(default=None, alias="exampleSha256")
    example_relative_path: Optional[str] = Field(default=None, alias="exampleRelativePath")


class SchemaResourcePage(CamelModel):
    items: list[SchemaResource]
    page: int
    limit: int
    total: int


class SchemaDocumentResource(CamelModel):
    id: str
    schema_id: str = Field(alias="schemaId")
    version: str
    title: Optional[str] = None
    description: Optional[str] = None
    sha256: Optional[str] = None
    relative_path: str = Field(alias="relativePath")
    example_sha256: Optional[str] = Field(default=None, alias="exampleSha256")
    example_relative_path: Optional[str] = Field(default=None, alias="exampleRelativePath")
    schema: dict[str, Any]
    example: Optional[dict[str, Any]] = None


class CapabilityMatrixResource(CamelModel):
    id: str
    contract_version: Optional[str] = Field(default=None, alias="contractVersion")
    sha256: Optional[str] = None
    relative_path: str = Field(alias="relativePath")
    entry_count: int = Field(alias="entryCount")
    matrix: dict[str, Any]


class ContractManifestResource(CamelModel):
    id: str
    contract_version: Optional[str] = Field(default=None, alias="contractVersion")
    sha256: Optional[str] = None
    relative_path: str = Field(alias="relativePath")
    schema_count: int = Field(alias="schemaCount")
    manifest: dict[str, Any]


def _isoformat(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_existing_path(candidates: Sequence[Path]) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


SCHEMA_ROOT = _resolve_existing_path(
    (
        Path("/app/var/contract/schemas"),
        Path("/app/schemas"),
        Path(__file__).resolve().parents[3] / "schemas",
    )
)
SCHEMA_EXAMPLES_ROOT = SCHEMA_ROOT / "examples"
CAPABILITY_MATRIX_PATH = _resolve_existing_path(
    (
        Path("/app/var/contract/capability_matrix.json"),
        Path("/app/docs/architecture/capability_matrix.json"),
        Path(__file__).resolve().parents[3] / "docs" / "architecture" / "capability_matrix.json",
    )
)
CONTRACT_MANIFEST_PATH = _resolve_existing_path(
    (
        Path("/app/var/contract/contract_manifest.json"),
        Path("/app/docs/architecture/contract_manifest.json"),
        Path(__file__).resolve().parents[3] / "docs" / "architecture" / "contract_manifest.json",
    )
)


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


def _load_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_document(document: dict[str, Any]) -> str:
    return hashlib.sha256(
        (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    ).hexdigest()


def _contract_manifest_document() -> tuple[dict[str, Any], str, float]:
    if CONTRACT_MANIFEST_PATH.exists():
        return (
            _load_json_file(CONTRACT_MANIFEST_PATH),
            _sha256_path(CONTRACT_MANIFEST_PATH),
            CONTRACT_MANIFEST_PATH.stat().st_mtime,
        )

    if packaged_contract_manifest_document is None:
        raise FileNotFoundError(CONTRACT_MANIFEST_PATH)

    manifest = packaged_contract_manifest_document()
    return (manifest, _sha256_document(manifest), 0.0)


def _schema_index() -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    contract_manifest: dict[str, Any] | None = None
    try:
        contract_manifest, _, _ = _contract_manifest_document()
    except FileNotFoundError:
        contract_manifest = None
    manifest_schema_index = {
        entry["schemaId"]: entry for entry in (contract_manifest or {}).get("schemas") or []
    }

    if SCHEMA_ROOT.exists():
        for schema_path in sorted(SCHEMA_ROOT.glob("*.v*.json")):
            document = _load_json_file(schema_path)
            schema_id = schema_path.stem
            version = schema_id.rsplit(".", 1)[-1] if "." in schema_id else "v1"
            example_path = SCHEMA_EXAMPLES_ROOT / f"{schema_id}.example.json"
            manifest_entry = manifest_schema_index.get(schema_id, {})
            resources.append(
                {
                    "id": schema_id,
                    "schemaId": schema_id,
                    "version": version,
                    "title": document.get("title"),
                    "description": document.get("description"),
                    "sha256": manifest_entry.get("sha256") or _sha256_path(schema_path),
                    "relativePath": f"schemas/{schema_path.name}",
                    "exampleSha256": (
                        manifest_entry.get("exampleSha256")
                        or (_sha256_path(example_path) if example_path.exists() else None)
                    ),
                    "exampleRelativePath": (
                        f"schemas/examples/{example_path.name}" if example_path.exists() else None
                    ),
                    "schema": document,
                    "example": _load_json_file(example_path) if example_path.exists() else None,
                    "_fingerprint": f"{schema_id}:{schema_path.stat().st_mtime}:{example_path.stat().st_mtime if example_path.exists() else 'none'}",
                    "_last_modified": max(
                        schema_path.stat().st_mtime,
                        example_path.stat().st_mtime if example_path.exists() else 0.0,
                    ),
                }
            )
        return resources

    if packaged_schema_documents is None or packaged_schema_examples is None:
        raise FileNotFoundError(SCHEMA_ROOT)

    documents = packaged_schema_documents()
    examples = packaged_schema_examples()
    for schema_id, document in sorted(documents.items()):
        version = schema_id.rsplit(".", 1)[-1] if "." in schema_id else "v1"
        example = examples.get(schema_id)
        manifest_entry = manifest_schema_index.get(schema_id, {})
        resources.append(
            {
                "id": schema_id,
                "schemaId": schema_id,
                "version": version,
                "title": document.get("title"),
                "description": document.get("description"),
                "sha256": manifest_entry.get("sha256") or _sha256_document(document),
                "relativePath": f"schemas/{schema_id}.json",
                "exampleSha256": (
                    manifest_entry.get("exampleSha256")
                    or (_sha256_document(example) if example is not None else None)
                ),
                "exampleRelativePath": (
                    f"schemas/examples/{schema_id}.example.json" if example is not None else None
                ),
                "schema": document,
                "example": example,
                "_fingerprint": hashlib.sha1(
                    json.dumps({"schema": document, "example": example}, sort_keys=True).encode("utf-8")
                ).hexdigest(),
                "_last_modified": 0.0,
            }
        )
    return resources


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
    return DetailedHTTPException(status_code=status_code, message=message, code=code, details=details)


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


@router.get("/models", response_model=ModelResourcePage)
async def list_model_resources(
    request: Request,
    response: Response,
    session_store: SessionRegistry = Depends(get_session_registry),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(default=None),
    backend: Optional[str] = Query(default=None),
    loaded_only: bool = Query(default=False, alias="loadedOnly"),
) -> ModelResourcePage:
    offload = _should_offload(request)
    snapshot = await maybe_to_thread(offload, session_store.snapshot)

    try:
        all_items = await maybe_to_thread(
            offload,
            discover_model_entries,
            search=search,
            backend=backend,
            loaded_records=snapshot,
            loaded_only=loaded_only,
        )
    except ValueError as exc:
        raise _http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(exc),
            code=ErrorCode.INVALID_INPUT,
            field="backend",
            hint="Use 'ospsuite' or 'rxode2'.",
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise _http_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Unexpected error discovering models",
            code=ErrorCode.INTERNAL_ERROR,
        ) from exc

    total = len(all_items)
    page_items = list(_paginate(all_items, page=page, limit=limit))
    items = [ModelResource.model_validate(item) for item in page_items]

    fingerprint = model_catalog_fingerprint(page_items)
    etag = _weak_etag([fingerprint, str(page), str(limit), search or "", backend or "", str(loaded_only)])
    headers = {"ETag": etag}
    if page_items:
        headers["Last-Modified"] = max(item["modifiedAt"] for item in page_items)

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    response.headers.update(headers)
    return ModelResourcePage(items=items, page=page, limit=limit, total=total)


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
            f"{simulation_id}:{summary.path}:{summary.unit or ''}:{summary.display_name or ''}:{summary.category or ''}:{summary.is_editable}"
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


@router.get("/schemas", response_model=SchemaResourcePage)
async def list_schema_resources(
    request: Request,
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(default=None),
) -> SchemaResourcePage:
    try:
        schema_items = _schema_index()
    except FileNotFoundError as exc:
        raise _http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Published schema resources are not available in the current runtime",
            code=ErrorCode.NOT_FOUND,
            hint="Mount the repository schemas directory into the API container.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise _http_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Published schema resources are malformed",
            code=ErrorCode.INTERNAL_ERROR,
        ) from exc

    if search:
        lowered = search.lower()
        schema_items = [
            item
            for item in schema_items
            if lowered in item["schemaId"].lower()
            or lowered in (item.get("title") or "").lower()
            or lowered in (item.get("description") or "").lower()
        ]

    total = len(schema_items)
    page_items = list(_paginate(schema_items, page=page, limit=limit))
    response_items = [
        SchemaResource.model_validate({key: value for key, value in item.items() if not key.startswith("_")})
        for item in page_items
    ]

    etag = _weak_etag([item["_fingerprint"] for item in page_items] + [str(page), str(limit), search or ""])
    headers = {"ETag": etag}
    if page_items:
        last_modified = max(item["_last_modified"] for item in page_items)
        if last_modified > 0:
            headers["Last-Modified"] = _isoformat(last_modified)

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    response.headers.update(headers)
    return SchemaResourcePage(items=response_items, page=page, limit=limit, total=total)


@router.get("/schemas/{schema_id}", response_model=SchemaDocumentResource)
async def get_schema_resource(
    schema_id: str,
    request: Request,
    response: Response,
) -> SchemaDocumentResource:
    normalized_id = schema_id.removesuffix(".json")
    try:
        match = next((item for item in _schema_index() if item["schemaId"] == normalized_id), None)
    except FileNotFoundError as exc:
        raise _http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Published schema resources are not available in the current runtime",
            code=ErrorCode.NOT_FOUND,
            hint="Mount the repository schemas directory into the API container.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise _http_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Published schema resources are malformed",
            code=ErrorCode.INTERNAL_ERROR,
        ) from exc

    if match is None:
        raise _http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"Schema resource '{schema_id}' was not found",
            code=ErrorCode.NOT_FOUND,
            field="schemaId",
        )

    etag = _weak_etag([match["_fingerprint"]])
    headers = {"ETag": etag}
    if match["_last_modified"] > 0:
        headers["Last-Modified"] = _isoformat(match["_last_modified"])
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    response.headers.update(headers)
    return SchemaDocumentResource.model_validate(
        {key: value for key, value in match.items() if not key.startswith("_")}
    )


@router.get("/capability-matrix", response_model=CapabilityMatrixResource)
async def get_capability_matrix_resource(
    request: Request,
    response: Response,
) -> CapabilityMatrixResource:
    try:
        contract_manifest, _, _ = _contract_manifest_document()
    except FileNotFoundError:
        contract_manifest = {}
    if CAPABILITY_MATRIX_PATH.exists():
        try:
            matrix = _load_json_file(CAPABILITY_MATRIX_PATH)
        except json.JSONDecodeError as exc:
            raise _http_error(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Capability matrix resource is malformed",
                code=ErrorCode.INTERNAL_ERROR,
            ) from exc

        etag = _weak_etag(
            [
                str(CAPABILITY_MATRIX_PATH.stat().st_mtime),
                matrix.get("contractVersion", ""),
                str(len(matrix.get("entries", []))),
            ]
        )
        headers = {
            "ETag": etag,
            "Last-Modified": _isoformat(CAPABILITY_MATRIX_PATH.stat().st_mtime),
        }
        matrix_sha256 = (
            (contract_manifest.get("capabilityMatrix") or {}).get("sha256")
            or _sha256_path(CAPABILITY_MATRIX_PATH)
        )
    else:
        if packaged_capability_matrix_document is None:
            raise _http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Capability matrix resource is not available in the current runtime",
                code=ErrorCode.NOT_FOUND,
                hint="Install the packaged contract artifacts or provide the runtime patch manifest copy.",
            )
        matrix = packaged_capability_matrix_document()
        etag = _weak_etag(
            [
                hashlib.sha1(json.dumps(matrix, sort_keys=True).encode("utf-8")).hexdigest(),
                matrix.get("contractVersion", ""),
                str(len(matrix.get("entries", []))),
            ]
        )
        headers = {"ETag": etag}
        matrix_sha256 = (
            (contract_manifest.get("capabilityMatrix") or {}).get("sha256")
            or _sha256_document(matrix)
        )
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    response.headers.update(headers)
    return CapabilityMatrixResource(
        id="capability-matrix",
        contractVersion=matrix.get("contractVersion"),
        sha256=matrix_sha256,
        relativePath="docs/architecture/capability_matrix.json",
        entryCount=len(matrix.get("entries", [])),
        matrix=matrix,
    )


@router.get("/contract-manifest", response_model=ContractManifestResource)
async def get_contract_manifest_resource(
    request: Request,
    response: Response,
) -> ContractManifestResource:
    try:
        manifest, manifest_sha256, manifest_last_modified = _contract_manifest_document()
    except json.JSONDecodeError as exc:
        raise _http_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Contract manifest resource is malformed",
            code=ErrorCode.INTERNAL_ERROR,
        ) from exc
    except FileNotFoundError:
        raise _http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Contract manifest resource is not available in the current runtime",
            code=ErrorCode.NOT_FOUND,
            hint="Install the packaged contract artifacts or provide the runtime patch manifest copy.",
        )

    etag = _weak_etag(
        [
            manifest_sha256,
            manifest.get("contractVersion", ""),
            str((manifest.get("artifactCounts") or {}).get("schemas", 0)),
        ]
    )
    headers = {"ETag": etag}
    if manifest_last_modified > 0:
        headers["Last-Modified"] = _isoformat(manifest_last_modified)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    response.headers.update(headers)
    return ContractManifestResource(
        id="contract-manifest",
        contractVersion=manifest.get("contractVersion"),
        sha256=manifest_sha256,
        relativePath="docs/architecture/contract_manifest.json",
        schemaCount=int((manifest.get("artifactCounts") or {}).get("schemas") or 0),
        manifest=manifest,
    )
