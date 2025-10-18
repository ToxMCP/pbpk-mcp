"""FastAPI dependency providers."""

from __future__ import annotations

from typing import Protocol, cast

from fastapi import Request

from .adapter import OspsuiteAdapter
from .services.job_service import JobService
from .storage.population_store import PopulationResultStore


class _AppState(Protocol):
    adapter: OspsuiteAdapter
    jobs: JobService
    population_store: PopulationResultStore


def get_adapter(request: Request) -> OspsuiteAdapter:
    state = cast(_AppState, request.app.state)
    return state.adapter


def get_job_service(request: Request) -> JobService:
    state = cast(_AppState, request.app.state)
    return state.jobs


def get_population_store(request: Request) -> PopulationResultStore:
    state = cast(_AppState, request.app.state)
    return state.population_store
