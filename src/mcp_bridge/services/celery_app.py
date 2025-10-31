"""Celery application configuration and task definitions for MCP jobs."""

from __future__ import annotations

from typing import Any, Dict, Optional

from celery import Celery

from ..config import AppConfig
from ..runtime.factory import build_adapter, build_population_store
from .snapshot_service import apply_snapshot_state

celery_app = Celery("mcp_bridge")


def configure_celery(config: AppConfig) -> Celery:
    """Configure the Celery application using runtime configuration."""

    celery_app.conf.update(
        broker_url=config.celery_broker_url,
        result_backend=config.celery_result_backend,
        task_always_eager=config.celery_task_always_eager,
        task_eager_propagates=config.celery_task_eager_propagates,
        timezone="UTC",
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
    )
    return celery_app


@celery_app.task(bind=True)
def run_simulation_task(
    self,
    *,
    config_data: Dict[str, Any],
    simulation_id: str,
    run_id: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
    simulation_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    config = AppConfig.model_validate(config_data)
    population_store = build_population_store(config)
    adapter = build_adapter(config, population_store=population_store)
    adapter.init()
    try:
        if simulation_state:
            apply_snapshot_state(adapter, simulation_state, simulation_id)
        result = adapter.run_simulation_sync(simulation_id, run_id=run_id)
        return {
            "status": "succeeded",
            "resultId": getattr(result, "results_id", None),
            "jobType": "simulation",
            "simulationId": simulation_id,
            "resultPayload": result.model_dump(mode="json"),
        }
    finally:
        adapter.shutdown()


@celery_app.task(bind=True)
def run_population_simulation_task(
    self,
    *,
    config_data: Dict[str, Any],
    payload: Dict[str, Any],
    timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    from mcp_bridge.adapter.schema import PopulationSimulationConfig

    config = AppConfig.model_validate(config_data)
    population_store = build_population_store(config)
    adapter = build_adapter(config, population_store=population_store)
    adapter.init()
    try:
        sim_config = PopulationSimulationConfig.model_validate(payload)
        result = adapter.run_population_simulation_sync(sim_config)
        return {
            "status": "succeeded",
            "resultId": getattr(result, "results_id", None),
            "jobType": "population",
            "simulationId": sim_config.simulation_id,
        }
    finally:
        adapter.shutdown()


__all__ = [
    "celery_app",
    "configure_celery",
    "run_simulation_task",
    "run_population_simulation_task",
]
