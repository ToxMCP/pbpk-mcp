from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class RuntimePatch:
    source: str
    target: str


PATCHES: tuple[RuntimePatch, ...] = (
    RuntimePatch("patches/mcp/__init__.py", "/usr/local/lib/python3.11/site-packages/mcp/__init__.py"),
    RuntimePatch(
        "patches/mcp_bridge/adapter/interface.py",
        "/usr/local/lib/python3.11/site-packages/mcp_bridge/adapter/interface.py",
    ),
    RuntimePatch(
        "patches/mcp_bridge/adapter/ospsuite.py",
        "/usr/local/lib/python3.11/site-packages/mcp_bridge/adapter/ospsuite.py",
    ),
    RuntimePatch(
        "patches/mcp/tools/run_verification_checks.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/run_verification_checks.py",
    ),
    RuntimePatch(
        "patches/mcp_bridge/model_catalog.py",
        "/usr/local/lib/python3.11/site-packages/mcp_bridge/model_catalog.py",
    ),
    RuntimePatch(
        "patches/mcp_bridge/model_manifest.py",
        "/usr/local/lib/python3.11/site-packages/mcp_bridge/model_manifest.py",
    ),
    RuntimePatch(
        "patches/mcp_bridge/routes/resources.py",
        "/usr/local/lib/python3.11/site-packages/mcp_bridge/routes/resources.py",
    ),
    RuntimePatch(
        "patches/mcp_bridge/tools/registry.py",
        "/usr/local/lib/python3.11/site-packages/mcp_bridge/tools/registry.py",
    ),
    RuntimePatch(
        "patches/mcp/tools/load_simulation.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/load_simulation.py",
    ),
    RuntimePatch(
        "patches/mcp/tools/get_job_status.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/get_job_status.py",
    ),
    RuntimePatch(
        "patches/mcp/tools/discover_models.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/discover_models.py",
    ),
    RuntimePatch(
        "patches/mcp/tools/export_oecd_report.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/export_oecd_report.py",
    ),
    RuntimePatch(
        "patches/mcp/tools/run_population_simulation.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/run_population_simulation.py",
    ),
    RuntimePatch(
        "patches/mcp/tools/validate_model_manifest.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/validate_model_manifest.py",
    ),
    RuntimePatch(
        "patches/mcp/tools/get_results.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/get_results.py",
    ),
    RuntimePatch(
        "patches/mcp/tools/ingest_external_pbpk_bundle.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/ingest_external_pbpk_bundle.py",
    ),
    RuntimePatch(
        "patches/mcp/tools/validate_simulation_request.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/validate_simulation_request.py",
    ),
    RuntimePatch("scripts/ospsuite_bridge.R", "/app/scripts/ospsuite_bridge.R"),
    RuntimePatch(
        "cisplatin_models/cisplatin_population_rxode2_model.R",
        "/app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R",
    ),
)

DEFAULT_PATCH_CONTAINERS: tuple[str, ...] = ("pbpk_mcp-api-1", "pbpk_mcp-worker-1")


def iter_patch_mappings(workspace_root: Path) -> Iterable[tuple[Path, str]]:
    for patch in PATCHES:
        yield workspace_root / patch.source, patch.target


def target_directories() -> tuple[str, ...]:
    directories = sorted({str(Path(patch.target).parent) for patch in PATCHES})
    return tuple(directories)


def python_target_paths() -> tuple[str, ...]:
    return tuple(patch.target for patch in PATCHES if patch.target.endswith(".py"))


def r_target_paths() -> tuple[str, ...]:
    return tuple(patch.target for patch in PATCHES if patch.target.endswith(".R"))


__all__ = [
    "DEFAULT_PATCH_CONTAINERS",
    "PATCHES",
    "RuntimePatch",
    "iter_patch_mappings",
    "python_target_paths",
    "r_target_paths",
    "target_directories",
]
