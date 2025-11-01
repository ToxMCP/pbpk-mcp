"""Thread-safe registry for tracking loaded simulations."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterable, Mapping, MutableMapping
from dataclasses import dataclass, field
from typing import Any, Optional

try:  # pragma: no cover - optional dependency
    import redis  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    redis = None  # type: ignore[assignment]

from mcp_bridge.adapter.schema import SimulationHandle


class SessionRegistryError(RuntimeError):
    """Raised when registry operations fail."""


@dataclass(frozen=True)
class SessionRecord:
    """Metadata persisted for a loaded simulation."""

    handle: SimulationHandle
    metadata: Mapping[str, object] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)

    def touch(self) -> SessionRecord:
        """Return a copy with an updated ``last_accessed`` timestamp."""
        return SessionRecord(
            handle=self.handle,
            metadata=self.metadata,
            created_at=self.created_at,
            last_accessed=time.time(),
        )


class SessionRegistry:
    """In-memory registry for loaded simulations."""

    def __init__(self) -> None:
        self._records: MutableMapping[str, SessionRecord] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ #
    # CRUD operations
    # ------------------------------------------------------------------ #
    def register(
        self,
        handle: SimulationHandle,
        *,
        metadata: Optional[Mapping[str, object]] = None,
        allow_replace: bool = False,
    ) -> SessionRecord:
        """Add ``handle`` to the registry.

        Args:
            handle: Simulation handle returned by the adapter.
            metadata: Optional metadata dictionary stored alongside the handle.
            allow_replace: When ``False`` (default) duplicate identifiers raise.

        Returns:
            The created session record.

        Raises:
            SessionRegistryError: If the identifier already exists (when
                ``allow_replace`` is ``False``).
        """

        record = SessionRecord(
            handle=handle,
            metadata=dict(metadata or {}),
        )

        with self._lock:
            exists = handle.simulation_id in self._records
            if exists and not allow_replace:
                raise SessionRegistryError(
                    f"Simulation '{handle.simulation_id}' is already registered"
                )
            self._records[handle.simulation_id] = record
        return record

    def get(self, simulation_id: str) -> SessionRecord:
        """Return the session record for ``simulation_id``."""
        with self._lock:
            try:
                record = self._records[simulation_id]
            except KeyError as exc:
                raise SessionRegistryError(f"Simulation '{simulation_id}' not found") from exc

            updated = record.touch()
            self._records[simulation_id] = updated
            return updated

    def remove(self, simulation_id: str) -> None:
        """Remove ``simulation_id`` from the registry."""
        with self._lock:
            if simulation_id in self._records:
                del self._records[simulation_id]

    def clear(self) -> None:
        """Remove all session records."""
        with self._lock:
            self._records.clear()

    # ------------------------------------------------------------------ #
    # Introspection helpers
    # ------------------------------------------------------------------ #
    def contains(self, simulation_id: str) -> bool:
        with self._lock:
            return simulation_id in self._records

    def list_ids(self) -> Iterable[str]:
        with self._lock:
            return tuple(self._records.keys())

    def snapshot(self) -> tuple[SessionRecord, ...]:
        """Return an immutable snapshot of all session records."""

        with self._lock:
            return tuple(self._records.values())

    def __len__(self) -> int:  # pragma: no cover - trivial
        with self._lock:
            return len(self._records)

    def prune_stale_entries(self) -> list[str]:  # pragma: no cover - nothing to prune in-memory
        return []


class RedisSessionRegistry:
    """Redis-backed registry for distributed session persistence."""

    def __init__(
        self,
        *,
        redis_url: str | None = None,
        client: redis.Redis[Any] | None = None,
        key_prefix: str = "mcp:sessions",
        ttl_seconds: Optional[int] = None,
    ) -> None:
        if client is None:
            if redis is None:  # pragma: no cover - import guard
                raise SessionRegistryError("redis package is required for RedisSessionRegistry")
            if not redis_url:
                raise SessionRegistryError("redis_url must be provided when client is not supplied")
            client = redis.Redis.from_url(redis_url)
        self._client = client
        self._prefix = key_prefix.rstrip(":")
        self._ttl = ttl_seconds if ttl_seconds and ttl_seconds > 0 else None
        self._lock = threading.RLock()

    @property
    def _ids_key(self) -> str:
        return f"{self._prefix}:ids"

    def _record_key(self, simulation_id: str) -> str:
        return f"{self._prefix}:record:{simulation_id}"

    def _encode(self, record: SessionRecord) -> str:
        payload = {
            "handle": record.handle.model_dump(mode="json"),
            "metadata": dict(record.metadata),
            "created_at": record.created_at,
            "last_accessed": record.last_accessed,
        }
        return json.dumps(payload, separators=(",", ":"))

    def _decode(self, payload: str, simulation_id: str) -> SessionRecord:
        data = json.loads(payload)
        handle = SimulationHandle.model_validate(data["handle"])
        metadata_raw = data.get("metadata", {})
        if not isinstance(metadata_raw, Mapping):
            metadata_raw = {}
        return SessionRecord(
            handle=handle,
            metadata=dict(metadata_raw),
            created_at=float(data.get("created_at", time.time())),
            last_accessed=float(data.get("last_accessed", time.time())),
        )

    def register(
        self,
        handle: SimulationHandle,
        *,
        metadata: Optional[Mapping[str, object]] = None,
        allow_replace: bool = False,
    ) -> SessionRecord:
        record = SessionRecord(handle=handle, metadata=dict(metadata or {}))
        key = self._record_key(handle.simulation_id)
        with self._lock:
            if not allow_replace and self._client.exists(key):
                raise SessionRegistryError(
                    f"Simulation '{handle.simulation_id}' is already registered"
                )
            encoded = self._encode(record)
            self._client.set(key, encoded, ex=self._ttl)
            self._client.sadd(self._ids_key, handle.simulation_id)
        return record

    def get(self, simulation_id: str) -> SessionRecord:
        key = self._record_key(simulation_id)
        with self._lock:
            payload = self._client.get(key)
            if payload is None:
                self._client.srem(self._ids_key, simulation_id)
                raise SessionRegistryError(f"Simulation '{simulation_id}' not found")
            payload_str = payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)
            record = self._decode(payload_str, simulation_id)
            touched = record.touch()
            self._client.set(key, self._encode(touched), ex=self._ttl)
            self._client.sadd(self._ids_key, simulation_id)
            return touched

    def remove(self, simulation_id: str) -> None:
        key = self._record_key(simulation_id)
        with self._lock:
            self._client.delete(key)
            self._client.srem(self._ids_key, simulation_id)

    def clear(self) -> None:
        with self._lock:
            ids = self.list_ids()
            if ids:
                keys = [self._record_key(sim_id) for sim_id in ids]
                self._client.delete(*keys)
            self._client.delete(self._ids_key)

    def contains(self, simulation_id: str) -> bool:
        key = self._record_key(simulation_id)
        with self._lock:
            return bool(self._client.exists(key))

    def list_ids(self) -> Iterable[str]:
        raw_ids = self._client.smembers(self._ids_key)
        ids = []
        for item in raw_ids:
            identifier = item.decode("utf-8") if isinstance(item, bytes) else str(item)
            ids.append(identifier)
        return tuple(sorted(ids))

    def snapshot(self) -> tuple[SessionRecord, ...]:
        records: list[SessionRecord] = []
        for simulation_id in self.list_ids():
            try:
                records.append(self.get(simulation_id))
            except SessionRegistryError:
                continue
        return tuple(records)

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self.list_ids())

    def prune_stale_entries(self) -> list[str]:
        removed: list[str] = []
        with self._lock:
            for simulation_id in list(self.list_ids()):
                key = self._record_key(simulation_id)
                if not self._client.exists(key):
                    self._client.srem(self._ids_key, simulation_id)
                    removed.append(simulation_id)
        return removed


class SessionRegistryFacade:
    """Proxy object that delegates to the active session registry backend."""

    __slots__ = ("_backend",)

    def __init__(self, backend: SessionRegistry | RedisSessionRegistry) -> None:
        self._backend = backend

    def set_backend(self, backend: SessionRegistry | RedisSessionRegistry) -> None:
        self._backend = backend

    def backend(self) -> SessionRegistry | RedisSessionRegistry:
        return self._backend

    def __getattr__(self, item: str):  # noqa: ANN001 - dynamic proxy
        return getattr(self._backend, item)

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._backend)


_registry_backend: SessionRegistry | RedisSessionRegistry = SessionRegistry()
registry: SessionRegistryFacade = SessionRegistryFacade(_registry_backend)


def set_registry(new_registry: SessionRegistry | RedisSessionRegistry) -> None:
    """Override the module-level registry instance."""

    registry.set_backend(new_registry)


__all__ = [
    "SessionRegistry",
    "RedisSessionRegistry",
    "SessionRegistryError",
    "SessionRecord",
    "SessionRegistryFacade",
    "registry",
    "set_registry",
]
