"""FastAPI dependency providers."""

from __future__ import annotations

from typing import Protocol, cast

from fastapi import Request

from mcp.session_registry import RedisSessionRegistry, SessionRegistry

from .adapter import OspsuiteAdapter
from .audit import AuditTrail
from .services.job_service import BaseJobService
from .storage.population_store import PopulationResultStore
from .storage.snapshot_store import SimulationSnapshotStore


class _AppState(Protocol):
    adapter: OspsuiteAdapter
    adapter_offload: bool
    jobs: BaseJobService
    population_store: PopulationResultStore
    snapshot_store: SimulationSnapshotStore
    session_registry: SessionRegistry | RedisSessionRegistry
    audit: AuditTrail


def get_adapter(request: Request) -> OspsuiteAdapter:
    state = cast(_AppState, request.app.state)
    return state.adapter


def should_offload_adapter(request: Request) -> bool:
    state = cast(_AppState, request.app.state)
    return getattr(state, "adapter_offload", True)


def get_job_service(request: Request) -> BaseJobService:
    state = cast(_AppState, request.app.state)
    return state.jobs


def get_population_store(request: Request) -> PopulationResultStore:
    state = cast(_AppState, request.app.state)
    return state.population_store


def get_snapshot_store(request: Request) -> SimulationSnapshotStore:
    state = cast(_AppState, request.app.state)
    return state.snapshot_store


def get_session_registry(request: Request) -> SessionRegistry | RedisSessionRegistry:
    state = cast(_AppState, request.app.state)
    return state.session_registry


def get_audit_trail(request: Request) -> AuditTrail:
    state = cast(_AppState, request.app.state)
    return state.audit
