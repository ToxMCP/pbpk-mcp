# ruff: noqa: UP007
"""Pydantic models describing adapter contracts."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SimulationHandle(BaseModel):
    simulation_id: str = Field(min_length=1, max_length=64)
    file_path: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParameterSummary(BaseModel):
    path: str
    display_name: Optional[str] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    is_editable: Optional[bool] = None


class ParameterValue(BaseModel):
    path: str
    value: float
    unit: str
    display_name: Optional[str] = None
    last_updated_at: Optional[str] = None
    source: Optional[str] = None


class SimulationResultSeries(BaseModel):
    parameter: str
    unit: str
    values: list[dict[str, float]]


class SimulationResult(BaseModel):
    results_id: str
    simulation_id: str
    generated_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    series: list[SimulationResultSeries]


class PopulationCohortConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    size: int = Field(..., ge=1)
    sampling: Optional[str] = None
    seed: Optional[int] = None
    covariates: list[dict[str, Any]] = Field(default_factory=list)


class PopulationOutputsConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    time_series: list[dict[str, Any]] = Field(default_factory=list)
    aggregates: list[str] = Field(default_factory=list)


class PopulationSimulationConfig(BaseModel):
    """Adapter-facing configuration for population simulations."""

    model_config = ConfigDict(protected_namespaces=())

    model_path: str
    simulation_id: str = Field(min_length=1, max_length=64)
    cohort: PopulationCohortConfig
    outputs: PopulationOutputsConfig = Field(default_factory=PopulationOutputsConfig)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PopulationChunkHandle(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    chunk_id: str = Field(serialization_alias="chunkId")
    uri: Optional[str] = None
    content_type: Optional[str] = Field(default=None, serialization_alias="contentType")
    size_bytes: Optional[int] = Field(default=None, serialization_alias="sizeBytes")
    subject_range: Optional[tuple[int, int]] = Field(
        default=None, serialization_alias="subjectRange"
    )
    time_range: Optional[tuple[float, float]] = Field(
        default=None, serialization_alias="timeRange"
    )
    preview: Optional[dict[str, Any]] = None


class PopulationSimulationResult(BaseModel):
    """Aggregate output for a population simulation run."""

    model_config = ConfigDict(protected_namespaces=())

    results_id: str
    simulation_id: str
    generated_at: str
    cohort: PopulationCohortConfig
    aggregates: dict[str, float] = Field(default_factory=dict)
    chunk_handles: list[PopulationChunkHandle] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
