"""MCP tool for exporting an OECD-style PBPK model dossier/report."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from mcp_bridge.adapter.interface import OspsuiteAdapter

TOOL_NAME = "export_oecd_report"
CONTRACT_VERSION = "pbpk-mcp.v1"


class ExportOecdReportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    simulation_id: str = Field(alias="simulationId", min_length=1, max_length=64)
    request: dict[str, Any] = Field(default_factory=dict)
    include_parameter_table: bool = Field(default=True, alias="includeParameterTable")
    parameter_pattern: Optional[str] = Field(default=None, alias="parameterPattern")
    parameter_limit: int = Field(default=200, alias="parameterLimit", ge=1, le=5000)


class ExportOecdReportResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    tool: str = TOOL_NAME
    contract_version: str = Field(default=CONTRACT_VERSION, alias="contractVersion")
    simulation_id: str = Field(alias="simulationId")
    backend: Optional[str] = None
    generated_at: Optional[str] = Field(default=None, alias="generatedAt")
    ngra_objects: dict[str, Any] = Field(default_factory=dict, alias="ngraObjects")
    qualification_state: dict[str, Any] | None = Field(default=None, alias="qualificationState")
    report: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_adapter_payload(cls, payload: Mapping[str, Any]) -> "ExportOecdReportResponse":
        report = payload.get("report")
        report_payload = dict(report) if isinstance(report, Mapping) else {}
        ngra_objects = payload.get("ngraObjects")
        ngra_objects_payload = dict(ngra_objects) if isinstance(ngra_objects, Mapping) else {}
        qualification_state = None
        report_state = report_payload.get("qualificationState") if isinstance(report_payload, Mapping) else None
        if isinstance(report_state, Mapping):
            qualification_state = dict(report_state)
        elif isinstance(report_payload.get("validation"), Mapping):
            assessment = report_payload["validation"].get("assessment")
            if isinstance(assessment, Mapping) and isinstance(assessment.get("qualificationState"), Mapping):
                qualification_state = dict(assessment["qualificationState"])
        return cls(
            tool=TOOL_NAME,
            contractVersion=CONTRACT_VERSION,
            simulationId=str(payload.get("simulationId")),
            backend=str(payload.get("backend")) if payload.get("backend") else None,
            generatedAt=str(payload.get("generatedAt")) if payload.get("generatedAt") else None,
            ngraObjects=ngra_objects_payload,
            qualificationState=qualification_state,
            report=report_payload,
        )


def export_oecd_report(
    adapter: OspsuiteAdapter,
    payload: ExportOecdReportRequest,
) -> ExportOecdReportResponse:
    response = adapter.export_oecd_report(
        payload.simulation_id,
        request=payload.request,
        include_parameter_table=payload.include_parameter_table,
        parameter_pattern=payload.parameter_pattern,
        parameter_limit=payload.parameter_limit,
    )
    return ExportOecdReportResponse.from_adapter_payload(response)


__all__ = [
    "ExportOecdReportRequest",
    "ExportOecdReportResponse",
    "export_oecd_report",
]
