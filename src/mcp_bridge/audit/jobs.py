"""Scheduled audit verification tasks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..config import AppConfig
from .verify import (
    VerificationResult,
    verify_audit_trail,
    verify_s3_audit_trail,
)


@dataclass
class ScheduledVerificationResult:
    result: VerificationResult
    start_key: str
    end_key: str


def _date_key(timestamp: datetime) -> str:
    return timestamp.strftime("%Y/%m/%d")


def run_scheduled_verification(
    config: AppConfig,
    *,
    reference_time: datetime | None = None,
) -> ScheduledVerificationResult:
    if not config.audit_enabled:
        return ScheduledVerificationResult(
            result=VerificationResult(ok=True, checked_events=0, message="Audit trail disabled"),
            start_key="",
            end_key="",
        )

    now = reference_time or datetime.now(timezone.utc)
    lookback = max(1, config.audit_verify_lookback_days)
    start_dt = now - timedelta(days=lookback - 1)
    start_key = _date_key(start_dt)
    end_key = _date_key(now)

    backend = config.audit_storage_backend.lower()
    if backend == "s3":
        if not config.audit_s3_bucket:
            raise ValueError("AUDIT_S3_BUCKET must be set for S3 audit verification")
        result = verify_s3_audit_trail(
            bucket=config.audit_s3_bucket,
            prefix=config.audit_s3_prefix,
            region=config.audit_s3_region,
            start=start_key,
            end=end_key,
            expected_lock_mode=config.audit_s3_object_lock_mode,
            expected_lock_days=config.audit_s3_object_lock_days,
        )
    else:
        result = verify_audit_trail(
            config.audit_storage_path,
            start=start_key,
            end=end_key,
        )

    return ScheduledVerificationResult(result=result, start_key=start_key, end_key=end_key)


def _main() -> None:  # pragma: no cover - CLI helper
    from ..config import load_config

    config = load_config()
    outcome = run_scheduled_verification(config)
    message = (
        "Audit verification window "
        f"{outcome.start_key}..{outcome.end_key}: {outcome.result.message}"
    )
    if outcome.result.ok:
        print(message)
    else:
        raise SystemExit(message)


if __name__ == "__main__":  # pragma: no cover
    _main()
