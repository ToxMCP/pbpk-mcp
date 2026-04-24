"""MCP tool for retrieving population simulation results."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from mcp_bridge.adapter.interface import OspsuiteAdapter
from mcp_bridge.adapter.schema import PopulationSimulationResult


class PopulationChunkModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    chunkId: str
    uri: Optional[str] = None
    contentType: Optional[str] = None
    sizeBytes: Optional[int] = None
    subjectRange: Optional[tuple[int, int]] = None
    timeRange: Optional[tuple[float, float]] = None
    preview: Optional[dict[str, Any]] = None


class GetPopulationResultsRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    results_id: str = Field(alias="resultsId", min_length=1)


class GetPopulationResultsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    resultsId: str
    simulationId: str
    generatedAt: str
    cohort: dict[str, Any]
    aggregates: Dict[str, float]
    chunks: list[PopulationChunkModel] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_result(cls, result: PopulationSimulationResult) -> "GetPopulationResultsResponse":
        return cls(
            resultsId=result.results_id,
            simulationId=result.simulation_id,
            generatedAt=result.generated_at,
            cohort=result.cohort.model_dump(),
            aggregates=result.aggregates,
            chunks=[
                PopulationChunkModel.model_validate(chunk.model_dump(by_alias=True))
                for chunk in result.chunk_handles
            ],
            metadata=result.metadata,
        )


def get_population_results(
    adapter: OspsuiteAdapter, payload: GetPopulationResultsRequest
) -> GetPopulationResultsResponse:
    result = adapter.get_population_results(payload.results_id)
    return GetPopulationResultsResponse.from_result(result)


__all__ = [
    "GetPopulationResultsRequest",
    "GetPopulationResultsResponse",
    "get_population_results",
]
