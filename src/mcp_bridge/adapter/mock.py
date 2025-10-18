"""Mock implementation of the ospsuite adapter for testing pipelines."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Optional

from .environment import REnvironmentStatus, detect_environment
from .errors import AdapterError, AdapterErrorCode
from .interface import AdapterConfig, OspsuiteAdapter
from .schema import (
    ParameterSummary,
    ParameterValue,
    PopulationSimulationConfig,
    PopulationSimulationResult,
    PopulationChunkHandle,
    SimulationHandle,
    SimulationResult,
    SimulationResultSeries,
)
from ..storage.population_store import PopulationResultStore, StoredChunk


class InMemoryAdapter(OspsuiteAdapter):
    def __init__(
        self,
        config: AdapterConfig | None = None,
        *,
        population_store: PopulationResultStore | None = None,
    ) -> None:
        super().__init__(config, population_store=population_store)
        self._simulations: dict[str, SimulationHandle] = {}
        self._parameters: dict[str, dict[str, ParameterValue]] = defaultdict(dict)
        self._results: dict[str, SimulationResult] = {}
        self._population_results: dict[str, PopulationSimulationResult] = {}
        self._population_chunks: dict[str, dict[str, object]] = {}
        self._initialised = False
        self._env_status: Optional[REnvironmentStatus] = None

    def init(self) -> None:
        status = detect_environment(self.config)
        if self.config.require_r_environment and not status.available:
            raise AdapterError(
                AdapterErrorCode.ENVIRONMENT_MISSING,
                "R environment unavailable",
                details={"issues": "; ".join(status.issues)},
            )
        self._env_status = status
        self._initialised = True

    def shutdown(self) -> None:
        self._initialised = False
        self._simulations.clear()
        self._parameters.clear()
        self._results.clear()
        self._population_results.clear()
        self._population_chunks.clear()

    def health(self) -> dict[str, object]:
        status = "initialised" if self._initialised else "stopped"
        env = self._env_status.to_dict() if self._env_status else {}
        return {"status": status, "environment": env}

    def load_simulation(self, file_path: str, simulation_id: str | None = None) -> SimulationHandle:
        self._ensure_initialised()
        if not file_path.endswith(".pkml"):
            raise AdapterError(AdapterErrorCode.INVALID_INPUT, "Unsupported file type")
        sim_id = simulation_id or str(uuid.uuid4())
        handle = SimulationHandle(simulation_id=sim_id, file_path=file_path)
        self._simulations[sim_id] = handle
        return handle

    def list_parameters(
        self, simulation_id: str, pattern: str | None = None
    ) -> list[ParameterSummary]:
        handle = self._get_simulation(simulation_id)
        params = self._parameters[handle.simulation_id]
        summaries = []
        for path, value in params.items():
            if pattern and pattern not in path:
                continue
            summaries.append(
                ParameterSummary(
                    path=path,
                    display_name=value.display_name,
                    unit=value.unit,
                    is_editable=True,
                )
            )
        return summaries

    def get_parameter_value(self, simulation_id: str, parameter_path: str) -> ParameterValue:
        handle = self._get_simulation(simulation_id)
        params = self._parameters[handle.simulation_id]
        try:
            return params[parameter_path]
        except KeyError as exc:  # pragma: no cover - simple forwarding
            raise AdapterError(AdapterErrorCode.NOT_FOUND, "Parameter not found") from exc

    def set_parameter_value(
        self,
        simulation_id: str,
        parameter_path: str,
        value: float,
        unit: str | None = None,
        *,
        comment: str | None = None,
    ) -> ParameterValue:
        handle = self._get_simulation(simulation_id)
        record = ParameterValue(path=parameter_path, value=value, unit=unit or "unitless")
        record.display_name = comment
        self._parameters[handle.simulation_id][parameter_path] = record
        return record

    def run_simulation_sync(
        self, simulation_id: str, *, run_id: str | None = None
    ) -> SimulationResult:
        handle = self._get_simulation(simulation_id)
        results_id = run_id or str(uuid.uuid4())
        series = SimulationResultSeries(
            parameter="Concentration",
            unit="mg/L",
            values=[{"time": 0.0, "value": 0.0}, {"time": 1.0, "value": 1.0}],
        )
        result = SimulationResult(
            results_id=results_id,
            simulation_id=handle.simulation_id,
            generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            series=[series],
        )
        self._results[results_id] = result
        return result

    def get_results(self, results_id: str) -> SimulationResult:
        try:
            return self._results[results_id]
        except KeyError as exc:
            raise AdapterError(AdapterErrorCode.NOT_FOUND, "Results not found") from exc

    def run_population_simulation_sync(
        self, config: PopulationSimulationConfig
    ) -> PopulationSimulationResult:
        self._ensure_initialised()
        if config.simulation_id not in self._simulations:
            self.load_simulation(config.model_path, simulation_id=config.simulation_id)

        results_id = f"pop-{uuid.uuid4()}"
        cohort_size = config.cohort.size
        aggregates = {
            "meanCmax": float(cohort_size) * 0.01 + 1.0,
            "sdCmax": float(cohort_size) * 0.001,
            "meanAUC": float(cohort_size) * 0.02 + 5.0,
        }

        chunk_id = f"{results_id}-chunk-1"
        subjects_to_store = min(20, cohort_size)
        time_points = [0.0, 4.0, 12.0, 24.0]
        series = [
            {
                "subjectId": idx,
                "time": time_points,
                "concentration": [round((idx * point) * 0.015, 4) for point in time_points],
            }
            for idx in range(1, subjects_to_store + 1)
        ]
        preview = {
            "subjects": [row["subjectId"] for row in series[:5]],
            "time": time_points,
            "concentration": series[0]["concentration"] if series else [],
        }
        chunk_payload = {
            "resultsId": results_id,
            "chunkId": chunk_id,
            "series": series,
            "totalSubjects": cohort_size,
        }
        stored_chunk: StoredChunk | None = None
        if self.population_store is not None:
            stored_chunk = self.population_store.store_json_chunk(results_id, chunk_id, chunk_payload)
        self._population_chunks[chunk_id] = chunk_payload

        chunk_handles = [
            PopulationChunkHandle(
                chunk_id=chunk_id,
                uri=stored_chunk.uri if stored_chunk else None,
                content_type=stored_chunk.content_type if stored_chunk else None,
                size_bytes=stored_chunk.size_bytes if stored_chunk else None,
                subject_range=(1, subjects_to_store),
                preview=preview,
            )
        ]

        result = PopulationSimulationResult(
            results_id=results_id,
            simulation_id=config.simulation_id,
            generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            cohort=config.cohort,
            aggregates=aggregates,
            chunk_handles=chunk_handles,
            metadata={"outputs": config.outputs.model_dump(), **config.metadata},
        )

        self._population_results[results_id] = result
        return result

    def get_population_results(self, results_id: str) -> PopulationSimulationResult:
        try:
            return self._population_results[results_id]
        except KeyError as exc:
            raise AdapterError(AdapterErrorCode.NOT_FOUND, "Population results not found") from exc

    # ------------------------------------------------------------------
    def _ensure_initialised(self) -> None:
        if not self._initialised:
            raise AdapterError(AdapterErrorCode.ENVIRONMENT_MISSING, "Adapter not initialised")

    def _get_simulation(self, simulation_id: str) -> SimulationHandle:
        self._ensure_initialised()
        try:
            return self._simulations[simulation_id]
        except KeyError as exc:
            raise AdapterError(AdapterErrorCode.NOT_FOUND, "Simulation not loaded") from exc
