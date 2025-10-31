from __future__ import annotations

import pytest

from mcp_bridge.audit import AuditTrail
from mcp_bridge.config import AppConfig
from mcp_bridge.services.job_service import JobStatus, create_job_service
from mcp_bridge.storage.population_store import PopulationResultStore


class _DummyAdapter:
    def run_simulation_sync(self, simulation_id: str, run_id: str | None = None):
        return type("Result", (), {"results_id": f"{simulation_id}-results"})()


@pytest.mark.hpc_stub
def test_hpc_stub_assigns_external_job_id(tmp_path):
    registry_path = tmp_path / "jobs.db"
    audit_path = tmp_path / "audit"
    population_path = tmp_path / "population"

    config = AppConfig(
        job_backend="hpc",
        job_registry_path=str(registry_path),
        hpc_stub_queue_delay_seconds=0.01,
        job_worker_threads=1,
        job_timeout_seconds=5,
    )

    audit = AuditTrail(audit_path, enabled=True)
    population_store = PopulationResultStore(population_path)
    job_service = create_job_service(
        config=config,
        audit_trail=audit,
        population_store=population_store,
    )

    adapter = _DummyAdapter()
    record = job_service.submit_simulation_job(adapter, "sim-hpc")

    completed = job_service.wait_for_completion(record.job_id, timeout=5.0)
    assert completed.status is JobStatus.SUCCEEDED
    assert completed.external_job_id is not None
    assert completed.external_job_id.startswith("SLURM-")

    events = audit.fetch_events(limit=10)
    event_types = {event.get("eventType") for event in events}
    assert any(event_type and event_type.endswith(".hpc_submitted") for event_type in event_types)
    assert any(event_type and event_type.endswith(".hpc_dispatched") for event_type in event_types)

    job_service.shutdown()
    audit.close()
