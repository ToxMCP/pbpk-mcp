"""Audit trail package."""

from .trail import AuditTrail, LocalAuditTrail, S3AuditTrail, compute_event_hash

__all__ = [
    "AuditTrail",
    "LocalAuditTrail",
    "S3AuditTrail",
    "compute_event_hash",
    "run_scheduled_verification",
]


def __getattr__(name: str):
    if name == "run_scheduled_verification":
        from .jobs import run_scheduled_verification

        return run_scheduled_verification
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
