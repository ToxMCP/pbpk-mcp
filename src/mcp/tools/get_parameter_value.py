"""Contracts and helper for the get_parameter_value MCP tool."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mcp.session_registry import SessionRegistryError, registry
from mcp_bridge.adapter import AdapterError
from mcp_bridge.adapter.interface import OspsuiteAdapter


class GetParameterValueRequest(BaseModel):
    """Payload for retrieving a parameter value from a simulation."""

    model_config = ConfigDict(populate_by_name=True)

    simulation_id: str = Field(alias="simulationId", min_length=1, max_length=64)
    parameter_path: str = Field(alias="parameterPath", min_length=1)

    @field_validator("parameter_path")
    @classmethod
    def _normalise_path(cls, value: str) -> str:
        path = value.strip()
        if not path:
            raise ValueError("parameter_path must be provided")
        if any(char in path for char in {"\0", "\n"}):
            raise ValueError("Invalid parameter path")
        return path


class ParameterValuePayload(BaseModel):
    path: str
    value: float
    unit: str
    display_name: Optional[str] = Field(default=None, alias="displayName")
    last_updated_at: Optional[str] = Field(default=None, alias="lastUpdatedAt")
    source: Optional[str] = None


class GetParameterValueResponse(BaseModel):
    parameter: ParameterValuePayload


class GetParameterValueValidationError(ValueError):
    """Raised when validation fails for get_parameter_value."""


def _ensure_simulation(simulation_id: str) -> None:
    try:
        registry.get(simulation_id)
    except SessionRegistryError as exc:
        raise GetParameterValueValidationError(str(exc)) from exc


def get_parameter_value(
    adapter: OspsuiteAdapter,
    payload: GetParameterValueRequest,
) -> GetParameterValueResponse:
    _ensure_simulation(payload.simulation_id)

    try:
        value = adapter.get_parameter_value(payload.simulation_id, payload.parameter_path)
    except AdapterError as exc:
        raise GetParameterValueValidationError(str(exc)) from exc

    return GetParameterValueResponse(
        parameter=ParameterValuePayload.model_validate(value.model_dump()),
    )


__all__ = [
    "GetParameterValueRequest",
    "GetParameterValueResponse",
    "GetParameterValueValidationError",
    "get_parameter_value",
]
