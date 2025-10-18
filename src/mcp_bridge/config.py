"""Application configuration management."""

from __future__ import annotations

import os
from typing import Any, Optional, Tuple

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from . import __version__
from .constants import SERVICE_NAME
from .logging import DEFAULT_LOG_LEVEL


class ConfigError(RuntimeError):
    """Raised when application configuration is invalid."""


class AppConfig(BaseModel):
    """Validated application configuration loaded from environment variables."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    host: str = Field(default="0.0.0.0", description="Host interface to bind the HTTP server")
    port: int = Field(default=8000, ge=1, le=65535, description="Port for the HTTP server")
    log_level: str = Field(default=DEFAULT_LOG_LEVEL, description="Root log level")
    service_name: str = Field(default=SERVICE_NAME, description="Service identifier")
    service_version: str = Field(default=__version__, description="Service version override")
    environment: str = Field(default="development", description="Deployment environment tag")
    adapter_backend: str = Field(
        default="inmemory", description="Adapter backend to use (inmemory, subprocess)"
    )
    adapter_require_r: bool = Field(
        default=False, description="Fail startup if R/ospsuite environment is unavailable"
    )
    adapter_timeout_ms: int = Field(
        default=30000, ge=1000, description="Default timeout for adapter operations in milliseconds"
    )
    adapter_r_path: Optional[str] = Field(
        default=None, description="Explicit path to the R binary (overrides PATH lookup)"
    )
    adapter_r_home: Optional[str] = Field(
        default=None, description="R_HOME override for subprocesses"
    )
    adapter_r_libs: Optional[str] = Field(
        default=None, description="Additional R library lookup path (R_LIBS)"
    )
    adapter_ospsuite_libs: Optional[str] = Field(
        default=None, description="Absolute path to ospsuite R libraries"
    )
    adapter_model_paths: Tuple[str, ...] = Field(
        default=(), description="Allow-listed directories for simulation model files (.pkml)"
    )
    job_worker_threads: int = Field(
        default=2, ge=1, le=32, description="Number of in-process worker threads for async jobs"
    )
    job_timeout_seconds: int = Field(
        default=300, ge=1, description="Default execution timeout (seconds) for jobs"
    )
    job_max_retries: int = Field(
        default=0, ge=0, description="Automatic retry attempts for failed jobs"
    )
    population_storage_path: str = Field(
        default="var/population-results",
        description="Filesystem path for persisted population simulation chunks",
    )
    audit_enabled: bool = Field(default=True, description="Enable immutable audit trail")
    audit_storage_path: str = Field(
        default="var/audit",
        description="Filesystem path for audit trail storage",
    )
    auth_issuer_url: Optional[str] = Field(default=None, description="OIDC issuer URL")
    auth_audience: Optional[str] = Field(default=None, description="Expected audience claim")
    auth_jwks_url: Optional[str] = Field(default=None, description="JWKS endpoint for token validation")
    auth_jwks_cache_seconds: int = Field(default=900, ge=60, description="JWKS cache TTL in seconds")
    auth_dev_secret: Optional[str] = Field(default=None, description="Shared secret for HS256 dev tokens")

    @field_validator("log_level")
    @classmethod
    def _normalise_log_level(cls, value: str) -> str:
        from logging import getLevelName

        candidate = value.upper()
        resolved = getLevelName(candidate)
        if isinstance(resolved, int):
            return candidate
        raise ValueError(f"Unsupported log level '{value}'")

    @field_validator("adapter_backend")
    @classmethod
    def _normalise_backend(cls, value: str) -> str:
        backend = value.lower()
        if backend not in {"inmemory", "subprocess"}:
            raise ValueError(f"Unsupported adapter backend '{value}'")
        return backend

    @field_validator("adapter_model_paths")
    @classmethod
    def _coerce_paths(cls, value: Tuple[str, ...]) -> Tuple[str, ...]:
        normalised = tuple(path for path in (item.strip() for item in value) if path)
        return normalised

    @classmethod
    def from_env(cls) -> AppConfig:
        """Load configuration from environment variables (respecting .env)."""
        load_dotenv()
        try:
            raw: dict[str, Any] = {
                "host": os.getenv("HOST", cls.model_fields["host"].default),
                "port": os.getenv("PORT", cls.model_fields["port"].default),
                "log_level": os.getenv("LOG_LEVEL", cls.model_fields["log_level"].default),
                "service_name": os.getenv("SERVICE_NAME", cls.model_fields["service_name"].default),
                "service_version": os.getenv(
                    "SERVICE_VERSION", cls.model_fields["service_version"].default
                ),
                "environment": os.getenv("ENVIRONMENT", cls.model_fields["environment"].default),
                "adapter_backend": os.getenv(
                    "ADAPTER_BACKEND", cls.model_fields["adapter_backend"].default
                ),
                "adapter_require_r": cls._env_to_bool(
                    "ADAPTER_REQUIRE_R_ENV", cls.model_fields["adapter_require_r"].default
                ),
                "adapter_timeout_ms": cls._env_to_int(
                    "ADAPTER_TIMEOUT_MS", cls.model_fields["adapter_timeout_ms"].default
                ),
                "adapter_r_path": os.getenv("ADAPTER_R_PATH"),
                "adapter_r_home": os.getenv("ADAPTER_R_HOME"),
                "adapter_r_libs": os.getenv("ADAPTER_R_LIBS"),
                "adapter_ospsuite_libs": os.getenv("OSPSUITE_LIBS"),
                "adapter_model_paths": cls._env_to_paths(
                    os.getenv("ADAPTER_MODEL_PATHS"),
                    cls.model_fields["adapter_model_paths"].default,
                ),
                "job_worker_threads": cls._env_to_int(
                    "JOB_WORKER_THREADS", cls.model_fields["job_worker_threads"].default
                ),
                "job_timeout_seconds": cls._env_to_int(
                    "JOB_TIMEOUT_SECONDS", cls.model_fields["job_timeout_seconds"].default
                ),
                "job_max_retries": cls._env_to_int(
                    "JOB_MAX_RETRIES", cls.model_fields["job_max_retries"].default
                ),
                "population_storage_path": os.getenv(
                    "POPULATION_STORAGE_PATH",
                    cls.model_fields["population_storage_path"].default,
                ),
                "audit_enabled": cls._env_to_bool(
                    "AUDIT_ENABLED",
                    cls.model_fields["audit_enabled"].default,
                ),
                "audit_storage_path": os.getenv(
                    "AUDIT_STORAGE_PATH",
                    cls.model_fields["audit_storage_path"].default,
                ),
                "auth_issuer_url": os.getenv("AUTH_ISSUER_URL"),
                "auth_audience": os.getenv("AUTH_AUDIENCE"),
                "auth_jwks_url": os.getenv("AUTH_JWKS_URL"),
                "auth_jwks_cache_seconds": cls._env_to_int(
                    "AUTH_JWKS_CACHE_SECONDS",
                    cls.model_fields["auth_jwks_cache_seconds"].default,
                ),
                "auth_dev_secret": os.getenv("AUTH_DEV_SECRET"),
            }
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
        try:
            return cls.model_validate(raw)
        except ValidationError as exc:  # pragma: no cover - exercised in tests
            raise ConfigError("Invalid application configuration") from exc

    @staticmethod
    def _env_to_bool(name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        lowered = raw.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        raise ValueError(f"Environment variable {name} must be a boolean expression")

    @staticmethod
    def _env_to_int(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError as exc:
            raise ValueError(f"Environment variable {name} must be an integer") from exc

    @staticmethod
    def _env_to_paths(value: str | None, default: Tuple[str, ...]) -> Tuple[str, ...]:
        if value is None:
            return default
        return tuple(path.strip() for path in value.split(os.pathsep) if path.strip())


def load_config() -> AppConfig:
    """Convenience helper to load configuration with error propagation."""
    return AppConfig.from_env()
