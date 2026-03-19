"""MCP tool for preflight OECD-style simulation validation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from mcp_bridge.adapter.interface import OspsuiteAdapter

TOOL_NAME = "validate_simulation_request"
CONTRACT_VERSION = "pbpk-mcp.v1"


def _validation_warnings(validation: Mapping[str, object] | None) -> list[str]:
    if not validation:
        return []

    messages: list[str] = []
    for entry in validation.get("warnings", []):
        if isinstance(entry, Mapping):
            message = entry.get("message")
            if message:
                messages.append(str(message))
        elif entry:
            messages.append(str(entry))
    return messages


class ValidateSimulationRequestRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    simulation_id: str = Field(alias="simulationId", min_length=1, max_length=64)
    stage: Optional[str] = None
    request: dict[str, Any] = Field(default_factory=dict)


class ValidateSimulationRequestResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    tool: str = TOOL_NAME
    contract_version: str = Field(default=CONTRACT_VERSION, alias="contractVersion")
    simulation_id: str = Field(alias="simulationId")
    backend: Optional[str] = None
    validation: dict[str, Any] = Field(default_factory=dict)
    profile: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    qualification_state: dict[str, Any] | None = Field(default=None, alias="qualificationState")
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def from_adapter_payload(
        cls, payload: Mapping[str, Any]
    ) -> "ValidateSimulationRequestResponse":
        validation = payload.get("validation")
        validation_payload = dict(validation) if isinstance(validation, Mapping) else {}
        profile = payload.get("profile")
        profile_payload = dict(profile) if isinstance(profile, Mapping) else {}
        capabilities = payload.get("capabilities")
        capabilities_payload = dict(capabilities) if isinstance(capabilities, Mapping) else {}
        assessment = validation_payload.get("assessment") if isinstance(validation_payload, Mapping) else None
        qualification_state = (
            dict(assessment.get("qualificationState"))
            if isinstance(assessment, Mapping) and isinstance(assessment.get("qualificationState"), Mapping)
            else None
        )
        return cls(
            tool=TOOL_NAME,
            contractVersion=CONTRACT_VERSION,
            simulationId=str(payload.get("simulationId")),
            backend=str(payload.get("backend")) if payload.get("backend") else None,
            validation=validation_payload,
            profile=profile_payload,
            capabilities=capabilities_payload,
            qualificationState=qualification_state,
            warnings=_validation_warnings(validation_payload),
        )


def validate_simulation_request(
    adapter: OspsuiteAdapter,
    payload: ValidateSimulationRequestRequest,
) -> ValidateSimulationRequestResponse:
    response = adapter.validate_simulation_request(
        payload.simulation_id,
        request=payload.request,
        stage=payload.stage,
    )
    return ValidateSimulationRequestResponse.from_adapter_payload(response)


__all__ = [
    "ValidateSimulationRequestRequest",
    "ValidateSimulationRequestResponse",
    "validate_simulation_request",
]
