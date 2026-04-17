"""Audit-backed operator review sign-off helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .security.auth import AuthContext

SIGNOFF_RECORDED_EVENT = "review.signoff.recorded"
SIGNOFF_REVOKED_EVENT = "review.signoff.revoked"
TRUST_BEARING_SIGNOFF_SCOPES = frozenset(
    {
        "validate_simulation_request",
        "run_verification_checks",
        "export_oecd_report",
    }
)

_SCOPE_LABELS = {
    "validate_simulation_request": "validation output",
    "run_verification_checks": "verification output",
    "export_oecd_report": "OECD report export",
}

_DISPOSITION_SUMMARIES = {
    "acknowledged": "An operator recorded acknowledgement of bounded review context.",
    "approved-for-bounded-use": "An operator recorded bounded-use sign-off.",
    "rejected": "An operator explicitly recorded that sign-off was not granted.",
}


def signoff_scope_for_tool(tool_name: str) -> str | None:
    if tool_name in TRUST_BEARING_SIGNOFF_SCOPES:
        return tool_name
    return None


def build_operator_review_governance(scope: str) -> dict[str, Any]:
    scope_label = _SCOPE_LABELS.get(scope, scope.replace("_", " "))
    supported = scope in TRUST_BEARING_SIGNOFF_SCOPES
    workflow_status = "descriptive-signoff-only" if supported else "unsupported-scope"
    plain_language_summary = (
        f"This {scope_label} supports additive operator sign-off and revocation for auditability, "
        "but PBPK MCP does not adjudicate scientific truth, override qualification state, or grant "
        "regulatory or organizational decision authority."
        if supported
        else f"Scope '{scope}' is not a published trust-bearing sign-off surface."
    )
    return {
        "governanceVersion": "pbpk-operator-review-governance.v1",
        "scope": scope,
        "scopeLabel": scope_label,
        "workflowStatus": workflow_status,
        "supportsRecordedSignoff": supported,
        "supportsRevocation": supported,
        "supportsOverride": False,
        "supportsAdjudication": False,
        "signoffChangesQualificationState": False,
        "signoffConfersDecisionAuthority": False,
        "externalAuthorityRequiredForOverrides": True,
        "nonGoals": [
            "does not adjudicate scientific truth",
            "does not override qualification state",
            "does not grant regulatory or organizational decision authority",
        ],
        "plainLanguageSummary": plain_language_summary,
    }


def _clean_text_list(values: list[str] | tuple[str, ...] | None) -> list[str]:
    cleaned: list[str] = []
    for item in values or ():
        text = str(item).strip()
        if text:
            cleaned.append(text)
    return cleaned


def _identity_payload(auth: AuthContext | None) -> dict[str, Any] | None:
    if auth is None:
        return None
    return {
        "subject": auth.subject,
        "roles": list(auth.roles),
        "tokenId": auth.token_id,
        "isServiceAccount": auth.is_service_account,
    }


def _base_summary(simulation_id: str, scope: str) -> dict[str, Any]:
    scope_label = _SCOPE_LABELS.get(scope, scope.replace("_", " "))
    return {
        "summaryVersion": "pbpk-operator-review-signoff.v1",
        "simulationId": simulation_id,
        "scope": scope,
        "scopeLabel": scope_label,
        "status": "not-recorded",
        "disposition": None,
        "plainLanguageSummary": (
            f"No operator sign-off has been recorded for this {scope_label}. "
            "Human review remains required, and absence of sign-off must not be mistaken for review completion."
        ),
        "limitationsAccepted": [],
        "reviewFocus": [],
        "rationale": None,
        "recordedAt": None,
        "recordedBy": None,
        "revokedAt": None,
        "revokedBy": None,
        "revocationRationale": None,
        "changesQualificationState": False,
        "confersDecisionAuthority": False,
        "traceability": {
            "sourceEventType": None,
            "sourceEventId": None,
            "sourceEventHash": None,
            "previousHash": None,
        },
    }


def _latest_matching_event(
    events: list[dict[str, Any]],
    *,
    simulation_id: str,
    scope: str,
) -> dict[str, Any] | None:
    relevant: list[dict[str, Any]] = []
    for event in events:
        payload = event.get("reviewSignoff")
        if not isinstance(payload, Mapping):
            continue
        if str(payload.get("simulationId")) != simulation_id:
            continue
        if str(payload.get("scope")) != scope:
            continue
        relevant.append(event)
    if not relevant:
        return None
    return max(relevant, key=lambda item: str(item.get("timestamp") or ""))


def _matching_events(
    events: list[dict[str, Any]],
    *,
    simulation_id: str,
    scope: str,
) -> list[dict[str, Any]]:
    relevant: list[dict[str, Any]] = []
    for event in events:
        payload = event.get("reviewSignoff")
        if not isinstance(payload, Mapping):
            continue
        if str(payload.get("simulationId")) != simulation_id:
            continue
        if str(payload.get("scope")) != scope:
            continue
        relevant.append(event)
    return sorted(relevant, key=lambda item: str(item.get("timestamp") or ""), reverse=True)


def _fetch_matching_review_signoff_events(
    audit: Any,
    *,
    simulation_id: str,
    scope: str,
    limit: int,
    event_types: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    if hasattr(audit, "fetch_review_signoff_events"):
        try:
            return audit.fetch_review_signoff_events(
                limit=limit,
                simulation_id=simulation_id,
                scope=scope,
                event_types=event_types,
            )
        except NotImplementedError:
            pass

    merged: list[dict[str, Any]] = []
    if event_types is None:
        event_types = (SIGNOFF_RECORDED_EVENT, SIGNOFF_REVOKED_EVENT)
    for event_type in event_types:
        merged.extend(
            _matching_events(
                audit.fetch_events(limit=1000, event_type=event_type),
                simulation_id=simulation_id,
                scope=scope,
            )
        )
    merged.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    return merged[:limit]


def _count_matching_review_signoff_events(
    audit: Any,
    *,
    simulation_id: str,
    scope: str,
    event_types: tuple[str, ...] | None = None,
) -> int:
    if hasattr(audit, "count_review_signoff_events"):
        try:
            return int(
                audit.count_review_signoff_events(
                    simulation_id=simulation_id,
                    scope=scope,
                    event_types=event_types,
                )
            )
        except NotImplementedError:
            pass
    return len(
        _fetch_matching_review_signoff_events(
            audit,
            simulation_id=simulation_id,
            scope=scope,
            limit=1000,
            event_types=event_types,
        )
    )


def build_operator_review_signoff_summary(
    audit: Any,
    *,
    simulation_id: str,
    scope: str,
) -> dict[str, Any]:
    summary = _base_summary(simulation_id, scope)
    if scope not in TRUST_BEARING_SIGNOFF_SCOPES:
        summary["status"] = "unavailable"
        summary["plainLanguageSummary"] = (
            f"Scope '{scope}' is not a published trust-bearing sign-off surface."
        )
        return summary

    if audit is None or not getattr(audit, "enabled", False):
        summary["status"] = "unavailable"
        summary["plainLanguageSummary"] = (
            "Operator sign-off is unavailable because audit recording is disabled for this deployment."
        )
        return summary

    if hasattr(audit, "has_review_signoff_index"):
        try:
            if not audit.has_review_signoff_index(simulation_id=simulation_id, scope=scope):
                return summary
        except NotImplementedError:
            pass

    try:
        events = _fetch_matching_review_signoff_events(
            audit,
            simulation_id=simulation_id,
            scope=scope,
            limit=8,
            event_types=(SIGNOFF_RECORDED_EVENT, SIGNOFF_REVOKED_EVENT),
        )
    except NotImplementedError:
        summary["status"] = "unavailable"
        summary["plainLanguageSummary"] = (
            "Operator sign-off is unavailable because this audit backend does not support readable event history."
        )
        return summary

    latest_recorded = _latest_matching_event(
        [event for event in events if event.get("eventType") == SIGNOFF_RECORDED_EVENT],
        simulation_id=simulation_id,
        scope=scope,
    )
    latest_revoked = _latest_matching_event(
        [event for event in events if event.get("eventType") == SIGNOFF_REVOKED_EVENT],
        simulation_id=simulation_id,
        scope=scope,
    )
    latest_event = max(
        [event for event in (latest_recorded, latest_revoked) if event is not None],
        key=lambda item: str(item.get("timestamp") or ""),
        default=None,
    )
    if latest_event is None:
        return summary

    summary["traceability"] = {
        "sourceEventType": latest_event.get("eventType"),
        "sourceEventId": latest_event.get("eventId"),
        "sourceEventHash": latest_event.get("hash"),
        "previousHash": latest_event.get("previousHash"),
    }
    payload = latest_event.get("reviewSignoff")
    if not isinstance(payload, Mapping):
        return summary

    if latest_event.get("eventType") == SIGNOFF_REVOKED_EVENT:
        identity = latest_event.get("identity") if isinstance(latest_event.get("identity"), Mapping) else None
        summary["status"] = "revoked"
        summary["revokedAt"] = latest_event.get("timestamp")
        summary["revokedBy"] = dict(identity) if identity else None
        summary["revocationRationale"] = payload.get("rationale")
        summary["plainLanguageSummary"] = (
            f"A previously recorded operator sign-off for this {summary['scopeLabel']} was revoked. "
            "Treat the output as unsigned and continue to rely on the existing qualification, caution, and human-review boundaries."
        )
        return summary

    identity = latest_event.get("identity") if isinstance(latest_event.get("identity"), Mapping) else None
    disposition = str(payload.get("disposition") or "").strip() or None
    summary["status"] = "recorded"
    summary["disposition"] = disposition
    summary["rationale"] = payload.get("rationale")
    summary["recordedAt"] = latest_event.get("timestamp")
    summary["recordedBy"] = dict(identity) if identity else None
    summary["limitationsAccepted"] = _clean_text_list(payload.get("limitationsAccepted"))  # type: ignore[arg-type]
    summary["reviewFocus"] = _clean_text_list(payload.get("reviewFocus"))  # type: ignore[arg-type]
    subject = (
        str(summary["recordedBy"].get("subject"))
        if isinstance(summary["recordedBy"], Mapping) and summary["recordedBy"].get("subject")
        else "an operator"
    )
    disposition_summary = _DISPOSITION_SUMMARIES.get(
        disposition or "",
        "An operator recorded an explicit review disposition.",
    )
    summary["plainLanguageSummary"] = (
        f"{disposition_summary} It was recorded by {subject} for this {summary['scopeLabel']}. "
        "This trace is descriptive only: it does not change qualification state or confer decision authority."
    )
    return summary


def build_operator_review_signoff_history(
    audit: Any,
    *,
    simulation_id: str,
    scope: str,
    limit: int = 20,
) -> dict[str, Any]:
    scope_label = _SCOPE_LABELS.get(scope, scope.replace("_", " "))
    response = {
        "historyVersion": "pbpk-operator-review-signoff-history.v1",
        "simulationId": simulation_id,
        "scope": scope,
        "scopeLabel": scope_label,
        "status": "available",
        "readableAuditHistory": True,
        "plainLanguageSummary": (
            f"No operator sign-off audit events are recorded yet for this {scope_label}."
        ),
        "latestStatus": "not-recorded",
        "latestDisposition": None,
        "returnedEntryCount": 0,
        "totalEntryCount": 0,
        "truncated": False,
        "entries": [],
    }
    if scope not in TRUST_BEARING_SIGNOFF_SCOPES:
        response["status"] = "unavailable"
        response["readableAuditHistory"] = False
        response["plainLanguageSummary"] = (
            f"Scope '{scope}' is not a published trust-bearing sign-off surface."
        )
        return response

    if audit is None or not getattr(audit, "enabled", False):
        response["status"] = "unavailable"
        response["readableAuditHistory"] = False
        response["plainLanguageSummary"] = (
            "Operator sign-off history is unavailable because audit recording is disabled for this deployment."
        )
        return response

    if hasattr(audit, "has_review_signoff_index"):
        try:
            if not audit.has_review_signoff_index(simulation_id=simulation_id, scope=scope):
                return response
        except NotImplementedError:
            pass

    try:
        capped_limit = max(1, min(int(limit), 100))
        merged = _fetch_matching_review_signoff_events(
            audit,
            simulation_id=simulation_id,
            scope=scope,
            limit=capped_limit,
            event_types=(SIGNOFF_RECORDED_EVENT, SIGNOFF_REVOKED_EVENT),
        )
        total_count = _count_matching_review_signoff_events(
            audit,
            simulation_id=simulation_id,
            scope=scope,
            event_types=(SIGNOFF_RECORDED_EVENT, SIGNOFF_REVOKED_EVENT),
        )
    except NotImplementedError:
        response["status"] = "unavailable"
        response["readableAuditHistory"] = False
        response["plainLanguageSummary"] = (
            "Operator sign-off history is unavailable because this audit backend does not support readable event history."
        )
        return response

    entries: list[dict[str, Any]] = []
    for event in merged[:capped_limit]:
        payload = event.get("reviewSignoff")
        payload_map = payload if isinstance(payload, Mapping) else {}
        identity = event.get("identity")
        action = "revoked" if event.get("eventType") == SIGNOFF_REVOKED_EVENT else "recorded"
        actor = dict(identity) if isinstance(identity, Mapping) else None
        entries.append(
            {
                "eventType": event.get("eventType"),
                "action": action,
                "timestamp": event.get("timestamp"),
                "disposition": payload_map.get("disposition"),
                "rationale": payload_map.get("rationale"),
                "limitationsAccepted": _clean_text_list(payload_map.get("limitationsAccepted")),  # type: ignore[arg-type]
                "reviewFocus": _clean_text_list(payload_map.get("reviewFocus")),  # type: ignore[arg-type]
                "actor": actor,
                "serviceVersion": payload_map.get("serviceVersion"),
                "traceability": {
                    "sourceEventId": event.get("eventId"),
                    "sourceEventHash": event.get("hash"),
                    "previousHash": event.get("previousHash"),
                },
            }
        )

    response["entries"] = entries
    response["returnedEntryCount"] = len(entries)
    response["totalEntryCount"] = total_count
    response["truncated"] = total_count > len(entries)
    if entries:
        response["latestStatus"] = entries[0]["action"]
        response["latestDisposition"] = entries[0]["disposition"]
        response["plainLanguageSummary"] = (
            f"Showing {len(entries)} sign-off audit event(s) for this {scope_label}. "
            "This history is descriptive only and does not confer decision authority."
        )
    return response


def record_operator_review_signoff(
    audit: Any,
    *,
    auth: AuthContext,
    simulation_id: str,
    scope: str,
    disposition: str,
    rationale: str,
    limitations_accepted: list[str] | tuple[str, ...] | None = None,
    review_focus: list[str] | tuple[str, ...] | None = None,
    service_version: str = "unknown",
) -> None:
    audit.record_event(
        SIGNOFF_RECORDED_EVENT,
        {
            "identity": _identity_payload(auth),
            "reviewSignoff": {
                "simulationId": simulation_id,
                "scope": scope,
                "disposition": disposition,
                "rationale": rationale.strip(),
                "limitationsAccepted": _clean_text_list(list(limitations_accepted or ())),
                "reviewFocus": _clean_text_list(list(review_focus or ())),
                "serviceVersion": service_version,
            },
        },
    )


def revoke_operator_review_signoff(
    audit: Any,
    *,
    auth: AuthContext,
    simulation_id: str,
    scope: str,
    rationale: str,
    service_version: str = "unknown",
) -> None:
    audit.record_event(
        SIGNOFF_REVOKED_EVENT,
        {
            "identity": _identity_payload(auth),
            "reviewSignoff": {
                "simulationId": simulation_id,
                "scope": scope,
                "rationale": rationale.strip(),
                "serviceVersion": service_version,
            },
        },
    )


def attach_operator_review_signoff(
    payload: dict[str, Any],
    *,
    audit: Any,
    tool_name: str,
) -> None:
    scope = signoff_scope_for_tool(tool_name)
    if scope is None:
        return
    simulation_id = payload.get("simulationId")
    if not simulation_id:
        return
    governance = build_operator_review_governance(scope)
    summary = build_operator_review_signoff_summary(
        audit,
        simulation_id=str(simulation_id),
        scope=scope,
    )
    payload["operatorReviewSignoff"] = dict(summary)
    payload["operatorReviewGovernance"] = dict(governance)
    report = payload.get("report")
    if not isinstance(report, Mapping):
        return
    report_payload = dict(report)
    report_payload["operatorReviewSignoff"] = dict(summary)
    report_payload["operatorReviewGovernance"] = dict(governance)
    human_review = report_payload.get("humanReviewSummary")
    if isinstance(human_review, Mapping):
        human_review_payload = dict(human_review)
        human_review_payload["operatorReviewSignoff"] = dict(summary)
        human_review_payload["operatorReviewGovernance"] = dict(governance)
        report_payload["humanReviewSummary"] = human_review_payload
    payload["report"] = report_payload


__all__ = [
    "SIGNOFF_RECORDED_EVENT",
    "SIGNOFF_REVOKED_EVENT",
    "TRUST_BEARING_SIGNOFF_SCOPES",
    "attach_operator_review_signoff",
    "build_operator_review_governance",
    "build_operator_review_signoff_history",
    "build_operator_review_signoff_summary",
    "record_operator_review_signoff",
    "revoke_operator_review_signoff",
    "signoff_scope_for_tool",
]
