"""Filesystem-backed discovery helpers for supported PBPK model files."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.session_registry import SessionRecord

MODEL_PATH_ENV = "MCP_MODEL_SEARCH_PATHS"
SUPPORTED_MODEL_EXTENSIONS = {
    ".pkml": "ospsuite",
    ".r": "rxode2",
}
_IDENTIFIER_SANITIZER = re.compile(r"[^a-zA-Z0-9]+")
_R_HOOK_PATTERNS = {
    "scientificProfile": re.compile(r"\bpbpk_model_profile\b"),
    "validationHook": re.compile(r"\bpbpk_validate_request\b"),
    "populationSimulation": re.compile(r"\bpbpk_run_population\b"),
}


def isoformat_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_model_roots() -> tuple[Path, ...]:
    raw = os.getenv(MODEL_PATH_ENV, "")
    candidates: list[Path] = []

    if raw.strip():
        for chunk in raw.split(os.pathsep):
            value = chunk.strip()
            if value:
                candidates.append(Path(value).expanduser())
    else:
        cwd = Path.cwd()
        candidates.extend(
            [
                cwd / "var",
                cwd / "reference" / "models" / "standard",
                cwd / "tests" / "fixtures",
            ]
        )

    roots: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        resolved = _safe_resolve(candidate)
        if resolved is None or not resolved.exists():
            continue
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        roots.append(resolved)
    return tuple(roots)


def normalise_backend(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip().lower()
    if not candidate:
        return None
    if candidate not in {"ospsuite", "rxode2"}:
        raise ValueError("backend must be one of: ospsuite, rxode2")
    return candidate


def discover_models(
    *,
    roots: Iterable[Path] | None = None,
    search: str | None = None,
    backend: str | None = None,
    loaded_records: Sequence[SessionRecord] = (),
    loaded_only: bool = False,
) -> list[dict[str, Any]]:
    root_list = tuple(roots or resolve_model_roots())
    backend_filter = normalise_backend(backend)
    lowered_search = search.strip().lower() if search and search.strip() else None
    loaded_by_path = _index_loaded_records(loaded_records)

    items: list[dict[str, Any]] = []
    seen_files: set[str] = set()

    for root in root_list:
        for path in root.rglob("*"):
            if not path.is_file():
                continue

            backend_name = SUPPORTED_MODEL_EXTENSIONS.get(path.suffix.lower())
            if backend_name is None:
                continue
            if backend_filter and backend_name != backend_filter:
                continue

            resolved = _safe_resolve(path)
            if resolved is None:
                continue
            resolved_key = str(resolved)
            if resolved_key in seen_files:
                continue
            seen_files.add(resolved_key)

            item = _build_discovered_item(
                path=resolved,
                root=root,
                backend_name=backend_name,
                loaded_records=loaded_by_path.get(resolved_key, ()),
            )
            if loaded_only and not item["isLoaded"]:
                continue
            if lowered_search and not _matches_search(item, lowered_search):
                continue
            items.append(item)

    items.sort(
        key=lambda item: (
            not bool(item.get("isLoaded")),
            str(item.get("relativePath", "")).lower(),
            str(item.get("filePath", "")).lower(),
        )
    )
    return items


def model_catalog_fingerprint(items: Sequence[Mapping[str, Any]]) -> str:
    try:
        payload = json.dumps(list(items), sort_keys=True, default=str)
    except TypeError:
        payload = json.dumps([str(item) for item in items], sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def ospsuite_profile_sidecar_candidates(file_path: Path) -> tuple[Path, ...]:
    stem = file_path.with_suffix("")
    return (
        Path(f"{stem}.profile.json"),
        Path(f"{stem}.pbpk.json"),
        Path(f"{file_path}.profile.json"),
    )


def _build_discovered_item(
    *,
    path: Path,
    root: Path,
    backend_name: str,
    loaded_records: Sequence[SessionRecord],
) -> dict[str, Any]:
    relative_path = _safe_relative_path(path, root)
    relative_no_suffix = str(relative_path.with_suffix(""))
    model_id = f"{backend_name}:{relative_no_suffix.replace(os.sep, '/')}"
    suggested_simulation_id = _suggested_simulation_id(relative_path)

    loaded_ids = sorted({record.handle.simulation_id for record in loaded_records})
    primary_metadata = dict(loaded_records[0].metadata or {}) if loaded_records else {}
    loaded_capabilities = primary_metadata.get("capabilities")
    capabilities = dict(loaded_capabilities) if isinstance(loaded_capabilities, Mapping) else {}
    loaded_profile = primary_metadata.get("profile")
    profile = dict(loaded_profile) if isinstance(loaded_profile, Mapping) else {}

    detection = (
        _detect_rxode_features(path)
        if backend_name == "rxode2"
        else _detect_ospsuite_features(path)
    )

    display_name = (
        _safe_str(primary_metadata.get("name"))
        or _safe_str(primary_metadata.get("displayName"))
        or _humanise_name(path.stem)
    )
    model_version = _safe_str(primary_metadata.get("modelVersion")) or _safe_str(
        primary_metadata.get("model_version")
    )
    scientific_profile = _coalesce_bool(
        capabilities.get("scientificProfile"),
        detection.get("scientificProfile"),
    )
    population_simulation = _coalesce_bool(
        capabilities.get("populationSimulation"),
        detection.get("populationSimulation"),
    )
    validation_hook = _coalesce_bool(
        capabilities.get("validationHook"),
        detection.get("validationHook"),
    )

    profile_source = None
    if isinstance(profile.get("profileSource"), Mapping):
        profile_source = _safe_str(profile["profileSource"].get("type"))
    if not profile_source:
        profile_source = _safe_str(detection.get("profileSource"))

    metadata = dict(primary_metadata)
    metadata.setdefault("backend", backend_name)
    metadata.setdefault("discoverySource", "filesystem")

    modified_at = isoformat_timestamp(path.stat().st_mtime)
    return {
        "id": model_id,
        "modelId": model_id,
        "suggestedSimulationId": suggested_simulation_id,
        "filePath": str(path),
        "relativePath": relative_path.as_posix(),
        "rootPath": str(root),
        "backend": backend_name,
        "runtimeFormat": path.suffix.lower().lstrip("."),
        "displayName": display_name or None,
        "modelVersion": model_version or None,
        "scientificProfile": scientific_profile,
        "profileSource": profile_source,
        "populationSimulation": population_simulation,
        "validationHook": validation_hook,
        "discoveryState": "loaded" if loaded_ids else "discovered",
        "isLoaded": bool(loaded_ids),
        "loadedSimulationIds": loaded_ids,
        "modifiedAt": modified_at,
        "metadata": metadata,
    }


def _detect_ospsuite_features(path: Path) -> dict[str, Any]:
    sidecar = next(
        (candidate for candidate in ospsuite_profile_sidecar_candidates(path) if candidate.exists()),
        None,
    )
    return {
        "scientificProfile": sidecar is not None,
        "profileSource": "sidecar" if sidecar is not None else "bridge-default",
        "populationSimulation": False,
        "validationHook": False,
    }


def _detect_rxode_features(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    features = {
        name: bool(pattern.search(text))
        for name, pattern in _R_HOOK_PATTERNS.items()
    }
    features["profileSource"] = (
        "module-hook-detected" if features.get("scientificProfile") else None
    )
    return features


def _index_loaded_records(
    records: Sequence[SessionRecord],
) -> dict[str, tuple[SessionRecord, ...]]:
    by_path: dict[str, list[SessionRecord]] = defaultdict(list)
    for record in records:
        resolved = _safe_resolve(Path(record.handle.file_path))
        if resolved is None:
            continue
        by_path[str(resolved)].append(record)
    return {key: tuple(value) for key, value in by_path.items()}


def _matches_search(item: Mapping[str, Any], lowered_search: str) -> bool:
    haystacks = [
        item.get("modelId"),
        item.get("suggestedSimulationId"),
        item.get("filePath"),
        item.get("relativePath"),
        item.get("displayName"),
        item.get("backend"),
        json.dumps(item.get("metadata", {}), sort_keys=True, default=str),
    ]
    for value in haystacks:
        if value and lowered_search in str(value).lower():
            return True
    return False


def _suggested_simulation_id(relative_path: Path) -> str:
    without_suffix = relative_path.with_suffix("")
    parts = [
        _normalise_token(part)
        for part in without_suffix.parts
        if part.lower() not in {"models"}
    ]
    tokens = [token for token in parts if token]
    candidate = "-".join(tokens) or _normalise_token(without_suffix.stem) or "model"
    if len(candidate) <= 64:
        return candidate
    digest = hashlib.sha1(without_suffix.as_posix().encode("utf-8")).hexdigest()[:8]
    return f"{candidate[:55].rstrip('-')}-{digest}"


def _normalise_token(value: str) -> str:
    token = _IDENTIFIER_SANITIZER.sub("-", value.strip().lower()).strip("-")
    return token


def _humanise_name(stem: str) -> str:
    cleaned = stem.replace("_", " ").replace("-", " ").strip()
    return cleaned or stem


def _safe_relative_path(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return Path(path.name)


def _safe_resolve(path: Path) -> Path | None:
    try:
        return path.expanduser().resolve()
    except OSError:
        return None


def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coalesce_bool(*values: Any) -> bool | None:
    for value in values:
        if value is None:
            continue
        return bool(value)
    return None


__all__ = [
    "SUPPORTED_MODEL_EXTENSIONS",
    "discover_models",
    "isoformat_timestamp",
    "model_catalog_fingerprint",
    "normalise_backend",
    "ospsuite_profile_sidecar_candidates",
    "resolve_model_roots",
]
