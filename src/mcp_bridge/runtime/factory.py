"""Factories for building runtime components used across the MCP bridge."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from mcp.session_registry import RedisSessionRegistry, SessionRegistry

from ..adapter import AdapterConfig
from ..adapter.mock import InMemoryAdapter
from ..adapter.ospsuite import SubprocessOspsuiteAdapter
from ..config import AppConfig, ConfigError
from ..storage.population_store import PopulationResultStore
from ..storage.snapshot_store import SimulationSnapshotStore


def build_population_store(config: AppConfig) -> PopulationResultStore:
    """Create the population result store using configuration defaults."""

    storage_path = Path(config.population_storage_path).expanduser()
    if not storage_path.is_absolute():
        storage_path = (Path.cwd() / storage_path).resolve()
    return PopulationResultStore(storage_path)


def build_snapshot_store(config: AppConfig) -> SimulationSnapshotStore:
    """Create the snapshot store used for baseline simulation state."""

    return SimulationSnapshotStore(config.snapshot_storage_path)


def build_adapter(
    config: AppConfig,
    *,
    population_store: Optional[PopulationResultStore] = None,
):
    """Instantiate the ospsuite adapter for the configured backend."""

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


def should_offload_adapter_calls(config: AppConfig) -> bool:
    """Return True when adapter operations should run in background threads."""

    return bool(getattr(config, "adapter_to_thread", True))


def build_session_registry(config: AppConfig) -> SessionRegistry | RedisSessionRegistry:
    """Create the session registry backend based on configuration."""

    backend = getattr(config, "session_backend", "memory").lower()
    if backend == "memory":
        return SessionRegistry()
    if backend == "redis":
        url = getattr(config, "session_redis_url", None)
        if not url:
            raise ConfigError("SESSION_REDIS_URL must be set when SESSION_BACKEND=redis")
        key_prefix = getattr(config, "session_redis_prefix", "mcp:sessions")
        ttl = getattr(config, "session_ttl_seconds", None)
        return RedisSessionRegistry(redis_url=url, key_prefix=key_prefix, ttl_seconds=ttl)
    raise ConfigError(f"Unsupported session backend '{backend}'")


__all__ = [
    "build_adapter",
    "build_population_store",
    "build_snapshot_store",
    "should_offload_adapter_calls",
    "build_session_registry",
]
