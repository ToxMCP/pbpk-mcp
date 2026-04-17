"""Helpers for exposing top-level trust-surface rendering requirements."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _unique_texts(*groups: Any) -> list[str]:
    items: list[str] = []
    for group in groups:
        if isinstance(group, (list, tuple)):
            candidates = group
        else:
            candidates = [group]
        for candidate in candidates:
            text = _text(candidate)
            if text and text not in items:
                items.append(text)
    return items


def _block_reason_codes(export_block_policy: Mapping[str, Any] | None) -> list[str]:
    codes: list[str] = []
    for entry in (_as_mapping(export_block_policy).get("blockReasons") or []):
        code = _text(_as_mapping(entry).get("code"))
        if code and code not in codes:
            codes.append(code)
    return codes


def _build_surface(
    *,
    surface_path: str,
    surface_type: str,
    summary: str,
    required_adjacent_paths: list[str],
    block_reason_codes: list[str],
    operator_signoff_path: str | None = None,
    operator_governance_path: str | None = None,
    applies_per_item: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "surfacePath": surface_path,
        "surfaceType": surface_type,
        "requiresContextualRendering": True,
        "refuseBareRendering": True,
        "requiredAdjacentPaths": required_adjacent_paths,
        "primaryBlockReasonCodes": block_reason_codes,
        "plainLanguageSummary": summary,
    }
    if operator_signoff_path:
        payload["operatorReviewSignoffPath"] = operator_signoff_path
    if operator_governance_path:
        payload["operatorReviewGovernancePath"] = operator_governance_path
    if applies_per_item:
        payload["appliesPerItem"] = True
    return payload


def build_trust_surface_contract(payload: Mapping[str, Any], *, tool_name: str) -> dict[str, Any] | None:
    if tool_name == "validate_model_manifest":
        curation = _as_mapping(payload.get("curationSummary"))
        if not curation:
            return None
        surface = _build_surface(
            surface_path="curationSummary",
            surface_type="static-curation-summary",
            summary=(
                "Do not render the static curation label alone. Carry the curation summary, "
                "caution summary, transport risk, anti-misread guidance, and block reasons together."
            ),
            required_adjacent_paths=_unique_texts(
                "curationSummary.reviewLabel",
                "curationSummary.humanSummary",
                "curationSummary.regulatoryBenchmarkReadiness",
                "curationSummary.regulatoryBenchmarkReadiness.prioritizedGaps",
                "curationSummary.regulatoryBenchmarkReadiness.recommendedNextArtifacts",
                "curationSummary.cautionSummary",
                "curationSummary.summaryTransportRisk",
                "curationSummary.misreadRiskSummary",
                "curationSummary.exportBlockPolicy",
                "curationSummary.renderingGuardrails",
            ),
            block_reason_codes=_block_reason_codes(curation.get("exportBlockPolicy")),
        )
        return {
            "summaryVersion": "pbpk-trust-surface-contract.v1",
            "tool": tool_name,
            "trustBearing": True,
            "requiresContextualRendering": True,
            "clientDirective": "carry-adjacent-caveats-and-refuse-lossy-thin-views",
            "surfaceCount": 1,
            "surfaces": [surface],
        }

    if tool_name == "discover_models":
        items = payload.get("items") or []
        sample = next(
            (
                _as_mapping(item).get("curationSummary")
                for item in items
                if isinstance(_as_mapping(item).get("curationSummary"), Mapping)
            ),
            None,
        )
        curation = _as_mapping(sample)
        if not curation:
            return None
        surface = _build_surface(
            surface_path="items[*].curationSummary",
            surface_type="discovery-curation-summary-list",
            summary=(
                "Apply the curation guardrails to each discovered model item. Do not render a discovery "
                "label or trust-bearing badge without the nearby caution, transport-risk, and anti-misread context."
            ),
            required_adjacent_paths=_unique_texts(
                "items[*].curationSummary.reviewLabel",
                "items[*].curationSummary.humanSummary",
                "items[*].curationSummary.regulatoryBenchmarkReadiness",
                "items[*].curationSummary.regulatoryBenchmarkReadiness.prioritizedGaps",
                "items[*].curationSummary.regulatoryBenchmarkReadiness.recommendedNextArtifacts",
                "items[*].curationSummary.cautionSummary",
                "items[*].curationSummary.summaryTransportRisk",
                "items[*].curationSummary.misreadRiskSummary",
                "items[*].curationSummary.exportBlockPolicy",
                "items[*].curationSummary.renderingGuardrails",
            ),
            block_reason_codes=_block_reason_codes(curation.get("exportBlockPolicy")),
            applies_per_item=True,
        )
        return {
            "summaryVersion": "pbpk-trust-surface-contract.v1",
            "tool": tool_name,
            "trustBearing": True,
            "requiresContextualRendering": True,
            "clientDirective": "carry-adjacent-caveats-and-refuse-lossy-thin-views",
            "surfaceCount": 1,
            "surfaces": [surface],
        }

    if tool_name == "validate_simulation_request":
        qualification = _as_mapping(_as_mapping(payload.get("ngraObjects")).get("pbpkQualificationSummary"))
        if not qualification:
            return None
        surface = _build_surface(
            surface_path="ngraObjects.pbpkQualificationSummary",
            surface_type="qualification-summary",
            summary=(
                "Do not render qualification-facing state alone. Carry review status, evidence basis, "
                "claim boundaries, missing-evidence context, caution summary, warnings, benchmark advisory signals, "
                "and operator sign-off context together."
            ),
            required_adjacent_paths=_unique_texts(
                "qualificationState",
                "evidenceBasis",
                "workflowClaimBoundaries",
                "cautionSummary",
                "missingEvidence",
                "warnings",
                "dossierImprovementSignals",
                "ngraObjects.pbpkQualificationSummary.reviewStatus",
                "ngraObjects.pbpkQualificationSummary.evidenceBasis",
                "ngraObjects.pbpkQualificationSummary.workflowClaimBoundaries",
                "ngraObjects.pbpkQualificationSummary.cautionSummary",
                "ngraObjects.pbpkQualificationSummary.exportBlockPolicy",
                "operatorReviewSignoff",
                "operatorReviewGovernance",
            ),
            block_reason_codes=_block_reason_codes(qualification.get("exportBlockPolicy")),
            operator_signoff_path="operatorReviewSignoff",
            operator_governance_path="operatorReviewGovernance",
        )
        return {
            "summaryVersion": "pbpk-trust-surface-contract.v1",
            "tool": tool_name,
            "trustBearing": True,
            "requiresContextualRendering": True,
            "clientDirective": "carry-adjacent-caveats-and-refuse-lossy-thin-views",
            "surfaceCount": 1,
            "surfaces": [surface],
        }

    if tool_name == "run_verification_checks":
        qualification_state = _as_mapping(payload.get("qualificationState"))
        if not qualification_state:
            return None
        surface = _build_surface(
            surface_path="qualificationState",
            surface_type="verification-qualification-state",
            summary=(
                "Do not render verification-facing qualification state alone. Carry workflow role, "
                "population support, evidence basis, claim boundaries, missing-evidence context, benchmark "
                "advisory signals, active warnings, and operator sign-off context together."
            ),
            required_adjacent_paths=_unique_texts(
                "qualificationState",
                "qualificationState.reviewStatus",
                "profile.workflowRole",
                "profile.populationSupport",
                "evidenceBasis",
                "workflowClaimBoundaries",
                "missingEvidence",
                "dossierImprovementSignals",
                "profile.evidenceBasis",
                "profile.workflowClaimBoundaries",
                "warnings",
                "operatorReviewSignoff",
                "operatorReviewGovernance",
            ),
            block_reason_codes=[],
            operator_signoff_path="operatorReviewSignoff",
            operator_governance_path="operatorReviewGovernance",
        )
        return {
            "summaryVersion": "pbpk-trust-surface-contract.v1",
            "tool": tool_name,
            "trustBearing": True,
            "requiresContextualRendering": True,
            "clientDirective": "carry-adjacent-caveats-and-refuse-lossy-thin-views",
            "surfaceCount": 1,
            "surfaces": [surface],
        }

    if tool_name == "export_oecd_report":
        report = _as_mapping(payload.get("report"))
        qualification = _as_mapping(_as_mapping(report.get("ngraObjects")).get("pbpkQualificationSummary"))
        human_review = _as_mapping(report.get("humanReviewSummary"))
        if not report or not human_review:
            return None
        surfaces = [
            _build_surface(
                surface_path="report.humanReviewSummary",
                surface_type="human-review-summary",
                summary=(
                    "Do not render the OECD human-review summary alone. Carry the caution summary, "
                    "transport risk, anti-misread section, missing-evidence context, benchmark advisory "
                    "signals, objective performance-evidence metrics, block reasons, and operator sign-off together."
                ),
                required_adjacent_paths=_unique_texts(
                    "report.humanReviewSummary.plainLanguageSummary",
                    "report.humanReviewSummary.reviewStatus",
                    "report.humanReviewSummary.cautionSummary",
                    "report.humanReviewSummary.summaryTransportRisk",
                    "report.humanReviewSummary.summaryTransportRisk",
                    "report.humanReviewSummary.exportBlockPolicy",
                    "report.missingEvidence",
                    "report.dossierImprovementSignals",
                    "report.performanceEvidence.objectiveMetrics",
                    "report.misreadRiskSummary",
                    "report.exportBlockPolicy",
                    "report.operatorReviewSignoff",
                    "report.operatorReviewGovernance",
                ),
                block_reason_codes=_block_reason_codes(
                    human_review.get("exportBlockPolicy") or report.get("exportBlockPolicy")
                ),
                operator_signoff_path="report.operatorReviewSignoff",
                operator_governance_path="report.operatorReviewGovernance",
            ),
        ]
        if qualification:
            surfaces.append(
                _build_surface(
                    surface_path="report.ngraObjects.pbpkQualificationSummary",
                    surface_type="qualification-summary",
                    summary=(
                        "Do not render the nested PBPK qualification summary alone. Carry review status, "
                        "evidence basis, claim boundaries, caution summary, missing-evidence context, "
                        "benchmark advisory signals, and report-level anti-misread context together."
                    ),
                    required_adjacent_paths=_unique_texts(
                        "report.ngraObjects.pbpkQualificationSummary.reviewStatus",
                        "report.ngraObjects.pbpkQualificationSummary.evidenceBasis",
                        "report.ngraObjects.pbpkQualificationSummary.workflowClaimBoundaries",
                        "report.ngraObjects.pbpkQualificationSummary.cautionSummary",
                        "report.ngraObjects.pbpkQualificationSummary.exportBlockPolicy",
                        "report.missingEvidence",
                        "report.dossierImprovementSignals",
                        "report.humanReviewSummary.summaryTransportRisk",
                        "report.misreadRiskSummary",
                        "report.operatorReviewSignoff",
                        "report.operatorReviewGovernance",
                    ),
                    block_reason_codes=_block_reason_codes(qualification.get("exportBlockPolicy")),
                    operator_signoff_path="report.operatorReviewSignoff",
                    operator_governance_path="report.operatorReviewGovernance",
                )
            )
        return {
            "summaryVersion": "pbpk-trust-surface-contract.v1",
            "tool": tool_name,
            "trustBearing": True,
            "requiresContextualRendering": True,
            "clientDirective": "carry-adjacent-caveats-and-refuse-lossy-thin-views",
            "surfaceCount": len(surfaces),
            "surfaces": surfaces,
        }

    return None


def attach_trust_surface_contract(payload: dict[str, Any], *, tool_name: str) -> dict[str, Any] | None:
    contract = build_trust_surface_contract(payload, tool_name=tool_name)
    if contract is None:
        return None
    payload["trustSurfaceContract"] = dict(contract)
    return contract


__all__ = [
    "attach_trust_surface_contract",
    "build_trust_surface_contract",
]
