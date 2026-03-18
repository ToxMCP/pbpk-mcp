"""MCP tool for discovering supported PBPK model files on disk."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mcp.session_registry import registry
from mcp_bridge.model_catalog import discover_models as discover_model_entries
from mcp_bridge.model_catalog import normalise_backend

TOOL_NAME = "discover_models"
CONTRACT_VERSION = "pbpk-mcp.v1"


def _paginate(items: list[dict[str, Any]], *, page: int, limit: int) -> list[dict[str, Any]]:
    start = (page - 1) * limit
    if start >= len(items):
        return []
    return items[start : start + limit]


class DiscoverModelsRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    search: Optional[str] = None
    backend: Optional[str] = None
    loaded_only: bool = Field(default=False, alias="loadedOnly")
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=100, ge=1, le=1000)

    @field_validator("backend")
    @classmethod
    def _validate_backend(cls, value: Optional[str]) -> Optional[str]:
        return normalise_backend(value)


class DiscoverableModelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

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


class DiscoverModelsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    tool: str = TOOL_NAME
    contract_version: str = Field(default=CONTRACT_VERSION, alias="contractVersion")
    items: list[DiscoverableModelModel] = Field(default_factory=list)
    page: int
    limit: int
    total: int


def discover_models(payload: DiscoverModelsRequest) -> DiscoverModelsResponse:
    snapshot = registry.snapshot()
    items = discover_model_entries(
        search=payload.search,
        backend=payload.backend,
        loaded_records=snapshot,
        loaded_only=payload.loaded_only,
    )
    total = len(items)
    page_items = _paginate(items, page=payload.page, limit=payload.limit)
    return DiscoverModelsResponse(
        tool=TOOL_NAME,
        contractVersion=CONTRACT_VERSION,
        items=[DiscoverableModelModel.model_validate(item) for item in page_items],
        page=payload.page,
        limit=payload.limit,
        total=total,
    )


__all__ = [
    "DiscoverModelsRequest",
    "DiscoverModelsResponse",
    "DiscoverableModelModel",
    "discover_models",
]
