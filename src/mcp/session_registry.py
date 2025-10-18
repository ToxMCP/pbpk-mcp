"""Thread-safe registry for tracking loaded simulations."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterable, Mapping, MutableMapping
from dataclasses import dataclass, field
from typing import Optional

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

    def __len__(self) -> int:  # pragma: no cover - trivial
        with self._lock:
            return len(self._records)


# Shared registry instance used across tools
registry = SessionRegistry()

__all__ = ["SessionRegistry", "SessionRegistryError", "SessionRecord", "registry"]
