"""MCP tool for running cross-parameter consistency checks on a loaded PBPK model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from mcp_bridge.adapter.interface import OspsuiteAdapter
from mcp_bridge.services.cross_parameter_consistency import (
    CrossParameterConsistencyValidator,
)

TOOL_NAME = "run_parameter_consistency_check"
CONTRACT_VERSION = "pbpk-mcp.v1"


class RunParameterConsistencyCheckRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    simulation_id: str = Field(alias="simulationId", min_length=1, max_length=64)


class RunParameterConsistencyCheckResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    tool: str = TOOL_NAME
    contract_version: str = Field(default=CONTRACT_VERSION, alias="contractVersion")
    simulation_id: str = Field(alias="simulationId")
    ok: bool
    violation_count: int = Field(alias="violationCount")
    violations: list[str]
    summary: str
    checked_rules: list[str] = Field(alias="checkedRules")


def run_parameter_consistency_check(
    adapter: OspsuiteAdapter,
    payload: RunParameterConsistencyCheckRequest,
) -> RunParameterConsistencyCheckResponse:
    validator = CrossParameterConsistencyValidator(adapter, payload.simulation_id)
    result = validator.validate_all()
    return RunParameterConsistencyCheckResponse(
        tool=TOOL_NAME,
        contractVersion=CONTRACT_VERSION,
        simulationId=payload.simulation_id,
        ok=result["ok"],
        violationCount=result["violationCount"],
        violations=result["violations"],
        summary=result["summary"],
        checkedRules=result["checkedRules"],
    )


__all__ = [
    "RunParameterConsistencyCheckRequest",
    "RunParameterConsistencyCheckResponse",
    "run_parameter_consistency_check",
]
