"""Tests for application configuration loading."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mcp_bridge.config import AppConfig, ConfigError


def test_app_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "9001")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("SERVICE_NAME", "custom-service")
    monkeypatch.setenv("SERVICE_VERSION", "1.2.3")
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("ADAPTER_BACKEND", "subprocess")
    monkeypatch.setenv("ADAPTER_REQUIRE_R_ENV", "true")
    monkeypatch.setenv("ADAPTER_TIMEOUT_MS", "45000")
    monkeypatch.setenv("ADAPTER_R_PATH", "/usr/local/bin/R")
    monkeypatch.setenv("ADAPTER_R_HOME", "/opt/R")
    monkeypatch.setenv("ADAPTER_R_LIBS", "/opt/R/libs")
    monkeypatch.setenv("OSPSUITE_LIBS", "/opt/ospsuite")
    monkeypatch.setenv("ADAPTER_MODEL_PATHS", "/data/models:/more/models")
    monkeypatch.setenv("ADAPTER_TO_THREAD", "false")
    monkeypatch.setenv("JOB_WORKER_THREADS", "4")
    monkeypatch.setenv("JOB_TIMEOUT_SECONDS", "600")
    monkeypatch.setenv("JOB_MAX_RETRIES", "3")
    monkeypatch.setenv("SESSION_BACKEND", "redis")
    monkeypatch.setenv("SESSION_REDIS_URL", "redis://localhost:6390/2")
    monkeypatch.setenv("SESSION_REDIS_PREFIX", "custom:sessions")
    monkeypatch.setenv("SESSION_TTL_SECONDS", "900")
    monkeypatch.setenv("JOB_REGISTRY_PATH", "/tmp/jobs.json")

    config = AppConfig.from_env()

    assert config.host == "127.0.0.1"
    assert config.port == 9001
    assert config.log_level == "DEBUG"
    assert config.service_name == "custom-service"
    assert config.service_version == "1.2.3"
    assert config.environment == "staging"
    assert config.adapter_backend == "subprocess"
    assert config.adapter_require_r is True
    assert config.adapter_timeout_ms == 45000
    assert config.adapter_r_path == "/usr/local/bin/R"
    assert config.adapter_r_home == "/opt/R"
    assert config.adapter_r_libs == "/opt/R/libs"
    assert config.adapter_ospsuite_libs == "/opt/ospsuite"
    assert config.adapter_model_paths == ("/data/models", "/more/models")
    assert config.adapter_to_thread is False
    assert config.job_worker_threads == 4
    assert config.job_timeout_seconds == 600
    assert config.job_max_retries == 3
    assert config.session_backend == "redis"
    assert config.session_redis_url == "redis://localhost:6390/2"
    assert config.session_redis_prefix == "custom:sessions"
    assert config.session_ttl_seconds == 900
    assert config.job_registry_path == "/tmp/jobs.json"


def test_app_config_invalid_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "70000")

    with pytest.raises(ConfigError):
        AppConfig.from_env()


def test_env_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    config = AppConfig.from_env()

    assert config.host == "0.0.0.0"
    assert config.port == 8000
    assert config.log_level == "INFO"


def test_auth_dev_secret_allowed_in_development() -> None:
    config = AppConfig(environment="development", auth_dev_secret="secret")
    assert config.auth_dev_secret == "secret"


def test_auth_dev_secret_rejected_in_production() -> None:
    with pytest.raises(ValidationError):
        AppConfig(environment="production", auth_dev_secret="secret")
