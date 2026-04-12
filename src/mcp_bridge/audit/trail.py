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
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - optional dependency
    boto3 = None  # type: ignore
    BotoConfig = None  # type: ignore
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

    def fetch_review_signoff_events(
        self,
        *,
        limit: int,
        simulation_id: str,
        scope: str,
        event_types: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("fetch_review_signoff_events not implemented for this audit backend")

    def count_review_signoff_events(
        self,
        *,
        simulation_id: str,
        scope: str,
        event_types: tuple[str, ...] | None = None,
    ) -> int:
        raise NotImplementedError("count_review_signoff_events not implemented for this audit backend")

    def has_review_signoff_index(
        self,
        *,
        simulation_id: str,
        scope: str,
    ) -> bool:
        raise NotImplementedError("has_review_signoff_index not implemented for this audit backend")

    def backfill_review_signoff_index(self, *, dry_run: bool = False) -> dict[str, int | str]:
        raise NotImplementedError("backfill_review_signoff_index not implemented for this audit backend")

    # Hooks for subclasses -------------------------------------------------
    def _prepare_for_timestamp(self, timestamp: datetime) -> None:
        """Prepare writer for the current timestamp (e.g., rollover)."""

    def _persist_event(self, timestamp: datetime, line: str, event: dict[str, Any]) -> None:
        raise NotImplementedError  # pragma: no cover


_REVIEW_SIGNOFF_EVENT_TYPES = frozenset(
    {
        "review.signoff.recorded",
        "review.signoff.revoked",
    }
)


def _review_signoff_index_key(simulation_id: str, scope: str) -> str:
    payload = f"{simulation_id}\n{scope}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _extract_review_signoff_locator(event: dict[str, Any]) -> tuple[str, str] | None:
    if event.get("eventType") not in _REVIEW_SIGNOFF_EVENT_TYPES:
        return None
    payload = event.get("reviewSignoff")
    if not isinstance(payload, dict):
        return None
    simulation_id = str(payload.get("simulationId") or "").strip()
    scope = str(payload.get("scope") or "").strip()
    if not simulation_id or not scope:
        return None
    return simulation_id, scope


class LocalAuditTrail(_AuditTrailBase):
    """Append-only JSONL writer backed by the local filesystem."""

    def __init__(self, storage_dir: Path | str, *, enabled: bool = True) -> None:
        super().__init__(enabled=enabled)
        self._storage_dir = Path(storage_dir).expanduser()
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._review_signoff_index_dir = self._storage_dir / "_index" / "review_signoff"
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

        tail_hash = self._previous_tail_hash(relative_path)
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

    def _previous_tail_hash(self, relative_path: Path) -> str:
        latest_hash = "0" * 64
        for candidate in sorted(self._storage_dir.glob("**/*.jsonl"), reverse=True):
            candidate_relative = candidate.relative_to(self._storage_dir)
            if candidate_relative >= relative_path:
                continue
            last_line = self._read_last_line(candidate)
            if not last_line:
                continue
            try:
                data = json.loads(last_line)
            except json.JSONDecodeError:
                continue
            return data.get("hash", latest_hash)
        return latest_hash

    def _persist_event(self, timestamp: datetime, line: str, event: dict[str, Any]) -> None:
        assert self._file is not None
        self._file.write(line + "\n")
        self._file.flush()
        self._persist_review_signoff_index(timestamp, line, event)

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
            if self._is_index_path(path):
                continue
            try:
                lines = self._iter_lines_reverse(path)
            except FileNotFoundError:  # pragma: no cover - rotation race
                continue
            for line in lines:
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

    def fetch_review_signoff_events(
        self,
        *,
        limit: int,
        simulation_id: str,
        scope: str,
        event_types: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 1000))
        events: list[dict[str, Any]] = []
        paths = list(self._iter_review_signoff_index_paths(simulation_id=simulation_id, scope=scope))
        for path in paths:
            try:
                event = json.loads(path.read_text(encoding="utf-8").strip())
            except (FileNotFoundError, json.JSONDecodeError):
                continue
            if event_types and event.get("eventType") not in event_types:
                continue
            events.append(event)
            if len(events) >= limit:
                return events
        if events or paths:
            return events
        return self._scan_review_signoff_events_from_audit(
            limit=limit,
            simulation_id=simulation_id,
            scope=scope,
            event_types=event_types,
        )

    def count_review_signoff_events(
        self,
        *,
        simulation_id: str,
        scope: str,
        event_types: tuple[str, ...] | None = None,
    ) -> int:
        if not self.has_review_signoff_index(simulation_id=simulation_id, scope=scope):
            return 0
        paths = list(self._iter_review_signoff_index_paths(simulation_id=simulation_id, scope=scope))
        count = 0
        for path in paths:
            if not event_types:
                count += 1
                continue
            try:
                event = json.loads(path.read_text(encoding="utf-8").strip())
            except (FileNotFoundError, json.JSONDecodeError):
                continue
            if event.get("eventType") in event_types:
                count += 1
        return count

    def _iter_lines_reverse(self, path: Path, chunk_size: int = 8192):
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            position = fh.tell()
            remainder = b""
            while position > 0:
                read_size = min(chunk_size, position)
                position -= read_size
                fh.seek(position)
                chunk = fh.read(read_size)
                if not chunk:
                    break
                parts = (chunk + remainder).split(b"\n")
                remainder = parts[0]
                for part in reversed(parts[1:]):
                    line = part.decode("utf-8").strip()
                    if line:
                        yield line
            if remainder:
                line = remainder.decode("utf-8").strip()
                if line:
                    yield line

    def _persist_review_signoff_index(self, timestamp: datetime, line: str, event: dict[str, Any]) -> None:
        locator = _extract_review_signoff_locator(event)
        if locator is None:
            return
        simulation_id, scope = locator
        target_path = self._review_signoff_index_path(
            simulation_id=simulation_id,
            scope=scope,
            timestamp=timestamp,
            event_id=str(event["eventId"]),
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(line + "\n", encoding="utf-8")

    def _iter_review_signoff_index_paths(self, *, simulation_id: str, scope: str):
        target_dir = self._review_signoff_index_dir / _review_signoff_index_key(simulation_id, scope)
        if not target_dir.exists():
            return iter(())
        return iter(sorted(target_dir.glob("*.json"), reverse=True))

    def has_review_signoff_index(
        self,
        *,
        simulation_id: str,
        scope: str,
    ) -> bool:
        target_dir = self._review_signoff_index_dir / _review_signoff_index_key(simulation_id, scope)
        return target_dir.exists()

    def backfill_review_signoff_index(self, *, dry_run: bool = False) -> dict[str, int | str]:
        scanned_events = 0
        malformed_events = 0
        signoff_events = 0
        indexed_new = 0
        indexed_existing = 0
        for path in sorted(self._storage_dir.glob("**/*.jsonl")):
            if self._is_index_path(path):
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except FileNotFoundError:  # pragma: no cover - rotation race
                continue
            for line in lines:
                if not line.strip():
                    continue
                scanned_events += 1
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    malformed_events += 1
                    continue
                locator = _extract_review_signoff_locator(event)
                if locator is None:
                    continue
                signoff_events += 1
                timestamp = self._parse_event_timestamp(event)
                if timestamp is None:
                    malformed_events += 1
                    continue
                simulation_id, scope = locator
                target_path = self._review_signoff_index_path(
                    simulation_id=simulation_id,
                    scope=scope,
                    timestamp=timestamp,
                    event_id=str(event.get("eventId") or ""),
                )
                if target_path.exists():
                    indexed_existing += 1
                    continue
                indexed_new += 1
                if dry_run:
                    continue
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(line.strip() + "\n", encoding="utf-8")
        return {
            "backend": "local",
            "dryRun": int(dry_run),
            "scannedEvents": scanned_events,
            "malformedEvents": malformed_events,
            "signoffEvents": signoff_events,
            "indexedNew": indexed_new,
            "indexedExisting": indexed_existing,
        }

    def _scan_review_signoff_events_from_audit(
        self,
        *,
        limit: int,
        simulation_id: str,
        scope: str,
        event_types: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        requested_types = set(event_types or _REVIEW_SIGNOFF_EVENT_TYPES)
        for path in sorted(self._storage_dir.glob("**/*.jsonl"), reverse=True):
            if self._is_index_path(path):
                continue
            try:
                lines = self._iter_lines_reverse(path)
            except FileNotFoundError:  # pragma: no cover - rotation race
                continue
            for line in lines:
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("eventType") not in requested_types:
                    continue
                locator = _extract_review_signoff_locator(event)
                if locator != (simulation_id, scope):
                    continue
                events.append(event)
                if len(events) >= limit:
                    return events
        return events

    def _count_review_signoff_events_from_audit(
        self,
        *,
        simulation_id: str,
        scope: str,
        event_types: tuple[str, ...] | None = None,
    ) -> int:
        return len(
            self._scan_review_signoff_events_from_audit(
                limit=1000,
                simulation_id=simulation_id,
                scope=scope,
                event_types=event_types,
            )
        )

    def _is_index_path(self, path: Path) -> bool:
        try:
            return self._review_signoff_index_dir in path.parents
        except ValueError:  # pragma: no cover - defensive
            return False

    def _review_signoff_index_path(
        self,
        *,
        simulation_id: str,
        scope: str,
        timestamp: datetime,
        event_id: str,
    ) -> Path:
        index_key = _review_signoff_index_key(simulation_id, scope)
        target_dir = self._review_signoff_index_dir / index_key
        return target_dir / f"{timestamp.strftime('%Y%m%dT%H%M%S%f')}-{event_id}.json"

    def _parse_event_timestamp(self, event: dict[str, Any]) -> Optional[datetime]:
        raw = str(event.get("timestamp") or "").strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None


class S3AuditTrail(_AuditTrailBase):
    """Audit writer that stores each event as an immutable S3 object with Object Lock."""

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str,
        region: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        force_path_style: bool = False,
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
        self._client = client or build_s3_client(
            region=region,
            endpoint_url=endpoint_url,
            force_path_style=force_path_style,
        )
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
        if not last_key:
            last_key = self._find_previous_key(day_prefix)
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

    def fetch_events(self, *, limit: int, event_type: str | None = None) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 1000))
        events: list[dict[str, Any]] = []
        for key in reversed(list(self._iter_all_keys())):
            if self._is_index_key(key):
                continue
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=key)
            except ClientError:  # pragma: no cover - defensive
                continue
            body = response["Body"].read().decode("utf-8").splitlines()
            for line in reversed(body):
                line = line.strip()
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

    def fetch_review_signoff_events(
        self,
        *,
        limit: int,
        simulation_id: str,
        scope: str,
        event_types: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 1000))
        events: list[dict[str, Any]] = []
        prefix = self._review_signoff_index_prefix(simulation_id=simulation_id, scope=scope)
        keys = self._iter_all_keys(prefix=prefix)
        for key in reversed(keys):
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=key)
            except ClientError:  # pragma: no cover - defensive
                continue
            body = response["Body"].read().decode("utf-8").strip()
            if not body:
                continue
            try:
                event = json.loads(body)
            except json.JSONDecodeError:
                continue
            if event_types and event.get("eventType") not in event_types:
                continue
            events.append(event)
            if len(events) >= limit:
                return events
        if events or keys:
            return events
        return self._scan_review_signoff_events_from_audit(
            limit=limit,
            simulation_id=simulation_id,
            scope=scope,
            event_types=event_types,
        )

    def count_review_signoff_events(
        self,
        *,
        simulation_id: str,
        scope: str,
        event_types: tuple[str, ...] | None = None,
    ) -> int:
        if not self.has_review_signoff_index(simulation_id=simulation_id, scope=scope):
            return 0
        prefix = self._review_signoff_index_prefix(simulation_id=simulation_id, scope=scope)
        keys = self._iter_all_keys(prefix=prefix)
        if not event_types:
            return len(keys)
        count = 0
        for key in keys:
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=key)
            except ClientError:  # pragma: no cover - defensive
                continue
            body = response["Body"].read().decode("utf-8").strip()
            if not body:
                continue
            try:
                event = json.loads(body)
            except json.JSONDecodeError:
                continue
            if event.get("eventType") in event_types:
                count += 1
        return count

    def _persist_event(self, timestamp: datetime, line: str, event: dict[str, Any]) -> None:
        key = self._object_key(timestamp, event["eventId"])
        params = self._put_object_params(
            key=key,
            body=(line + "\n").encode("utf-8"),
            timestamp=timestamp,
        )
        self._client.put_object(**params)
        self._last_key = key
        self._persist_review_signoff_index(timestamp, line, event)

    def _put_object_params(self, *, key: str, body: bytes, timestamp: datetime) -> dict[str, Any]:
        params: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": body,
            "ContentType": "application/json",
        }
        if self._object_lock_mode and self._object_lock_days:
            retain_until = timestamp + timedelta(days=self._object_lock_days)
            params["ObjectLockMode"] = self._object_lock_mode
            params["ObjectLockRetainUntilDate"] = retain_until
        if self._kms_key_id:
            params["ServerSideEncryption"] = "aws:kms"
            params["SSEKMSKeyId"] = self._kms_key_id
        return params

    def _day_prefix(self, timestamp: datetime) -> str:
        return f"{self._prefix}/{timestamp.strftime('%Y/%m/%d')}"

    def _object_key(self, timestamp: datetime, event_id: str) -> str:
        return f"{self._day_prefix(timestamp)}/{timestamp.strftime('%H%M%S%f')}-{event_id}.jsonl"

    def _review_signoff_index_prefix(self, *, simulation_id: str, scope: str) -> str:
        return f"{self._prefix}/_index/review_signoff/{_review_signoff_index_key(simulation_id, scope)}"

    def _review_signoff_index_key_for_event(
        self,
        *,
        simulation_id: str,
        scope: str,
        timestamp: datetime,
        event_id: str,
    ) -> str:
        return (
            f"{self._review_signoff_index_prefix(simulation_id=simulation_id, scope=scope)}"
            f"/{timestamp.strftime('%Y%m%dT%H%M%S%f')}-{event_id}.json"
        )

    def has_review_signoff_index(
        self,
        *,
        simulation_id: str,
        scope: str,
    ) -> bool:
        prefix = self._review_signoff_index_prefix(simulation_id=simulation_id, scope=scope)
        return bool(self._iter_all_keys(prefix=prefix))

    def backfill_review_signoff_index(self, *, dry_run: bool = False) -> dict[str, int | str]:
        scanned_events = 0
        malformed_events = 0
        signoff_events = 0
        indexed_new = 0
        indexed_existing = 0
        existing_index_keys = set(self._iter_all_keys(prefix=f"{self._prefix}/_index/review_signoff"))
        for key in self._iter_all_keys():
            if self._is_index_key(key):
                continue
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=key)
            except ClientError:  # pragma: no cover - defensive
                continue
            for line in response["Body"].read().decode("utf-8").splitlines():
                if not line.strip():
                    continue
                scanned_events += 1
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    malformed_events += 1
                    continue
                locator = _extract_review_signoff_locator(event)
                if locator is None:
                    continue
                signoff_events += 1
                timestamp = self._parse_event_timestamp(event)
                if timestamp is None:
                    malformed_events += 1
                    continue
                simulation_id, scope = locator
                index_key = self._review_signoff_index_key_for_event(
                    simulation_id=simulation_id,
                    scope=scope,
                    timestamp=timestamp,
                    event_id=str(event.get("eventId") or ""),
                )
                if index_key in existing_index_keys:
                    indexed_existing += 1
                    continue
                indexed_new += 1
                if dry_run:
                    continue
                params = self._put_object_params(
                    key=index_key,
                    body=(line.strip() + "\n").encode("utf-8"),
                    timestamp=timestamp,
                )
                self._client.put_object(**params)
                existing_index_keys.add(index_key)
        return {
            "backend": "s3",
            "dryRun": int(dry_run),
            "scannedEvents": scanned_events,
            "malformedEvents": malformed_events,
            "signoffEvents": signoff_events,
            "indexedNew": indexed_new,
            "indexedExisting": indexed_existing,
        }

    def _persist_review_signoff_index(self, timestamp: datetime, line: str, event: dict[str, Any]) -> None:
        locator = _extract_review_signoff_locator(event)
        if locator is None:
            return
        simulation_id, scope = locator
        key = self._review_signoff_index_key_for_event(
            simulation_id=simulation_id,
            scope=scope,
            timestamp=timestamp,
            event_id=str(event["eventId"]),
        )
        params = self._put_object_params(
            key=key,
            body=(line + "\n").encode("utf-8"),
            timestamp=timestamp,
        )
        self._client.put_object(**params)

    def _scan_review_signoff_events_from_audit(
        self,
        *,
        limit: int,
        simulation_id: str,
        scope: str,
        event_types: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        requested_types = set(event_types or _REVIEW_SIGNOFF_EVENT_TYPES)
        for key in reversed(self._iter_all_keys()):
            if self._is_index_key(key):
                continue
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=key)
            except ClientError:  # pragma: no cover - defensive
                continue
            body = response["Body"].read().decode("utf-8").splitlines()
            for line in reversed(body):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("eventType") not in requested_types:
                    continue
                locator = _extract_review_signoff_locator(event)
                if locator != (simulation_id, scope):
                    continue
                events.append(event)
                if len(events) >= limit:
                    return events
        return events

    def _count_review_signoff_events_from_audit(
        self,
        *,
        simulation_id: str,
        scope: str,
        event_types: tuple[str, ...] | None = None,
    ) -> int:
        return len(
            self._scan_review_signoff_events_from_audit(
                limit=1000,
                simulation_id=simulation_id,
                scope=scope,
                event_types=event_types,
            )
        )

    def _iter_all_keys(self, *, prefix: str | None = None) -> list[str]:
        continuation: Optional[str] = None
        keys: list[str] = []
        while True:
            kwargs = {"Bucket": self._bucket, "Prefix": prefix or self._prefix}
            if continuation:
                kwargs["ContinuationToken"] = continuation
            response = self._client.list_objects_v2(**kwargs)
            for item in response.get("Contents", []):
                keys.append(item["Key"])
            if not response.get("IsTruncated"):
                break
            continuation = response.get("NextContinuationToken")
        return sorted(keys)

    def _is_index_key(self, key: str) -> bool:
        return f"{self._prefix}/_index/" in key

    def _parse_event_timestamp(self, event: dict[str, Any]) -> Optional[datetime]:
        raw = str(event.get("timestamp") or "").strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    def _find_last_key(self, day_prefix: str) -> Optional[str]:
        keys = self._iter_all_keys(prefix=day_prefix)
        if not keys:
            return None
        return keys[-1]

    def _find_previous_key(self, day_prefix: str) -> Optional[str]:
        boundary = f"{day_prefix}/"
        previous = [key for key in self._iter_all_keys() if key < boundary]
        if not previous:
            return None
        return previous[-1]


def build_s3_client(
    *,
    region: Optional[str] = None,
    endpoint_url: Optional[str] = None,
    force_path_style: bool = False,
) -> Any:
    if boto3 is None:
        raise RuntimeError("boto3 must be installed to use S3 audit features")

    kwargs: dict[str, Any] = {}
    if region:
        kwargs["region_name"] = region
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    if force_path_style and BotoConfig is not None:
        kwargs["config"] = BotoConfig(s3={"addressing_style": "path"})
    return boto3.client("s3", **kwargs)


# Backwards compatibility exports -------------------------------------------------
AuditTrail = LocalAuditTrail

__all__ = [
    "AuditTrail",
    "LocalAuditTrail",
    "S3AuditTrail",
    "build_s3_client",
    "compute_event_hash",
]
