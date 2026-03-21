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
    return {
        "objectType": "pbpkQualificationSummary.v1",
        "objectId": f"{payload.source_platform.lower()}-qualification-summary",
        "simulationId": None,
        "backend": EXTERNAL_BACKEND,
        "sourcePlatform": payload.source_platform,
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
        "performanceEvidenceBoundary": qualification.get("performanceEvidenceBoundary"),
        "executableVerificationStatus": qualification.get("verificationStatus") or "not-run-in-pbpk-mcp",
        "platformClass": qualification.get("platformClass"),
        "validationReferences": _normalize_text_list(qualification.get("validationReferences")),
    }


def _build_uncertainty_summary(payload: IngestExternalPbpkBundleRequest) -> dict[str, Any]:
    uncertainty = _as_mapping(payload.uncertainty)
    return {
        "objectType": "uncertaintySummary.v1",
        "objectId": f"{payload.source_platform.lower()}-uncertainty-summary",
        "simulationId": None,
        "backend": EXTERNAL_BACKEND,
        "sourcePlatform": payload.source_platform,
        "status": uncertainty.get("status") or "unreported",
        "summary": uncertainty.get("summary"),
        "evidenceSource": uncertainty.get("source") or "external-import",
        "sources": _normalize_text_list(uncertainty.get("sources")),
        "issueCount": int(uncertainty.get("issueCount") or 0),
        "evidenceRowCount": int(uncertainty.get("evidenceRowCount") or 0),
        "totalEvidenceRows": int(uncertainty.get("totalEvidenceRows") or 0),
        "hasSensitivityAnalysis": bool(
            uncertainty.get("hasSensitivityAnalysis") or uncertainty.get("sensitivityAnalysis")
        ),
        "hasVariabilityApproach": bool(
            uncertainty.get("hasVariabilityApproach") or uncertainty.get("variabilityApproach")
        ),
        "hasVariabilityPropagation": bool(
            uncertainty.get("hasVariabilityPropagation") or uncertainty.get("variabilityPropagation")
        ),
        "hasResidualUncertainty": bool(
            uncertainty.get("hasResidualUncertainty") or uncertainty.get("residualUncertainty")
        ),
        "bundleMetadata": _as_mapping(uncertainty.get("bundleMetadata")) or None,
    }


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
        "status": "available" if has_metric else "not-available",
        "resultsId": _safe_text(internal.get("resultsId")) or _safe_text(internal.get("runId")),
        "source": "external-import",
        "requestedTargetOutput": target_output,
        "selectionStatus": "explicit" if target_output else ("imported-selected" if has_metric else "unresolved"),
        "selectedOutput": selected_output if has_metric else None,
        "candidateOutputCount": 1 if has_metric else 0,
        "candidateOutputs": [selected_output] if has_metric else [],
        "candidateOutputsTruncated": False,
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


def _build_ber_input_bundle(
    payload: IngestExternalPbpkBundleRequest,
    *,
    internal_exposure_estimate: Mapping[str, Any],
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
        "status": (
            "ready-for-external-ber-calculation" if not blocking_reasons else "incomplete"
        ),
        "comparisonMetric": comparison_metric,
        "internalExposureEstimateRef": internal_exposure_estimate.get("objectId"),
        "internalExposureMetric": internal_metric,
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
    ber_input_bundle, ber_warnings = _build_ber_input_bundle(
        payload,
        internal_exposure_estimate=internal_exposure_estimate,
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
            "internalExposureEstimate": internal_exposure_estimate,
            "berInputBundle": ber_input_bundle,
        },
        warnings=list(dict.fromkeys([*internal_warnings, *ber_warnings])),
    )


__all__ = [
    "IngestExternalPbpkBundleRequest",
    "IngestExternalPbpkBundleResponse",
    "ingest_external_pbpk_bundle",
]
