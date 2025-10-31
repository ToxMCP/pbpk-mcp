"""Job execution framework for asynchronous simulation runs."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING, Protocol

if TYPE_CHECKING:  # pragma: no cover
    from mcp_bridge.audit import AuditTrail

try:
    from celery.result import AsyncResult
    from .celery_app import (
        configure_celery,
        run_population_simulation_task,
        run_simulation_task,
    )
    CELERY_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    AsyncResult = None  # type: ignore[assignment]
    configure_celery = run_population_simulation_task = run_simulation_task = None  # type: ignore
    CELERY_AVAILABLE = False

from ..config import AppConfig, ConfigError
from mcp_bridge.adapter.errors import AdapterError
from mcp_bridge.adapter.schema import (
    PopulationSimulationConfig,
    PopulationSimulationResult,
    SimulationResult,
)
from ..storage.population_store import PopulationResultStore
from ..logging import get_logger

logger = get_logger(__name__)


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class JobRecord:
    job_id: str
    simulation_id: str
    submitted_at: float
    job_type: str = "simulation"
    status: JobStatus = JobStatus.QUEUED
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    result_id: Optional[str] = None
    error: Optional[Dict[str, Any]] = None
    attempts: int = 0
    max_retries: int = 0
    timeout_seconds: float = 0.0
    cancel_requested: bool = False
    idempotency_key: Optional[str] = None
    idempotency_fingerprint: Optional[str] = None
    external_job_id: Optional[str] = None
    _future: Optional[Future[Any]] = field(default=None, repr=False)


class DurableJobRegistry:
    """Lightweight SQLite-backed registry for persisting JobRecord state."""

    def __init__(self, path: str) -> None:
        self._path = self._prepare_path(path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_records (
                job_id TEXT PRIMARY KEY,
                simulation_id TEXT NOT NULL,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                submitted_at REAL NOT NULL,
                started_at REAL,
                finished_at REAL,
                result_id TEXT,
                error_json TEXT,
                attempts INTEGER NOT NULL,
                max_retries INTEGER NOT NULL,
                timeout_seconds REAL NOT NULL,
                cancel_requested INTEGER NOT NULL,
                idempotency_key TEXT,
                idempotency_fingerprint TEXT,
                external_job_id TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_job_records_idempotency
            ON job_records(idempotency_key)
            WHERE idempotency_key IS NOT NULL
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS simulation_results (
                result_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            )
            """
        )
        try:
            self._conn.execute(
                "ALTER TABLE job_records ADD COLUMN external_job_id TEXT"
            )
        except sqlite3.OperationalError:
            pass
        self._conn.commit()

    @staticmethod
    def _prepare_path(path_str: str) -> Path:
        path = Path(path_str).expanduser()
        if path.suffix.lower() == ".json":
            path = path.with_suffix(".db")
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def upsert(self, record: JobRecord) -> None:
        payload = self._serialize(record)
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO job_records (
                    job_id,
                    simulation_id,
                    job_type,
                    status,
                    submitted_at,
                    started_at,
                    finished_at,
                    result_id,
                    error_json,
                    attempts,
                    max_retries,
                    timeout_seconds,
                    cancel_requested,
                idempotency_key,
                idempotency_fingerprint,
                external_job_id
            ) VALUES (
                :job_id,
                :simulation_id,
                :job_type,
                :status,
                    :submitted_at,
                    :started_at,
                    :finished_at,
                    :result_id,
                    :error_json,
                    :attempts,
                    :max_retries,
                :timeout_seconds,
                :cancel_requested,
                :idempotency_key,
                :idempotency_fingerprint,
                :external_job_id
            )
            ON CONFLICT(job_id) DO UPDATE SET
                simulation_id = excluded.simulation_id,
                job_type = excluded.job_type,
                status = excluded.status,
                    submitted_at = excluded.submitted_at,
                    started_at = excluded.started_at,
                    finished_at = excluded.finished_at,
                    result_id = excluded.result_id,
                    error_json = excluded.error_json,
                    attempts = excluded.attempts,
                    max_retries = excluded.max_retries,
                timeout_seconds = excluded.timeout_seconds,
                cancel_requested = excluded.cancel_requested,
                idempotency_key = excluded.idempotency_key,
                idempotency_fingerprint = excluded.idempotency_fingerprint,
                external_job_id = excluded.external_job_id
                """,
                payload,
            )
            self._conn.commit()

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM job_records WHERE job_id = ?", (job_id,)
            ).fetchone()
        if row is None:
            return None
        return self._deserialize(row)

    def load_all(self) -> list[JobRecord]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM job_records").fetchall()
        return [self._deserialize(row) for row in rows]

    def get_by_idempotency(self, key: str) -> JobRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM job_records WHERE idempotency_key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        return self._deserialize(row)

    def delete(self, job_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM job_records WHERE job_id = ?", (job_id,))
            self._conn.commit()

    def store_result_payload(self, result_id: str, payload: dict[str, Any]) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO simulation_results(result_id, payload_json) VALUES (?, ?)",
                (result_id, json.dumps(payload)),
            )
            self._conn.commit()

    def get_result_payload(self, result_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload_json FROM simulation_results WHERE result_id = ?",
                (result_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:  # pragma: no cover - defensive guard
            logger.warning("job_registry.result_decode_failed", resultId=result_id)
            return None

    def delete_result_payload(self, result_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "DELETE FROM simulation_results WHERE result_id = ?",
                (result_id,),
            )
            self._conn.commit()

    def purge_expired(self, retention_seconds: float) -> int:
        """Delete job records (and payloads) older than the retention window."""

        if retention_seconds <= 0:
            return 0
        cutoff = time.time() - float(retention_seconds)
        with self._lock, self._conn:
            rows = self._conn.execute(
                """
                SELECT job_id, result_id
                FROM job_records
                WHERE (
                    finished_at IS NOT NULL AND finished_at < ?
                ) OR (
                    finished_at IS NULL AND submitted_at < ?
                )
                """,
                (cutoff, cutoff),
            ).fetchall()
            job_ids = [row["job_id"] for row in rows]
            result_ids = [row["result_id"] for row in rows if row["result_id"]]
            if result_ids:
                self._conn.executemany(
                    "DELETE FROM simulation_results WHERE result_id = ?",
                    [(result_id,) for result_id in result_ids],
                )
            if job_ids:
                self._conn.executemany(
                    "DELETE FROM job_records WHERE job_id = ?",
                    [(job_id,) for job_id in job_ids],
                )
            self._conn.commit()
        return len(job_ids)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _serialize(self, record: JobRecord) -> dict[str, Any]:
        return {
            "job_id": record.job_id,
            "simulation_id": record.simulation_id,
            "job_type": record.job_type,
            "status": record.status.value,
            "submitted_at": record.submitted_at,
            "started_at": record.started_at,
            "finished_at": record.finished_at,
            "result_id": record.result_id,
            "error_json": json.dumps(record.error) if record.error else None,
            "attempts": record.attempts,
            "max_retries": record.max_retries,
            "timeout_seconds": record.timeout_seconds,
            "cancel_requested": 1 if record.cancel_requested else 0,
            "idempotency_key": record.idempotency_key,
            "idempotency_fingerprint": record.idempotency_fingerprint,
            "external_job_id": record.external_job_id,
        }

    def _deserialize(self, row: sqlite3.Row | tuple) -> JobRecord:
        if isinstance(row, tuple):
            (
                job_id,
                simulation_id,
                job_type,
                status,
                submitted_at,
                started_at,
                finished_at,
                result_id,
                error_json,
                attempts,
                max_retries,
                timeout_seconds,
                cancel_requested,
                idempotency_key,
                idempotency_fingerprint,
                external_job_id,
            ) = row
        else:
            job_id = row["job_id"]
            simulation_id = row["simulation_id"]
            job_type = row["job_type"]
            status = row["status"]
            submitted_at = row["submitted_at"]
            started_at = row["started_at"]
            finished_at = row["finished_at"]
            result_id = row["result_id"]
            error_json = row["error_json"]
            attempts = row["attempts"]
            max_retries = row["max_retries"]
            timeout_seconds = row["timeout_seconds"]
            cancel_requested = row["cancel_requested"]
            idempotency_key = row["idempotency_key"]
            idempotency_fingerprint = row["idempotency_fingerprint"]
            external_job_id = row["external_job_id"]

        error_payload = json.loads(error_json) if error_json else None
        return JobRecord(
            job_id=str(job_id),
            simulation_id=str(simulation_id),
            submitted_at=float(submitted_at),
            job_type=str(job_type),
            status=JobStatus(str(status)),
            started_at=None if started_at is None else float(started_at),
            finished_at=None if finished_at is None else float(finished_at),
            result_id=None if result_id is None else str(result_id),
            error=error_payload,
            attempts=int(attempts),
            max_retries=int(max_retries),
            timeout_seconds=float(timeout_seconds),
            cancel_requested=bool(cancel_requested),
            idempotency_key=str(idempotency_key) if idempotency_key else None,
            idempotency_fingerprint=str(idempotency_fingerprint) if idempotency_fingerprint else None,
            external_job_id=str(external_job_id) if external_job_id else None,
        )

def _to_iso(timestamp: Optional[float]) -> Optional[str]:
    if timestamp is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp))


def _emit_job_event(audit, record: JobRecord, event_type: str, **extra: Any) -> None:
    if audit is None:
        return
    payload = {
        "job": {
            "jobId": record.job_id,
            "simulationId": record.simulation_id,
            "jobType": record.job_type,
            "status": record.status,
            "attempts": record.attempts,
            "maxRetries": record.max_retries,
            "timeoutSeconds": record.timeout_seconds,
            "submittedAt": _to_iso(record.submitted_at),
            "startedAt": _to_iso(record.started_at),
            "finishedAt": _to_iso(record.finished_at),
            "resultId": record.result_id,
        },
    }
    if record.error:
        payload["error"] = record.error
    if extra:
        payload.update(extra)
    audit.record_event(event_type, payload)


class IdempotencyConflictError(RuntimeError):
    """Raised when an idempotency key is reused with different payload."""


class JobScheduler(Protocol):
    """Coordinator that controls when jobs are dispatched to the local executor."""

    def attach(self, job_service: "JobService") -> None:
        ...

    def submit(self, record: JobRecord, start_execution: Callable[[], None]) -> None:
        ...

    def shutdown(self) -> None:
        ...


class BaseJobService(Protocol):
    def submit_simulation_job(
        self,
        adapter: Any,
        simulation_id: str,
        *,
        run_id: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        idempotency_fingerprint: Optional[str] = None,
    ) -> JobRecord:
        ...

    def submit_population_job(
        self,
        adapter: Any,
        config: PopulationSimulationConfig,
        *,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        idempotency_fingerprint: Optional[str] = None,
    ) -> JobRecord:
        ...

    def cancel_job(self, job_id: str) -> JobRecord:
        ...

    def get_job(self, job_id: str) -> JobRecord:
        ...

    def wait_for_completion(self, job_id: str, timeout: Optional[float] = None) -> JobRecord:
        ...

    def shutdown(self) -> None:
        ...

    def get_stored_simulation_result(self, result_id: str) -> Optional[dict[str, Any]]:
        ...


class JobService:
    """Simple thread-pool based job execution service."""

    def __init__(
        self,
        *,
        max_workers: int = 2,
        default_timeout: float = 300.0,
        max_retries: int = 0,
        audit_trail: "AuditTrail | None" = None,
        registry: DurableJobRegistry | None = None,
        scheduler: JobScheduler | None = None,
        retention_seconds: float | None = None,
        population_store: PopulationResultStore | None = None,
        population_retention_seconds: float | None = None,
    ) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="job")
        self._default_timeout = float(default_timeout)
        self._default_retries = max(0, max_retries)
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()
        self._audit = audit_trail
        self._registry_owner: tempfile.TemporaryDirectory[str] | None = None
        if registry is None:
            temp_dir = tempfile.TemporaryDirectory(prefix="mcp-jobs-")
            self._registry_owner = temp_dir
            registry = DurableJobRegistry(str((Path(temp_dir.name) / "registry.db")))
        self._registry = registry
        self._scheduler = scheduler
        self._retention_seconds = float(retention_seconds) if retention_seconds else 0.0
        self._population_store = population_store
        self._population_retention_seconds = (
            float(population_retention_seconds) if population_retention_seconds else 0.0
        )
        self._restore_from_registry()
        self._apply_retention_policy()
        if self._scheduler is not None:
            self._scheduler.attach(self)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def submit_simulation_job(
        self,
        adapter: Any,
        simulation_id: str,
        *,
        run_id: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        idempotency_fingerprint: Optional[str] = None,
    ) -> JobRecord:
        """Queue a simulation job for asynchronous execution."""

        if idempotency_key:
            existing = self._registry.get_by_idempotency(idempotency_key)
            if existing:
                if existing.idempotency_fingerprint != idempotency_fingerprint:
                    raise IdempotencyConflictError(
                        "Idempotency key reused with different payload for run_simulation"
                    )
                with self._lock:
                    self._jobs.setdefault(existing.job_id, existing)
                return self.get_job(existing.job_id)

        job_id = str(uuid.uuid4())
        record = JobRecord(
            job_id=job_id,
            simulation_id=simulation_id,
            submitted_at=time.time(),
            job_type="simulation",
            status=JobStatus.QUEUED,
            max_retries=self._default_retries if max_retries is None else max(0, max_retries),
            timeout_seconds=float(timeout_seconds) if timeout_seconds else self._default_timeout,
            idempotency_key=idempotency_key,
            idempotency_fingerprint=idempotency_fingerprint,
        )

        with self._lock:
            self._jobs[job_id] = record
        _emit_job_event(self._audit, record, "job.simulation.queued")
        self._persist_record(record)

        self._schedule_simulation_execution(record, adapter, simulation_id, run_id)

        return record

    def _restore_from_registry(self) -> None:
        try:
            records = self._registry.load_all()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("job_registry.restore_failed", reason=str(exc))
            return

        now = time.time()
        for record in records:
            record._future = None
            if record.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
                record.status = JobStatus.FAILED
                record.finished_at = now
                record.error = {"message": "Job service restarted before completion"}
                self._registry.upsert(record)
            self._jobs[record.job_id] = record

    def _persist_record(self, record: JobRecord) -> None:
        try:
            self._registry.upsert(record)
        except Exception as exc:  # pragma: no cover - persistence failures logged
            logger.warning("job_registry.persist_failed", jobId=record.job_id, reason=str(exc))

    def _apply_retention_policy(self) -> None:
        """Purge expired job metadata and population artefacts."""

        cutoff = None
        if self._retention_seconds > 0:
            cutoff = time.time() - self._retention_seconds
            with self._lock:
                stale_ids = [
                    job_id
                    for job_id, record in list(self._jobs.items())
                    if record.finished_at and record.finished_at < cutoff
                ]
                for job_id in stale_ids:
                    self._jobs.pop(job_id, None)
            try:
                removed = self._registry.purge_expired(self._retention_seconds)
                if removed:
                    logger.debug("job_registry.purged", removed=removed)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("job_registry.purge_failed", reason=str(exc))

        if self._population_store and self._population_retention_seconds > 0:
            try:
                removed = self._population_store.purge_expired(self._population_retention_seconds)
                if removed:
                    logger.debug("population_results.purged", removed=removed)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("population_results.purge_failed", reason=str(exc))

    def submit_population_job(
        self,
        adapter: Any,
        config: PopulationSimulationConfig,
        *,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        idempotency_fingerprint: Optional[str] = None,
    ) -> JobRecord:
        """Queue a population simulation job for asynchronous execution."""

        if idempotency_key:
            existing = self._registry.get_by_idempotency(idempotency_key)
            if existing:
                if existing.idempotency_fingerprint != idempotency_fingerprint:
                    raise IdempotencyConflictError(
                        "Idempotency key reused with different payload for run_population_simulation"
                    )
                with self._lock:
                    self._jobs.setdefault(existing.job_id, existing)
                return self.get_job(existing.job_id)

        job_id = str(uuid.uuid4())
        record = JobRecord(
            job_id=job_id,
            simulation_id=config.simulation_id,
            job_type="population",
            submitted_at=time.time(),
            status=JobStatus.QUEUED,
            max_retries=self._default_retries if max_retries is None else max(0, max_retries),
            timeout_seconds=float(timeout_seconds) if timeout_seconds else self._default_timeout,
            idempotency_key=idempotency_key,
            idempotency_fingerprint=idempotency_fingerprint,
        )

        with self._lock:
            self._jobs[job_id] = record
        _emit_job_event(self._audit, record, "job.population.queued")
        self._persist_record(record)

        self._schedule_population_execution(record, adapter, config)

        return record

    def cancel_job(self, job_id: str) -> JobRecord:
        """Attempt to cancel a queued or running job."""

        with self._lock:
            record = self._jobs[job_id]
            record.cancel_requested = True
            future = record._future
        self._persist_record(record)

        if future and future.cancel():
            # Cancellation succeeded before the job started running.
            with self._lock:
                record.status = JobStatus.CANCELLED
                record.finished_at = time.time()
                record._future = None
            self._persist_record(record)
            _emit_job_event(self._audit, record, f"job.{record.job_type}.cancelled", reason="future_cancelled")
            self._apply_retention_policy()
        return record

    def get_job(self, job_id: str) -> JobRecord:
        with self._lock:
            record = self._jobs.get(job_id)
        if record is None:
            restored = self._registry.get(job_id)
            if restored is None:
                raise KeyError(job_id)
            restored._future = None
            with self._lock:
                self._jobs[job_id] = restored
            record = restored
        return record

    def wait_for_completion(self, job_id: str, timeout: Optional[float] = None) -> JobRecord:
        deadline = None if timeout is None else time.time() + timeout
        while True:
            with self._lock:
                record = self._jobs[job_id]
                future = record._future
                status = record.status
            if future is not None:
                remaining = None if deadline is None else max(0.0, deadline - time.time())
                future.result(timeout=remaining)
                break
            if status in {
                JobStatus.SUCCEEDED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
                JobStatus.TIMEOUT,
            }:
                break
            if deadline is not None and time.time() >= deadline:
                raise FuturesTimeoutError()
            time.sleep(0.01)
        return self.get_job(job_id)

    def shutdown(self) -> None:
        if self._scheduler is not None:
            try:
                self._scheduler.shutdown()
            except Exception:  # pragma: no cover - defensive guard
                logger.warning("job_scheduler.shutdown_failed")
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._registry.close()
        if self._registry_owner is not None:
            self._registry_owner.cleanup()
            self._registry_owner = None

    def get_stored_simulation_result(self, result_id: str) -> Optional[dict[str, Any]]:
        return None

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _schedule_simulation_execution(
        self,
        record: JobRecord,
        adapter: Any,
        simulation_id: str,
        run_id: Optional[str],
    ) -> None:
        def start_execution() -> None:
            future = self._executor.submit(
                self._execute_run_simulation,
                record.job_id,
                adapter,
                simulation_id,
                run_id,
            )
            with self._lock:
                tracked = self._jobs[record.job_id]
                tracked._future = future
            self._persist_record(self._jobs[record.job_id])

        if self._scheduler is not None:
            self._scheduler.submit(record, start_execution)
        else:
            start_execution()

    def _schedule_population_execution(
        self,
        record: JobRecord,
        adapter: Any,
        config: PopulationSimulationConfig,
    ) -> None:
        def start_execution() -> None:
            future = self._executor.submit(
                self._execute_population_simulation,
                record.job_id,
                adapter,
                config,
            )
            with self._lock:
                tracked = self._jobs[record.job_id]
                tracked._future = future
            self._persist_record(self._jobs[record.job_id])

        if self._scheduler is not None:
            self._scheduler.submit(record, start_execution)
        else:
            start_execution()

    def assign_external_job_id(self, job_id: str, external_job_id: str) -> None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                raise KeyError(job_id)
            record.external_job_id = external_job_id
        self._persist_record(record)

    def emit_job_event(self, job_id: str, event_type: str, **extra: Any) -> None:
        try:
            record = self.get_job(job_id)
        except KeyError:  # pragma: no cover - defensive guard
            logger.warning("job.emit_event.missing", jobId=job_id, eventType=event_type)
            return
        _emit_job_event(self._audit, record, event_type, **extra)

    def _execute_run_simulation(
        self,
        job_id: str,
        adapter: Any,
        simulation_id: str,
        run_id: Optional[str],
    ) -> None:
        attempts = 0
        while True:
            attempts += 1
            with self._lock:
                record = self._jobs[job_id]
                record.attempts = attempts
                if record.cancel_requested:
                    self._mark_cancelled(record)
                    return
                record.status = JobStatus.RUNNING
                record.started_at = time.time()
            self._persist_record(record)
            _emit_job_event(self._audit, record, f"job.{record.job_type}.running")

            if self._check_cancel_requested(job_id):
                return

            try:
                result = self._call_with_timeout(
                    adapter.run_simulation_sync,
                    record.timeout_seconds,
                    simulation_id,
                    run_id=run_id,
                )
            except FuturesTimeoutError:
                self._mark_timeout(job_id)
                return
            except AdapterError as exc:
                if attempts <= record.max_retries:
                    self._record_retry(job_id, exc)
                    continue
                self._mark_failed(job_id, exc)
                return
            except Exception as exc:  # pragma: no cover - unexpected failures
                self._mark_failed(job_id, exc)
                return

            if self._check_cancel_requested(job_id):
                return

            self._mark_succeeded(job_id, result)
            return

    def _execute_population_simulation(
        self,
        job_id: str,
        adapter: Any,
        config: PopulationSimulationConfig,
    ) -> None:
        attempts = 0
        while True:
            attempts += 1
            with self._lock:
                record = self._jobs[job_id]
                record.attempts = attempts
                if record.cancel_requested:
                    self._mark_cancelled(record)
                    return
                record.status = JobStatus.RUNNING
                record.started_at = time.time()
            self._persist_record(record)

            if self._check_cancel_requested(job_id):
                return

            try:
                result = self._call_with_timeout(
                    adapter.run_population_simulation_sync,
                    record.timeout_seconds,
                    config,
                )
            except FuturesTimeoutError:
                self._mark_timeout(job_id)
                return
            except AdapterError as exc:
                if attempts <= record.max_retries:
                    self._record_retry(job_id, exc)
                    continue
                self._mark_failed(job_id, exc)
                return
            except Exception as exc:  # pragma: no cover - unexpected failures
                self._mark_failed(job_id, exc)
                return

            if self._check_cancel_requested(job_id):
                return

            self._mark_succeeded(job_id, result)
            return

    def _record_retry(self, job_id: str, exc: Exception) -> None:
        with self._lock:
            record = self._jobs[job_id]
            record.status = JobStatus.QUEUED
            record.error = {"message": str(exc)}
        self._persist_record(record)
        _emit_job_event(self._audit, record, f"job.{record.job_type}.retry", reason=str(exc))

    def _mark_succeeded(self, job_id: str, result: Any) -> None:
        with self._lock:
            record = self._jobs[job_id]
            record.status = JobStatus.SUCCEEDED
            record.finished_at = time.time()
            record.result_id = getattr(result, "results_id", None)
            record.error = None
            record._future = None
        self._persist_record(record)
        _emit_job_event(self._audit, record, f"job.{record.job_type}.succeeded")
        self._apply_retention_policy()

    def _mark_failed(self, job_id: str, exc: Exception) -> None:
        with self._lock:
            record = self._jobs[job_id]
            record.status = JobStatus.FAILED
            record.finished_at = time.time()
            record.error = {"message": str(exc)}
            record._future = None
        self._persist_record(record)
        _emit_job_event(self._audit, record, f"job.{record.job_type}.failed", reason=str(exc))
        self._apply_retention_policy()

    def _mark_timeout(self, job_id: str) -> None:
        with self._lock:
            record = self._jobs[job_id]
            record.status = JobStatus.TIMEOUT
            record.finished_at = time.time()
            record.error = {"message": "Job execution exceeded timeout"}
            record._future = None
        self._persist_record(record)
        _emit_job_event(self._audit, record, f"job.{record.job_type}.timeout")
        self._apply_retention_policy()

    def _mark_cancelled(self, record: JobRecord) -> None:
        record.status = JobStatus.CANCELLED
        record.finished_at = time.time()
        record._future = None
        self._persist_record(record)
        _emit_job_event(self._audit, record, f"job.{record.job_type}.cancelled")
        self._apply_retention_policy()

    def _check_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            record = self._jobs[job_id]
            cancelled = record.cancel_requested
            future = record._future
        if cancelled:
            if future and not future.cancelled():
                with self._lock:
                    self._jobs[job_id].status = JobStatus.CANCELLED
                    self._jobs[job_id].finished_at = time.time()
                self._jobs[job_id]._future = None
            self._persist_record(self._jobs[job_id])
            _emit_job_event(
                self._audit,
                self._jobs[job_id],
                f"job.{self._jobs[job_id].job_type}.cancelled",
                reason="checked",
            )
            self._apply_retention_policy()
            return True
        return False

    @staticmethod
    def _call_with_timeout(
        func: Callable[..., Any],
        timeout_seconds: float,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if timeout_seconds <= 0:
            return func(*args, **kwargs)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, *args, **kwargs)
            return future.result(timeout=timeout_seconds)


class CeleryJobService:
    """Celery-backed job execution service for distributed processing."""

    def __init__(
        self,
        *,
        config: AppConfig,
        audit_trail: "AuditTrail | None" = None,
        registry: DurableJobRegistry,
        population_store: PopulationResultStore | None = None,
    ) -> None:
        if not CELERY_AVAILABLE:
            raise ConfigError("Celery backend requested but celery is not installed")
        self._config = config
        self._audit = audit_trail
        self._celery_app = configure_celery(config)
        self._default_timeout = float(config.job_timeout_seconds)
        self._default_retries = max(0, config.job_max_retries)
        self._jobs: Dict[str, JobRecord] = {}
        self._lock = threading.Lock()
        self._registry = registry
        self._retention_seconds = float(config.job_retention_seconds)
        self._population_store = population_store
        self._population_retention_seconds = float(config.population_retention_seconds)
        self._restore_from_registry()
        self._apply_retention_policy()
        for job_id in list(self._jobs.keys()):
            try:
                self._sync_record(job_id)
            except KeyError:
                continue

    def _restore_from_registry(self) -> None:
        try:
            records = self._registry.load_all()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("job_registry.restore_failed", reason=str(exc))
            return

        for record in records:
            record._future = None
            self._jobs[record.job_id] = record

    def _persist_record(self, record: JobRecord) -> None:
        try:
            self._registry.upsert(record)
        except Exception as exc:  # pragma: no cover
            logger.warning("job_registry.persist_failed", jobId=record.job_id, reason=str(exc))

    def _apply_retention_policy(self) -> None:
        if self._retention_seconds > 0:
            cutoff = time.time() - self._retention_seconds
            with self._lock:
                stale_ids = [
                    job_id
                    for job_id, record in list(self._jobs.items())
                    if record.finished_at and record.finished_at < cutoff
                ]
                for job_id in stale_ids:
                    self._jobs.pop(job_id, None)
            try:
                removed = self._registry.purge_expired(self._retention_seconds)
                if removed:
                    logger.debug("job_registry.purged", removed=removed)
            except Exception as exc:  # pragma: no cover
                logger.warning("job_registry.purge_failed", reason=str(exc))

        if self._population_store and self._population_retention_seconds > 0:
            try:
                removed = self._population_store.purge_expired(self._population_retention_seconds)
                if removed:
                    logger.debug("population_results.purged", removed=removed)
            except Exception as exc:  # pragma: no cover
                logger.warning("population_results.purge_failed", reason=str(exc))

    def submit_simulation_job(
        self,
        adapter: Any,  # noqa: ARG002 - adapter is unused; kept for API parity
        simulation_id: str,
        *,
        run_id: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        idempotency_fingerprint: Optional[str] = None,
    ) -> JobRecord:
        if idempotency_key:
            existing = self._registry.get_by_idempotency(idempotency_key)
            if existing:
                if existing.idempotency_fingerprint != idempotency_fingerprint:
                    raise IdempotencyConflictError(
                        "Idempotency key reused with different payload for run_simulation"
                    )
                with self._lock:
                    self._jobs.setdefault(existing.job_id, existing)
                return self.get_job(existing.job_id)

        job_id = str(uuid.uuid4())
        record = JobRecord(
            job_id=job_id,
            simulation_id=simulation_id,
            submitted_at=time.time(),
            job_type="simulation",
            status=JobStatus.QUEUED,
            max_retries=self._default_retries if max_retries is None else max(0, max_retries),
            timeout_seconds=float(timeout_seconds) if timeout_seconds else self._default_timeout,
            idempotency_key=idempotency_key,
            idempotency_fingerprint=idempotency_fingerprint,
        )

        with self._lock:
            self._jobs[job_id] = record
        _emit_job_event(self._audit, record, "job.simulation.queued")
        self._persist_record(record)

        simulation_state: Optional[dict[str, Any]] = None
        if adapter is not None and hasattr(adapter, "export_simulation_state"):
            try:
                simulation_state = adapter.export_simulation_state(simulation_id)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning(
                    "celery.export_state_failed",
                    simulationId=simulation_id,
                    reason=str(exc),
                )

        run_simulation_task.apply_async(  # type: ignore[arg-type]
            kwargs={
                "config_data": self._config.model_dump(),
                "simulation_id": simulation_id,
                "run_id": run_id,
                "timeout_seconds": record.timeout_seconds,
                "simulation_state": simulation_state,
            },
            task_id=job_id,
        )

        return record

    def submit_population_job(
        self,
        adapter: Any,  # noqa: ARG002
        config: PopulationSimulationConfig,
        *,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        idempotency_fingerprint: Optional[str] = None,
    ) -> JobRecord:
        if idempotency_key:
            existing = self._registry.get_by_idempotency(idempotency_key)
            if existing:
                if existing.idempotency_fingerprint != idempotency_fingerprint:
                    raise IdempotencyConflictError(
                        "Idempotency key reused with different payload for run_population_simulation"
                    )
                with self._lock:
                    self._jobs.setdefault(existing.job_id, existing)
                return self.get_job(existing.job_id)

        job_id = str(uuid.uuid4())
        record = JobRecord(
            job_id=job_id,
            simulation_id=config.simulation_id,
            submitted_at=time.time(),
            job_type="population",
            status=JobStatus.QUEUED,
            max_retries=self._default_retries if max_retries is None else max(0, max_retries),
            timeout_seconds=float(timeout_seconds) if timeout_seconds else self._default_timeout,
            idempotency_key=idempotency_key,
            idempotency_fingerprint=idempotency_fingerprint,
        )

        with self._lock:
            self._jobs[job_id] = record
        _emit_job_event(self._audit, record, "job.population.queued")
        self._persist_record(record)

        run_population_simulation_task.apply_async(  # type: ignore[arg-type]
            kwargs={
                "config_data": self._config.model_dump(),
                "payload": config.model_dump(mode="json"),
                "timeout_seconds": record.timeout_seconds,
            },
            task_id=job_id,
        )

        return record

    def cancel_job(self, job_id: str) -> JobRecord:
        async_result = AsyncResult(job_id, app=self._celery_app)
        async_result.revoke(terminate=True)
        with self._lock:
            record = self._jobs[job_id]
            record.cancel_requested = True
        self._persist_record(record)
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> JobRecord:
        with self._lock:
            record = self._jobs.get(job_id)
        if record is None:
            restored = self._registry.get(job_id)
            if restored is None:
                raise KeyError(job_id)
            restored._future = None
            with self._lock:
                self._jobs[job_id] = restored
        self._sync_record(job_id)
        with self._lock:
            return self._jobs[job_id]

    def wait_for_completion(self, job_id: str, timeout: Optional[float] = None) -> JobRecord:
        async_result = AsyncResult(job_id, app=self._celery_app)
        try:
            async_result.get(timeout=timeout)
        except Exception:  # pragma: no cover - propagate status via sync call
            pass
        return self.get_job(job_id)

    def get_stored_simulation_result(self, result_id: str) -> Optional[dict[str, Any]]:
        return self._registry.get_result_payload(result_id)

    def shutdown(self) -> None:  # pragma: no cover - Celery manages its own pool
        self._registry.close()

    def _sync_record(self, job_id: str) -> None:
        async_result = AsyncResult(job_id, app=self._celery_app)
        state = async_result.state
        with self._lock:
            record = self._jobs[job_id]
            previous_status = record.status

        new_status = self._map_state(state)
        now = time.time()

        if new_status == JobStatus.RUNNING and record.started_at is None:
            record.started_at = now
        if new_status in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.TIMEOUT}:
            if record.finished_at is None:
                record.finished_at = now

        if new_status == JobStatus.SUCCEEDED:
            info = async_result.result or async_result.info or {}
            if isinstance(info, dict):
                record.result_id = info.get("resultId", record.result_id)
                payload = info.get("resultPayload")
                if record.result_id and isinstance(payload, dict):
                    self._registry.store_result_payload(record.result_id, payload)
            record.error = None
        elif new_status == JobStatus.FAILED:
            record.error = {"message": str(async_result.info)}
            if record.result_id:
                self._registry.delete_result_payload(record.result_id)
        elif new_status == JobStatus.CANCELLED and record.error is None:
            record.error = {"message": "Job cancelled"}
            if record.result_id:
                self._registry.delete_result_payload(record.result_id)
        elif new_status == JobStatus.TIMEOUT and record.result_id:
            self._registry.delete_result_payload(record.result_id)

        record.status = new_status

        with self._lock:
            self._jobs[job_id] = record
        self._persist_record(record)
        self._apply_retention_policy()

        if new_status != previous_status:
            self._emit_transition(record, new_status)

    def _map_state(self, state: str) -> JobStatus:
        mapping = {
            "PENDING": JobStatus.QUEUED,
            "RECEIVED": JobStatus.QUEUED,
            "STARTED": JobStatus.RUNNING,
            "RETRY": JobStatus.RUNNING,
            "SUCCESS": JobStatus.SUCCEEDED,
            "FAILURE": JobStatus.FAILED,
            "REVOKED": JobStatus.CANCELLED,
        }
        return mapping.get(state, JobStatus.QUEUED)

    def _emit_transition(self, record: JobRecord, status: JobStatus) -> None:
        event_suffix = {
            JobStatus.RUNNING: "running",
            JobStatus.SUCCEEDED: "succeeded",
            JobStatus.FAILED: "failed",
            JobStatus.CANCELLED: "cancelled",
            JobStatus.TIMEOUT: "timeout",
        }.get(status)
        if event_suffix:
            _emit_job_event(self._audit, record, f"job.{record.job_type}.{event_suffix}")


class StubSlurmScheduler(JobScheduler):
    """Lightweight scheduler that emulates Slurm job submission semantics."""

    def __init__(self, *, queue_delay: float = 0.5) -> None:
        self._queue_delay = max(0.0, float(queue_delay))
        self._job_service: JobService | None = None
        self._threads: set[threading.Thread] = set()
        self._lock = threading.Lock()

    def attach(self, job_service: JobService) -> None:
        self._job_service = job_service

    def submit(self, record: JobRecord, start_execution: Callable[[], None]) -> None:
        if self._job_service is None:  # pragma: no cover - defensive guard
            raise RuntimeError("Scheduler not attached to job service")

        external_job_id = f"SLURM-{uuid.uuid4().hex[:8].upper()}"
        self._job_service.assign_external_job_id(record.job_id, external_job_id)
        event_prefix = f"job.{record.job_type}"
        self._job_service.emit_job_event(
            record.job_id,
            f"{event_prefix}.hpc_submitted",
            externalJobId=external_job_id,
        )

        def runner() -> None:
            try:
                if self._queue_delay:
                    time.sleep(self._queue_delay)
                self._job_service.emit_job_event(
                    record.job_id,
                    f"{event_prefix}.hpc_dispatched",
                    externalJobId=external_job_id,
                )
                start_execution()
            finally:
                with self._lock:
                    self._threads.discard(threading.current_thread())

        thread = threading.Thread(
            target=runner,
            name=f"hpc-stub-{record.job_id}",
            daemon=True,
        )
        with self._lock:
            self._threads.add(thread)
        thread.start()

    def shutdown(self) -> None:
        with self._lock:
            threads = list(self._threads)
            self._threads.clear()
        for thread in threads:
            thread.join(timeout=1.0)


def create_job_service(
    *,
    config: AppConfig,
    audit_trail: "AuditTrail | None",
    population_store: PopulationResultStore,
) -> BaseJobService:
    registry = DurableJobRegistry(config.job_registry_path)
    try:
        removed = registry.purge_expired(config.job_retention_seconds)
        if removed:
            logger.debug("job_registry.startup_purge", removed=removed)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("job_registry.startup_purge_failed", reason=str(exc))
    if population_store is not None and config.population_retention_seconds > 0:
        try:
            removed = population_store.purge_expired(config.population_retention_seconds)
            if removed:
                logger.debug("population_results.startup_purge", removed=removed)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("population_results.startup_purge_failed", reason=str(exc))

    if config.job_backend == "celery":
        if not CELERY_AVAILABLE:
            raise ConfigError("Celery backend requested but celery is not installed")
        return CeleryJobService(
            config=config,
            audit_trail=audit_trail,
            registry=registry,
            population_store=population_store,
        )

    if config.job_backend == "hpc":
        scheduler = StubSlurmScheduler(queue_delay=config.hpc_stub_queue_delay_seconds)
        return JobService(
            max_workers=config.job_worker_threads,
            default_timeout=float(config.job_timeout_seconds),
            max_retries=config.job_max_retries,
            audit_trail=audit_trail,
            registry=registry,
            scheduler=scheduler,
            retention_seconds=config.job_retention_seconds,
            population_store=population_store,
            population_retention_seconds=config.population_retention_seconds,
        )

    return JobService(
        max_workers=config.job_worker_threads,
        default_timeout=float(config.job_timeout_seconds),
        max_retries=config.job_max_retries,
        audit_trail=audit_trail,
        registry=registry,
        retention_seconds=config.job_retention_seconds,
        population_store=population_store,
        population_retention_seconds=config.population_retention_seconds,
    )


__all__ = [
    "JobScheduler",
    "BaseJobService",
    "CeleryJobService",
    "JobRecord",
    "JobService",
    "JobStatus",
    "IdempotencyConflictError",
    "StubSlurmScheduler",
    "create_job_service",
]
