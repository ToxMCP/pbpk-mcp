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
    job_retention_seconds: int = Field(
        default=7 * 24 * 60 * 60,
        ge=0,
        description="Retention window (seconds) for completed job metadata and stored results",
    )
    adapter_to_thread: bool = Field(
        default=True,
        description="Offload blocking adapter calls to background threads in API routes",
    )
    session_backend: str = Field(
        default="memory", description="Session registry backend (memory or redis)"
    )
    session_redis_url: Optional[str] = Field(
        default=None, description="Redis URL used when session backend is redis"
    )
    session_redis_prefix: str = Field(
        default="mcp:sessions", description="Redis key prefix for session registry entries"
    )
    session_ttl_seconds: Optional[int] = Field(
        default=None,
        ge=1,
        description="Expiry (seconds) applied to Redis session records; unset disables TTL",
    )
    job_registry_path: str = Field(
        default="var/jobs/registry.json",
        description="Filesystem path for persisted job metadata (Celery backend)",
    )
    job_backend: str = Field(
        default="thread",
        description="Job execution backend (thread, celery, or hpc for the stub scheduler)",
    )
    hpc_stub_queue_delay_seconds: float = Field(
        default=0.5,
        ge=0.0,
        description="Artificial queue delay applied by the HPC stub scheduler before dispatching jobs",
    )
    celery_broker_url: Optional[str] = Field(
        default="memory://", description="Celery broker URL"
    )
    celery_result_backend: Optional[str] = Field(
        default="cache+memory://", description="Celery result backend URL"
    )
    celery_task_always_eager: bool = Field(
        default=False, description="Run Celery tasks eagerly (for local testing)"
    )
    celery_task_eager_propagates: bool = Field(
        default=True, description="Propagate exceptions when tasks run eagerly"
    )
    celery_task_store_eager_result: bool = Field(
        default=False,
        description="Persist results when Celery runs tasks eagerly (required for tests)",
    )
    population_storage_path: str = Field(
        default="var/population-results",
        description="Filesystem path for persisted population simulation chunks",
    )
    population_retention_seconds: int = Field(
        default=7 * 24 * 60 * 60,
        ge=0,
        description="Retention window (seconds) for population simulation artefacts",
    )
    snapshot_storage_path: str = Field(
        default="var/snapshots",
        description="Filesystem path for persisted simulation baseline snapshots",
    )
    agent_checkpointer_path: str = Field(
        default="var/agent/checkpoints.sqlite",
        description="Filesystem path for the persistent LangGraph agent checkpointer",
    )
    audit_enabled: bool = Field(default=True, description="Enable immutable audit trail")
    audit_storage_path: str = Field(
        default="var/audit",
        description="Filesystem path for audit trail storage",
    )
    audit_storage_backend: str = Field(
        default="local", description="Audit storage backend (local or s3)"
    )
    audit_s3_bucket: Optional[str] = Field(
        default=None, description="S3 bucket for audit trail when AUDIT_STORAGE_BACKEND=s3"
    )
    audit_s3_prefix: str = Field(
        default="audit-trail", description="S3 prefix for audit objects"
    )
    audit_s3_region: Optional[str] = Field(
        default=None, description="AWS region where the audit bucket resides"
    )
    audit_s3_object_lock_mode: Optional[str] = Field(
        default=None, description="S3 Object Lock mode (governance or compliance)"
    )
    audit_s3_object_lock_days: Optional[int] = Field(
        default=None, ge=1, description="Retention in days for S3 Object Lock"
    )
    audit_s3_kms_key_id: Optional[str] = Field(
        default=None, description="KMS key ID used to encrypt audit objects"
    )
    audit_verify_lookback_days: int = Field(
        default=1,
        ge=1,
        description="Number of days of audit data to verify in scheduled jobs",
    )
    auth_issuer_url: Optional[str] = Field(default=None, description="OIDC issuer URL")
    auth_audience: Optional[str] = Field(default=None, description="Expected audience claim")
    auth_jwks_url: Optional[str] = Field(default=None, description="JWKS endpoint for token validation")
    auth_jwks_cache_seconds: int = Field(default=900, ge=60, description="JWKS cache TTL in seconds")
    auth_dev_secret: Optional[str] = Field(default=None, description="Shared secret for HS256 dev tokens")
    auth_rate_limit_per_minute: int = Field(
        default=120,
        ge=0,
        description="Maximum authenticated requests per minute per client IP (0 disables limiting)",
    )
    auth_clock_skew_seconds: int = Field(
        default=60,
        ge=0,
        description="Allowed clock skew (seconds) when validating token timestamps",
    )
    auth_replay_window_seconds: int = Field(
        default=300,
        ge=0,
        description="Replay protection window applied to tokens with jti claims",
    )
    auth_allow_anonymous: bool = Field(
        default=False,
        description="Permit anonymous access (development/testing only)",
    )

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

    @field_validator("auth_dev_secret")
    @classmethod
    def _validate_dev_secret(cls, value: Optional[str], info) -> Optional[str]:
        if value:
            env = (info.data or {}).get("environment", "development").lower()
            if env not in {"development", "local"}:
                raise ValueError("AUTH_DEV_SECRET may only be set in development environments")
        return value

    @field_validator("auth_allow_anonymous")
    @classmethod
    def _validate_allow_anonymous(cls, value: bool, info) -> bool:
        enabled = bool(value)
        if enabled:
            env = (info.data or {}).get("environment", "development")
            if str(env).lower() not in {"development", "local"}:
                raise ValueError("AUTH_ALLOW_ANONYMOUS may only be enabled in development environments")
        return enabled

    @field_validator("job_backend")
    @classmethod
    def _normalise_job_backend(cls, value: str) -> str:
        backend = value.lower()
        if backend not in {"thread", "celery", "hpc"}:
            raise ValueError(f"Unsupported job backend '{value}'")
        return backend

    @field_validator("session_backend")
    @classmethod
    def _normalise_session_backend(cls, value: str) -> str:
        backend = value.lower()
        if backend not in {"memory", "redis"}:
            raise ValueError(f"Unsupported session backend '{value}'")
        return backend

    @field_validator("adapter_to_thread")
    @classmethod
    def _normalise_adapter_to_thread(cls, value: bool) -> bool:
        return bool(value)

    @field_validator("adapter_model_paths")
    @classmethod
    def _coerce_paths(cls, value: Tuple[str, ...]) -> Tuple[str, ...]:
        normalised = tuple(path for path in (item.strip() for item in value) if path)
        return normalised

    @field_validator("audit_storage_backend")
    @classmethod
    def _normalize_audit_backend(cls, value: str) -> str:
        backend = value.lower()
        if backend not in {"local", "s3"}:
            raise ValueError(f"Unsupported audit storage backend '{value}'")
        return backend

    @field_validator("audit_s3_object_lock_mode")
    @classmethod
    def _normalize_lock_mode(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        mode = value.lower()
        if mode not in {"governance", "compliance"}:
            raise ValueError(
                "AUDIT_S3_OBJECT_LOCK_MODE must be 'governance' or 'compliance' when specified"
            )
        return mode

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
                "adapter_to_thread": cls._env_to_bool(
                    "ADAPTER_TO_THREAD", cls.model_fields["adapter_to_thread"].default
                ),
                "session_backend": os.getenv(
                    "SESSION_BACKEND", cls.model_fields["session_backend"].default
                ),
                "session_redis_url": os.getenv("SESSION_REDIS_URL"),
                "session_redis_prefix": os.getenv(
                    "SESSION_REDIS_PREFIX", cls.model_fields["session_redis_prefix"].default
                ),
                "session_ttl_seconds": (
                    cls._env_to_int("SESSION_TTL_SECONDS", 0)
                    if os.getenv("SESSION_TTL_SECONDS")
                    else cls.model_fields["session_ttl_seconds"].default
                ),
                "job_registry_path": os.getenv(
                    "JOB_REGISTRY_PATH", cls.model_fields["job_registry_path"].default
                ),
                "job_backend": os.getenv("JOB_BACKEND", cls.model_fields["job_backend"].default),
                "celery_broker_url": os.getenv(
                    "CELERY_BROKER_URL",
                    cls.model_fields["celery_broker_url"].default,
                ),
                "celery_result_backend": os.getenv(
                    "CELERY_RESULT_BACKEND",
                    cls.model_fields["celery_result_backend"].default,
                ),
                "celery_task_always_eager": cls._env_to_bool(
                    "CELERY_TASK_ALWAYS_EAGER",
                    cls.model_fields["celery_task_always_eager"].default,
                ),
                "celery_task_eager_propagates": cls._env_to_bool(
                    "CELERY_TASK_EAGER_PROPAGATES",
                    cls.model_fields["celery_task_eager_propagates"].default,
                ),
                "celery_task_store_eager_result": cls._env_to_bool(
                    "CELERY_TASK_STORE_EAGER_RESULT",
                    cls.model_fields["celery_task_store_eager_result"].default,
                ),
                "population_storage_path": os.getenv(
                    "POPULATION_STORAGE_PATH",
                    cls.model_fields["population_storage_path"].default,
                ),
                "snapshot_storage_path": os.getenv(
                    "SNAPSHOT_STORAGE_PATH",
                    cls.model_fields["snapshot_storage_path"].default,
                ),
                "agent_checkpointer_path": os.getenv(
                    "AGENT_CHECKPOINTER_PATH",
                    cls.model_fields["agent_checkpointer_path"].default,
                ),
                "audit_enabled": cls._env_to_bool(
                    "AUDIT_ENABLED",
                    cls.model_fields["audit_enabled"].default,
                ),
                "audit_storage_path": os.getenv(
                    "AUDIT_STORAGE_PATH",
                    cls.model_fields["audit_storage_path"].default,
                ),
                "audit_storage_backend": os.getenv(
                    "AUDIT_STORAGE_BACKEND",
                    cls.model_fields["audit_storage_backend"].default,
                ),
                "audit_s3_bucket": os.getenv("AUDIT_S3_BUCKET"),
                "audit_s3_prefix": os.getenv(
                    "AUDIT_S3_PREFIX", cls.model_fields["audit_s3_prefix"].default
                ),
                "audit_s3_region": os.getenv("AUDIT_S3_REGION"),
                "audit_s3_object_lock_mode": os.getenv("AUDIT_S3_OBJECT_LOCK_MODE"),
                "audit_s3_object_lock_days": (
                    cls._env_to_int("AUDIT_S3_OBJECT_LOCK_DAYS", 1)
                    if os.getenv("AUDIT_S3_OBJECT_LOCK_DAYS")
                    else cls.model_fields["audit_s3_object_lock_days"].default
                ),
                "audit_s3_kms_key_id": os.getenv("AUDIT_S3_KMS_KEY_ID"),
                "audit_verify_lookback_days": cls._env_to_int(
                    "AUDIT_VERIFY_LOOKBACK_DAYS",
                    cls.model_fields["audit_verify_lookback_days"].default,
                ),
                "auth_issuer_url": os.getenv("AUTH_ISSUER_URL"),
                "auth_audience": os.getenv("AUTH_AUDIENCE"),
                "auth_jwks_url": os.getenv("AUTH_JWKS_URL"),
                "auth_jwks_cache_seconds": cls._env_to_int(
                    "AUTH_JWKS_CACHE_SECONDS",
                    cls.model_fields["auth_jwks_cache_seconds"].default,
                ),
                "auth_dev_secret": os.getenv("AUTH_DEV_SECRET"),
                "auth_rate_limit_per_minute": cls._env_to_int(
                    "AUTH_RATE_LIMIT_PER_MINUTE",
                    cls.model_fields["auth_rate_limit_per_minute"].default,
                ),
                "auth_clock_skew_seconds": cls._env_to_int(
                    "AUTH_CLOCK_SKEW_SECONDS",
                    cls.model_fields["auth_clock_skew_seconds"].default,
                ),
                "auth_replay_window_seconds": cls._env_to_int(
                    "AUTH_REPLAY_WINDOW_SECONDS",
                    cls.model_fields["auth_replay_window_seconds"].default,
                ),
                "auth_allow_anonymous": cls._env_to_bool(
                    "AUTH_ALLOW_ANONYMOUS",
                    cls.model_fields["auth_allow_anonymous"].default,
                ),
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
