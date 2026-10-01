"""Local deadlines report promptly without pretending a thread was killed."""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from mcp_bridge.adapter.errors import AdapterError, AdapterErrorCode
from mcp_bridge.adapter.schema import PopulationSimulationConfig
from mcp_bridge.services.job_service import DurableJobRegistry, JobService, JobStatus
from mcp_bridge.services import job_service


class BlockingAdapter:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()
        self.calls = []

    def run_simulation_sync(self, simulation_id, *, run_id=None):
        self.calls.append(simulation_id)
        self.started.set()
        assert self.release.wait(5), "Test must release the stub backend"
        self.finished.set()
        return SimpleNamespace(results_id="late-result")

    def run_population_simulation_sync(self, config):
        return self.run_simulation_sync(config.simulation_id)


@pytest.mark.parametrize("population", [False, True])
def test_deadline_is_terminal_before_backend_finishes(tmp_path, population):
    registry = DurableJobRegistry(str(tmp_path / "jobs.db"))
    service = JobService(max_workers=1, default_timeout=0.05, registry=registry)
    adapter = BlockingAdapter()
    try:
        if population:
            config = PopulationSimulationConfig(
                model_path="stub.R", simulation_id="blocked", cohort={"size": 1}
            )
            job = service.submit_population_job(adapter, config)
        else:
            job = service.submit_simulation_job(adapter, "blocked")
        assert adapter.started.wait(1)
        assert service.wait_for_completion(job.job_id, timeout=1).status == JobStatus.TIMEOUT
        assert not adapter.finished.is_set()
        assert registry.get(job.job_id).status == JobStatus.TIMEOUT
        assert job.result_id is None
        assert "may continue" in job.error["message"]

        adapter.release.set()
        assert adapter.finished.wait(1)
        service._backend_executor.submit(lambda: None).result(timeout=1)
        assert service.get_job(job.job_id).status == JobStatus.TIMEOUT
        assert registry.get(job.job_id).status == JobStatus.TIMEOUT
        assert service.cancel_job(job.job_id).status == JobStatus.TIMEOUT
    finally:
        adapter.release.set()
        service.shutdown()


def test_expired_queued_backend_call_never_runs_and_pool_recovers():
    service = JobService(max_workers=1, default_timeout=0.05)
    adapter = BlockingAdapter()
    try:
        first = service.submit_simulation_job(adapter, "first")
        assert adapter.started.wait(1)
        assert service.wait_for_completion(first.job_id, timeout=1).status == JobStatus.TIMEOUT
        queued = service.submit_simulation_job(adapter, "expired-while-queued")
        assert service.wait_for_completion(queued.job_id, timeout=1).status == JobStatus.TIMEOUT
        assert adapter.calls == ["first"]

        adapter.release.set()
        service._backend_executor.submit(lambda: None).result(timeout=1)
        recovered = service.submit_simulation_job(adapter, "recovered", timeout_seconds=1)
        assert (
            service.wait_for_completion(recovered.job_id, timeout=1).status == JobStatus.SUCCEEDED
        )
        assert adapter.calls == ["first", "recovered"]
    finally:
        adapter.release.set()
        service.shutdown()


def test_shutdown_preserves_cancelled_states_after_late_backend_exit(tmp_path):
    path = str(tmp_path / "jobs.db")
    service = JobService(max_workers=1, default_timeout=10, registry=DurableJobRegistry(path))
    adapter = BlockingAdapter()
    try:
        running = service.submit_simulation_job(adapter, "running")
        assert adapter.started.wait(1)
        queued = service.submit_simulation_job(adapter, "queued")
        coordinator = running._future
        service.shutdown()
        assert not adapter.finished.is_set()
        assert running.status == queued.status == JobStatus.CANCELLED

        adapter.release.set()
        coordinator.result(timeout=1)
        assert running.status == queued.status == JobStatus.CANCELLED
        assert adapter.calls == ["running"]
        reopened = DurableJobRegistry(path)
        try:
            assert reopened.get(running.job_id).status == JobStatus.CANCELLED
            assert reopened.get(queued.job_id).status == JobStatus.CANCELLED
        finally:
            reopened.close()
        service.shutdown()  # Idempotent cleanup.
    finally:
        adapter.release.set()
        service.shutdown()


def test_retry_still_succeeds_before_deadline():
    attempts = []

    def run(simulation_id, **_kwargs):
        attempts.append(simulation_id)
        if len(attempts) == 1:
            raise AdapterError(AdapterErrorCode.INTEROP_ERROR, "retryable backend failure")
        return SimpleNamespace(results_id="retry-result")

    service = JobService(max_workers=1, default_timeout=1, max_retries=1)
    try:
        job = service.submit_simulation_job(SimpleNamespace(run_simulation_sync=run), "retry")
        done = service.wait_for_completion(job.job_id, timeout=2)
        assert done.status == JobStatus.SUCCEEDED
        assert done.attempts == 2
        assert done.result_id == "retry-result"
    finally:
        service.shutdown()


@pytest.mark.parametrize("population", [False, True])
def test_shutdown_during_submission_does_not_leave_an_orphaned_job(monkeypatch, population):
    service = JobService(max_workers=1)
    original_uuid = job_service.uuid.uuid4

    def stop_before_job_is_registered():
        service.shutdown()
        return original_uuid()

    monkeypatch.setattr(job_service.uuid, "uuid4", stop_before_job_is_registered)
    try:
        with pytest.raises(RuntimeError, match="shut down"):
            if population:
                config = PopulationSimulationConfig(
                    model_path="stub.R", simulation_id="blocked", cohort={"size": 1}
                )
                service.submit_population_job(BlockingAdapter(), config)
            else:
                service.submit_simulation_job(BlockingAdapter(), "blocked")
        assert service._jobs == {}
    finally:
        service.shutdown()
