"""Immutable audit trail writer."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4


def compute_event_hash(event: dict[str, Any]) -> str:
    temp = dict(event)
    temp.pop("hash", None)
    payload = json.dumps(temp, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class AuditTrail:
    """Append-only audit log with hash chaining."""

    def __init__(self, storage_dir: Path | str, *, enabled: bool = True) -> None:
        self._enabled = enabled
        self._storage_dir = Path(storage_dir).expanduser()
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._current_date: Optional[str] = None
        self._current_path: Optional[Path] = None
        self._file = None
        self._tail_hash = "0" * 64

    @property
    def enabled(self) -> bool:
        return self._enabled

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    def record_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if not self._enabled:
            return

        timestamp = datetime.now(timezone.utc)
        base_event: dict[str, Any] = {
            "eventId": str(uuid4()),
            "timestamp": timestamp.isoformat(),
            "eventType": event_type,
            **payload,
        }

        with self._lock:
            self._rollover_if_needed(timestamp)
            base_event["previousHash"] = self._tail_hash
            event_hash = compute_event_hash(base_event)
            base_event["hash"] = event_hash
            line = json.dumps(base_event, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            assert self._file is not None
            self._file.write(line + "\n")
            self._file.flush()
            self._tail_hash = event_hash

    # ------------------------------------------------------------------
    def _rollover_if_needed(self, timestamp: datetime) -> None:
        date_key = timestamp.strftime("%Y-%m-%d")
        if self._current_date == date_key and self._file is not None:
            return

        if self._file is not None:
            self._file.close()

        relative_path = Path(timestamp.strftime("%Y/%m/%d.jsonl"))
        path = self._storage_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)

        tail_hash = "0" * 64
        if path.exists():
            last_line = self._read_last_line(path)
            if last_line:
                try:
                    data = json.loads(last_line)
                    tail_hash = data.get("hash", tail_hash)
                except json.JSONDecodeError:
                    tail_hash = "0" * 64

        self._file = path.open("a", encoding="utf-8")
        self._current_date = date_key
        self._current_path = path
        self._tail_hash = tail_hash

    def _read_last_line(self, path: Path) -> Optional[str]:
        if path.stat().st_size == 0:
            return None
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            position = fh.tell()
            buffer = bytearray()
            while position > 0:
                position -= 1
                fh.seek(position)
                byte = fh.read(1)
                if byte == b"\n" and buffer:
                    break
                buffer.extend(byte)
            if not buffer:
                fh.seek(0)
                return fh.read().decode("utf-8").strip() or None
            return bytes(reversed(buffer)).decode("utf-8").strip()

__all__ = ["AuditTrail", "compute_event_hash"]
