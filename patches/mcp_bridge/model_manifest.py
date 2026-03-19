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
}
_R_SECTION_PATTERNS = {
    "contextOfUse": re.compile(r"\bcontextOfUse\s*="),
    "applicabilityDomain": re.compile(r"\bapplicabilityDomain\s*="),
    "modelPerformance": re.compile(r"\bmodelPerformance\s*="),
    "parameterProvenance": re.compile(r"\bparameterProvenance\s*="),
    "uncertainty": re.compile(r"\buncertainty\s*="),
    "implementationVerification": re.compile(r"\bimplementationVerification\s*="),
    "peerReview": re.compile(r"\bpeerReview\s*="),
}
_REQUIRED_SECTION_FIELDS = {
    "contextOfUse": ("scientificPurpose", "decisionContext", "regulatoryUse"),
    "applicabilityDomain": ("type", "qualificationLevel"),
    "modelPerformance": ("status",),
    "parameterProvenance": ("status",),
    "uncertainty": ("status",),
    "implementationVerification": ("status",),
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


def _extract_assignment(text: str, field_name: str) -> str | None:
    pattern = re.compile(rf"\b{re.escape(field_name)}\s*=\s*['\"]([^'\"]+)['\"]")
    match = pattern.search(text)
    if not match:
        return None
    candidate = match.group(1).strip()
    return candidate or None


def _validate_r_model(file_path: Path) -> dict[str, Any]:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    hooks = {
        name: bool(pattern.search(text))
        for name, pattern in _R_HOOK_PATTERNS.items()
    }
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
    if not hooks["parameterTable"]:
        issues.append(
            _issue(
                "parameter_table_hook_missing",
                "R model does not declare pbpk_parameter_table(...).",
                field=str(file_path),
                severity="warning",
            )
        )
    if not hooks["performanceEvidence"]:
        issues.append(
            _issue(
                "performance_evidence_hook_missing",
                "R model does not declare pbpk_performance_evidence(...).",
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
    evidence_sections_complete = hooks["parameterTable"] and hooks["performanceEvidence"] and all(
        sections[name]["present"]
        for name in (
            "modelPerformance",
            "parameterProvenance",
            "uncertainty",
            "implementationVerification",
            "peerReview",
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
                    "issues": sidecar_issues,
                    "sidecarPath": sidecar_path,
                },
            }

        manifest = _validate_profile_manifest(
            profile,
            backend=backend,
            profile_source="sidecar",
            sidecar_path=sidecar_path,
        )
        manifest["issues"] = [*sidecar_issues, *manifest["issues"]]
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
