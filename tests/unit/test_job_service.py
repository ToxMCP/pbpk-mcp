"""Unit tests for the asynchronous JobService."""

from __future__ import annotations

import os
import threading
import time

import pytest

from mcp_bridge.adapter.errors import AdapterError, AdapterErrorCode
from mcp_bridge.adapter.schema import SimulationResult
from mcp_bridge.services.job_service import JobService, JobStatus
from mcp_bridge.storage.population_store import PopulationResultStore


def make_result(simulation_id: str, results_id: str) -> SimulationResult:
    return SimulationResult(
        results_id=results_id,
        simulation_id=simulation_id,
        generated_at="2024-01-01T00:00:00Z",
        series=[],
    )


class SuccessfulAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def run_simulation_sync(
        self, simulation_id: str, *, run_id: str | None = None
    ) -> SimulationResult:
        self.calls += 1
        return make_result(simulation_id, f"{simulation_id}-result")


class FlakyAdapter:
    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    def run_simulation_sync(
        self, simulation_id: str, *, run_id: str | None = None
    ) -> SimulationResult:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise AdapterError(AdapterErrorCode.INTEROP_ERROR, "transient failure")
        return make_result(simulation_id, f"{simulation_id}-result")


class BlockingAdapter:
    def __init__(self, hold_event: threading.Event) -> None:
        self.hold_event = hold_event
        self.started = threading.Event()

    def run_simulation_sync(
        self, simulation_id: str, *, run_id: str | None = None
    ) -> SimulationResult:
        self.started.set()
        self.hold_event.wait()
        return make_result(simulation_id, f"{simulation_id}-result")


class SlowAdapter:
    def __init__(self, delay: float) -> None:
        self.delay = delay

    def run_simulation_sync(
        self, simulation_id: str, *, run_id: str | None = None
    ) -> SimulationResult:
        time.sleep(self.delay)
        return make_result(simulation_id, f"{simulation_id}-result")


def test_submit_and_complete_job() -> None:
    adapter = SuccessfulAdapter()
    service = JobService(max_workers=2, default_timeout=5.0, max_retries=0)
    try:
        job = service.submit_simulation_job(adapter, "sim-1")
        record = service.wait_for_completion(job.job_id, timeout=2.0)
        assert record.status is JobStatus.SUCCEEDED
        assert record.result_id == "sim-1-result"
        assert adapter.calls == 1
    finally:
        service.shutdown()


def test_job_retries_on_failure() -> None:
    adapter = FlakyAdapter(fail_times=1)
    service = JobService(max_workers=1, default_timeout=5.0, max_retries=2)
    try:
        job = service.submit_simulation_job(adapter, "sim-2")
        record = service.wait_for_completion(job.job_id, timeout=2.0)
        assert record.status is JobStatus.SUCCEEDED
        assert record.attempts == 2
        assert adapter.calls == 2
    finally:
        service.shutdown()


def test_cancel_job_before_execution() -> None:
    hold_event = threading.Event()
    blocking_adapter = BlockingAdapter(hold_event)
    service = JobService(max_workers=1, default_timeout=5.0, max_retries=0)
    try:
        # Occupy the worker with a blocking job.
        first_job = service.submit_simulation_job(blocking_adapter, "sim-block")
        assert blocking_adapter.started.wait(timeout=1.0)

        # Submit a second job that we immediately cancel while queued.
        adapter = SuccessfulAdapter()
        second_job = service.submit_simulation_job(adapter, "sim-cancel")
        cancelled_record = service.cancel_job(second_job.job_id)
        assert cancelled_record.cancel_requested is True

        hold_event.set()
        service.wait_for_completion(first_job.job_id, timeout=2.0)
        time.sleep(0.05)  # allow cancellation to propagate
        final_record = service.get_job(second_job.job_id)
        assert final_record.status in {JobStatus.CANCELLED, JobStatus.QUEUED}
        assert final_record.cancel_requested is True
    finally:
        service.shutdown()


def test_job_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = SlowAdapter(delay=0.2)
    service = JobService(max_workers=1, default_timeout=0.05, max_retries=0)
    try:
        job = service.submit_simulation_job(adapter, "sim-timeout")
        record = service.wait_for_completion(job.job_id, timeout=1.0)
        assert record.status is JobStatus.TIMEOUT
        assert record.error is not None
    finally:
        service.shutdown()


def test_retention_policy_prunes_jobs_and_population(tmp_path) -> None:
    population_store = PopulationResultStore(tmp_path / "population")
    service = JobService(
        max_workers=1,
        default_timeout=5.0,
        max_retries=0,
        population_store=population_store,
        population_retention_seconds=0.1,
        retention_seconds=0.1,
    )
    try:
        adapter = SuccessfulAdapter()
        job = service.submit_simulation_job(adapter, "retention-sim")
        record = service.wait_for_completion(job.job_id, timeout=2.0)
        assert record.status is JobStatus.SUCCEEDED

        registry_record = service._registry.get(job.job_id)
        assert registry_record is not None
        stale_timestamp = time.time() - 3600
        registry_record.finished_at = stale_timestamp
        service._registry.upsert(registry_record)
        with service._lock:
            service._jobs[job.job_id].finished_at = stale_timestamp

        stored_chunk = population_store.store_json_chunk("pop-old", "chunk-1", {"values": [1]})
        os.utime(stored_chunk.path.parent, (stale_timestamp, stale_timestamp))
        os.utime(stored_chunk.path, (stale_timestamp, stale_timestamp))

        service._apply_retention_policy()

        with pytest.raises(KeyError):
            service.get_job(job.job_id)
        assert not (stored_chunk.path.parent.exists())
    finally:
        service.shutdown()
