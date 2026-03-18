"""MCP tool for retrieving deterministic simulation results."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from mcp_bridge.adapter import AdapterError, AdapterErrorCode
from mcp_bridge.adapter.interface import OspsuiteAdapter
from mcp_bridge.adapter.schema import SimulationResult
from mcp_bridge.services.job_service import BaseJobService

TOOL_NAME = "get_results"
CONTRACT_VERSION = "pbpk-mcp.v1"


class SimulationSeriesModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    parameter: str
    unit: str
    values: list[dict[str, float]] = Field(default_factory=list)


class GetResultsRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    results_id: str = Field(alias="resultsId", min_length=1)


class GetResultsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tool: str = TOOL_NAME
    contract_version: str = Field(default=CONTRACT_VERSION, alias="contractVersion")
    results_id: str = Field(alias="resultsId")
    simulation_id: str = Field(alias="simulationId")
    backend: Optional[str] = None
    generated_at: str = Field(alias="generatedAt")
    metadata: dict[str, Any] = Field(default_factory=dict)
    series: list[SimulationSeriesModel] = Field(default_factory=list)

    @classmethod
    def from_result(cls, result: SimulationResult) -> "GetResultsResponse":
        backend = None
        if isinstance(result.metadata, dict):
            backend_value = result.metadata.get("backend") or result.metadata.get("engine")
            if backend_value:
                backend = str(backend_value)
        return cls(
            tool=TOOL_NAME,
            contractVersion=CONTRACT_VERSION,
            resultsId=result.results_id,
            simulationId=result.simulation_id,
            backend=backend,
            generatedAt=result.generated_at,
            metadata=result.metadata,
            series=[
                SimulationSeriesModel.model_validate(series.model_dump())
                for series in result.series
            ],
        )


def get_results(
    adapter: OspsuiteAdapter,
    job_service: BaseJobService,
    payload: GetResultsRequest,
) -> GetResultsResponse:
    try:
        result = adapter.get_results(payload.results_id)
    except AdapterError as exc:
        if exc.code != AdapterErrorCode.NOT_FOUND:
            raise
        stored = job_service.get_stored_simulation_result(payload.results_id)
        if stored is None:
            raise
        result = SimulationResult.model_validate(stored)
    return GetResultsResponse.from_result(result)


__all__ = [
    "GetResultsRequest",
    "GetResultsResponse",
    "get_results",
]
