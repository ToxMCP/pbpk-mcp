"""FastAPI application factory for the MCP Bridge."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter
from fastapi.staticfiles import StaticFiles
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from mcp.session_registry import set_registry

from .audit import AuditTrail, S3AuditTrail
from .audit.middleware import AuditMiddleware
from .config import AppConfig, ConfigError, load_config
from .constants import CORRELATION_HEADER
from .errors import (
    DetailedHTTPException,
    ErrorCode,
    ErrorDetail,
    default_message,
    error_detail,
    error_response,
    map_status_to_code,
    redact_sensitive,
)
from .logging import DEFAULT_LOG_LEVEL, bind_context, clear_context, get_logger, setup_logging
from .routes import audit as audit_routes
from .routes import console as console_routes
from .routes import mcp as mcp_routes
from .routes import resources as resource_routes
from .routes import simulation as simulation_routes
from .runtime.factory import (
    build_adapter,
    build_population_store,
    build_session_registry,
    build_snapshot_store,
    should_offload_adapter_calls,
)
from .services.job_service import create_job_service

_REQUEST_COUNT = Counter(
    "mcp_http_requests_total",
    "Total HTTP requests processed by the MCP bridge.",
    ("method", "route", "status_code"),
)
_REQUEST_LATENCY = Histogram(
    "mcp_http_request_duration_seconds",
    "Latency of HTTP requests handled by the MCP bridge.",
    ("method", "route", "status_code"),
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.0,
        5.0,
        10.0,
    ),
)
_REQUEST_IN_PROGRESS = Gauge(
    "mcp_http_requests_in_progress",
    "Concurrent HTTP requests being processed by the MCP bridge.",
    ("method", "route"),
)


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
        route = _resolve_route_template(request)
        method = request.method.upper()
        labels = {"method": method, "route": route}
        _REQUEST_IN_PROGRESS.labels(**labels).inc()
        bind_context(
            correlation_id=correlation_id,
            http_method=request.method,
            http_path=str(request.url.path),
        )
        start = time.perf_counter()
        self._logger.info("request.start")
        status_code: int | None = None

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            self._logger.exception("request.error", durationMs=duration_ms)
            if isinstance(exc, HTTPException):
                status_code = exc.status_code
            else:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            raise
        else:
            duration_ms = (time.perf_counter() - start) * 1000
            response.headers[CORRELATION_HEADER] = correlation_id
            self._logger.info(
                "request.complete", status_code=response.status_code, durationMs=duration_ms
            )
            return response
        finally:
            duration_seconds = time.perf_counter() - start
            status_value = str(status_code or status.HTTP_500_INTERNAL_SERVER_ERROR)
            _REQUEST_LATENCY.labels(method=method, route=route, status_code=status_value).observe(
                duration_seconds
            )
            _REQUEST_COUNT.labels(method=method, route=route, status_code=status_value).inc()
            _REQUEST_IN_PROGRESS.labels(**labels).dec()
            clear_context("correlation_id", "http_method", "http_path")


def _resolve_route_template(request: Request) -> str:
    """Normalise the request path to the FastAPI route template to limit cardinality."""
    route = request.scope.get("route")
    if route is not None:
        template = getattr(route, "path", None)
        if template:
            return template
    return str(request.url.path)


def create_app(config: AppConfig | None = None, log_level: str | None = None) -> FastAPI:
    """Create the FastAPI application."""
    if config is None:
        config = load_config()

    environment = config.environment.lower()
    if environment not in {"development", "local"}:
        missing = [
            name
            for name, value in [
                ("AUTH_ISSUER_URL", config.auth_issuer_url),
                ("AUTH_AUDIENCE", config.auth_audience),
                ("AUTH_JWKS_URL", config.auth_jwks_url),
            ]
            if not value
        ]
        if missing:
            raise ConfigError(
                "Production deployments require OIDC configuration. "
                f"Missing settings: {', '.join(missing)}"
            )

    setup_logging(log_level or config.log_level or DEFAULT_LOG_LEVEL)
    logger = get_logger(__name__)

    app = FastAPI(title="MCP Bridge", version=config.service_version)
    app.state.config = config
    app.add_middleware(RequestContextMiddleware)
    app.state.started_at = time.monotonic()

    console_static_dir = Path(__file__).resolve().parents[1] / "ui" / "analyst-console"
    if console_static_dir.exists():
        app.mount(
            "/console/static",
            StaticFiles(directory=str(console_static_dir)),
            name="console-static",
        )

        @app.get("/console", include_in_schema=False)
        async def console_index() -> FileResponse:
            return FileResponse(console_static_dir / "index.html")

    population_store = build_population_store(config)
    app.state.population_store = population_store
    snapshot_store = build_snapshot_store(config)
    app.state.snapshot_store = snapshot_store
    session_registry = build_session_registry(config)
    app.state.session_registry = session_registry
    set_registry(session_registry)

    audit_backend = getattr(config, "audit_storage_backend", "local").lower()
    if audit_backend == "s3":
        if not config.audit_s3_bucket:
            raise ConfigError("AUDIT_S3_BUCKET must be set when AUDIT_STORAGE_BACKEND=s3")
        audit_trail = S3AuditTrail(
            bucket=config.audit_s3_bucket,
            prefix=config.audit_s3_prefix,
            region=config.audit_s3_region,
            enabled=config.audit_enabled,
            object_lock_mode=config.audit_s3_object_lock_mode,
            object_lock_retain_days=config.audit_s3_object_lock_days,
            kms_key_id=config.audit_s3_kms_key_id,
        )
    else:
        audit_storage = Path(config.audit_storage_path).expanduser()
        if not audit_storage.is_absolute():
            audit_storage = (Path.cwd() / audit_storage).resolve()
        audit_trail = AuditTrail(audit_storage, enabled=config.audit_enabled)
    app.state.audit = audit_trail
    app.add_middleware(AuditMiddleware, audit=audit_trail)

    adapter = build_adapter(config, population_store=population_store)
    adapter.init()
    app.state.adapter = adapter
    app.state.adapter_offload = should_offload_adapter_calls(config)
    job_service = create_job_service(
        config=config, audit_trail=audit_trail, population_store=population_store
    )
    app.state.jobs = job_service

    router = APIRouter()

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> Response:
        correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))

        raw_detail = exc.detail
        details = None
        retryable = None
        if isinstance(raw_detail, dict):
            details = raw_detail.get("details")
            message = raw_detail.get("message") or default_message(exc.status_code)
        else:
            message = str(raw_detail) if raw_detail else default_message(exc.status_code)
        message = redact_sensitive(message)

        error_code = map_status_to_code(exc.status_code)
        if isinstance(exc, DetailedHTTPException):
            if exc.error_code:
                error_code = exc.error_code
            if exc.error_details:
                details = exc.error_details
            if exc.retryable_hint is not None:
                retryable = exc.retryable_hint

        logger.warning(
            "http.error",
            status_code=exc.status_code,
            message=message,
            correlationId=correlation_id,
        )
        normalized_details = None
        if details:
            candidate_list = details if isinstance(details, list) else [details]
            normalized_details = []
            for item in candidate_list:
                if isinstance(item, ErrorDetail):
                    normalized_details.append(item)
                elif isinstance(item, dict):
                    normalized_details.append(
                        error_detail(
                            issue=str(item.get("issue") or item.get("message") or item),
                            field=item.get("field"),
                            hint=item.get("hint"),
                            code=item.get("code"),
                        )
                    )
                else:
                    normalized_details.append(error_detail(issue=str(item)))

        return error_response(
            code=error_code,
            message=message,
            correlation_id=correlation_id,
            status_code=exc.status_code,
            retryable=retryable if retryable is not None else False,
            details=normalized_details,
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
    app.include_router(mcp_routes.router)
    app.include_router(resource_routes.router)
    app.include_router(simulation_routes.router)
    app.include_router(audit_routes.router)
    app.include_router(console_routes.router)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        payload = generate_latest()
        headers = {"Cache-Control": "no-store"}
        return Response(payload, media_type=CONTENT_TYPE_LATEST, headers=headers)

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
