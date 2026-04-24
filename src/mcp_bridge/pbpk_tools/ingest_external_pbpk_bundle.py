"""MCP tool for normalizing external PBPK outputs into PBPK-side NGRA objects."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

TOOL_NAME = "ingest_external_pbpk_bundle"
CONTRACT_VERSION = "pbpk-mcp.v1"
EXTERNAL_BACKEND = "external-import"

KNOWN_QUALIFICATION_STATES = {
    "exploratory",
    "illustrative-example",
    "research-use",
    "regulatory-candidate",
    "qualified-within-context",
}
LINEAGE_FAIL_CLOSED_ORIGINS = {"derived_proxy"}
LINEAGE_PRIMARY_VERIFICATION_ORIGINS = {"secondary_citation"}


def _safe_text(value: object | None) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


def _safe_float(value: object | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_bool(value: object | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    token = _normalize_token(value)
    if token in {"true", "yes", "1"}:
        return True
    if token in {"false", "no", "0"}:
        return False
    return default


def _safe_optional_bool(value: object | None) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    token = _normalize_token(value)
    if token in {"true", "yes", "1"}:
        return True
    if token in {"false", "no", "0"}:
        return False
    return None


def _safe_int(value: object | None, default: int = 0) -> int:
    numeric = _safe_float(value)
    if numeric is None:
        return default
    return int(numeric)


def _normalize_token(value: object | None) -> str | None:
    candidate = _safe_text(value)
    if candidate is None:
        return None
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in candidate)
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return normalized.strip("-") or None


def _normalize_origin_classification(value: object | None) -> str | None:
    token = _normalize_token(value)
    if token is None:
        return None
    mapping = {
        "primary-observation": "primary_observation",
        "secondary-citation": "secondary_citation",
        "derived-proxy": "derived_proxy",
        "model-output": "model_output",
        "curated-summary": "curated_summary",
    }
    return mapping.get(token, token.replace("-", "_"))


def _as_mapping(value: object | None) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _normalize_text_list(value: object | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        items = [_safe_text(item) for item in value]
    else:
        items = [_safe_text(value)]
    return [item for item in items if item]


def _extract_quantitative_lineage(section: Mapping[str, Any]) -> dict[str, Any]:
    source_chain = _normalize_text_list(
        section.get("sourceChain")
        or section.get("citationChain")
        or section.get("source_chain")
        or section.get("citation_chain")
    )
    return {
        "originClassification": _normalize_origin_classification(
            section.get("originClassification")
            or section.get("quantitativeClaimOrigin")
            or section.get("quantitativeClaimOriginClassification")
            or section.get("origin_classification")
        ),
        "primarySourceVerified": _safe_optional_bool(
            section.get("primarySourceVerified")
            or section.get("primary_source_verified")
        ),
        "sourceChain": source_chain,
        "underlyingPrimarySourceRef": _safe_text(
            section.get("underlyingPrimarySourceRef")
            or section.get("underlying_primary_source_ref")
            or section.get("primaryStudyRef")
            or section.get("primarySourceRef")
        ),
        "bridgingMethod": _safe_text(
            section.get("bridgingMethod")
            or section.get("bridging_method")
            or section.get("derivationMethod")
        ),
    }


def _lineage_warnings(lineage: Mapping[str, Any], role_label: str) -> list[str]:
    warnings: list[str] = []
    origin = _safe_text(lineage.get("originClassification"))
    primary_verified = _safe_optional_bool(lineage.get("primarySourceVerified"))

    if origin == "derived_proxy":
        warnings.append(
            f"{role_label} is declared as a derived proxy; treat it as review-only until replaced "
            "with a direct observation or qualified model output."
        )
    elif origin == "secondary_citation":
        warnings.append(
            f"{role_label} is declared as a secondary-citation numeric anchor; retain the citation "
            "chain and primary-study verification state in downstream review."
        )

    if origin in LINEAGE_PRIMARY_VERIFICATION_ORIGINS and primary_verified is not True:
        warnings.append(
            f"{role_label} lacks verified review of the underlying primary study for the declared "
            "secondary-citation numeric anchor."
        )

    return warnings


def _lineage_blocking_reasons(lineage: Mapping[str, Any], role_label: str) -> list[str]:
    blocking_reasons: list[str] = []
    origin = _safe_text(lineage.get("originClassification"))
    primary_verified = _safe_optional_bool(lineage.get("primarySourceVerified"))

    if origin in LINEAGE_FAIL_CLOSED_ORIGINS:
        blocking_reasons.append(
            f"{role_label} is marked as a derived proxy and is not admissible as a governed BER input."
        )
    elif origin in LINEAGE_PRIMARY_VERIFICATION_ORIGINS and primary_verified is not True:
        blocking_reasons.append(
            f"{role_label} is sourced through a secondary citation without verified review of the underlying primary study."
        )

    return blocking_reasons


def _build_lineage_flags(
    *,
    internal_lineage: Mapping[str, Any],
    pod_lineage: Mapping[str, Any],
) -> dict[str, Any]:
    internal_blocking = _lineage_blocking_reasons(
        internal_lineage,
        "Internal exposure denominator",
    )
    pod_blocking = _lineage_blocking_reasons(
        pod_lineage,
        "Point-of-departure anchor",
    )
    return {
        "internalExposureOriginClassification": _safe_text(
            internal_lineage.get("originClassification")
        ),
        "internalExposurePrimarySourceVerified": _safe_optional_bool(
            internal_lineage.get("primarySourceVerified")
        ),
        "internalExposureSourceChainLength": len(
            _normalize_text_list(internal_lineage.get("sourceChain"))
        ),
        "internalExposureBridgingMethod": _safe_text(
            internal_lineage.get("bridgingMethod")
        ),
        "internalExposureReviewOnly": bool(internal_blocking),
        "podOriginClassification": _safe_text(pod_lineage.get("originClassification")),
        "podPrimarySourceVerified": _safe_optional_bool(
            pod_lineage.get("primarySourceVerified")
        ),
        "podSourceChainLength": len(_normalize_text_list(pod_lineage.get("sourceChain"))),
        "podReviewOnly": bool(pod_blocking),
    }


def _normalized_text_list_or_default(value: object | None, default: list[str]) -> list[str]:
    items = _normalize_text_list(value)
    return items or list(default)


def _coerce_section(value: object | None, *, scalar_key: str | None = None) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    scalar = _safe_text(value)
    if scalar is None or scalar_key is None:
        return {}
    return {scalar_key: scalar}


def _extract_uncertainty_rows(uncertainty: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("rows", "evidence", "evidenceRows", "evidenceTable"):
        value = uncertainty.get(key)
        if isinstance(value, (list, tuple)):
            return [_as_mapping(entry) for entry in value if isinstance(entry, Mapping)]
    return []


def _uncertainty_rows_for_kind(rows: list[Mapping[str, Any]], kind: str) -> list[Mapping[str, Any]]:
    return [entry for entry in rows if _safe_text(entry.get("kind")) == kind]


def _uncertainty_row_has_quantitative_signal(row: Mapping[str, Any]) -> bool:
    for field in ("value", "lowerBound", "upperBound", "mean", "sd"):
        if _safe_float(row.get(field)) is not None:
            return True
    return False


def _build_uncertainty_semantic_coverage(
    *,
    status: str,
    has_variability_approach: bool,
    has_variability_propagation: bool,
    has_sensitivity: bool,
    has_residual_uncertainty: bool,
    variability_row_count: int,
    sensitivity_row_count: int,
    residual_row_count: int,
    quantified_variability: bool,
    quantified_row_count: int,
    declared_only_row_count: int,
    quantified_sensitivity: bool,
    quantified_residual: bool,
) -> dict[str, Any]:
    variability_type = (
        "aleatoric-or-population-variability"
        if has_variability_approach or has_variability_propagation
        else "unreported"
    )
    sensitivity_type = "parameter-influence-analysis" if has_sensitivity else "unreported"
    residual_type = (
        "epistemic-or-unresolved-uncertainty"
        if has_residual_uncertainty
        else "unreported"
    )

    if quantified_variability:
        variability_quantification_status = "quantified"
    elif has_variability_approach or has_variability_propagation:
        variability_quantification_status = "declared-or-characterized"
    elif status != "unreported":
        variability_quantification_status = "not-reported"
    else:
        variability_quantification_status = "unreported"

    if quantified_sensitivity:
        sensitivity_quantification_status = "quantified"
    elif has_sensitivity:
        sensitivity_quantification_status = "structured-analysis-without-quantitative-output"
    elif status != "unreported":
        sensitivity_quantification_status = "not-bundled"
    else:
        sensitivity_quantification_status = "unreported"

    if quantified_residual:
        residual_quantification_status = "quantified"
    elif has_residual_uncertainty:
        residual_quantification_status = "declared-only"
    elif status != "unreported":
        residual_quantification_status = "not-explicit"
    else:
        residual_quantification_status = "unreported"

    quantified_components: list[str] = []
    if quantified_variability:
        quantified_components.append("variability")
    if quantified_sensitivity:
        quantified_components.append("sensitivity-analysis")
    if quantified_residual:
        quantified_components.append("residual-uncertainty")

    declared_only_components: list[str] = []
    if (has_variability_approach or has_variability_propagation) and not quantified_variability:
        declared_only_components.append("variability")
    if has_sensitivity and not quantified_sensitivity:
        declared_only_components.append("sensitivity-analysis")
    if has_residual_uncertainty and not quantified_residual:
        declared_only_components.append("residual-uncertainty")

    missing_components: list[str] = []
    if not (has_variability_approach or has_variability_propagation):
        missing_components.append("variability")
    if not has_sensitivity:
        missing_components.append("sensitivity-analysis")
    if not has_residual_uncertainty:
        missing_components.append("residual-uncertainty")

    if quantified_components and not declared_only_components and not missing_components:
        overall_quantification_status = "quantified"
    elif quantified_components:
        overall_quantification_status = "partially-quantified"
    elif declared_only_components:
        overall_quantification_status = "declared-without-complete-quantification"
    elif status != "unreported":
        overall_quantification_status = "declared-without-structured-quantification"
    else:
        overall_quantification_status = "unreported"

    return {
        "variabilityType": variability_type,
        "variabilityEvidenceRowCount": variability_row_count,
        "variabilityQuantificationStatus": variability_quantification_status,
        "sensitivityType": sensitivity_type,
        "sensitivityEvidenceRowCount": sensitivity_row_count,
        "sensitivityQuantificationStatus": sensitivity_quantification_status,
        "residualUncertaintyType": residual_type,
        "residualUncertaintyEvidenceRowCount": residual_row_count,
        "residualUncertaintyQuantificationStatus": residual_quantification_status,
        "overallQuantificationStatus": overall_quantification_status,
        "quantifiedRowCount": quantified_row_count,
        "declaredOnlyRowCount": declared_only_row_count,
        "quantifiedComponents": list(dict.fromkeys(quantified_components)),
        "declaredOnlyComponents": list(dict.fromkeys(declared_only_components)),
        "missingComponents": list(dict.fromkeys(missing_components)),
    }


def _selection_triplet(requested: object | None, declared: object | None) -> dict[str, Any]:
    requested_text = _safe_text(requested)
    declared_text = _safe_text(declared)
    return {
        "requested": requested_text,
        "declared": declared_text,
        "effective": requested_text or declared_text,
    }


def _review_record_entries(review: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("reviewRecords", "reviews", "peerReviewRecords", "reviewHistory"):
        value = review.get(key)
        if isinstance(value, Mapping):
            return [dict(value)]
        if isinstance(value, (list, tuple)):
            return [_as_mapping(entry) for entry in value if isinstance(entry, Mapping)]
    return []


def _review_record_topic(entry: Mapping[str, Any]) -> str | None:
    for key in ("topic", "focus", "issue", "summary"):
        candidate = _safe_text(entry.get(key))
        if candidate:
            return candidate
    return None


def _review_record_has_explicit_dissent(entry: Mapping[str, Any]) -> bool:
    if _safe_bool(entry.get("dissent") or entry.get("hasDissent"), False):
        return True

    stance_tokens = {
        _normalize_token(entry.get(key))
        for key in (
            "stance",
            "reviewStance",
            "reviewOutcome",
            "outcome",
            "decision",
            "recommendation",
            "finding",
            "findingStatus",
        )
    }
    stance_tokens.discard(None)
    return bool(
        stance_tokens
        & {
            "dissent",
            "major-concern",
            "major-concerns",
            "blocking-concern",
            "blocking-concerns",
            "blocking-issue",
            "critical-issue",
            "request-changes",
            "changes-requested",
            "rejected",
            "reject",
            "not-approved",
            "not-accepted",
            "disputed",
            "contested",
        }
    )


def _review_record_resolution_state(entry: Mapping[str, Any]) -> str:
    if not _review_record_has_explicit_dissent(entry):
        return "not-dissent"
    if _safe_bool(entry.get("resolved"), False):
        return "resolved"
    if _safe_bool(entry.get("unresolved"), False):
        return "unresolved"

    resolution_tokens = {
        _normalize_token(entry.get(key))
        for key in ("resolutionState", "resolutionStatus", "issueStatus", "followUpStatus", "status")
    }
    resolution_tokens.discard(None)
    if resolution_tokens & {"resolved", "closed", "addressed", "accepted", "completed", "implemented"}:
        return "resolved"
    if resolution_tokens & {
        "unresolved",
        "open",
        "pending",
        "needs-follow-up",
        "follow-up-required",
        "outstanding",
        "not-addressed",
    }:
        return "unresolved"
    return "unresolved"


def _derive_review_status(review: Mapping[str, Any]) -> dict[str, Any]:
    review_record_count = 0
    review_records = _review_record_entries(review)
    if review_records:
        review_record_count = len(review_records)
    elif _normalize_text_list(
        [
            review.get("reviewType"),
            review.get("reviewOutcome"),
            review.get("reviewDate"),
            review.get("reviewer"),
            review.get("reviewBody"),
        ]
    ):
        review_record_count = 1

    prior_use_value = (
        review.get("priorRegulatoryUse")
        or review.get("priorUse")
        or review.get("priorApplications")
        or review.get("priorUseHistory")
    )
    prior_use_count = len(_normalize_text_list(prior_use_value)) if not isinstance(prior_use_value, bool) else int(prior_use_value)
    if isinstance(prior_use_value, (list, tuple)):
        prior_use_count = sum(
            1 for entry in prior_use_value if _normalize_text_list(entry if isinstance(entry, (list, tuple, set)) else [entry])
        )
    elif isinstance(prior_use_value, Mapping):
        prior_use_count = 1 if any(_normalize_text_list(prior_use_value.values())) else 0

    revision_history_value = (
        review.get("revisionHistory")
        or review.get("changeHistory")
        or review.get("versionHistory")
        or review.get("revisions")
    )
    revision_entry_count = len(_normalize_text_list(revision_history_value)) if not isinstance(revision_history_value, bool) else int(revision_history_value)
    if isinstance(revision_history_value, (list, tuple)):
        revision_entry_count = sum(
            1 for entry in revision_history_value if _normalize_text_list(entry if isinstance(entry, (list, tuple, set)) else [entry])
        )
    elif isinstance(revision_history_value, Mapping):
        revision_entry_count = 1 if any(_normalize_text_list(revision_history_value.values())) else 0

    has_revision_status = bool(
        _normalize_text_list(
            review.get("revisionStatus") or review.get("changeStatus") or review.get("versionStatus")
        )
    )

    unresolved_dissent_count = 0
    resolved_dissent_count = 0
    unresolved_topics: list[str] = []
    resolved_topics: list[str] = []
    for entry in review_records:
        resolution_state = _review_record_resolution_state(entry)
        if resolution_state == "not-dissent":
            continue
        if resolution_state == "resolved":
            resolved_dissent_count += 1
            topic = _review_record_topic(entry)
            if topic:
                resolved_topics.append(topic)
        else:
            unresolved_dissent_count += 1
            topic = _review_record_topic(entry)
            if topic:
                unresolved_topics.append(topic)

    unresolved_dissent_count = max(
        unresolved_dissent_count,
        _safe_int(review.get("unresolvedDissentCount"), 0),
    )
    resolved_dissent_count = max(
        resolved_dissent_count,
        _safe_int(review.get("resolvedDissentCount"), 0),
    )

    limited_traceability = (
        review_record_count == 0
        or prior_use_count == 0
        or (revision_entry_count == 0 and not has_revision_status)
    )
    declared_status = _normalize_token(review.get("status"))
    focus_topics = list(
        dict.fromkeys(
            _normalize_text_list(review.get("focusTopics"))
            + _normalize_text_list(review.get("reviewFocus"))
            + unresolved_topics
        )
    )
    open_topics = list(dict.fromkeys(unresolved_topics))
    closed_topics = list(dict.fromkeys(resolved_topics))

    if declared_status in {
        "not-applicable-to-fixture",
        "fixture-only",
        "integration-fixture",
        "example-only",
    }:
        status = "not-applicable-to-fixture"
        summary = "Peer-review workflow is not expected for this fixture or illustrative integration asset."
        requires_attention = False
    elif declared_status in {None, "unreported", "undeclared", "not-reported", "unknown", "unspecified", "not-assessed"}:
        status = "not-declared"
        summary = "No peer-review, reviewer stance, or prior-use workflow metadata are declared."
        requires_attention = True
    elif unresolved_dissent_count > 0:
        status = "declared-with-unresolved-dissent"
        summary = (
            "Explicit reviewer dissent or change requests remain unresolved and require "
            "human follow-up before stronger qualification-facing claims."
        )
        requires_attention = True
    elif limited_traceability:
        status = "traceability-limited"
        summary = (
            "Peer-review metadata are declared, but review records, prior-use traceability, "
            "or revision history remain incomplete."
        )
        requires_attention = True
    elif resolved_dissent_count > 0:
        status = "declared-with-resolved-dissent"
        summary = (
            "Explicit reviewer dissent is recorded as resolved, but the recorded disposition "
            "should still be checked in context."
        )
        requires_attention = False
    else:
        status = "declared-no-explicit-dissent"
        summary = "Peer-review metadata are traceable and no explicit unresolved dissent is declared."
        requires_attention = False

    if unresolved_dissent_count > 0:
        intervention_summary: dict[str, Any] = {
            "status": "open-review-interventions",
            "summary": (
                "Explicit reviewer interventions remain open and should travel with the summary "
                "so unresolved concerns are not flattened into a single label."
            ),
            "openTopicCount": len(open_topics),
            "resolvedTopicCount": len(closed_topics),
            "openTopics": open_topics,
            "resolvedTopics": closed_topics,
        }
    elif resolved_dissent_count > 0:
        intervention_summary = {
            "status": "resolved-review-interventions",
            "summary": (
                "Resolved reviewer interventions are recorded and should remain visible as context "
                "for how the current summary was narrowed or clarified."
            ),
            "openTopicCount": len(open_topics),
            "resolvedTopicCount": len(closed_topics),
            "openTopics": open_topics,
            "resolvedTopics": closed_topics,
        }
    elif review_record_count > 0:
        intervention_summary = {
            "status": "no-explicit-interventions-recorded",
            "summary": "Review metadata are declared, but no explicit dissent-linked intervention topics are recorded.",
            "openTopicCount": 0,
            "resolvedTopicCount": 0,
            "openTopics": [],
            "resolvedTopics": [],
        }
    else:
        intervention_summary = {
            "status": "no-review-interventions-recorded",
            "summary": "No explicit review interventions are recorded in the current metadata.",
            "openTopicCount": 0,
            "resolvedTopicCount": 0,
            "openTopics": [],
            "resolvedTopics": [],
        }

    return {
        "status": status,
        "declaredStatus": _safe_text(review.get("status")) or "unreported",
        "summary": summary,
        "reviewRecordCount": int(review_record_count),
        "priorUseCount": int(prior_use_count),
        "revisionEntryCount": int(revision_entry_count),
        "unresolvedDissentCount": int(unresolved_dissent_count),
        "resolvedDissentCount": int(resolved_dissent_count),
        "revisionStatus": _safe_text(
            review.get("revisionStatus") or review.get("changeStatus") or review.get("versionStatus")
        ),
        "focusTopics": focus_topics,
        "openTopics": open_topics,
        "resolvedTopics": closed_topics,
        "interventionSummary": intervention_summary,
        "requiresReviewerAttention": requires_attention,
    }


def _build_workflow_role(assessment: Mapping[str, Any]) -> dict[str, Any]:
    workflow = _as_mapping(
        assessment.get("workflowRole")
        or assessment.get("ngraWorkflowRole")
        or assessment.get("exposureLedWorkflow")
    )
    return {
        "role": _safe_text(workflow.get("role") or workflow.get("primaryRole"))
        or "pbpk-exposure-translation-and-internal-dose-support",
        "workflow": _safe_text(workflow.get("workflow") or workflow.get("workflowType"))
        or "exposure-led-ngra",
        "upstreamDependencies": _normalized_text_list_or_default(
            workflow.get("upstreamDependencies") or workflow.get("upstreamInputs"),
            [
                "dose scenario or exposure estimate defined outside PBPK MCP",
                "in vitro ADME or IVIVE parameterization evidence defined outside PBPK MCP",
                "bioactivity, point-of-departure, or NAM interpretation defined outside PBPK MCP",
            ],
        ),
        "downstreamOutputs": _normalized_text_list_or_default(
            workflow.get("downstreamOutputs"),
            [
                "internal exposure estimates",
                "PBPK qualification and uncertainty handoff objects",
                "BER-ready input bundle when compatible external PoD metadata are attached",
            ],
        ),
        "nonGoals": _normalized_text_list_or_default(
            workflow.get("nonGoals"),
            [
                "standalone weight-of-evidence integration",
                "standalone exposure assessment ownership",
                "direct regulatory decision authority",
                "standalone hazard or AOP interpretation",
            ],
        ),
    }


def _variability_representation_from_uncertainty(uncertainty: Mapping[str, Any]) -> str:
    rows = _extract_uncertainty_rows(uncertainty)
    variability_approach_rows = _uncertainty_rows_for_kind(rows, "variability-approach")
    variability_propagation_rows = _uncertainty_rows_for_kind(rows, "variability-propagation")
    quantified_variability = any(
        _uncertainty_row_has_quantitative_signal(entry)
        for entry in variability_propagation_rows
    )
    status = _safe_text(uncertainty.get("status")) or "unreported"

    if quantified_variability:
        return "quantified-propagation"
    if (
        variability_approach_rows
        or variability_propagation_rows
        or uncertainty.get("variabilityApproach")
        or uncertainty.get("hasVariabilityApproach")
        or uncertainty.get("variabilityPropagation")
        or uncertainty.get("hasVariabilityPropagation")
    ):
        return "declared-or-characterized"
    if status != "unreported":
        return "declared-without-structured-variability"
    return "not-declared"


def _build_population_support(
    assessment: Mapping[str, Any],
    internal: Mapping[str, Any],
    uncertainty: Mapping[str, Any],
) -> dict[str, Any]:
    domain = _as_mapping(assessment.get("domain") or assessment.get("applicabilityDomain"))
    support = _as_mapping(
        assessment.get("populationSupport")
        or assessment.get("variabilitySupport")
    )
    return {
        "supportedSpecies": _normalize_text_list(
            support.get("supportedSpecies")
            or domain.get("species")
            or internal.get("species")
        ),
        "supportedPhysiologyContexts": _normalize_text_list(
            support.get("supportedPhysiologyContexts")
            or support.get("physiologyContexts")
            or domain.get("sex")
            or domain.get("physiologyContexts")
            or internal.get("sex")
        ),
        "supportedLifeStages": _normalize_text_list(
            support.get("supportedLifeStages")
            or domain.get("lifeStage")
            or internal.get("lifeStage")
        ),
        "supportedGenotypesOrPhenotypes": _normalize_text_list(
            support.get("supportedGenotypesOrPhenotypes")
            or support.get("supportedGenotypeOrPhenotype")
            or domain.get("genotype")
            or domain.get("phenotype")
            or internal.get("genotype")
        ),
        "variabilityRepresentation": _safe_text(
            support.get("variabilityRepresentation")
        )
        or _variability_representation_from_uncertainty(uncertainty),
        "extrapolationPolicy": _safe_text(support.get("extrapolationPolicy"))
        or "outside-declared-population-context-requires-human-review",
    }


def _build_evidence_basis(
    qualification: Mapping[str, Any],
    *,
    population_support: Mapping[str, Any],
) -> dict[str, Any]:
    evidence_basis = _as_mapping(qualification.get("evidenceBasis"))
    return {
        "basisType": _safe_text(evidence_basis.get("basisType") or evidence_basis.get("type"))
        or "external-imported",
        "inVivoSupportStatus": _safe_text(
            evidence_basis.get("inVivoSupportStatus")
            or evidence_basis.get("directInVivoSupport")
        )
        or "not-declared",
        "iviveLinkageStatus": _safe_text(evidence_basis.get("iviveLinkageStatus"))
        or "external-or-not-declared",
        "parameterizationBasis": _safe_text(evidence_basis.get("parameterizationBasis"))
        or "inspect-parameter-provenance",
        "populationVariabilityStatus": _safe_text(
            evidence_basis.get("populationVariabilityStatus")
        )
        or _safe_text(population_support.get("variabilityRepresentation"))
        or "not-declared",
    }


def _build_workflow_claim_boundaries(qualification: Mapping[str, Any]) -> dict[str, Any]:
    claim_boundaries = _as_mapping(
        qualification.get("workflowClaimBoundaries")
        or qualification.get("claimBoundaries")
    )
    return {
        "forwardDosimetry": _safe_text(claim_boundaries.get("forwardDosimetry"))
        or "external-imported-not-executed-by-pbpk-mcp",
        "reverseDosimetry": _safe_text(claim_boundaries.get("reverseDosimetry"))
        or "not-performed-directly-external-workflow-required",
        "exposureLedPrioritization": _safe_text(
            claim_boundaries.get("exposureLedPrioritization")
        )
        or "supported-only-as-pbpk-substrate-with-external-orchestrator",
        "directRegulatoryDoseDerivation": _safe_text(
            claim_boundaries.get("directRegulatoryDoseDerivation")
        )
        or "not-supported",
    }


def _build_export_block_policy(
    *,
    assessment_context: Mapping[str, Any],
    qualification_summary: Mapping[str, Any],
) -> dict[str, Any]:
    claim_boundaries = _as_mapping(qualification_summary.get("workflowClaimBoundaries"))
    review_status = _as_mapping(qualification_summary.get("reviewStatus"))
    blocked_view_modes = [
        "report-card",
        "screenshot",
        "chat-snippet",
        "forwarded-bundle",
        "thin-api-response",
    ]
    required_fields = [
        "qualificationState",
        "reviewStatus",
        "evidenceBasis",
        "claimBoundaries",
        "misreadRiskSummary.plainLanguageSummary",
        "summaryTransportRisk.plainLanguageSummary",
    ]
    block_reasons: list[dict[str, Any]] = [
        {
            "code": "detached-summary-blocked",
            "severity": "high",
            "appliesTo": blocked_view_modes,
            "message": (
                "Block lossy report cards, screenshots, chat snippets, or forwarded bundles when "
                "qualification state, review status, evidence basis, claim boundaries, and anti-misread "
                "guidance cannot travel with them."
            ),
            "requiredFields": required_fields,
            "currentStatus": "high",
        },
        {
            "code": "bare-review-summary-blocked",
            "severity": "high",
            "appliesTo": ["review-badge", "report-card", "thin-api-response"],
            "message": (
                "Do not render the trust-bearing PBPK review summary alone. Adjacent caveats and "
                "anti-misread guidance are required."
            ),
            "requiredFields": required_fields,
            "currentStatus": "context-required",
        },
    ]

    direct_dose = _safe_text(claim_boundaries.get("directRegulatoryDoseDerivation")) or "not-supported"
    if direct_dose != "supported":
        block_reasons.append(
            {
                "code": "direct-regulatory-dose-derivation-blocked",
                "severity": "high",
                "appliesTo": ["regulatory-dose-claim", "regulatory-decision-summary", "decision-recommendation"],
                "message": (
                    "Block downstream presentations that frame this PBPK output as a direct regulatory dose "
                    "derivation or final decision recommendation."
                ),
                "currentStatus": direct_dose,
            }
        )

    if not _safe_bool(qualification_summary.get("riskAssessmentReady"), False):
        block_reasons.append(
            {
                "code": "risk-assessment-ready-overclaim-blocked",
                "severity": "high",
                "appliesTo": ["decision-card", "release-highlight", "automation-forwarding"],
                "message": (
                    "Block decision-ready or regulatory-ready framing when the imported qualification remains "
                    "bounded to research or illustrative use."
                ),
                "currentStatus": _safe_text(qualification_summary.get("state")) or "research-use",
            }
        )

    if qualification_summary.get("withinDeclaredContext") is False:
        block_reasons.append(
            {
                "code": "outside-declared-context-overclaim-blocked",
                "severity": "high",
                "appliesTo": ["cross-population-extrapolation-claim", "decision-card", "forwarded-bundle"],
                "message": (
                    "Block stronger downstream claims when the imported request falls outside the declared PBPK "
                    "context of use."
                ),
                "currentStatus": "outside-declared-context",
            }
        )

    if _safe_int(review_status.get("unresolvedDissentCount"), 0) > 0:
        block_reasons.append(
            {
                "code": "open-review-intervention-blocked",
                "severity": "high",
                "appliesTo": ["approval-badge", "decision-card", "public-summary"],
                "message": (
                    "Block approval-style rendering while reviewer dissent or open intervention topics "
                    "remain unresolved."
                ),
                "currentStatus": _safe_text(review_status.get("status")) or "declared-with-unresolved-dissent",
            }
        )

    return {
        "policyVersion": "pbpk-export-block-policy.v1",
        "defaultAction": "block-lossy-or-decision-leaning-exports",
        "contextualizedRenderOnly": True,
        "workflow": _safe_text(_as_mapping(assessment_context.get("workflowRole")).get("workflow")) or "not-declared",
        "blockedViewModes": blocked_view_modes,
        "requiredFields": required_fields,
        "blockReasons": block_reasons,
        "notes": [
            "This policy is descriptive and machine-readable so analyst-facing clients can refuse unsafe thin views.",
            "Imported or operator-reviewed state does not create regulatory decision authority inside PBPK MCP.",
        ],
    }


def _build_caution_summary(
    *,
    assessment_context: Mapping[str, Any],
    qualification_summary: Mapping[str, Any],
) -> dict[str, Any]:
    evidence_basis = _as_mapping(qualification_summary.get("evidenceBasis"))
    claim_boundaries = _as_mapping(qualification_summary.get("workflowClaimBoundaries"))
    review_status = _as_mapping(qualification_summary.get("reviewStatus"))
    population_support = _as_mapping(assessment_context.get("populationSupport"))

    cautions: list[dict[str, Any]] = []

    def add_caution(
        *,
        code: str,
        caution_type: str,
        severity: str,
        handling: str,
        scope: str,
        source_surface: str,
        message: str,
        current_status: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "code": code,
            "cautionType": caution_type,
            "severity": severity,
            "handling": handling,
            "scope": scope,
            "sourceSurface": source_surface,
            "message": message,
            "requiresHumanReview": True,
        }
        if current_status:
            payload["currentStatus"] = current_status
        cautions.append(payload)

    add_caution(
        code="detached-summary-overread",
        caution_type="summary-transport-risk",
        severity="high",
        handling="blocking",
        scope="summary-surface",
        source_surface="exportBlockPolicy",
        message=(
            "Thin report cards, screenshots, or forwarded imported summaries can detach the "
            "trust-bearing PBPK label from the caveats it needs."
        ),
        current_status="detached-summary-unsafe",
    )

    direct_dose = _safe_text(claim_boundaries.get("directRegulatoryDoseDerivation")) or "not-supported"
    if direct_dose != "supported":
        add_caution(
            code="direct-regulatory-dose-derivation-blocked",
            caution_type="decision-overclaim-risk",
            severity="high",
            handling="blocking",
            scope="workflow-claim",
            source_surface="workflowClaimBoundaries",
            message=(
                "Imported PBPK outputs should not be presented as direct regulatory dose derivations "
                "or final decision recommendations."
            ),
            current_status=direct_dose,
        )

    if not _safe_bool(qualification_summary.get("riskAssessmentReady"), False):
        add_caution(
            code="risk-assessment-ready-overclaim",
            caution_type="decision-overclaim-risk",
            severity="high",
            handling="blocking",
            scope="workflow-claim",
            source_surface="qualificationState",
            message=(
                "Imported qualification remains bounded, so decision-ready or regulatory-ready framing "
                "should stay blocked."
            ),
            current_status=_safe_text(qualification_summary.get("state")) or "research-use",
        )

    if qualification_summary.get("withinDeclaredContext") is False:
        add_caution(
            code="outside-declared-context",
            caution_type="context-mismatch",
            severity="high",
            handling="blocking",
            scope="scenario",
            source_surface="assessmentContext",
            message=(
                "The imported PBPK request falls outside the declared context, so stronger downstream "
                "claims should stay blocked."
            ),
            current_status="outside-declared-context",
        )

    if _safe_int(review_status.get("unresolvedDissentCount"), 0) > 0:
        add_caution(
            code="reviewer-dissent-open",
            caution_type="review-dissent",
            severity="high",
            handling="blocking",
            scope="review",
            source_surface="reviewStatus",
            message=(
                "Explicit reviewer dissent remains unresolved and should stay visible before stronger "
                "qualification-facing claims are made."
            ),
            current_status=_safe_text(review_status.get("status")) or "declared-with-unresolved-dissent",
        )

    ivive_status = _safe_text(evidence_basis.get("iviveLinkageStatus")) or "not-declared"
    if ivive_status in {"not-declared", "external-or-not-declared"}:
        add_caution(
            code="ivive-linkage-limited",
            caution_type="weak-ivive-linkage",
            severity="medium",
            handling="advisory",
            scope="evidence-basis",
            source_surface="evidenceBasis",
            message=(
                "IVIVE linkage remains weak or externally undeclared, so reverse-dosimetry or "
                "exposure-led interpretations need extra review."
            ),
            current_status=ivive_status,
        )

    parameter_basis = _safe_text(evidence_basis.get("parameterizationBasis")) or "not-declared"
    if any(token in parameter_basis for token in ("literature", "transfer", "default")):
        add_caution(
            code="parameter-transfer-uncertainty",
            caution_type="parameter-transfer-uncertainty",
            severity="medium",
            handling="advisory",
            scope="model",
            source_surface="evidenceBasis",
            message=(
                "Parameterization depends on transferred, literature-derived, or default assumptions, "
                "so parameter-transfer uncertainty should be reviewed before stronger claims."
            ),
            current_status=parameter_basis,
        )

    variability_status = (
        _safe_text(evidence_basis.get("populationVariabilityStatus"))
        or _safe_text(population_support.get("variabilityRepresentation"))
        or "not-declared"
    )
    if variability_status in {"not-declared", "declared-without-structured-variability"}:
        add_caution(
            code="population-variability-limited",
            caution_type="population-variability",
            severity="medium",
            handling="advisory",
            scope="population",
            source_surface="populationSupport",
            message=(
                "Population variability support remains limited or weakly structured, so extrapolation "
                "beyond the declared population context needs extra review."
            ),
            current_status=variability_status,
        )

    if _safe_int(qualification_summary.get("missingEvidenceCount"), 0) > 0:
        add_caution(
            code="known-evidence-gaps",
            caution_type="evidence-gap",
            severity="high",
            handling="blocking",
            scope="evidence-basis",
            source_surface="qualificationState",
            message=(
                "Imported qualification metadata declare known evidence gaps, so approval-style or "
                "strong publication framing should stay blocked."
            ),
            current_status=str(_safe_int(qualification_summary.get("missingEvidenceCount"), 0)),
        )

    severity_order = {"low": 0, "medium": 1, "high": 2}
    highest_severity = max(
        (entry["severity"] for entry in cautions),
        key=lambda value: severity_order.get(value, -1),
        default="medium",
    )
    blocking_count = sum(1 for entry in cautions if entry["handling"] == "blocking")
    advisory_count = sum(1 for entry in cautions if entry["handling"] == "advisory")
    return {
        "summaryVersion": "pbpk-caution-summary.v1",
        "highestSeverity": highest_severity,
        "blockingCount": blocking_count,
        "advisoryCount": advisory_count,
        "requiresHumanReview": True,
        "blockingRecommended": blocking_count > 0,
        "cautions": cautions,
    }


class ExternalArtifactModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    type: str = Field(min_length=1)
    path: str = Field(min_length=1)
    checksum: Optional[str] = None
    title: Optional[str] = None


class IngestExternalPbpkBundleRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    source_platform: str = Field(alias="sourcePlatform", min_length=1)
    source_version: Optional[str] = Field(default=None, alias="sourceVersion")
    model_name: Optional[str] = Field(default=None, alias="modelName")
    model_type: str = Field(default="pbpk", alias="modelType")
    execution_date: Optional[str] = Field(default=None, alias="executionDate")
    run_id: Optional[str] = Field(default=None, alias="runId")
    operator: Optional[str] = None
    sponsor: Optional[str] = None
    raw_artifacts: list[ExternalArtifactModel] = Field(default_factory=list, alias="rawArtifacts")
    assessment_context: dict[str, Any] = Field(default_factory=dict, alias="assessmentContext")
    internal_exposure: dict[str, Any] = Field(default_factory=dict, alias="internalExposure")
    qualification: dict[str, Any] = Field(default_factory=dict)
    uncertainty: dict[str, Any] = Field(default_factory=dict)
    uncertainty_register: dict[str, Any] = Field(default_factory=dict, alias="uncertaintyRegister")
    pod: dict[str, Any] = Field(default_factory=dict)
    true_dose_adjustment: dict[str, Any] = Field(default_factory=dict, alias="trueDoseAdjustment")
    comparison_metric: str = Field(default="cmax", alias="comparisonMetric")


class IngestExternalPbpkBundleResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    tool: str = TOOL_NAME
    contract_version: str = Field(default=CONTRACT_VERSION, alias="contractVersion")
    external_run: dict[str, Any] = Field(default_factory=dict, alias="externalRun")
    ngra_objects: dict[str, Any] = Field(default_factory=dict, alias="ngraObjects")
    warnings: list[str] = Field(default_factory=list)


def _extract_metric_entry(internal_exposure: Mapping[str, Any], *names: str) -> dict[str, Any]:
    metrics = _as_mapping(internal_exposure.get("metrics"))
    for name in names:
        if name in metrics:
            value = metrics[name]
            if isinstance(value, Mapping):
                return dict(value)
            return {"value": value}
    return {}


def _build_external_run(payload: IngestExternalPbpkBundleRequest) -> dict[str, Any]:
    run_id = payload.run_id or f"external-{payload.source_platform.lower()}-{uuid4().hex[:10]}"
    return {
        "objectType": "externalPbpkRun.v1",
        "runId": run_id,
        "sourcePlatform": payload.source_platform,
        "sourceVersion": payload.source_version,
        "modelName": payload.model_name,
        "modelType": payload.model_type,
        "executionDate": payload.execution_date,
        "operator": payload.operator,
        "sponsor": payload.sponsor,
        "rawArtifacts": [artifact.model_dump(by_alias=True) for artifact in payload.raw_artifacts],
        "normalizationBoundary": (
            "External PBPK import normalizes outputs and metadata into PBPK-side objects, "
            "but does not execute or validate the upstream engine itself."
        ),
    }


def _build_assessment_context(payload: IngestExternalPbpkBundleRequest) -> dict[str, Any]:
    assessment = _as_mapping(payload.assessment_context)
    internal = _as_mapping(payload.internal_exposure)
    qualification = _as_mapping(payload.qualification)
    context = _coerce_section(assessment.get("contextOfUse"), scalar_key="regulatoryUse")
    domain = _coerce_section(assessment.get("domain") or assessment.get("applicabilityDomain"))
    target_output = (
        _safe_text(assessment.get("targetOutput"))
        or _safe_text(internal.get("targetOutput"))
        or _safe_text(internal.get("outputPath"))
    )
    return {
        "objectType": "assessmentContext.v1",
        "objectId": f"{payload.source_platform.lower()}-assessment-context",
        "simulationId": None,
        "backend": EXTERNAL_BACKEND,
        "sourcePlatform": payload.source_platform,
        "assessmentBoundary": "pbpk-context-alignment-only",
        "decisionBoundary": "no-ngra-decision-policy",
        "validationDecision": None,
        "contextOfUse": {
            "regulatoryUse": _selection_triplet(
                context.get("regulatoryUse") or context.get("intendedUse"),
                qualification.get("contextOfUse") or qualification.get("regulatoryUse"),
            ),
            "scientificPurpose": _selection_triplet(
                context.get("scientificPurpose"),
                qualification.get("scientificPurpose"),
            ),
            "decisionContext": _selection_triplet(
                context.get("decisionContext"),
                qualification.get("decisionContext"),
            ),
        },
        "domain": {
            "species": _selection_triplet(domain.get("species"), internal.get("species")),
            "route": _selection_triplet(
                domain.get("route") or domain.get("routes"),
                internal.get("route"),
            ),
            "lifeStage": _selection_triplet(domain.get("lifeStage"), internal.get("lifeStage")),
            "population": _selection_triplet(domain.get("population"), internal.get("population")),
            "compound": _selection_triplet(domain.get("compound"), internal.get("analyte")),
        },
        "doseScenario": assessment.get("doseScenario") or internal.get("doseScenario"),
        "targetOutput": {
            "requested": target_output,
            "declared": [target_output] if target_output else [],
        },
        "workflowRole": _build_workflow_role(assessment),
        "populationSupport": _build_population_support(
            assessment,
            internal,
            _as_mapping(payload.uncertainty),
        ),
        "supports": {
            "declaredProfileComparison": True,
            "requestContextAlignment": True,
            "typedNgraHandoff": True,
            "decisionRecommendation": False,
        },
    }


def _derive_external_qualification_state(qualification: Mapping[str, Any]) -> str:
    explicit = _normalize_token(qualification.get("state") or qualification.get("qualificationState"))
    if explicit in KNOWN_QUALIFICATION_STATES:
        return str(explicit)

    evidence_level = _normalize_token(qualification.get("evidenceLevel") or qualification.get("level"))
    verification_status = _normalize_token(qualification.get("verificationStatus"))
    context_use = _normalize_token(qualification.get("contextOfUse") or qualification.get("regulatoryUse"))

    if context_use in {"illustrative-example", "demo-only", "example-only"}:
        return "illustrative-example"
    if (
        verification_status in {"regulatory-used", "externally-reviewed", "regulatory-qualified"}
        and evidence_level in {"l3", "level-3", "high"}
    ):
        return "regulatory-candidate"
    if evidence_level or verification_status or context_use:
        return "research-use"
    return "exploratory"


def _build_review_status(qualification: Mapping[str, Any]) -> dict[str, Any]:
    explicit_status = _as_mapping(qualification.get("reviewStatus"))
    peer_review = _as_mapping(qualification.get("peerReview"))
    merged_review = dict(peer_review)
    for key in (
        "reviewRecords",
        "reviews",
        "peerReviewRecords",
        "reviewHistory",
        "priorRegulatoryUse",
        "priorUse",
        "priorApplications",
        "priorUseHistory",
        "revisionHistory",
        "changeHistory",
        "versionHistory",
        "revisions",
        "revisionStatus",
        "changeStatus",
        "versionStatus",
        "status",
        "summary",
        "focusTopics",
        "reviewFocus",
        "unresolvedDissentCount",
        "resolvedDissentCount",
    ):
        if key in qualification and key not in merged_review:
            merged_review[key] = qualification.get(key)

    derived = _derive_review_status(merged_review)
    for key in (
        "status",
        "declaredStatus",
        "summary",
        "reviewRecordCount",
        "priorUseCount",
        "revisionEntryCount",
        "unresolvedDissentCount",
        "resolvedDissentCount",
        "revisionStatus",
        "focusTopics",
        "openTopics",
        "resolvedTopics",
        "interventionSummary",
        "requiresReviewerAttention",
    ):
        if key in explicit_status and explicit_status.get(key) is not None:
            derived[key] = explicit_status.get(key)

    derived["focusTopics"] = list(dict.fromkeys(_normalize_text_list(derived.get("focusTopics"))))
    derived["openTopics"] = list(dict.fromkeys(_normalize_text_list(derived.get("openTopics"))))
    derived["resolvedTopics"] = list(dict.fromkeys(_normalize_text_list(derived.get("resolvedTopics"))))
    derived["reviewRecordCount"] = _safe_int(derived.get("reviewRecordCount"), 0)
    derived["priorUseCount"] = _safe_int(derived.get("priorUseCount"), 0)
    derived["revisionEntryCount"] = _safe_int(derived.get("revisionEntryCount"), 0)
    derived["unresolvedDissentCount"] = _safe_int(derived.get("unresolvedDissentCount"), 0)
    derived["resolvedDissentCount"] = _safe_int(derived.get("resolvedDissentCount"), 0)
    if not derived["openTopics"] and derived["unresolvedDissentCount"] > 0:
        derived["openTopics"] = list(derived["focusTopics"])
    if not derived["resolvedTopics"] and derived["resolvedDissentCount"] > 0:
        derived["resolvedTopics"] = list(derived["focusTopics"])

    explicit_intervention = _as_mapping(explicit_status.get("interventionSummary"))
    if explicit_intervention:
        intervention_summary = dict(explicit_intervention)
    elif derived["unresolvedDissentCount"] > 0:
        intervention_summary = {
            "status": "open-review-interventions",
            "summary": (
                "Explicit reviewer interventions remain open and should travel with the summary "
                "so unresolved concerns are not flattened into a single label."
            ),
            "openTopicCount": len(derived["openTopics"]),
            "resolvedTopicCount": len(derived["resolvedTopics"]),
            "openTopics": list(derived["openTopics"]),
            "resolvedTopics": list(derived["resolvedTopics"]),
        }
    elif derived["resolvedDissentCount"] > 0:
        intervention_summary = {
            "status": "resolved-review-interventions",
            "summary": (
                "Resolved reviewer interventions are recorded and should remain visible as context "
                "for how the current summary was narrowed or clarified."
            ),
            "openTopicCount": len(derived["openTopics"]),
            "resolvedTopicCount": len(derived["resolvedTopics"]),
            "openTopics": list(derived["openTopics"]),
            "resolvedTopics": list(derived["resolvedTopics"]),
        }
    else:
        intervention_summary = _as_mapping(derived.get("interventionSummary")) or {}
    if intervention_summary:
        intervention_summary.setdefault("openTopicCount", len(derived["openTopics"]))
        intervention_summary.setdefault("resolvedTopicCount", len(derived["resolvedTopics"]))
        intervention_summary.setdefault("openTopics", list(derived["openTopics"]))
        intervention_summary.setdefault("resolvedTopics", list(derived["resolvedTopics"]))
        derived["interventionSummary"] = intervention_summary

    derived["requiresReviewerAttention"] = _safe_bool(
        derived.get("requiresReviewerAttention"),
        derived["status"] in {"not-declared", "traceability-limited", "declared-with-unresolved-dissent"},
    )
    return derived


def _build_pbpk_qualification_summary(payload: IngestExternalPbpkBundleRequest) -> dict[str, Any]:
    qualification = _as_mapping(payload.qualification)
    assessment_context = _as_mapping(payload.assessment_context)
    population_support = _build_population_support(
        assessment_context,
        _as_mapping(payload.internal_exposure),
        _as_mapping(payload.uncertainty),
    )
    review_status = _build_review_status(qualification)
    derived_state = _derive_external_qualification_state(qualification)
    state = derived_state
    downgraded_for_review = False
    if state == "qualified-within-context" and review_status["unresolvedDissentCount"] > 0:
        state = "regulatory-candidate"
        downgraded_for_review = True
    performance_boundary = _safe_text(qualification.get("performanceEvidenceBoundary"))
    required_external_inputs = [
        "higher-level NGRA decision policy or orchestrator outside PBPK MCP"
    ]
    if not performance_boundary or performance_boundary == "no-bundled-performance-evidence":
        required_external_inputs.append(
            "predictive or external qualification evidence for stronger regulatory-facing claims"
        )
    elif performance_boundary == "runtime-or-internal-evidence-only":
        required_external_inputs.append(
            "observed-vs-predicted, predictive-dataset, or external qualification evidence"
        )
    if review_status["unresolvedDissentCount"] > 0:
        required_external_inputs.append(
            "reviewer resolution or explicit acceptance of open dissent outside PBPK MCP"
        )

    limitations: list[str] = []
    if performance_boundary == "runtime-or-internal-evidence-only":
        limitations.append(
            "Imported performance evidence is limited to runtime or internal supporting evidence."
        )
    elif performance_boundary == "no-bundled-performance-evidence":
        limitations.append(
            "No bundled predictive-performance evidence were attached to the imported PBPK bundle."
        )
    if review_status["unresolvedDissentCount"] > 0:
        limitations.append(
            "Explicit reviewer dissent remains unresolved for the imported qualification-facing record."
        )

    label = (
        None if downgraded_for_review else _safe_text(qualification.get("label"))
    ) or state.replace("-", " ").title()
    summary = _safe_text(qualification.get("summary")) or (
        "External PBPK qualification metadata were normalized without executing the upstream platform."
    )
    if review_status["unresolvedDissentCount"] > 0:
        summary = (
            summary
            + " Explicit reviewer dissent remains unresolved, so stronger qualification-facing claims stay conservative."
        )

    qualification_summary = {
        "objectType": "pbpkQualificationSummary.v1",
        "objectId": f"{payload.source_platform.lower()}-qualification-summary",
        "simulationId": None,
        "backend": EXTERNAL_BACKEND,
        "sourcePlatform": payload.source_platform,
        "assessmentBoundary": "external-pbpk-normalization-only",
        "decisionBoundary": "no-ngra-decision-policy",
        "state": state,
        "label": label,
        "summary": summary,
        "qualificationLevel": qualification.get("evidenceLevel") or qualification.get("qualificationLevel") or "unreported",
        "oecdReadiness": qualification.get("oecdReadiness") or "external-imported",
        "validationDecision": None,
        "withinDeclaredContext": None,
        "scientificProfile": bool(qualification or payload.assessment_context or payload.internal_exposure),
        "riskAssessmentReady": state == "qualified-within-context" and review_status["unresolvedDissentCount"] == 0,
        "checklistScore": qualification.get("checklistScore"),
        "evidenceStatus": qualification.get("verificationStatus") or "imported",
        "profileSource": "external-import",
        "missingEvidenceCount": int(qualification.get("missingEvidenceCount") or 0),
        "reviewStatus": review_status,
        "performanceEvidenceBoundary": performance_boundary,
        "executableVerificationStatus": qualification.get("verificationStatus") or "not-run-in-pbpk-mcp",
        "platformClass": qualification.get("platformClass"),
        "validationReferences": _normalize_text_list(qualification.get("validationReferences")),
        "evidenceBasis": _build_evidence_basis(
            qualification,
            population_support=population_support,
        ),
        "workflowClaimBoundaries": _build_workflow_claim_boundaries(qualification),
        "supports": {
            "nativeExecution": False,
            "externalImportNormalization": True,
            "manifestValidation": False,
            "preflightValidation": False,
            "executableVerification": False,
            "oecdDossierExport": True,
            "typedNgraHandoff": True,
            "externalBerHandoff": True,
            "regulatoryDecision": False,
        },
        "requiredExternalInputs": list(dict.fromkeys(required_external_inputs)),
        "limitations": list(dict.fromkeys(limitations)),
    }
    qualification_summary["exportBlockPolicy"] = _build_export_block_policy(
        assessment_context=assessment_context,
        qualification_summary=qualification_summary,
    )
    qualification_summary["cautionSummary"] = _build_caution_summary(
        assessment_context=assessment_context,
        qualification_summary=qualification_summary,
    )
    return qualification_summary


def _build_uncertainty_summary(payload: IngestExternalPbpkBundleRequest) -> dict[str, Any]:
    uncertainty = _as_mapping(payload.uncertainty)
    uncertainty_rows = _extract_uncertainty_rows(uncertainty)
    variability_approach_rows = _uncertainty_rows_for_kind(uncertainty_rows, "variability-approach")
    variability_propagation_rows = _uncertainty_rows_for_kind(uncertainty_rows, "variability-propagation")
    sensitivity_rows = _uncertainty_rows_for_kind(uncertainty_rows, "sensitivity-analysis")
    residual_rows = _uncertainty_rows_for_kind(uncertainty_rows, "residual-uncertainty")
    has_sensitivity = bool(
        uncertainty.get("hasSensitivityAnalysis")
        or uncertainty.get("sensitivityAnalysis")
        or sensitivity_rows
    )
    has_variability_approach = bool(
        uncertainty.get("hasVariabilityApproach")
        or uncertainty.get("variabilityApproach")
        or variability_approach_rows
    )
    has_variability_propagation = bool(
        uncertainty.get("hasVariabilityPropagation")
        or uncertainty.get("variabilityPropagation")
        or variability_propagation_rows
    )
    has_residual_uncertainty = bool(
        uncertainty.get("hasResidualUncertainty")
        or uncertainty.get("residualUncertainty")
        or residual_rows
    )
    status = _safe_text(uncertainty.get("status")) or "unreported"
    evidence_row_count = int(uncertainty.get("evidenceRowCount") or len(uncertainty_rows))
    total_evidence_rows = int(uncertainty.get("totalEvidenceRows") or len(uncertainty_rows))
    quantified_sensitivity = any(
        _uncertainty_row_has_quantitative_signal(entry) for entry in sensitivity_rows
    )
    quantified_residual = any(
        _uncertainty_row_has_quantitative_signal(entry) for entry in residual_rows
    )
    quantified_variability = any(
        _uncertainty_row_has_quantitative_signal(entry)
        for entry in variability_propagation_rows
    )
    quantified_row_count = sum(
        1 for entry in uncertainty_rows if _uncertainty_row_has_quantitative_signal(entry)
    )
    declared_only_row_count = sum(
        1 for entry in uncertainty_rows if not _uncertainty_row_has_quantitative_signal(entry)
    )
    semantic_coverage = _build_uncertainty_semantic_coverage(
        status=status,
        has_variability_approach=has_variability_approach,
        has_variability_propagation=has_variability_propagation,
        has_sensitivity=has_sensitivity,
        has_residual_uncertainty=has_residual_uncertainty,
        variability_row_count=len(variability_approach_rows) + len(variability_propagation_rows),
        sensitivity_row_count=len(sensitivity_rows),
        residual_row_count=len(residual_rows),
        quantified_variability=quantified_variability,
        quantified_row_count=quantified_row_count,
        declared_only_row_count=declared_only_row_count,
        quantified_sensitivity=quantified_sensitivity,
        quantified_residual=quantified_residual,
    )
    if has_variability_propagation:
        variability_status = "propagated"
    elif has_variability_approach:
        variability_status = "characterized"
    elif status != "unreported":
        variability_status = "declared-without-structured-variability"
    else:
        variability_status = "unreported"

    if has_sensitivity:
        sensitivity_status = "available"
    elif status != "unreported":
        sensitivity_status = "not-bundled"
    else:
        sensitivity_status = "unreported"

    if has_residual_uncertainty:
        residual_status = "declared"
    elif status != "unreported":
        residual_status = "not-explicit"
    else:
        residual_status = "unreported"

    required_external_inputs = ["cross-domain uncertainty synthesis outside PBPK MCP"]
    if not has_residual_uncertainty:
        required_external_inputs.append(
            "explicit residual uncertainty register for broader NGRA interpretation"
        )

    return {
        "objectType": "uncertaintySummary.v1",
        "objectId": f"{payload.source_platform.lower()}-uncertainty-summary",
        "simulationId": None,
        "backend": EXTERNAL_BACKEND,
        "sourcePlatform": payload.source_platform,
        "assessmentBoundary": "pbpk-side-uncertainty-summary-only",
        "decisionBoundary": "no-ngra-decision-policy",
        "status": status,
        "summary": uncertainty.get("summary"),
        "evidenceSource": uncertainty.get("source") or "external-import",
        "sources": _normalize_text_list(uncertainty.get("sources")),
        "issueCount": int(uncertainty.get("issueCount") or 0),
        "evidenceRowCount": evidence_row_count,
        "totalEvidenceRows": total_evidence_rows,
        "hasSensitivityAnalysis": has_sensitivity,
        "hasVariabilityApproach": has_variability_approach,
        "hasVariabilityPropagation": has_variability_propagation,
        "hasResidualUncertainty": has_residual_uncertainty,
        "semanticCoverage": semantic_coverage,
        "variabilityStatus": variability_status,
        "sensitivityStatus": sensitivity_status,
        "residualUncertaintyStatus": residual_status,
        "supports": {
            "qualitativeSummary": status != "unreported" or evidence_row_count > 0,
            "sensitivityAnalysis": has_sensitivity,
            "variabilityCharacterization": has_variability_approach,
            "quantitativePropagation": has_variability_propagation,
            "residualUncertaintyTracking": has_residual_uncertainty,
            "typedUncertaintySemantics": True,
            "classifiedVariability": semantic_coverage["variabilityType"] != "unreported",
            "classifiedResidualUncertainty": semantic_coverage["residualUncertaintyType"] != "unreported",
            "quantifiedVariability": semantic_coverage["variabilityQuantificationStatus"] == "quantified",
            "quantifiedSensitivity": semantic_coverage["sensitivityQuantificationStatus"] == "quantified",
            "quantifiedResidualUncertainty": (
                semantic_coverage["residualUncertaintyQuantificationStatus"] == "quantified"
            ),
            "typedNgraHandoff": True,
            "crossDomainUncertaintyRegister": False,
            "decisionRecommendation": False,
        },
        "requiredExternalInputs": list(dict.fromkeys(required_external_inputs)),
        "bundleMetadata": _as_mapping(uncertainty.get("bundleMetadata")) or None,
    }


def _build_uncertainty_handoff(
    payload: IngestExternalPbpkBundleRequest,
    *,
    qualification_summary: Mapping[str, Any],
    uncertainty_summary: Mapping[str, Any],
    internal_exposure_estimate: Mapping[str, Any],
    point_of_departure_reference: Mapping[str, Any],
    uncertainty_register_reference: Mapping[str, Any],
) -> dict[str, Any]:
    qualification_attached = bool(_safe_text(qualification_summary.get("objectId")))
    uncertainty_status = _safe_text(uncertainty_summary.get("status")) or "unreported"
    semantic_coverage = _as_mapping(uncertainty_summary.get("semanticCoverage"))
    uncertainty_attached = bool(
        uncertainty_status != "unreported"
        or _safe_float(uncertainty_summary.get("evidenceRowCount")) not in (None, 0.0)
    )
    internal_exposure_attached = (
        _safe_text(internal_exposure_estimate.get("status")) == "available"
    )
    pod_reference_attached = (
        _safe_text(point_of_departure_reference.get("status")) == "attached-external-reference"
    )
    uncertainty_register_attached = (
        _safe_text(uncertainty_register_reference.get("status")) == "attached-external-reference"
    )
    residual_uncertainty_tracked = bool(
        _as_mapping(uncertainty_summary.get("supports")).get("residualUncertaintyTracking")
    )
    typed_uncertainty_semantics_attached = bool(
        _safe_text(semantic_coverage.get("overallQuantificationStatus"))
    )
    classified_variability_attached = (
        _safe_text(semantic_coverage.get("variabilityType")) != "unreported"
    )
    classified_residual_attached = (
        _safe_text(semantic_coverage.get("residualUncertaintyType")) != "unreported"
    )
    quantified_variability = (
        _safe_text(semantic_coverage.get("variabilityQuantificationStatus")) == "quantified"
    )
    quantified_sensitivity = (
        _safe_text(semantic_coverage.get("sensitivityQuantificationStatus")) == "quantified"
    )
    quantified_residual = (
        _safe_text(semantic_coverage.get("residualUncertaintyQuantificationStatus")) == "quantified"
    )

    blocking_reasons: list[str] = []
    if not qualification_attached:
        blocking_reasons.append("No PBPK qualification summary is attached.")
    if not uncertainty_attached:
        blocking_reasons.append("No structured PBPK uncertainty summary is attached.")

    if not blocking_reasons:
        status = "ready-for-cross-domain-uncertainty-synthesis"
    elif qualification_attached or uncertainty_attached:
        status = "partial-pbpk-uncertainty-handoff"
    else:
        status = "not-ready"

    required_external_inputs = [
        "cross-domain uncertainty synthesis outside PBPK MCP",
        "exposure-scenario uncertainty outside PBPK MCP",
        "PoD or NAM uncertainty outside PBPK MCP",
    ]
    if not uncertainty_register_attached:
        required_external_inputs.append(
            "external cross-domain uncertainty register reference"
        )
    if not residual_uncertainty_tracked:
        required_external_inputs.append(
            "explicit residual uncertainty register for broader NGRA interpretation"
        )

    return {
        "objectType": "uncertaintyHandoff.v1",
        "objectId": f"{payload.source_platform.lower()}-uncertainty-handoff",
        "simulationId": None,
        "backend": EXTERNAL_BACKEND,
        "sourcePlatform": payload.source_platform,
        "assessmentBoundary": "pbpk-to-cross-domain-uncertainty-handoff-only",
        "decisionBoundary": "cross-domain-uncertainty-synthesis-owned-by-external-orchestrator",
        "decisionOwner": "external-orchestrator",
        "status": status,
        "pbpkQualificationSummaryRef": _safe_text(qualification_summary.get("objectId")),
        "uncertaintySummaryRef": _safe_text(uncertainty_summary.get("objectId")),
        "internalExposureEstimateRef": _safe_text(internal_exposure_estimate.get("objectId")),
        "pointOfDepartureReferenceRef": _safe_text(point_of_departure_reference.get("objectId")),
        "uncertaintyRegisterReferenceRef": _safe_text(
            uncertainty_register_reference.get("objectId")
        ),
        "supports": {
            "pbpkQualificationAttached": qualification_attached,
            "pbpkUncertaintySummaryAttached": uncertainty_attached,
            "internalExposureContextAttached": internal_exposure_attached,
            "pointOfDepartureReferenceAttached": pod_reference_attached,
            "uncertaintyRegisterReferenceAttached": uncertainty_register_attached,
            "residualUncertaintyTracked": residual_uncertainty_tracked,
            "typedUncertaintySemanticsAttached": typed_uncertainty_semantics_attached,
            "classifiedVariabilitySummaryAttached": classified_variability_attached,
            "classifiedResidualUncertaintySummaryAttached": classified_residual_attached,
            "quantifiedPbpkVariability": quantified_variability,
            "quantifiedPbpkSensitivity": quantified_sensitivity,
            "quantifiedPbpkResidualUncertainty": quantified_residual,
            "crossDomainUncertaintySynthesis": False,
            "decisionRecommendation": False,
        },
        "requiredExternalInputs": list(dict.fromkeys(required_external_inputs)),
        "blockingReasons": blocking_reasons,
    }


def _build_uncertainty_register_reference(
    payload: IngestExternalPbpkBundleRequest,
) -> tuple[dict[str, Any], list[str]]:
    register = _as_mapping(payload.uncertainty_register)
    register_ref = _safe_text(
        register.get("ref")
        or register.get("registerRef")
        or register.get("uncertaintyRegisterRef")
        or register.get("id")
    )
    warnings: list[str] = []
    required_external_inputs = ["cross-domain uncertainty synthesis outside PBPK MCP"]
    if register_ref is None:
        required_external_inputs.append("external cross-domain uncertainty register reference")

    register_reference = {
        "objectType": "uncertaintyRegisterReference.v1",
        "objectId": f"{payload.source_platform.lower()}-uncertainty-register-reference",
        "simulationId": None,
        "backend": EXTERNAL_BACKEND,
        "sourcePlatform": payload.source_platform,
        "assessmentBoundary": "external-uncertainty-register-reference-only",
        "decisionBoundary": "cross-domain-uncertainty-synthesis-owned-by-external-orchestrator",
        "decisionOwner": "external-orchestrator",
        "status": "attached-external-reference" if register_ref is not None else "not-attached",
        "registerRef": register_ref,
        "source": _safe_text(register.get("source") or register.get("system")),
        "summary": _safe_text(register.get("summary")),
        "scope": _safe_text(register.get("scope")),
        "owner": _safe_text(register.get("owner")),
        "supports": {
            "typedReference": register_ref is not None,
            "crossDomainUncertaintySynthesis": False,
            "decisionRecommendation": False,
        },
        "requiredExternalInputs": list(dict.fromkeys(required_external_inputs)),
        "warnings": warnings,
    }
    return register_reference, warnings


def _build_internal_exposure_estimate(payload: IngestExternalPbpkBundleRequest) -> tuple[dict[str, Any], list[str]]:
    internal = _as_mapping(payload.internal_exposure)
    warnings: list[str] = []
    lineage = _extract_quantitative_lineage(internal)
    cmax = _extract_metric_entry(internal, "cmax", "Cmax")
    tmax = _extract_metric_entry(internal, "tmax", "Tmax")
    auc = _extract_metric_entry(internal, "auc0Tlast", "auc0tlast", "auc", "AUC")
    target_output = _safe_text(
        internal.get("targetOutput") or internal.get("outputPath") or internal.get("output")
    )
    concentration_unit = _safe_text(cmax.get("unit") or internal.get("unit"))
    auc_unit = _safe_text(auc.get("unit") or internal.get("aucUnit"))
    selected_output = {
        "outputPath": target_output or "external-import",
        "unit": concentration_unit,
        "pointCount": int(internal.get("pointCount") or 0),
        "cmax": _safe_float(cmax.get("value") if cmax else None),
        "tmax": _safe_float(tmax.get("value") if tmax else None),
        "auc0Tlast": _safe_float(auc.get("value") if auc else None),
        "aucUnitBasis": auc_unit,
    }
    has_metric = any(
        selected_output[key] is not None for key in ("cmax", "tmax", "auc0Tlast")
    )
    if not has_metric:
        warnings.append("No external internal-exposure metrics were provided.")
    warnings.extend(_lineage_warnings(lineage, "Internal exposure estimate"))
    lineage_blocking = _lineage_blocking_reasons(lineage, "Internal exposure denominator")

    payload_dict = {
        "objectType": "internalExposureEstimate.v1",
        "objectId": f"{payload.source_platform.lower()}-internal-exposure-estimate",
        "simulationId": None,
        "backend": EXTERNAL_BACKEND,
        "sourcePlatform": payload.source_platform,
        "assessmentBoundary": "pbpk-side-internal-exposure-estimate-only",
        "decisionBoundary": "no-ngra-decision-policy",
        "status": "available" if has_metric else "not-available",
        "resultsId": _safe_text(internal.get("resultsId")) or _safe_text(internal.get("runId")),
        "source": "external-import",
        "originClassification": lineage["originClassification"],
        "primarySourceVerified": lineage["primarySourceVerified"],
        "sourceChain": lineage["sourceChain"],
        "underlyingPrimarySourceRef": lineage["underlyingPrimarySourceRef"],
        "bridgingMethod": lineage["bridgingMethod"],
        "requestedTargetOutput": target_output,
        "selectionStatus": "explicit" if target_output else ("imported-selected" if has_metric else "unresolved"),
        "selectedOutput": selected_output if has_metric else None,
        "candidateOutputCount": 1 if has_metric else 0,
        "candidateOutputs": [selected_output] if has_metric else [],
        "candidateOutputsTruncated": False,
        "supports": {
            "deterministicMetricSelection": has_metric,
            "populationDistributionSummary": bool(_as_mapping(internal.get("distribution"))),
            "externalBerHandoff": has_metric and not lineage_blocking,
            "decisionRecommendation": False,
        },
        "distribution": _as_mapping(internal.get("distribution")) or None,
        "analyte": _safe_text(internal.get("analyte")),
        "species": _safe_text(internal.get("species")),
        "population": _safe_text(internal.get("population")),
        "route": _safe_text(internal.get("route")),
        "doseScenario": internal.get("doseScenario"),
        "warnings": warnings,
    }
    return payload_dict, warnings


def _resolved_internal_metric(
    internal_exposure_estimate: Mapping[str, Any], comparison_metric: str
) -> dict[str, Any] | None:
    selected_output = _as_mapping(internal_exposure_estimate.get("selectedOutput"))
    if not selected_output:
        return None

    metric_token = _normalize_token(comparison_metric) or "cmax"
    if metric_token in {"cmax", "maximum-concentration", "max-concentration"}:
        value = _safe_float(selected_output.get("cmax"))
        if value is None:
            return None
        return {
            "metric": "cmax",
            "value": value,
            "unit": _safe_text(selected_output.get("unit")),
            "outputPath": _safe_text(selected_output.get("outputPath")),
        }
    if metric_token in {"tmax", "time-to-cmax", "time-of-maximum-concentration"}:
        value = _safe_float(selected_output.get("tmax"))
        if value is None:
            return None
        return {
            "metric": "tmax",
            "value": value,
            "unit": "model-time-axis",
            "outputPath": _safe_text(selected_output.get("outputPath")),
        }
    if metric_token in {"auc", "auc0-tlast", "auc0tlast", "area-under-curve"}:
        value = _safe_float(selected_output.get("auc0Tlast"))
        if value is None:
            return None
        return {
            "metric": "auc0Tlast",
            "value": value,
            "unit": _safe_text(selected_output.get("aucUnitBasis")),
            "outputPath": _safe_text(selected_output.get("outputPath")),
        }
    return None


def _build_point_of_departure_reference(
    payload: IngestExternalPbpkBundleRequest,
) -> tuple[dict[str, Any], list[str]]:
    pod = _as_mapping(payload.pod)
    lineage = _extract_quantitative_lineage(pod)
    pod_ref = _safe_text(
        pod.get("ref") or pod.get("podRef") or pod.get("reference") or pod.get("id")
    )
    true_dose_adjustment = {
        "applied": bool(payload.true_dose_adjustment.get("applied")),
        "basis": _safe_text(payload.true_dose_adjustment.get("basis")),
        "summary": _safe_text(payload.true_dose_adjustment.get("summary")),
    }
    warnings: list[str] = []

    if pod_ref and not _safe_text(pod.get("metric")):
        warnings.append(
            "No explicit PoD metric metadata were attached; downstream BER logic should validate metric compatibility."
        )

    if true_dose_adjustment["applied"] and not true_dose_adjustment["basis"]:
        warnings.append(
            "True-dose adjustment is marked as applied, but no true-dose basis was provided."
        )
    warnings.extend(_lineage_warnings(lineage, "Point-of-departure reference"))

    required_external_inputs = [
        "PoD interpretation and suitability assessment outside PBPK MCP",
        "BER calculation and decision policy outside PBPK MCP",
    ]
    if pod_ref is None:
        required_external_inputs.append("external point-of-departure reference")

    pod_reference = {
        "objectType": "pointOfDepartureReference.v1",
        "objectId": f"{payload.source_platform.lower()}-point-of-departure-reference",
        "simulationId": None,
        "backend": EXTERNAL_BACKEND,
        "sourcePlatform": payload.source_platform,
        "assessmentBoundary": "external-pod-reference-only",
        "decisionBoundary": "pod-interpretation-and-ber-policy-owned-by-external-orchestrator",
        "decisionOwner": "external-orchestrator",
        "status": "attached-external-reference" if pod_ref is not None else "not-attached",
        "podRef": pod_ref,
        "source": _safe_text(pod.get("source") or pod.get("dataset")),
        "originClassification": lineage["originClassification"],
        "primarySourceVerified": lineage["primarySourceVerified"],
        "sourceChain": lineage["sourceChain"],
        "underlyingPrimarySourceRef": lineage["underlyingPrimarySourceRef"],
        "bridgingMethod": lineage["bridgingMethod"],
        "metric": _safe_text(pod.get("metric")),
        "unit": _safe_text(pod.get("unit")),
        "basis": _safe_text(pod.get("basis")),
        "summary": _safe_text(pod.get("summary")),
        "value": _safe_float(pod.get("value")),
        "trueDoseAdjustment": true_dose_adjustment,
        "trueDoseAdjustmentApplied": true_dose_adjustment["applied"],
        "supports": {
            "typedReference": pod_ref is not None,
            "metricMetadataAttached": bool(_safe_text(pod.get("metric"))),
            "trueDoseMetadataAttached": (
                (not true_dose_adjustment["applied"]) or bool(true_dose_adjustment["basis"])
            ),
            "externalBerCalculation": False,
            "decisionRecommendation": False,
        },
        "requiredExternalInputs": list(dict.fromkeys(required_external_inputs)),
        "warnings": warnings,
    }
    return pod_reference, warnings


def _build_ber_input_bundle(
    payload: IngestExternalPbpkBundleRequest,
    *,
    internal_exposure_estimate: Mapping[str, Any],
    point_of_departure_reference: Mapping[str, Any],
    uncertainty_summary: Mapping[str, Any],
    qualification_summary: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    blocking_reasons: list[str] = []
    warnings: list[str] = []
    pod = _as_mapping(payload.pod)
    internal_lineage = _extract_quantitative_lineage(_as_mapping(payload.internal_exposure))
    pod_lineage = _extract_quantitative_lineage(pod)
    pod_ref = _safe_text(
        pod.get("ref") or pod.get("podRef") or pod.get("reference") or pod.get("id")
    )
    comparison_metric = payload.comparison_metric
    internal_metric = _resolved_internal_metric(internal_exposure_estimate, comparison_metric)
    true_dose_adjustment = {
        "applied": bool(payload.true_dose_adjustment.get("applied")),
        "basis": _safe_text(payload.true_dose_adjustment.get("basis")),
        "summary": _safe_text(payload.true_dose_adjustment.get("summary")),
    }

    if _safe_text(internal_exposure_estimate.get("status")) != "available":
        blocking_reasons.append("No external internal exposure estimate is available.")
    elif internal_metric is None:
        blocking_reasons.append(
            f"Comparison metric '{comparison_metric}' is not available in the imported external PBPK outputs."
        )

    if pod_ref is None:
        blocking_reasons.append("No external point-of-departure reference is attached.")

    if pod_ref and not _safe_text(pod.get("metric")):
        warnings.append(
            "No explicit PoD metric metadata were attached; downstream BER logic should validate metric compatibility."
        )

    if true_dose_adjustment["applied"] and not true_dose_adjustment["basis"]:
        warnings.append(
            "True-dose adjustment is marked as applied, but no true-dose basis was provided."
        )
    warnings.extend(_lineage_warnings(internal_lineage, "Internal exposure denominator"))
    warnings.extend(_lineage_warnings(pod_lineage, "Point-of-departure anchor"))
    blocking_reasons.extend(
        _lineage_blocking_reasons(internal_lineage, "Internal exposure denominator")
    )
    blocking_reasons.extend(
        _lineage_blocking_reasons(pod_lineage, "Point-of-departure anchor")
    )

    ber_input_bundle = {
        "objectType": "berInputBundle.v1",
        "objectId": f"{payload.source_platform.lower()}-ber-input-bundle",
        "simulationId": None,
        "backend": EXTERNAL_BACKEND,
        "sourcePlatform": payload.source_platform,
        "assessmentBoundary": "external-ber-calculation-only",
        "decisionBoundary": "ber-calculation-and-decision-owned-by-external-orchestrator",
        "decisionOwner": "external-orchestrator",
        "status": (
            "ready-for-external-ber-calculation" if not blocking_reasons else "incomplete"
        ),
        "comparisonMetric": comparison_metric,
        "internalExposureEstimateRef": internal_exposure_estimate.get("objectId"),
        "internalExposureMetric": internal_metric,
        "pointOfDepartureReferenceRef": point_of_departure_reference.get("objectId"),
        "uncertaintySummaryRef": uncertainty_summary.get("objectId"),
        "qualificationSummaryRef": qualification_summary.get("objectId"),
        "podRef": pod_ref,
        "lineageFlags": _build_lineage_flags(
            internal_lineage=internal_lineage,
            pod_lineage=pod_lineage,
        ),
        "podMetadata": {
            "ref": pod_ref,
            "source": _safe_text(pod.get("source") or pod.get("dataset")),
            "metric": _safe_text(pod.get("metric")),
            "unit": _safe_text(pod.get("unit")),
            "basis": _safe_text(pod.get("basis")),
            "summary": _safe_text(pod.get("summary")),
            "value": _safe_float(pod.get("value")),
        },
        "trueDoseAdjustment": true_dose_adjustment,
        "trueDoseAdjustmentApplied": true_dose_adjustment["applied"],
        "supports": {
            "internalExposureMetricAttached": internal_metric is not None,
            "externalPodReferenceAttached": pod_ref is not None,
            "trueDoseMetadataAttached": (
                (not true_dose_adjustment["applied"]) or bool(true_dose_adjustment["basis"])
            ),
            "externalBerCalculation": not blocking_reasons,
            "decisionRecommendation": False,
        },
        "requiredExternalInputs": list(
            dict.fromkeys(
                [
                    *(
                        ["external point-of-departure reference"]
                        if pod_ref is None
                        else []
                    ),
                    "BER calculation and decision policy outside PBPK MCP",
                ]
            )
        ),
        "blockingReasons": blocking_reasons,
        "warnings": warnings,
    }
    return ber_input_bundle, warnings


def ingest_external_pbpk_bundle(
    payload: IngestExternalPbpkBundleRequest,
) -> IngestExternalPbpkBundleResponse:
    external_run = _build_external_run(payload)
    assessment_context = _build_assessment_context(payload)
    qualification_summary = _build_pbpk_qualification_summary(payload)
    uncertainty_summary = _build_uncertainty_summary(payload)
    internal_exposure_estimate, internal_warnings = _build_internal_exposure_estimate(payload)
    uncertainty_register_reference, uncertainty_register_warnings = _build_uncertainty_register_reference(
        payload
    )
    point_of_departure_reference, pod_warnings = _build_point_of_departure_reference(payload)
    uncertainty_handoff = _build_uncertainty_handoff(
        payload,
        qualification_summary=qualification_summary,
        uncertainty_summary=uncertainty_summary,
        internal_exposure_estimate=internal_exposure_estimate,
        point_of_departure_reference=point_of_departure_reference,
        uncertainty_register_reference=uncertainty_register_reference,
    )
    ber_input_bundle, ber_warnings = _build_ber_input_bundle(
        payload,
        internal_exposure_estimate=internal_exposure_estimate,
        point_of_departure_reference=point_of_departure_reference,
        uncertainty_summary=uncertainty_summary,
        qualification_summary=qualification_summary,
    )

    return IngestExternalPbpkBundleResponse(
        tool=TOOL_NAME,
        contractVersion=CONTRACT_VERSION,
        externalRun=external_run,
        ngraObjects={
            "assessmentContext": assessment_context,
            "pbpkQualificationSummary": qualification_summary,
            "uncertaintySummary": uncertainty_summary,
            "uncertaintyHandoff": uncertainty_handoff,
            "internalExposureEstimate": internal_exposure_estimate,
            "uncertaintyRegisterReference": uncertainty_register_reference,
            "pointOfDepartureReference": point_of_departure_reference,
            "berInputBundle": ber_input_bundle,
        },
        warnings=list(
            dict.fromkeys(
                [
                    *internal_warnings,
                    *uncertainty_register_warnings,
                    *pod_warnings,
                    *ber_warnings,
                ]
            )
        ),
    )


__all__ = [
    "IngestExternalPbpkBundleRequest",
    "IngestExternalPbpkBundleResponse",
    "ingest_external_pbpk_bundle",
]
