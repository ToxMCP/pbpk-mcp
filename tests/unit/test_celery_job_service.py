"""Unit tests for the Celery-backed job service."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp.session_registry import registry
from mcp_bridge.config import AppConfig
from mcp_bridge.runtime.factory import build_adapter, build_population_store
from mcp_bridge.services.job_service import JobStatus, create_job_service


pytest.importorskip("celery")


@pytest.fixture()
def celery_config(tmp_path: Path) -> AppConfig:
    path = tmp_path / "population"
    return AppConfig(
        adapter_backend="inmemory",
        population_storage_path=str(path),
        job_registry_path=str(tmp_path / "jobs" / "registry.json"),
        audit_enabled=False,
        job_backend="celery",
        celery_broker_url="memory://",
        celery_result_backend="cache+memory://",
        celery_task_always_eager=True,
        celery_task_eager_propagates=True,
    )


def test_celery_job_service_runs_simulation_eager_mode(celery_config: AppConfig) -> None:
    population_store = build_population_store(celery_config)
    adapter = build_adapter(celery_config, population_store=population_store)
    adapter.init()
    job_service = create_job_service(
        config=celery_config,
        audit_trail=None,
        population_store=population_store,
    )

    try:
        adapter.load_simulation("tests/fixtures/demo.pkml", simulation_id="demo-sim")
        record = job_service.submit_simulation_job(adapter, "demo-sim")
        refreshed = job_service.get_job(record.job_id)
        assert refreshed.status == JobStatus.SUCCEEDED
        assert refreshed.result_id is not None
    finally:
        job_service.shutdown()
        adapter.shutdown()
        registry.clear()


def test_celery_job_service_persists_registry_between_instances(
    celery_config: AppConfig,
) -> None:
    population_store = build_population_store(celery_config)
    adapter = build_adapter(celery_config, population_store=population_store)
    adapter.init()
    job_service = create_job_service(
        config=celery_config,
        audit_trail=None,
        population_store=population_store,
    )

    adapter.load_simulation("tests/fixtures/demo.pkml", simulation_id="demo-sim")
    record = job_service.submit_simulation_job(adapter, "demo-sim")
    job_service.wait_for_completion(record.job_id)

    job_service.shutdown()
    adapter.shutdown()
    registry.clear()

    registry_path = Path(celery_config.job_registry_path).expanduser()
    if not registry_path.is_absolute():
        registry_path = (Path.cwd() / registry_path).resolve()
    if not registry_path.exists():
        registry_path = registry_path.with_suffix(".db")
    assert registry_path.exists()

    population_store_restarted = build_population_store(celery_config)
    adapter_restarted = build_adapter(celery_config, population_store=population_store_restarted)
    adapter_restarted.init()
    restarted_service = create_job_service(
        config=celery_config,
        audit_trail=None,
        population_store=population_store_restarted,
    )

    try:
        restored = restarted_service.get_job(record.job_id)
        assert restored.status == JobStatus.SUCCEEDED
        assert restored.result_id is not None
    finally:
        restarted_service.shutdown()
        adapter_restarted.shutdown()
        registry.clear()


def test_celery_job_service_stores_result_payload(celery_config: AppConfig) -> None:
    population_store = build_population_store(celery_config)
    adapter = build_adapter(celery_config, population_store=population_store)
    adapter.init()
    job_service = create_job_service(
        config=celery_config,
        audit_trail=None,
        population_store=population_store,
    )

    try:
        adapter.load_simulation("tests/fixtures/demo.pkml", simulation_id="demo-state")
        adapter.set_parameter_value("demo-state", "Organism|Weight", 75.0, unit="kg")
        record = job_service.submit_simulation_job(adapter, "demo-state", run_id="state-run")
        job_service.wait_for_completion(record.job_id)
        refreshed = job_service.get_job(record.job_id)
        assert refreshed.status == JobStatus.SUCCEEDED
        assert refreshed.result_id is not None
        stored = job_service.get_stored_simulation_result(refreshed.result_id)
        assert stored is not None
        assert stored["simulation_id"] == "demo-state"
        assert stored["series"]
    finally:
        job_service.shutdown()
        adapter.shutdown()
        registry.clear()
