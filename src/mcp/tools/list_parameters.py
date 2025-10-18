"""Contracts and execution helpers for the list_parameters MCP tool."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mcp.session_registry import SessionRegistryError, registry
from mcp_bridge.adapter import AdapterError
from mcp_bridge.adapter.interface import OspsuiteAdapter


class ListParametersRequest(BaseModel):
    """Payload for listing parameters in a loaded simulation."""

    model_config = ConfigDict(populate_by_name=True)

    simulation_id: str = Field(alias="simulationId", min_length=1, max_length=64)
    search_pattern: Optional[str] = Field(default="*", alias="searchPattern")

    @field_validator("search_pattern")
    @classmethod
    def _normalise_pattern(cls, value: Optional[str]) -> str:
        pattern = (value or "*").strip()
        if not pattern:
            if value:
                raise ValueError("Invalid search pattern")
            return "*"
        if any(char in pattern for char in {"\0", "\n"}):
            raise ValueError("Invalid search pattern")
        return pattern


class ListParametersResponse(BaseModel):
    parameters: list[str]


class ListParametersValidationError(ValueError):
    """Raised when list_parameters inputs fail validation."""


def _ensure_simulation(simulation_id: str) -> None:
    try:
        registry.get(simulation_id)
    except SessionRegistryError as exc:
        raise ListParametersValidationError(str(exc)) from exc


def list_parameters(
    adapter: OspsuiteAdapter,
    payload: ListParametersRequest,
    *,
    result_limit: int = 500,
) -> ListParametersResponse:
    _ensure_simulation(payload.simulation_id)
    try:
        pattern = None if payload.search_pattern == "*" else payload.search_pattern
        raw = adapter.list_parameters(payload.simulation_id, pattern)
    except AdapterError as exc:
        raise ListParametersValidationError(str(exc)) from exc

    paths: list[str] = sorted({item.path for item in raw})
    if len(paths) > result_limit:
        paths = paths[:result_limit]
    return ListParametersResponse(parameters=paths)


__all__ = [
    "ListParametersRequest",
    "ListParametersResponse",
    "ListParametersValidationError",
    "list_parameters",
]
