"""FastAPI application factory for the MCP Bridge."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable
from typing import Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.routing import APIRouter
from pydantic import BaseModel
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp
from pathlib import Path

from .adapter import AdapterConfig
from .adapter.mock import InMemoryAdapter
from .adapter.ospsuite import SubprocessOspsuiteAdapter
from .audit import AuditTrail
from .audit.middleware import AuditMiddleware
from .config import AppConfig, ConfigError, load_config
from .constants import CORRELATION_HEADER
from .errors import (
    ErrorCode,
    default_message,
    error_response,
    map_status_to_code,
    redact_sensitive,
)
from .logging import DEFAULT_LOG_LEVEL, bind_context, clear_context, get_logger, setup_logging
from .routes import simulation as simulation_routes
from .services.job_service import JobService
from .storage.population_store import PopulationResultStore


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
    version: str
    uptimeSeconds: float


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach correlation IDs and request metadata to the log context."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._logger = get_logger(__name__)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = request.headers.get(CORRELATION_HEADER, str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        bind_context(
            correlation_id=correlation_id,
            http_method=request.method,
            http_path=str(request.url.path),
        )
        start = time.perf_counter()
        self._logger.info("request.start")

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            self._logger.exception("request.error", durationMs=duration_ms)
            raise
        else:
            duration_ms = (time.perf_counter() - start) * 1000
            response.headers[CORRELATION_HEADER] = correlation_id
            self._logger.info(
                "request.complete", status_code=response.status_code, durationMs=duration_ms
            )
            return response
        finally:
            clear_context("correlation_id", "http_method", "http_path")


def _build_adapter(config: AppConfig, *, population_store: PopulationResultStore | None = None):
    adapter_config = AdapterConfig(
        ospsuite_libs=config.adapter_ospsuite_libs,
        default_timeout_seconds=config.adapter_timeout_ms / 1000,
        r_path=config.adapter_r_path,
        r_home=config.adapter_r_home,
        r_libs=config.adapter_r_libs,
        require_r_environment=config.adapter_require_r,
        model_search_paths=config.adapter_model_paths,
    )
    backend = config.adapter_backend
    if backend == "inmemory":
        return InMemoryAdapter(adapter_config, population_store=population_store)
    if backend == "subprocess":
        return SubprocessOspsuiteAdapter(adapter_config, population_store=population_store)
    raise ConfigError(f"Unsupported adapter backend '{backend}'")


def create_app(config: AppConfig | None = None, log_level: str | None = None) -> FastAPI:
    """Create the FastAPI application."""
    if config is None:
        config = load_config()

    setup_logging(log_level or config.log_level or DEFAULT_LOG_LEVEL)
    logger = get_logger(__name__)

    app = FastAPI(title="MCP Bridge", version=config.service_version)
    app.state.config = config
    app.add_middleware(RequestContextMiddleware)
    app.state.started_at = time.monotonic()

    storage_path = Path(config.population_storage_path).expanduser()
    if not storage_path.is_absolute():
        storage_path = (Path.cwd() / storage_path).resolve()
    population_store = PopulationResultStore(storage_path)
    app.state.population_store = population_store

    audit_storage = Path(config.audit_storage_path).expanduser()
    if not audit_storage.is_absolute():
        audit_storage = (Path.cwd() / audit_storage).resolve()
    audit_trail = AuditTrail(audit_storage, enabled=config.audit_enabled)
    app.state.audit = audit_trail
    app.add_middleware(AuditMiddleware, audit=audit_trail)

    adapter = _build_adapter(config, population_store=population_store)
    adapter.init()
    app.state.adapter = adapter
    job_service = JobService(
        max_workers=config.job_worker_threads,
        default_timeout=float(config.job_timeout_seconds),
        max_retries=config.job_max_retries,
        audit_trail=audit_trail,
    )
    app.state.jobs = job_service

    router = APIRouter()

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> Response:
        correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
        message = (
            redact_sensitive(str(exc.detail)) if exc.detail else default_message(exc.status_code)
        )
        logger.warning(
            "http.error",
            status_code=exc.status_code,
            message=message,
            correlationId=correlation_id,
        )
        return error_response(
            code=map_status_to_code(exc.status_code),
            message=message,
            correlation_id=correlation_id,
            status_code=exc.status_code,
            retryable=False,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception) -> Response:
        correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
        logger.exception("http.unhandled_error", correlationId=correlation_id)
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message="Internal server error",
            correlation_id=correlation_id,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            retryable=False,
        )

    @router.get("/health", response_model=HealthResponse, tags=["health"])
    async def health(request: Request) -> HealthResponse:
        uptime_seconds = time.monotonic() - app.state.started_at
        payload = HealthResponse(
            uptimeSeconds=uptime_seconds,
            service=config.service_name,
            version=config.service_version,
        )
        correlation_id = getattr(request.state, "correlation_id", None)
        logger.info("health.ok", uptimeSeconds=uptime_seconds, correlationId=correlation_id)
        return payload

    app.include_router(router)
    app.include_router(simulation_routes.router)

    @app.on_event("startup")
    async def _startup_event() -> None:
        logger.info(
            "application.startup",
            service=config.service_name,
            version=config.service_version,
            adapterBackend=config.adapter_backend,
        )

    @app.on_event("shutdown")
    async def _shutdown_event() -> None:
        logger.info("application.shutdown", service=config.service_name)
        adapter.shutdown()
        job_service.shutdown()
        audit_trail.close()

    return app
