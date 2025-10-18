"""Contracts and helper for the set_parameter_value MCP tool."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mcp.session_registry import SessionRegistryError, registry
from mcp_bridge.adapter import AdapterError
from mcp_bridge.adapter.interface import OspsuiteAdapter

from .get_parameter_value import ParameterValuePayload


class SetParameterValueRequest(BaseModel):
    """Payload for updating a parameter in a loaded simulation."""

    model_config = ConfigDict(populate_by_name=True)

    simulation_id: str = Field(alias="simulationId", min_length=1, max_length=64)
    parameter_path: str = Field(alias="parameterPath", min_length=1)
    value: float
    unit: Optional[str] = None
    update_mode: Optional[str] = Field(default="absolute", alias="updateMode")
    comment: Optional[str] = None

    @field_validator("parameter_path")
    @classmethod
    def _normalise_path(cls, value: str) -> str:
        path = value.strip()
        if not path:
            raise ValueError("parameter_path must be provided")
        if any(char in path for char in {"\0", "\n"}):
            raise ValueError("Invalid parameter path")
        return path

    @field_validator("update_mode")
    @classmethod
    def _validate_update_mode(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return "absolute"
        normalised = value.strip().lower()
        if normalised not in {"absolute", "relative"}:
            raise ValueError("updateMode must be 'absolute' or 'relative'")
        return normalised


class SetParameterValueResponse(BaseModel):
    parameter: ParameterValuePayload


class SetParameterValueValidationError(ValueError):
    """Raised when validation fails for set_parameter_value."""


def _ensure_simulation(simulation_id: str) -> None:
    try:
        registry.get(simulation_id)
    except SessionRegistryError as exc:
        raise SetParameterValueValidationError(str(exc)) from exc


def set_parameter_value(
    adapter: OspsuiteAdapter,
    payload: SetParameterValueRequest,
) -> SetParameterValueResponse:
    _ensure_simulation(payload.simulation_id)

    try:
        result = adapter.set_parameter_value(
            payload.simulation_id,
            payload.parameter_path,
            payload.value,
            payload.unit,
            comment=payload.comment,
        )
    except AdapterError as exc:
        raise SetParameterValueValidationError(str(exc)) from exc

    return SetParameterValueResponse(
        parameter=ParameterValuePayload.model_validate(result.model_dump()),
    )


__all__ = [
    "SetParameterValueRequest",
    "SetParameterValueResponse",
    "SetParameterValueValidationError",
    "set_parameter_value",
]
