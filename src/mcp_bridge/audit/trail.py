"""Immutable audit trail writers for local and S3-backed storage."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

try:  # pragma: no cover - optional dependency for S3
    import boto3  # type: ignore
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - optional dependency
    boto3 = None  # type: ignore
    ClientError = Exception  # type: ignore


def compute_event_hash(event: dict[str, Any]) -> str:
    temp = dict(event)
    temp.pop("hash", None)
    payload = json.dumps(temp, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass
class _WriteResult:
    tail_hash: str


class _AuditTrailBase:
    """Shared hashing logic for audit trail writers."""

    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = enabled
        self._lock = threading.Lock()
        self._tail_hash = "0" * 64

    @property
    def enabled(self) -> bool:
        return self._enabled

    def close(self) -> None:  # pragma: no cover - default no-op
        return None

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
            self._prepare_for_timestamp(timestamp)
            base_event["previousHash"] = self._tail_hash
            event_hash = compute_event_hash(base_event)
            base_event["hash"] = event_hash
            line = json.dumps(base_event, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            self._persist_event(timestamp, line, base_event)
            self._tail_hash = event_hash

    def fetch_events(self, *, limit: int, event_type: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError("fetch_events not implemented for this audit backend")

    # Hooks for subclasses -------------------------------------------------
    def _prepare_for_timestamp(self, timestamp: datetime) -> None:
        """Prepare writer for the current timestamp (e.g., rollover)."""

    def _persist_event(self, timestamp: datetime, line: str, event: dict[str, Any]) -> None:
        raise NotImplementedError  # pragma: no cover


class LocalAuditTrail(_AuditTrailBase):
    """Append-only JSONL writer backed by the local filesystem."""

    def __init__(self, storage_dir: Path | str, *, enabled: bool = True) -> None:
        super().__init__(enabled=enabled)
        self._storage_dir = Path(storage_dir).expanduser()
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._current_date: Optional[str] = None
        self._file: Optional[Any] = None
        self._current_path: Optional[Path] = None

    def close(self) -> None:
        with self._lock:
            if self._file is not None:
                self._file.close()
                self._file = None

    def _prepare_for_timestamp(self, timestamp: datetime) -> None:
        date_key = timestamp.strftime("%Y-%m-%d")
        if self._current_date == date_key and self._file is not None:
            return
        self._rollover(timestamp)

    def _rollover(self, timestamp: datetime) -> None:
        if self._file is not None:
            self._file.close()

        relative_path = Path(timestamp.strftime("%Y/%m/%d.jsonl"))
        path = self._storage_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)

        tail_hash = "0" * 64
        if path.exists() and path.stat().st_size > 0:
            last_line = self._read_last_line(path)
            if last_line:
                try:
                    data = json.loads(last_line)
                    tail_hash = data.get("hash", tail_hash)
                except json.JSONDecodeError:
                    tail_hash = "0" * 64

        self._file = path.open("a", encoding="utf-8")
        self._current_date = timestamp.strftime("%Y-%m-%d")
        self._current_path = path
        self._tail_hash = tail_hash

    def _persist_event(self, timestamp: datetime, line: str, event: dict[str, Any]) -> None:
        assert self._file is not None
        self._file.write(line + "\n")
        self._file.flush()

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
                data = fh.read().decode("utf-8").strip()
                return data or None
            return bytes(reversed(buffer)).decode("utf-8").strip()

    def fetch_events(self, *, limit: int, event_type: str | None = None) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 1000))
        events: list[dict[str, Any]] = []
        paths = sorted(self._storage_dir.glob("**/*.jsonl"), reverse=True)
        for path in paths:
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except FileNotFoundError:  # pragma: no cover - rotation race
                continue
            for line in reversed(lines):
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event_type and event.get("eventType") != event_type:
                    continue
                events.append(event)
                if len(events) >= limit:
                    return events
        return events


class S3AuditTrail(_AuditTrailBase):
    """Audit writer that stores each event as an immutable S3 object with Object Lock."""

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str,
        region: Optional[str] = None,
        client: Any = None,
        enabled: bool = True,
        object_lock_mode: Optional[str] = None,
        object_lock_retain_days: Optional[int] = None,
        kms_key_id: Optional[str] = None,
    ) -> None:
        if boto3 is None:
            raise RuntimeError("boto3 must be installed to use S3AuditTrail")
        super().__init__(enabled=enabled)
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        self._client = client or boto3.client("s3", region_name=region)
        self._current_date: Optional[str] = None
        self._object_lock_mode = object_lock_mode.upper() if object_lock_mode else None
        self._object_lock_days = object_lock_retain_days
        self._kms_key_id = kms_key_id
        self._last_key: Optional[str] = None

    def _prepare_for_timestamp(self, timestamp: datetime) -> None:
        date_key = timestamp.strftime("%Y-%m-%d")
        if self._current_date == date_key:
            return
        self._initialise_day(timestamp)

    def _initialise_day(self, timestamp: datetime) -> None:
        day_prefix = self._day_prefix(timestamp)
        last_key = self._find_last_key(day_prefix)
        if last_key:
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=last_key)
                body = response["Body"].read().decode("utf-8").strip()
                data = json.loads(body)
                self._tail_hash = data.get("hash", "0" * 64)
            except ClientError:  # pragma: no cover - defensive
                self._tail_hash = "0" * 64
        else:
            self._tail_hash = "0" * 64
        self._current_date = timestamp.strftime("%Y-%m-%d")
        self._last_key = last_key

    def _persist_event(self, timestamp: datetime, line: str, event: dict[str, Any]) -> None:
        key = self._object_key(timestamp, event["eventId"])
        params: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": (line + "\n").encode("utf-8"),
            "ContentType": "application/json",
        }
        if self._object_lock_mode and self._object_lock_days:
            retain_until = timestamp + timedelta(days=self._object_lock_days)
            params["ObjectLockMode"] = self._object_lock_mode
            params["ObjectLockRetainUntilDate"] = retain_until
        if self._kms_key_id:
            params["ServerSideEncryption"] = "aws:kms"
            params["SSEKMSKeyId"] = self._kms_key_id
        self._client.put_object(**params)
        self._last_key = key

    def _day_prefix(self, timestamp: datetime) -> str:
        return f"{self._prefix}/{timestamp.strftime('%Y/%m/%d')}"

    def _object_key(self, timestamp: datetime, event_id: str) -> str:
        return f"{self._day_prefix(timestamp)}/{timestamp.strftime('%H%M%S%f')}-{event_id}.jsonl"

    def _find_last_key(self, day_prefix: str) -> Optional[str]:
        continuation: Optional[str] = None
        last_key: Optional[str] = None
        while True:
            kwargs = {"Bucket": self._bucket, "Prefix": day_prefix}
            if continuation:
                kwargs["ContinuationToken"] = continuation
            response = self._client.list_objects_v2(**kwargs)
            for item in response.get("Contents", []):
                last_key = item["Key"]
            if not response.get("IsTruncated"):
                break
            continuation = response.get("NextContinuationToken")
        return last_key


# Backwards compatibility exports -------------------------------------------------
AuditTrail = LocalAuditTrail

__all__ = [
    "AuditTrail",
    "LocalAuditTrail",
    "S3AuditTrail",
    "compute_event_hash",
]
