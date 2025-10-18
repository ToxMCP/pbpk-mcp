"""Job execution framework for asynchronous simulation runs."""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from mcp_bridge.audit import AuditTrail

from mcp_bridge.adapter.errors import AdapterError
from mcp_bridge.adapter.schema import (
    PopulationSimulationConfig,
    PopulationSimulationResult,
    SimulationResult,
)


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
    _future: Optional[Future[Any]] = field(default=None, repr=False)


class JobService:
    """Simple thread-pool based job execution service."""

    def __init__(
        self,
        *,
        max_workers: int = 2,
        default_timeout: float = 300.0,
        max_retries: int = 0,
        audit_trail: "AuditTrail | None" = None,
    ) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="job")
        self._default_timeout = float(default_timeout)
        self._default_retries = max(0, max_retries)
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()
        self._audit = audit_trail

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
    ) -> JobRecord:
        """Queue a simulation job for asynchronous execution."""

        job_id = str(uuid.uuid4())
        record = JobRecord(
            job_id=job_id,
            simulation_id=simulation_id,
            submitted_at=time.time(),
            job_type="simulation",
            status=JobStatus.QUEUED,
            max_retries=self._default_retries if max_retries is None else max(0, max_retries),
            timeout_seconds=float(timeout_seconds) if timeout_seconds else self._default_timeout,
        )

        with self._lock:
            self._jobs[job_id] = record
        self._emit_job_event(record, "job.simulation.queued")

        future = self._executor.submit(
            self._execute_run_simulation, job_id, adapter, simulation_id, run_id
        )
        with self._lock:
            record._future = future

        return record

    def submit_population_job(
        self,
        adapter: Any,
        config: PopulationSimulationConfig,
        *,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> JobRecord:
        """Queue a population simulation job for asynchronous execution."""

        job_id = str(uuid.uuid4())
        record = JobRecord(
            job_id=job_id,
            simulation_id=config.simulation_id,
            job_type="population",
            submitted_at=time.time(),
            status=JobStatus.QUEUED,
            max_retries=self._default_retries if max_retries is None else max(0, max_retries),
            timeout_seconds=float(timeout_seconds) if timeout_seconds else self._default_timeout,
        )

        with self._lock:
            self._jobs[job_id] = record
        self._emit_job_event(record, "job.population.queued")

        future = self._executor.submit(
            self._execute_population_simulation, job_id, adapter, config
        )
        with self._lock:
            record._future = future

        return record

    def cancel_job(self, job_id: str) -> JobRecord:
        """Attempt to cancel a queued or running job."""

        with self._lock:
            record = self._jobs[job_id]
            record.cancel_requested = True
            future = record._future

        if future and future.cancel():
            # Cancellation succeeded before the job started running.
            with self._lock:
                record.status = JobStatus.CANCELLED
                record.finished_at = time.time()
                record._future = None
            self._emit_job_event(record, f"job.{record.job_type}.cancelled", reason="future_cancelled")
        return record

    def get_job(self, job_id: str) -> JobRecord:
        with self._lock:
            return self._jobs[job_id]

    def wait_for_completion(self, job_id: str, timeout: Optional[float] = None) -> JobRecord:
        with self._lock:
            record = self._jobs[job_id]
            future = record._future
        if future is not None:
            future.result(timeout=timeout)
        return self.get_job(job_id)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
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
            self._emit_job_event(record, f"job.{record.job_type}.running")

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
        self._emit_job_event(record, f"job.{record.job_type}.retry", reason=str(exc))

    def _mark_succeeded(self, job_id: str, result: Any) -> None:
        with self._lock:
            record = self._jobs[job_id]
            record.status = JobStatus.SUCCEEDED
            record.finished_at = time.time()
            record.result_id = getattr(result, "results_id", None)
            record.error = None
            record._future = None
        self._emit_job_event(record, f"job.{record.job_type}.succeeded")

    def _mark_failed(self, job_id: str, exc: Exception) -> None:
        with self._lock:
            record = self._jobs[job_id]
            record.status = JobStatus.FAILED
            record.finished_at = time.time()
            record.error = {"message": str(exc)}
            record._future = None
        self._emit_job_event(record, f"job.{record.job_type}.failed", reason=str(exc))

    def _mark_timeout(self, job_id: str) -> None:
        with self._lock:
            record = self._jobs[job_id]
            record.status = JobStatus.TIMEOUT
            record.finished_at = time.time()
            record.error = {"message": "Job execution exceeded timeout"}
            record._future = None
        self._emit_job_event(record, f"job.{record.job_type}.timeout")

    def _mark_cancelled(self, record: JobRecord) -> None:
        record.status = JobStatus.CANCELLED
        record.finished_at = time.time()
        record._future = None
        self._emit_job_event(record, f"job.{record.job_type}.cancelled")

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
                self._emit_job_event(self._jobs[job_id], f"job.{self._jobs[job_id].job_type}.cancelled", reason="checked")
            return True
        return False

    def _emit_job_event(self, record: JobRecord, event_type: str, **extra: Any) -> None:
        if self._audit is None:
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
                "submittedAt": self._to_iso(record.submitted_at),
                "startedAt": self._to_iso(record.started_at),
                "finishedAt": self._to_iso(record.finished_at),
                "resultId": record.result_id,
            },
        }
        if record.error:
            payload["error"] = record.error
        if extra:
            payload.update(extra)
        self._audit.record_event(event_type, payload)

    @staticmethod
    def _to_iso(timestamp: Optional[float]) -> Optional[str]:
        if timestamp is None:
            return None
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp))

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
