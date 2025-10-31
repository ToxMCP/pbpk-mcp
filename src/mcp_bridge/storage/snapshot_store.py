"""Filesystem-backed storage for simulation baseline snapshots."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional


_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _normalise_simulation_id(simulation_id: str) -> str:
    if not _IDENTIFIER_RE.match(simulation_id):
        raise ValueError(f"Invalid simulation identifier '{simulation_id}'")
    return simulation_id


def _hash_state(state: dict[str, Any]) -> str:
    serialised = json.dumps(state, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def _parse_timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SnapshotMetadata:
    simulation_id: str
    snapshot_id: str
    created_at: datetime
    hash: str
    path: Path


@dataclass(frozen=True)
class SnapshotRecord(SnapshotMetadata):
    state: dict[str, Any]


class SimulationSnapshotStore:
    """Persist and retrieve simulation baseline snapshots."""

    def __init__(self, base_path: str | Path) -> None:
        path = Path(base_path).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        path.mkdir(parents=True, exist_ok=True)
        self._base_path = path

    @property
    def base_path(self) -> Path:
        return self._base_path

    def save(self, simulation_id: str, state: dict[str, Any]) -> SnapshotRecord:
        safe_id = _normalise_simulation_id(simulation_id)
        timestamp = datetime.now(timezone.utc)
        snapshot_id = timestamp.strftime("%Y%m%dT%H%M%S%fZ")
        digest = _hash_state(state)

        payload = {
            "schemaVersion": 1,
            "simulationId": simulation_id,
            "snapshotId": snapshot_id,
            "createdAt": timestamp.isoformat(),
            "hash": digest,
            "state": state,
        }

        target_dir = self._base_path / safe_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{snapshot_id}.json"
        target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        return SnapshotRecord(
            simulation_id=simulation_id,
            snapshot_id=snapshot_id,
            created_at=timestamp,
            hash=digest,
            path=target_path,
            state=state,
        )

    def load(self, simulation_id: str, snapshot_id: str | None = None) -> Optional[SnapshotRecord]:
        records = self._load_all(simulation_id)
        if not records:
            return None
        if snapshot_id is None:
            return records[0]
        for record in records:
            if record.snapshot_id == snapshot_id:
                return record
        return None

    def list(self, simulation_id: str) -> List[SnapshotMetadata]:
        records = self._load_all(simulation_id)
        return [SnapshotMetadata(
            simulation_id=record.simulation_id,
            snapshot_id=record.snapshot_id,
            created_at=record.created_at,
            hash=record.hash,
            path=record.path,
        ) for record in records]

    def delete(self, simulation_id: str, snapshot_id: str | None = None) -> None:
        safe_id = _normalise_simulation_id(simulation_id)
        target_dir = self._base_path / safe_id
        if not target_dir.exists():
            return
        if snapshot_id is None:
            for path in target_dir.glob("*.json"):
                path.unlink(missing_ok=True)
            try:
                target_dir.rmdir()
            except OSError:
                pass
            return
        target_path = target_dir / f"{snapshot_id}.json"
        target_path.unlink(missing_ok=True)
        try:
            if not any(target_dir.iterdir()):
                target_dir.rmdir()
        except FileNotFoundError:
            pass

    def _load_all(self, simulation_id: str) -> List[SnapshotRecord]:
        safe_id = _normalise_simulation_id(simulation_id)
        target_dir = self._base_path / safe_id
        if not target_dir.exists():
            return []
        records: list[SnapshotRecord] = []
        for path in target_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):  # pragma: no cover - defensive
                continue
            created_at = _parse_timestamp(str(data.get("createdAt", "")))
            record = SnapshotRecord(
                simulation_id=str(data.get("simulationId", simulation_id)),
                snapshot_id=str(data.get("snapshotId", path.stem)),
                created_at=created_at,
                hash=str(data.get("hash", "")),
                path=path,
                state=dict(data.get("state", {})),
            )
            records.append(record)
        records.sort(key=lambda item: item.created_at, reverse=True)
        return records


__all__ = [
    "SimulationSnapshotStore",
    "SnapshotMetadata",
    "SnapshotRecord",
]
