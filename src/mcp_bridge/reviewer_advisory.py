"""Helpers for attaching reviewer-facing advisory blocks to trust-bearing outputs."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .model_manifest import validate_model_manifest as validate_manifest_payload


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _unique_texts(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in deduped:
            deduped.append(text)
    return deduped


def _resolve_model_path(*, simulation_id: str | None = None, file_path: str | None = None) -> Path | None:
    if file_path:
        path = Path(file_path)
        return path if path.exists() else None
    if not simulation_id:
        return None
    from mcp.session_registry import SessionRegistryError, registry

    try:
        record = registry.get(simulation_id)
    except SessionRegistryError:
        return None
    path = Path(record.handle.file_path)
    return path if path.exists() else None


def build_dossier_improvement_signals(
    *,
    simulation_id: str | None = None,
    file_path: str | None = None,
) -> dict[str, Any] | None:
    model_path = _resolve_model_path(simulation_id=simulation_id, file_path=file_path)
    if model_path is None:
        return None

    try:
        manifest_payload = validate_manifest_payload(model_path)
    except Exception:  # noqa: BLE001 - advisory-only helper
        return None

    curation_summary = _as_mapping(manifest_payload.get("curationSummary"))
    readiness = _as_mapping(curation_summary.get("regulatoryBenchmarkReadiness"))
    if not readiness:
        return None

    prioritized_gaps = [
        dict(entry)
        for entry in (readiness.get("prioritizedGaps") or [])
        if isinstance(entry, Mapping)
    ]
    recommended_next_artifacts = _unique_texts(
        [str(item) for item in (readiness.get("recommendedNextArtifacts") or [])]
        + [
            str(item)
            for gap in prioritized_gaps
            for item in (_as_mapping(gap).get("recommendedNextArtifacts") or [])
        ]
    )

    return {
        "summaryVersion": "pbpk-dossier-improvement-signals.v1",
        "advisoryOnly": True,
        "source": "curationSummary.regulatoryBenchmarkReadiness",
        "modelPath": str(model_path),
        "benchmarkResemblance": readiness.get("modelResemblance"),
        "overallStatus": readiness.get("overallStatus"),
        "presentDimensions": list(readiness.get("presentDimensions") or []),
        "partialDimensions": list(readiness.get("partialDimensions") or []),
        "missingDimensions": list(readiness.get("missingDimensions") or []),
        "prioritizedSignals": prioritized_gaps[:5],
        "recommendedNextArtifacts": recommended_next_artifacts,
        "plainLanguageSummary": (
            "Benchmark-derived dossier signals are advisory only. They highlight documentation, "
            "reproducibility, and evidence-packaging gaps without changing runtime permissions or "
            "qualification state."
        ),
        "benchmarkBarSource": dict(_as_mapping(readiness.get("benchmarkBarSource"))),
    }


def attach_dossier_improvement_signals(
    payload: dict[str, Any],
    *,
    simulation_id: str | None = None,
    file_path: str | None = None,
    report_path: str | None = None,
) -> dict[str, Any] | None:
    advisory = build_dossier_improvement_signals(simulation_id=simulation_id, file_path=file_path)
    if advisory is None:
        return None
    payload["dossierImprovementSignals"] = dict(advisory)
    if report_path and isinstance(payload.get(report_path), Mapping):
        report_payload = dict(payload[report_path])
        report_payload["dossierImprovementSignals"] = dict(advisory)
        payload[report_path] = report_payload
    return advisory


__all__ = [
    "attach_dossier_improvement_signals",
    "build_dossier_improvement_signals",
]
