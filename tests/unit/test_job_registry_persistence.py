from __future__ import annotations

import time
from pathlib import Path

from mcp_bridge.adapter.mock import InMemoryAdapter
from mcp.session_registry import registry as session_registry
from mcp.tools.load_simulation import LoadSimulationRequest, load_simulation
from mcp_bridge.services.job_service import (
    DurableJobRegistry,
    JobRecord,
    JobService,
    JobStatus,
)


def test_job_registry_persists_completed_jobs(tmp_path):
    registry_path = tmp_path / "jobs.db"

    adapter = InMemoryAdapter()
    adapter.init()
    session_registry.clear()
    fixture = Path("tests/fixtures/demo.pkml").resolve()
    load_simulation(
        adapter,
        LoadSimulationRequest(filePath=str(fixture), simulationId="sim-registry"),
    )

    registry = DurableJobRegistry(str(registry_path))
    service = JobService(
        max_workers=1,
        default_timeout=5.0,
        max_retries=0,
        audit_trail=None,
        registry=registry,
    )

    try:
        record = service.submit_simulation_job(adapter, "sim-registry", run_id="run-1")
        completed = service.wait_for_completion(record.job_id, timeout=5.0)
        assert completed.status == JobStatus.SUCCEEDED

        service.shutdown()
        adapter.shutdown()
        session_registry.clear()

        registry_reopen = DurableJobRegistry(str(registry_path))
        service_recovered = JobService(
            max_workers=1,
            default_timeout=5.0,
            max_retries=0,
            audit_trail=None,
            registry=registry_reopen,
        )
        try:
            restored = service_recovered.get_job(record.job_id)
            assert restored.status == JobStatus.SUCCEEDED
            assert restored.result_id is not None
        finally:
            service_recovered.shutdown()
    finally:
        # Adapter already shutdown above for happy path; guard for failure cases.
        try:
            adapter.shutdown()
        except Exception:
            pass


def test_inflight_jobs_marked_failed_on_restore(tmp_path):
    registry_path = tmp_path / "jobs.db"
    registry = DurableJobRegistry(str(registry_path))

    job_id = "restore-test-job"
    registry.upsert(
        JobRecord(
            job_id=job_id,
            simulation_id="restore-sim",
            submitted_at=time.time(),
            job_type="simulation",
            status=JobStatus.RUNNING,
            started_at=time.time(),
            attempts=1,
            max_retries=0,
            timeout_seconds=10.0,
        )
    )

    service = JobService(
        max_workers=1,
        default_timeout=5.0,
        max_retries=0,
        audit_trail=None,
        registry=registry,
    )
    try:
        restored = service.get_job(job_id)
        assert restored.status == JobStatus.FAILED
        assert restored.error is not None
        assert "restart" in restored.error["message"]
    finally:
        service.shutdown()
        session_registry.clear()
