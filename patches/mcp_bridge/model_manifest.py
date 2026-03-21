"""Static manifest validation helpers for supported PBPK model files."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SUPPORTED_MODEL_EXTENSIONS = {
    ".pkml": "ospsuite",
    ".r": "rxode2",
}

_R_HOOK_PATTERNS = {
    "modelProfile": re.compile(r"\bpbpk_model_profile\s*<-"),
    "validationHook": re.compile(r"\bpbpk_validate_request\s*<-"),
    "deterministicSimulation": re.compile(r"\bpbpk_run_simulation\s*<-"),
    "populationSimulation": re.compile(r"\bpbpk_run_population\s*<-"),
    "parameterTable": re.compile(r"\bpbpk_parameter_table\s*<-"),
    "performanceEvidence": re.compile(r"\bpbpk_performance_evidence\s*<-"),
    "uncertaintyEvidence": re.compile(r"\bpbpk_uncertainty_evidence\s*<-"),
    "verificationEvidence": re.compile(r"\bpbpk_verification_evidence\s*<-"),
    "platformQualificationEvidence": re.compile(r"\bpbpk_platform_qualification_evidence\s*<-"),
    "runtimeVerificationHook": re.compile(r"\bpbpk_run_verification_checks\s*<-"),
}
_R_SECTION_PATTERNS = {
    "contextOfUse": re.compile(r"\bcontextOfUse\s*="),
    "applicabilityDomain": re.compile(r"\bapplicabilityDomain\s*="),
    "modelPerformance": re.compile(r"\bmodelPerformance\s*="),
    "parameterProvenance": re.compile(r"\bparameterProvenance\s*="),
    "uncertainty": re.compile(r"\buncertainty\s*="),
    "implementationVerification": re.compile(r"\bimplementationVerification\s*="),
    "platformQualification": re.compile(r"\bplatformQualification\s*="),
    "peerReview": re.compile(r"\bpeerReview\s*="),
}
_REQUIRED_SECTION_FIELDS = {
    "contextOfUse": ("scientificPurpose", "decisionContext", "regulatoryUse"),
    "applicabilityDomain": ("type", "qualificationLevel"),
    "modelPerformance": ("status",),
    "parameterProvenance": ("status",),
    "uncertainty": ("status",),
    "implementationVerification": ("status",),
    "platformQualification": ("status",),
    "peerReview": ("status",),
}
_EXAMPLE_QUALIFICATIONS = {"demo-only", "illustrative-example", "integration-example"}
_RESEARCH_QUALIFICATIONS = {
    "research-use",
    "research-only",
    "runtime-guardrails",
    "runtime-load-verified",
}
_REGULATORY_QUALIFICATIONS = {
    "fit-for-purpose",
    "qualified",
    "externally-qualified",
    "regulatory-use",
    "regulatory-qualified",
}


def ospsuite_profile_sidecar_candidates(file_path: Path) -> tuple[Path, ...]:
    stem = file_path.with_suffix("")
    return (
        Path(f"{stem}.profile.json"),
        Path(f"{stem}.pbpk.json"),
        Path(f"{file_path}.profile.json"),
    )


def performance_evidence_sidecar_candidates(file_path: Path) -> tuple[Path, ...]:
    stem = file_path.with_suffix("")
    return (
        Path(f"{stem}.performance.json"),
        Path(f"{stem}.performance-evidence.json"),
        Path(f"{file_path}.performance.json"),
        Path(f"{file_path}.performance-evidence.json"),
    )


def uncertainty_evidence_sidecar_candidates(file_path: Path) -> tuple[Path, ...]:
    stem = file_path.with_suffix("")
    return (
        Path(f"{stem}.uncertainty.json"),
        Path(f"{stem}.uncertainty-evidence.json"),
        Path(f"{file_path}.uncertainty.json"),
        Path(f"{file_path}.uncertainty-evidence.json"),
    )


def parameter_table_sidecar_candidates(file_path: Path) -> tuple[Path, ...]:
    stem = file_path.with_suffix("")
    return (
        Path(f"{stem}.parameters.json"),
        Path(f"{stem}.parameter-table.json"),
        Path(f"{file_path}.parameters.json"),
        Path(f"{file_path}.parameter-table.json"),
    )


def normalize_token(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return None
    candidate = str(value).strip().lower()
    if not candidate:
        return None
    normalized = re.sub(r"[^a-z0-9]+", "-", candidate).strip("-")
    return normalized or None


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        candidate = value.strip()
        return candidate or None
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            resolved = _safe_text(item)
            if resolved:
                return resolved
        return None
    return str(value)


def _issue(code: str, message: str, *, field: str | None = None, severity: str = "error") -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "field": field,
        "severity": severity,
    }


def _section_status(section_name: str, payload: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    required_fields = _REQUIRED_SECTION_FIELDS.get(section_name, ())

    if payload is None:
        issues.append(
            _issue(
                "section_missing",
                f"Section '{section_name}' is not declared in the manifest.",
                field=f"profile.{section_name}",
            )
        )
        return {
            "present": False,
            "declaredFields": [],
            "missingFields": list(required_fields),
            "summary": None,
        }, issues

    if isinstance(payload, Mapping):
        declared_fields = []
        missing_fields = []
        for field in required_fields:
            value = payload.get(field)
            if isinstance(value, Mapping):
                if len(value) > 0:
                    declared_fields.append(field)
                else:
                    missing_fields.append(field)
            elif _safe_text(value):
                declared_fields.append(field)
            else:
                missing_fields.append(field)
        if missing_fields:
            issues.append(
                _issue(
                    "section_incomplete",
                    f"Section '{section_name}' is missing required fields: {', '.join(missing_fields)}.",
                    field=f"profile.{section_name}",
                )
            )
        return {
            "present": True,
            "declaredFields": declared_fields,
            "missingFields": missing_fields,
            "summary": _safe_text(payload.get("summary") or payload.get("status")),
        }, issues

    summary = _safe_text(payload)
    if required_fields:
        issues.append(
            _issue(
                "section_scalar_only",
                f"Section '{section_name}' is declared only as a scalar summary and does not expose the required fields.",
                field=f"profile.{section_name}",
                severity="warning",
            )
        )
    return {
        "present": bool(summary),
        "declaredFields": [],
        "missingFields": list(required_fields),
        "summary": summary,
    }, issues


def _manifest_status(issues: Sequence[Mapping[str, Any]], has_scientific_profile: bool, core_complete: bool) -> str:
    error_count = sum(1 for issue in issues if str(issue.get("severity")) == "error")
    if not has_scientific_profile:
        return "missing"
    if error_count == 0 and core_complete:
        return "valid"
    return "partial"


def derive_qualification_state(
    *,
    scientific_profile: bool,
    profile_source: str | None,
    qualification_level: str | None,
    core_sections_complete: bool,
    evidence_sections_complete: bool,
) -> dict[str, Any]:
    token = normalize_token(qualification_level)
    source_token = normalize_token(profile_source)

    if not scientific_profile or source_token in {None, "bridge-default"}:
      state = "exploratory"
      label = "Exploratory"
      summary = "Runtime format is supported, but no model-specific scientific manifest is declared."
      risk_ready = False
    elif token in _EXAMPLE_QUALIFICATIONS:
      state = "illustrative-example"
      label = "Illustrative example"
      summary = "Manifest identifies this model as an example or integration fixture."
      risk_ready = False
    elif token in _RESEARCH_QUALIFICATIONS:
      state = "research-use"
      label = "Research use"
      summary = "Manifest supports research-oriented use within declared guardrails, not regulatory qualification."
      risk_ready = False
    elif token in _REGULATORY_QUALIFICATIONS:
      if core_sections_complete and evidence_sections_complete:
          state = "qualified-within-context"
          label = "Qualified within context"
          summary = "Manifest declares a qualification-oriented context with the key dossier sections in place."
          risk_ready = True
      else:
          state = "regulatory-candidate"
          label = "Regulatory candidate"
          summary = "Manifest targets qualification-oriented use, but dossier completeness is still partial."
          risk_ready = False
    else:
      if core_sections_complete:
          state = "regulatory-candidate"
          label = "Regulatory candidate"
          summary = "Manifest is structured enough to be developed toward qualification, but the declared state is incomplete."
      else:
          state = "research-use"
          label = "Research use"
          summary = "Manifest is partially structured but not complete enough for qualification-oriented claims."
      risk_ready = False

    return {
        "state": state,
        "label": label,
        "summary": summary,
        "qualificationLevel": qualification_level,
        "riskAssessmentReady": risk_ready,
        "coreSectionsComplete": core_sections_complete,
        "evidenceSectionsComplete": evidence_sections_complete,
    }


def _validate_profile_manifest(
    profile: Mapping[str, Any],
    *,
    backend: str,
    profile_source: str | None,
    sidecar_path: str | None = None,
) -> dict[str, Any]:
    sections: dict[str, Any] = {}
    issues: list[dict[str, Any]] = []

    for section_name in _REQUIRED_SECTION_FIELDS:
        section_status, section_issues = _section_status(section_name, profile.get(section_name))
        sections[section_name] = section_status
        issues.extend(section_issues)

    qualification_level = None
    applicability = profile.get("applicabilityDomain")
    if isinstance(applicability, Mapping):
        qualification_level = _safe_text(applicability.get("qualificationLevel"))

    scientific_profile = profile_source not in {None, "bridge-default"}
    core_sections_complete = all(
        bool(section["present"]) and not section["missingFields"]
        for section in sections.values()
    )
    evidence_sections_complete = all(
        not sections[name]["missingFields"]
        for name in (
            "modelPerformance",
            "parameterProvenance",
            "uncertainty",
            "implementationVerification",
            "platformQualification",
            "peerReview",
        )
    )

    if sidecar_path:
        metadata = {"sidecarPath": sidecar_path}
    else:
        metadata = {}

    qualification_state = derive_qualification_state(
        scientific_profile=scientific_profile,
        profile_source=profile_source,
        qualification_level=qualification_level,
        core_sections_complete=core_sections_complete,
        evidence_sections_complete=evidence_sections_complete,
    )

    return {
        "validationMode": "static-manifest-inspection",
        "backend": backend,
        "scientificProfile": scientific_profile,
        "profileSource": profile_source,
        "qualificationLevel": qualification_level,
        "manifestStatus": _manifest_status(issues, scientific_profile, core_sections_complete),
        "qualificationState": qualification_state,
        "sections": sections,
        "issues": issues,
        **metadata,
    }


def _load_sidecar_profile(file_path: Path) -> tuple[dict[str, Any] | None, str | None, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    for candidate in ospsuite_profile_sidecar_candidates(file_path):
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(
                _issue(
                    "sidecar_parse_error",
                    f"Failed to parse sidecar JSON: {exc}",
                    field=str(candidate),
                )
            )
            return None, str(candidate), issues

        profile_payload = payload.get("profile", payload)
        if not isinstance(profile_payload, Mapping):
            issues.append(
                _issue(
                    "sidecar_profile_missing",
                    "Sidecar JSON must provide a top-level 'profile' object or itself be a profile object.",
                    field=str(candidate),
                )
            )
            return None, str(candidate), issues
        return dict(profile_payload), str(candidate), issues

    issues.append(
        _issue(
            "sidecar_missing",
            "No profile sidecar was found for this OSPSuite transfer file.",
            field=str(file_path),
        )
    )
    return None, None, issues


def _extract_performance_evidence_rows(payload: Any) -> list[Any] | None:
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        if payload and not isinstance(payload, Mapping):
            return list(payload)
    if not isinstance(payload, Mapping):
        return None

    candidates = (
        payload.get("rows"),
        payload.get("performanceEvidence", {}).get("rows") if isinstance(payload.get("performanceEvidence"), Mapping) else None,
        payload.get("performanceEvidence"),
        payload.get("evidence"),
    )
    for candidate in candidates:
        if isinstance(candidate, Sequence) and not isinstance(candidate, (str, bytes, bytearray)):
            return list(candidate)
    return None


def _extract_performance_evidence_metadata(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    metadata = payload.get("metadata")
    if metadata is None and isinstance(payload.get("performanceEvidence"), Mapping):
        metadata = payload["performanceEvidence"].get("metadata")
    if not isinstance(metadata, Mapping):
        return None
    return dict(metadata)


def _extract_uncertainty_evidence_rows(payload: Any) -> list[Any] | None:
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        if payload and not isinstance(payload, Mapping):
            return list(payload)
    if not isinstance(payload, Mapping):
        return None

    candidates = (
        payload.get("rows"),
        payload.get("uncertaintyEvidence", {}).get("rows") if isinstance(payload.get("uncertaintyEvidence"), Mapping) else None,
        payload.get("uncertaintyEvidence"),
        payload.get("evidence"),
    )
    for candidate in candidates:
        if isinstance(candidate, Sequence) and not isinstance(candidate, (str, bytes, bytearray)):
            return list(candidate)
    return None


def _extract_uncertainty_evidence_metadata(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    metadata = payload.get("metadata")
    if metadata is None and isinstance(payload.get("uncertaintyEvidence"), Mapping):
        metadata = payload["uncertaintyEvidence"].get("metadata")
    if not isinstance(metadata, Mapping):
        return None
    return dict(metadata)


def _extract_parameter_table_rows(payload: Any) -> list[Any] | None:
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        if payload and not isinstance(payload, Mapping):
            return list(payload)
    if not isinstance(payload, Mapping):
        return None

    candidates = (
        payload.get("rows"),
        payload.get("parameterTable", {}).get("rows") if isinstance(payload.get("parameterTable"), Mapping) else None,
        payload.get("parameters"),
    )
    for candidate in candidates:
        if isinstance(candidate, Sequence) and not isinstance(candidate, (str, bytes, bytearray)):
            return list(candidate)
    return None


def _extract_parameter_table_metadata(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    metadata = payload.get("metadata")
    if metadata is None and isinstance(payload.get("parameterTable"), Mapping):
        metadata = payload["parameterTable"].get("metadata")
    if not isinstance(metadata, Mapping):
        return None
    return dict(metadata)


def _validate_performance_evidence_rows(rows: Sequence[Any], *, field_prefix: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for index, entry in enumerate(rows, start=1):
        if not isinstance(entry, Mapping):
            continue
        evidence_class = _safe_text(entry.get("evidenceClass") or entry.get("evidence_class")) or "other"
        row_id = _safe_text(entry.get("id")) or f"row-{index:03d}"
        row_field_prefix = f"{field_prefix}[{index}]"

        def add_issue(code: str, message: str, field: str) -> None:
            issues.append(
                _issue(
                    code,
                    message,
                    field=field,
                    severity="warning",
                )
            )

        acceptance = _safe_text(entry.get("acceptanceCriterion") or entry.get("acceptance_criterion"))
        dataset = _safe_text(entry.get("dataset") or entry.get("datasetId") or entry.get("study"))
        qualification_basis = _safe_text(entry.get("qualificationBasis") or entry.get("qualification_basis"))

        if evidence_class == "runtime-smoke" and not acceptance:
            add_issue(
                "performance_row_acceptance_missing",
                f"Runtime smoke row '{row_id}' should declare an acceptanceCriterion.",
                f"{row_field_prefix}.acceptanceCriterion",
            )
        if evidence_class == "observed-vs-predicted":
            if entry.get("observedValue") is None:
                add_issue(
                    "performance_row_observed_missing",
                    f"Observed-versus-predicted row '{row_id}' should include observedValue.",
                    f"{row_field_prefix}.observedValue",
                )
            if entry.get("predictedValue") is None:
                add_issue(
                    "performance_row_predicted_missing",
                    f"Observed-versus-predicted row '{row_id}' should include predictedValue.",
                    f"{row_field_prefix}.predictedValue",
                )
            if not dataset:
                add_issue(
                    "performance_row_dataset_missing",
                    f"Observed-versus-predicted row '{row_id}' should identify the benchmark dataset or study.",
                    f"{row_field_prefix}.dataset",
                )
            if not acceptance:
                add_issue(
                    "performance_row_acceptance_missing",
                    f"Observed-versus-predicted row '{row_id}' should declare the comparison acceptanceCriterion.",
                    f"{row_field_prefix}.acceptanceCriterion",
                )
        if evidence_class == "predictive-dataset":
            if not dataset:
                add_issue(
                    "performance_row_dataset_missing",
                    f"Predictive-dataset row '{row_id}' should identify the dataset or benchmark package.",
                    f"{row_field_prefix}.dataset",
                )
            if not acceptance:
                add_issue(
                    "performance_row_acceptance_missing",
                    f"Predictive-dataset row '{row_id}' should declare the dataset-level acceptanceCriterion.",
                    f"{row_field_prefix}.acceptanceCriterion",
                )
        if evidence_class == "external-qualification":
            if not dataset and not qualification_basis:
                add_issue(
                    "performance_row_external_basis_missing",
                    f"External-qualification row '{row_id}' should declare a dataset or qualificationBasis.",
                    row_field_prefix,
                )
            if not acceptance:
                add_issue(
                    "performance_row_acceptance_missing",
                    f"External-qualification row '{row_id}' should declare the qualification acceptanceCriterion.",
                    f"{row_field_prefix}.acceptanceCriterion",
                )
    return issues


def _validate_performance_evidence_metadata(
    metadata: Mapping[str, Any] | None,
    *,
    field_prefix: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    metadata_dict = dict(metadata or {})
    if not _safe_text(metadata_dict.get("bundleVersion")):
        issues.append(
            _issue(
                "performance_bundle_version_missing",
                "Performance evidence bundle metadata should declare bundleVersion.",
                field=f"{field_prefix}.bundleVersion",
                severity="warning",
            )
        )
    if not _safe_text(metadata_dict.get("summary")):
        issues.append(
            _issue(
                "performance_bundle_summary_missing",
                "Performance evidence bundle metadata should declare summary.",
                field=f"{field_prefix}.summary",
                severity="warning",
            )
        )
    return issues


def _validate_uncertainty_evidence_rows(rows: Sequence[Any], *, field_prefix: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for index, entry in enumerate(rows, start=1):
        if not isinstance(entry, Mapping):
            continue
        kind = _safe_text(entry.get("kind") or entry.get("type")) or "unspecified"
        row_id = _safe_text(entry.get("id")) or f"row-{index:03d}"
        row_field_prefix = f"{field_prefix}[{index}]"

        def add_issue(code: str, message: str, field: str) -> None:
            issues.append(
                _issue(
                    code,
                    message,
                    field=field,
                    severity="warning",
                )
            )

        summary = _safe_text(entry.get("summary") or entry.get("description"))
        method = _safe_text(entry.get("method"))
        metric = _safe_text(entry.get("metric") or entry.get("metricName") or entry.get("metric_name"))
        target_output = _safe_text(entry.get("targetOutput") or entry.get("target_output") or entry.get("output"))
        varied_parameters = entry.get("variedParameters") or entry.get("parameters")
        has_varied_parameters = isinstance(varied_parameters, Sequence) and not isinstance(varied_parameters, (str, bytes, bytearray)) and len(varied_parameters) > 0

        if kind == "variability-approach":
            if not summary and not method:
                add_issue(
                    "uncertainty_row_summary_missing",
                    f"Variability-approach row '{row_id}' should declare a method or summary.",
                    row_field_prefix,
                )
        elif kind in {"variability-propagation", "sensitivity-analysis"}:
            if not summary and not method:
                add_issue(
                    "uncertainty_row_summary_missing",
                    f"Uncertainty row '{row_id}' should declare a method or summary.",
                    row_field_prefix,
                )
            if not metric and not target_output and not has_varied_parameters:
                add_issue(
                    "uncertainty_row_scope_missing",
                    f"Uncertainty row '{row_id}' should declare a metric, targetOutput, or variedParameters.",
                    row_field_prefix,
                )
        elif kind == "residual-uncertainty":
            if not summary:
                add_issue(
                    "uncertainty_row_summary_missing",
                    f"Residual-uncertainty row '{row_id}' should declare a summary.",
                    f"{row_field_prefix}.summary",
                )
    return issues


def _validate_uncertainty_evidence_metadata(
    metadata: Mapping[str, Any] | None,
    *,
    field_prefix: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    metadata_dict = dict(metadata or {})
    if not _safe_text(metadata_dict.get("bundleVersion")):
        issues.append(
            _issue(
                "uncertainty_bundle_version_missing",
                "Uncertainty evidence bundle metadata should declare bundleVersion.",
                field=f"{field_prefix}.bundleVersion",
                severity="warning",
            )
        )
    if not _safe_text(metadata_dict.get("summary")):
        issues.append(
            _issue(
                "uncertainty_bundle_summary_missing",
                "Uncertainty evidence bundle metadata should declare summary.",
                field=f"{field_prefix}.summary",
                severity="warning",
            )
        )
    return issues


def _validate_parameter_table_rows(rows: Sequence[Any], *, field_prefix: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for index, entry in enumerate(rows, start=1):
        if not isinstance(entry, Mapping):
            continue
        row_id = _safe_text(entry.get("id") or entry.get("path")) or f"row-{index:03d}"
        row_field_prefix = f"{field_prefix}[{index}]"

        def add_issue(code: str, message: str, field: str) -> None:
            issues.append(
                _issue(
                    code,
                    message,
                    field=field,
                    severity="warning",
                )
            )

        path = _safe_text(entry.get("path"))
        if not path:
            add_issue(
                "parameter_row_path_missing",
                f"Parameter-table row '{row_id}' should declare a path.",
                f"{row_field_prefix}.path",
            )
            continue

        source = _safe_text(entry.get("source"))
        source_citation = _safe_text(entry.get("sourceCitation") or entry.get("source_citation"))
        source_table = _safe_text(entry.get("sourceTable") or entry.get("source_table"))
        source_type = _safe_text(entry.get("sourceType") or entry.get("source_type"))
        evidence_type = _safe_text(entry.get("evidenceType") or entry.get("evidence_type"))
        rationale = _safe_text(entry.get("rationale") or entry.get("motivation"))
        experimental_conditions = entry.get("experimentalConditions") or entry.get("testConditions") or entry.get("studyConditions")
        has_conditions = _safe_text(experimental_conditions) is not None or (
            isinstance(experimental_conditions, Sequence) and not isinstance(experimental_conditions, (str, bytes, bytearray)) and len(experimental_conditions) > 0
        )

        has_provenance = any(value is not None for value in (
            source,
            source_citation,
            source_table,
            source_type,
            evidence_type,
            rationale,
            _safe_text(entry.get("distribution") or entry.get("distributionType") or entry.get("distribution_type")),
            entry.get("mean"),
            entry.get("sd"),
            entry.get("standardDeviation"),
            entry.get("lowerBound"),
            entry.get("upperBound"),
            experimental_conditions,
        ))

        if has_provenance and not any(value is not None for value in (source, source_citation, source_table)):
            add_issue(
                "parameter_row_source_missing",
                f"Parameter row '{row_id}' declares provenance metadata but does not identify a source, citation, or source table.",
                row_field_prefix,
            )

        distribution = _safe_text(entry.get("distribution") or entry.get("distributionType") or entry.get("distribution_type"))
        if distribution and all(entry.get(field) is None for field in ("mean", "sd", "standardDeviation", "lowerBound", "upperBound")):
            add_issue(
                "parameter_row_distribution_details_missing",
                f"Parameter row '{row_id}' declares a distribution but does not provide supporting statistics or bounds.",
                f"{row_field_prefix}.distribution",
            )

        source_type_token = normalize_token(source_type)
        evidence_type_token = normalize_token(evidence_type)
        experimental_source = (
            bool(source_type_token and re.search(r"in-vitro|in-vivo|in-silico|experimental|study|guideline", source_type_token))
            or bool(evidence_type_token and re.search(r"experimental|study|literature", evidence_type_token))
        )
        if experimental_source and not has_conditions and rationale is None:
            add_issue(
                "parameter_row_conditions_missing",
                f"Parameter row '{row_id}' looks experimental or study-derived but does not declare study conditions or rationale.",
                row_field_prefix,
            )

    return issues


def _validate_parameter_table_metadata(
    metadata: Mapping[str, Any] | None,
    *,
    field_prefix: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    metadata_dict = dict(metadata or {})
    if not _safe_text(metadata_dict.get("bundleVersion")):
        issues.append(
            _issue(
                "parameter_table_bundle_version_missing",
                "Parameter-table bundle metadata should declare bundleVersion.",
                field=f"{field_prefix}.bundleVersion",
                severity="warning",
            )
        )
    if not _safe_text(metadata_dict.get("summary")):
        issues.append(
            _issue(
                "parameter_table_bundle_summary_missing",
                "Parameter-table bundle metadata should declare summary.",
                field=f"{field_prefix}.summary",
                severity="warning",
            )
        )
    return issues


def _load_performance_evidence_sidecar(
    file_path: Path,
) -> tuple[list[Any], dict[str, Any] | None, str | None, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    for candidate in performance_evidence_sidecar_candidates(file_path):
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(
                _issue(
                    "performance_sidecar_parse_error",
                    f"Failed to parse performance evidence sidecar JSON: {exc}",
                    field=str(candidate),
                    severity="warning",
                )
            )
            return [], None, str(candidate), issues

        rows = _extract_performance_evidence_rows(payload)
        metadata = _extract_performance_evidence_metadata(payload)
        if rows is None:
            issues.append(
                _issue(
                    "performance_sidecar_rows_missing",
                    "Performance evidence sidecar must provide 'rows', 'performanceEvidence.rows', or a top-level row array.",
                    field=str(candidate),
                    severity="warning",
                )
            )
            return [], metadata, str(candidate), issues
        issues.extend(_validate_performance_evidence_metadata(metadata, field_prefix=f"{candidate}:metadata"))
        issues.extend(_validate_performance_evidence_rows(rows, field_prefix=f"{candidate}:rows"))
        return rows, metadata, str(candidate), issues

    return [], None, None, issues


def _load_uncertainty_evidence_sidecar(
    file_path: Path,
) -> tuple[list[Any], dict[str, Any] | None, str | None, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    for candidate in uncertainty_evidence_sidecar_candidates(file_path):
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(
                _issue(
                    "uncertainty_sidecar_parse_error",
                    f"Failed to parse uncertainty evidence sidecar JSON: {exc}",
                    field=str(candidate),
                    severity="warning",
                )
            )
            return [], None, str(candidate), issues

        rows = _extract_uncertainty_evidence_rows(payload)
        metadata = _extract_uncertainty_evidence_metadata(payload)
        if rows is None:
            issues.append(
                _issue(
                    "uncertainty_sidecar_rows_missing",
                    "Uncertainty evidence sidecar must provide 'rows', 'uncertaintyEvidence.rows', or a top-level row array.",
                    field=str(candidate),
                    severity="warning",
                )
            )
            return [], metadata, str(candidate), issues
        issues.extend(_validate_uncertainty_evidence_metadata(metadata, field_prefix=f"{candidate}:metadata"))
        issues.extend(_validate_uncertainty_evidence_rows(rows, field_prefix=f"{candidate}:rows"))
        return rows, metadata, str(candidate), issues

    return [], None, None, issues


def _load_parameter_table_sidecar(
    file_path: Path,
) -> tuple[list[Any], dict[str, Any] | None, str | None, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    for candidate in parameter_table_sidecar_candidates(file_path):
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(
                _issue(
                    "parameter_table_sidecar_parse_error",
                    f"Failed to parse parameter-table sidecar JSON: {exc}",
                    field=str(candidate),
                    severity="warning",
                )
            )
            return [], None, str(candidate), issues

        rows = _extract_parameter_table_rows(payload)
        metadata = _extract_parameter_table_metadata(payload)
        if rows is None:
            issues.append(
                _issue(
                    "parameter_table_sidecar_rows_missing",
                    "Parameter-table sidecar must provide 'rows', 'parameterTable.rows', or a top-level row array.",
                    field=str(candidate),
                    severity="warning",
                )
            )
            return [], metadata, str(candidate), issues

        issues.extend(_validate_parameter_table_metadata(metadata, field_prefix=f"{candidate}:metadata"))
        issues.extend(_validate_parameter_table_rows(rows, field_prefix=f"{candidate}:rows"))
        return list(rows), metadata, str(candidate), issues

    return [], None, None, issues


def _extract_assignment(text: str, field_name: str) -> str | None:
    pattern = re.compile(rf"\b{re.escape(field_name)}\s*=\s*['\"]([^'\"]+)['\"]")
    match = pattern.search(text)
    if not match:
        return None
    candidate = match.group(1).strip()
    return candidate or None


def _validate_r_model(file_path: Path) -> dict[str, Any]:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    parameter_table_sidecar_rows, parameter_table_sidecar_metadata, parameter_table_sidecar_path, parameter_table_sidecar_issues = _load_parameter_table_sidecar(file_path)
    performance_sidecar_rows, performance_sidecar_metadata, performance_sidecar_path, performance_sidecar_issues = _load_performance_evidence_sidecar(file_path)
    uncertainty_sidecar_rows, uncertainty_sidecar_metadata, uncertainty_sidecar_path, uncertainty_sidecar_issues = _load_uncertainty_evidence_sidecar(file_path)
    hooks = {
        name: bool(pattern.search(text))
        for name, pattern in _R_HOOK_PATTERNS.items()
    }
    hooks["parameterTableSidecar"] = parameter_table_sidecar_path is not None
    hooks["performanceEvidenceSidecar"] = performance_sidecar_path is not None
    hooks["uncertaintyEvidenceSidecar"] = uncertainty_sidecar_path is not None
    sections = {
        name: {
            "present": bool(pattern.search(text)),
            "declaredFields": [],
            "missingFields": [],
            "summary": None,
        }
        for name, pattern in _R_SECTION_PATTERNS.items()
    }

    issues: list[dict[str, Any]] = []
    issues.extend(parameter_table_sidecar_issues)
    issues.extend(performance_sidecar_issues)
    issues.extend(uncertainty_sidecar_issues)
    if not hooks["modelProfile"]:
        issues.append(
            _issue(
                "profile_hook_missing",
                "R model does not declare pbpk_model_profile(...).",
                field=str(file_path),
            )
        )
    if not hooks["validationHook"]:
        issues.append(
            _issue(
                "validation_hook_missing",
                "R model does not declare pbpk_validate_request(...).",
                field=str(file_path),
                severity="warning",
            )
        )
    if not hooks["parameterTable"] and not hooks["parameterTableSidecar"]:
        issues.append(
            _issue(
                "parameter_table_hook_missing",
                "R model does not declare pbpk_parameter_table(...) and no parameter-table sidecar was found.",
                field=str(file_path),
                severity="warning",
            )
        )
    if not hooks["performanceEvidence"] and not hooks["performanceEvidenceSidecar"]:
        issues.append(
            _issue(
                "performance_evidence_hook_missing",
                "R model does not declare pbpk_performance_evidence(...) and no performance evidence sidecar was found.",
                field=str(file_path),
                severity="warning",
            )
        )
    if not hooks["uncertaintyEvidence"] and not hooks["uncertaintyEvidenceSidecar"]:
        issues.append(
            _issue(
                "uncertainty_evidence_hook_missing",
                "R model does not declare pbpk_uncertainty_evidence(...) and no uncertainty evidence sidecar was found.",
                field=str(file_path),
                severity="warning",
            )
        )
    if not hooks["verificationEvidence"]:
        issues.append(
            _issue(
                "verification_evidence_hook_missing",
                "R model does not declare pbpk_verification_evidence(...).",
                field=str(file_path),
                severity="warning",
            )
        )
    if not hooks["platformQualificationEvidence"]:
        issues.append(
            _issue(
                "platform_qualification_evidence_hook_missing",
                "R model does not declare pbpk_platform_qualification_evidence(...).",
                field=str(file_path),
                severity="warning",
            )
        )

    for name, status in sections.items():
        if not status["present"]:
            issues.append(
                _issue(
                    "profile_section_not_detected",
                    f"Could not detect profile section '{name}' in the R module text.",
                    field=f"{file_path}:{name}",
                    severity="warning",
                )
            )

    qualification_level = _extract_assignment(text, "qualificationLevel")
    scientific_profile = hooks["modelProfile"]
    profile_source = "module-hook-detected" if scientific_profile else "bridge-default"
    core_sections_complete = scientific_profile and hooks["validationHook"] and all(
        status["present"] for status in sections.values()
    )
    evidence_sections_complete = (
        (hooks["parameterTable"] or hooks["parameterTableSidecar"]) and
        (hooks["performanceEvidence"] or hooks["performanceEvidenceSidecar"]) and
        (hooks["uncertaintyEvidence"] or hooks["uncertaintyEvidenceSidecar"]) and
        hooks["verificationEvidence"] and
        hooks["platformQualificationEvidence"] and
        all(
        sections[name]["present"]
        for name in (
            "modelPerformance",
            "parameterProvenance",
            "uncertainty",
            "implementationVerification",
            "platformQualification",
            "peerReview",
        )
        )
    )

    return {
        "validationMode": "static-manifest-inspection",
        "backend": "rxode2",
        "scientificProfile": scientific_profile,
        "profileSource": profile_source,
        "qualificationLevel": qualification_level,
        "manifestStatus": _manifest_status(issues, scientific_profile, core_sections_complete),
        "qualificationState": derive_qualification_state(
            scientific_profile=scientific_profile,
            profile_source=profile_source,
            qualification_level=qualification_level,
            core_sections_complete=core_sections_complete,
            evidence_sections_complete=evidence_sections_complete,
        ),
        "hooks": hooks,
        "sections": sections,
        "issues": issues,
        "supplementalEvidence": {
            "parameterTableSidecarPath": parameter_table_sidecar_path,
            "parameterTableRowCount": len(parameter_table_sidecar_rows),
            "parameterTableBundleMetadata": parameter_table_sidecar_metadata,
            "performanceEvidenceSidecarPath": performance_sidecar_path,
            "performanceEvidenceRowCount": len(performance_sidecar_rows),
            "performanceEvidenceBundleMetadata": performance_sidecar_metadata,
            "uncertaintyEvidenceSidecarPath": uncertainty_sidecar_path,
            "uncertaintyEvidenceRowCount": len(uncertainty_sidecar_rows),
            "uncertaintyEvidenceBundleMetadata": uncertainty_sidecar_metadata,
        },
    }


def validate_model_manifest(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path).expanduser().resolve()
    suffix = path.suffix.lower()
    backend = SUPPORTED_MODEL_EXTENSIONS.get(suffix)
    if backend is None:
        raise ValueError(f"Unsupported model manifest type for '{path}'")
    if not path.is_file():
        raise FileNotFoundError(path)

    if backend == "ospsuite":
        profile, sidecar_path, sidecar_issues = _load_sidecar_profile(path)
        parameter_table_sidecar_rows, parameter_table_sidecar_metadata, parameter_table_sidecar_path, parameter_table_sidecar_issues = _load_parameter_table_sidecar(path)
        performance_sidecar_rows, performance_sidecar_metadata, performance_sidecar_path, performance_sidecar_issues = _load_performance_evidence_sidecar(path)
        uncertainty_sidecar_rows, uncertainty_sidecar_metadata, uncertainty_sidecar_path, uncertainty_sidecar_issues = _load_uncertainty_evidence_sidecar(path)
        if profile is None:
            scientific_profile = False
            return {
                "filePath": str(path),
                "backend": backend,
                "runtimeFormat": suffix.lstrip("."),
                "manifest": {
                    "validationMode": "static-manifest-inspection",
                    "backend": backend,
                    "scientificProfile": scientific_profile,
                    "profileSource": "bridge-default",
                    "qualificationLevel": None,
                    "manifestStatus": "missing",
                    "qualificationState": derive_qualification_state(
                        scientific_profile=False,
                        profile_source="bridge-default",
                        qualification_level=None,
                        core_sections_complete=False,
                        evidence_sections_complete=False,
                    ),
                    "sections": {},
                    "issues": [*sidecar_issues, *parameter_table_sidecar_issues, *performance_sidecar_issues, *uncertainty_sidecar_issues],
                    "sidecarPath": sidecar_path,
                    "supplementalEvidence": {
                        "parameterTableSidecarPath": parameter_table_sidecar_path,
                        "parameterTableRowCount": len(parameter_table_sidecar_rows),
                        "parameterTableBundleMetadata": parameter_table_sidecar_metadata,
                        "performanceEvidenceSidecarPath": performance_sidecar_path,
                        "performanceEvidenceRowCount": len(performance_sidecar_rows),
                        "performanceEvidenceBundleMetadata": performance_sidecar_metadata,
                        "uncertaintyEvidenceSidecarPath": uncertainty_sidecar_path,
                        "uncertaintyEvidenceRowCount": len(uncertainty_sidecar_rows),
                        "uncertaintyEvidenceBundleMetadata": uncertainty_sidecar_metadata,
                    },
                },
            }

        manifest = _validate_profile_manifest(
            profile,
            backend=backend,
            profile_source="sidecar",
            sidecar_path=sidecar_path,
        )
        manifest["issues"] = [*sidecar_issues, *parameter_table_sidecar_issues, *performance_sidecar_issues, *uncertainty_sidecar_issues, *manifest["issues"]]
        manifest["supplementalEvidence"] = {
            "parameterTableSidecarPath": parameter_table_sidecar_path,
            "parameterTableRowCount": len(parameter_table_sidecar_rows),
            "parameterTableBundleMetadata": parameter_table_sidecar_metadata,
            "performanceEvidenceSidecarPath": performance_sidecar_path,
            "performanceEvidenceRowCount": len(performance_sidecar_rows),
            "performanceEvidenceBundleMetadata": performance_sidecar_metadata,
            "uncertaintyEvidenceSidecarPath": uncertainty_sidecar_path,
            "uncertaintyEvidenceRowCount": len(uncertainty_sidecar_rows),
            "uncertaintyEvidenceBundleMetadata": uncertainty_sidecar_metadata,
        }
        return {
            "filePath": str(path),
            "backend": backend,
            "runtimeFormat": suffix.lstrip("."),
            "manifest": manifest,
        }

    return {
        "filePath": str(path),
        "backend": backend,
        "runtimeFormat": suffix.lstrip("."),
        "manifest": _validate_r_model(path),
    }


__all__ = ["derive_qualification_state", "validate_model_manifest"]
