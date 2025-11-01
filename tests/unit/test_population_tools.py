"""Tests for population simulation MCP tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp.tools.get_population_results import (
    GetPopulationResultsRequest,
    get_population_results,
)
from mcp.tools.run_population_simulation import (
    RunPopulationSimulationRequest,
    RunPopulationSimulationValidationError,
    run_population_simulation,
)
from mcp_bridge.adapter.mock import InMemoryAdapter
from mcp_bridge.services.job_service import JobService
from mcp_bridge.storage.population_store import PopulationResultStore

FIXTURE_PATH = str(Path("tests/fixtures/demo.pkml").resolve())


def _make_adapter_and_service(
    tmp_path,
) -> tuple[InMemoryAdapter, JobService, PopulationResultStore]:
    store = PopulationResultStore(tmp_path / "population-store")
    adapter = InMemoryAdapter(population_store=store)
    adapter.init()
    job_service = JobService()
    return adapter, job_service, store


def test_run_population_simulation_success(tmp_path) -> None:
    adapter, job_service, store = _make_adapter_and_service(tmp_path)
    try:
        request = RunPopulationSimulationRequest(
            modelPath=FIXTURE_PATH,
            simulationId="pop-sim",
            cohort={"size": 25},
        )
        response = run_population_simulation(adapter, job_service, request)

        job = job_service.wait_for_completion(response.job_id)
        assert job.job_type == "population"
        assert job.result_id is not None

        results = get_population_results(
            adapter,
            GetPopulationResultsRequest(resultsId=job.result_id),
        )
        assert results.simulationId == "pop-sim"
        assert results.aggregates
        assert results.chunks
        first_chunk = results.chunks[0]
        assert first_chunk.uri
        assert first_chunk.sizeBytes
        metadata = store.get_metadata(results.resultsId, first_chunk.chunkId)
        assert metadata.size_bytes == first_chunk.sizeBytes
    finally:
        job_service.shutdown()
        adapter.shutdown()


def test_run_population_simulation_invalid_path(tmp_path) -> None:
    adapter, job_service, _store = _make_adapter_and_service(tmp_path)
    try:
        request = RunPopulationSimulationRequest(
            modelPath="/tmp/not-a-model.txt",
            simulationId="pop-invalid",
            cohort={"size": 10},
        )
        with pytest.raises(RunPopulationSimulationValidationError):
            run_population_simulation(adapter, job_service, request)
    finally:
        job_service.shutdown()
        adapter.shutdown()
