"""Sweep review tracking for parameter change governance (M-02)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mcp_bridge.audit.sweep_detection import detect_parameter_sweep
from mcp_bridge.security.auth import AuthContext

SWEEP_REVIEWED_EVENT = "parameter.sweep.reviewed"


def _identity_payload(auth: AuthContext | None) -> dict[str, Any] | None:
    if auth is None:
        return None
    return {
        "subject": auth.subject,
        "roles": list(auth.roles),
        "tokenId": auth.token_id,
        "isServiceAccount": auth.is_service_account,
    }


def _fetch_parameter_events(audit: Any, simulation_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Fetch parameter.changed and parameter.sweep.reviewed events for a simulation."""
    if audit is None or not getattr(audit, "enabled", False):
        return []
    try:
        changed = audit.fetch_events(limit=limit, event_type="parameter.changed")
        reviewed = audit.fetch_events(limit=limit, event_type=SWEEP_REVIEWED_EVENT)
    except Exception:  # pragma: no cover - defensive
        return []
    events = [e for e in changed if str(e.get("simulationId")) == simulation_id]
    events.extend([e for e in reviewed if str(e.get("simulationId")) == simulation_id])
    # Sort oldest-first for sweep detection and review comparison
    events.sort(key=lambda e: str(e.get("timestamp", "")), reverse=False)
    return events


def build_sweep_review_summary(
    audit: Any,
    simulation_id: str,
    *,
    auth: AuthContext | None = None,
) -> dict[str, Any]:
    """Return a structured summary of parameter sweep review status for a simulation."""
    summary: dict[str, Any] = {
        "summaryVersion": "pbpk-parameter-sweep-review.v1",
        "simulationId": simulation_id,
        "status": "no_changes",
        "plainLanguageSummary": "No parameter changes have been recorded for this simulation.",
        "sweepAlerts": [],
        "reviewedAt": None,
        "reviewedBy": None,
        "requiresReviewerAttention": False,
        "blocksTrustBearingOutput": False,
    }

    events = _fetch_parameter_events(audit, simulation_id)
    if not events:
        return summary

    param_changes = [e for e in events if e.get("eventType") == "parameter.changed"]
    review_events = [e for e in events if e.get("eventType") == SWEEP_REVIEWED_EVENT]

    if not param_changes:
        return summary

    # Detect sweeps across all parameter changes
    sweep_alerts = detect_parameter_sweep(param_changes)

    # Determine if there are unreviewed sweeps
    last_review = review_events[-1] if review_events else None
    last_review_ts = str(last_review.get("timestamp", "")) if last_review else ""

    if last_review_ts:
        changes_after_review = [c for c in param_changes if str(c.get("timestamp", "")) > last_review_ts]
        unreviewed_alerts = detect_parameter_sweep(changes_after_review)
        reviewed_at = last_review.get("timestamp")
        reviewed_by = last_review.get("identity")
    else:
        unreviewed_alerts = sweep_alerts
        reviewed_at = None
        reviewed_by = None

    summary["sweepAlerts"] = sweep_alerts
    summary["reviewedAt"] = reviewed_at
    summary["reviewedBy"] = reviewed_by

    if unreviewed_alerts:
        summary["status"] = "unreviewed_sweeps"
        summary["requiresReviewerAttention"] = True
        summary["blocksTrustBearingOutput"] = True
        alert_types = ", ".join(a["type"] for a in unreviewed_alerts)
        summary["plainLanguageSummary"] = (
            f"Parameter sweep patterns ({alert_types}) have been detected and not yet reviewed. "
            "Human review is recommended before using this simulation for trust-bearing outputs."
        )
    else:
        summary["status"] = "reviewed"
        summary["requiresReviewerAttention"] = False
        summary["blocksTrustBearingOutput"] = False
        summary["plainLanguageSummary"] = (
            "Parameter changes have been reviewed or no sweep patterns were detected."
        )

    return summary


def record_sweep_review(
    audit: Any,
    *,
    auth: AuthContext,
    simulation_id: str,
    disposition: str,
    rationale: str,
    service_version: str = "unknown",
) -> None:
    """Record an operator review of parameter sweep status for a simulation."""
    if audit is None or not getattr(audit, "enabled", False):
        return
    audit.record_event(
        SWEEP_REVIEWED_EVENT,
        {
            "identity": _identity_payload(auth),
            "simulationId": simulation_id,
            "disposition": disposition,
            "rationale": rationale.strip(),
            "serviceVersion": service_version,
        },
    )


def attach_sweep_review(
    payload: dict[str, Any],
    *,
    audit: Any,
    tool_name: str,
    auth: AuthContext | None = None,
) -> None:
    """Attach sweep review summary to trust-bearing tool outputs when relevant."""
    simulation_id = payload.get("simulationId")
    if not simulation_id:
        return

    summary = build_sweep_review_summary(
        audit,
        simulation_id=str(simulation_id),
        auth=auth,
    )
    payload["parameterSweepReview"] = summary

    # If this is a report/export tool, also embed in the report block
    if tool_name in {"export_oecd_report", "run_verification_checks", "validate_simulation_request"}:
        report = payload.get("report")
        if isinstance(report, Mapping):
            report_payload = dict(report)
            report_payload["parameterSweepReview"] = summary
            payload["report"] = report_payload


__all__ = [
    "attach_sweep_review",
    "build_sweep_review_summary",
    "record_sweep_review",
    "SWEEP_REVIEWED_EVENT",
]
