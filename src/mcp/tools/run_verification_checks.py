"""MCP tool for running executable verification checks on a loaded PBPK model."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from mcp_bridge.adapter.interface import OspsuiteAdapter

TOOL_NAME = "run_verification_checks"
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


def _verification_warnings(verification: Mapping[str, object] | None) -> list[str]:
    if not verification:
        return []

    messages: list[str] = []
    for entry in verification.get("checks", []):
        if not isinstance(entry, Mapping):
            continue
        if str(entry.get("status")) not in {"warning", "failed"}:
            continue
        summary = entry.get("summary")
        label = entry.get("label") or entry.get("id")
        if summary and label:
            messages.append(f"{label}: {summary}")
        elif summary:
            messages.append(str(summary))
    return messages


class RunVerificationChecksRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    simulation_id: str = Field(alias="simulationId", min_length=1, max_length=64)
    request: dict[str, Any] = Field(default_factory=dict)
    include_population_smoke: bool = Field(default=False, alias="includePopulationSmoke")
    population_cohort: dict[str, Any] = Field(default_factory=dict, alias="populationCohort")
    population_outputs: dict[str, Any] = Field(default_factory=dict, alias="populationOutputs")


class RunVerificationChecksResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    tool: str = TOOL_NAME
    contract_version: str = Field(default=CONTRACT_VERSION, alias="contractVersion")
    simulation_id: str = Field(alias="simulationId")
    backend: Optional[str] = None
    generated_at: Optional[str] = Field(default=None, alias="generatedAt")
    validation: dict[str, Any] = Field(default_factory=dict)
    profile: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    qualification_state: dict[str, Any] | None = Field(default=None, alias="qualificationState")
    verification: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def from_adapter_payload(
        cls, payload: Mapping[str, Any]
    ) -> "RunVerificationChecksResponse":
        validation = payload.get("validation")
        validation_payload = dict(validation) if isinstance(validation, Mapping) else {}
        profile = payload.get("profile")
        profile_payload = dict(profile) if isinstance(profile, Mapping) else {}
        capabilities = payload.get("capabilities")
        capabilities_payload = dict(capabilities) if isinstance(capabilities, Mapping) else {}
        verification = payload.get("verification")
        verification_payload = dict(verification) if isinstance(verification, Mapping) else {}
        assessment = validation_payload.get("assessment") if isinstance(validation_payload, Mapping) else None
        qualification_state = (
            dict(assessment.get("qualificationState"))
            if isinstance(assessment, Mapping) and isinstance(assessment.get("qualificationState"), Mapping)
            else None
        )
        warnings = _validation_warnings(validation_payload)
        warnings.extend(_verification_warnings(verification_payload))
        return cls(
            tool=TOOL_NAME,
            contractVersion=CONTRACT_VERSION,
            simulationId=str(payload.get("simulationId")),
            backend=str(payload.get("backend")) if payload.get("backend") else None,
            generatedAt=str(payload.get("generatedAt")) if payload.get("generatedAt") else None,
            validation=validation_payload,
            profile=profile_payload,
            capabilities=capabilities_payload,
            qualificationState=qualification_state,
            verification=verification_payload,
            warnings=warnings,
        )


def run_verification_checks(
    adapter: OspsuiteAdapter,
    payload: RunVerificationChecksRequest,
) -> RunVerificationChecksResponse:
    response = adapter.run_verification_checks(
        payload.simulation_id,
        request=payload.request,
        include_population_smoke=payload.include_population_smoke,
        population_cohort=payload.population_cohort,
        population_outputs=payload.population_outputs,
    )
    return RunVerificationChecksResponse.from_adapter_payload(response)


__all__ = [
    "RunVerificationChecksRequest",
    "RunVerificationChecksResponse",
    "run_verification_checks",
]
