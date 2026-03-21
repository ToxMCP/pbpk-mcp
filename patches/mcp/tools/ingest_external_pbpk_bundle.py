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


def _normalize_token(value: object | None) -> str | None:
    candidate = _safe_text(value)
    if candidate is None:
        return None
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in candidate)
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return normalized.strip("-") or None


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


def _build_pbpk_qualification_summary(payload: IngestExternalPbpkBundleRequest) -> dict[str, Any]:
    qualification = _as_mapping(payload.qualification)
    state = _derive_external_qualification_state(qualification)
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

    limitations: list[str] = []
    if performance_boundary == "runtime-or-internal-evidence-only":
        limitations.append(
            "Imported performance evidence is limited to runtime or internal supporting evidence."
        )
    elif performance_boundary == "no-bundled-performance-evidence":
        limitations.append(
            "No bundled predictive-performance evidence were attached to the imported PBPK bundle."
        )

    return {
        "objectType": "pbpkQualificationSummary.v1",
        "objectId": f"{payload.source_platform.lower()}-qualification-summary",
        "simulationId": None,
        "backend": EXTERNAL_BACKEND,
        "sourcePlatform": payload.source_platform,
        "assessmentBoundary": "external-pbpk-normalization-only",
        "decisionBoundary": "no-ngra-decision-policy",
        "state": state,
        "label": qualification.get("label") or state.replace("-", " ").title(),
        "summary": qualification.get("summary")
        or "External PBPK qualification metadata were normalized without executing the upstream platform.",
        "qualificationLevel": qualification.get("evidenceLevel") or qualification.get("qualificationLevel") or "unreported",
        "oecdReadiness": qualification.get("oecdReadiness") or "external-imported",
        "validationDecision": None,
        "withinDeclaredContext": None,
        "scientificProfile": bool(qualification or payload.assessment_context or payload.internal_exposure),
        "riskAssessmentReady": state == "qualified-within-context",
        "checklistScore": qualification.get("checklistScore"),
        "evidenceStatus": qualification.get("verificationStatus") or "imported",
        "profileSource": "external-import",
        "missingEvidenceCount": int(qualification.get("missingEvidenceCount") or 0),
        "performanceEvidenceBoundary": performance_boundary,
        "executableVerificationStatus": qualification.get("verificationStatus") or "not-run-in-pbpk-mcp",
        "platformClass": qualification.get("platformClass"),
        "validationReferences": _normalize_text_list(qualification.get("validationReferences")),
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
        "requestedTargetOutput": target_output,
        "selectionStatus": "explicit" if target_output else ("imported-selected" if has_metric else "unresolved"),
        "selectedOutput": selected_output if has_metric else None,
        "candidateOutputCount": 1 if has_metric else 0,
        "candidateOutputs": [selected_output] if has_metric else [],
        "candidateOutputsTruncated": False,
        "supports": {
            "deterministicMetricSelection": has_metric,
            "populationDistributionSummary": bool(_as_mapping(internal.get("distribution"))),
            "externalBerHandoff": has_metric,
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
