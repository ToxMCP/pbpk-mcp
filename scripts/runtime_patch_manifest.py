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
        "src/mcp/tools/run_verification_checks.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/run_verification_checks.py",
    ),
    RuntimePatch(
        "src/mcp_bridge/model_catalog.py",
        "/usr/local/lib/python3.11/site-packages/mcp_bridge/model_catalog.py",
    ),
    RuntimePatch(
        "src/mcp_bridge/model_manifest.py",
        "/usr/local/lib/python3.11/site-packages/mcp_bridge/model_manifest.py",
    ),
    RuntimePatch(
        "src/mcp_bridge/routes/resources_base.py",
        "/usr/local/lib/python3.11/site-packages/mcp_bridge/routes/resources_base.py",
    ),
    RuntimePatch(
        "src/mcp_bridge/tools/registry_base.py",
        "/usr/local/lib/python3.11/site-packages/mcp_bridge/tools/registry_base.py",
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
        "src/mcp/tools/load_simulation.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/load_simulation.py",
    ),
    RuntimePatch(
        "src/mcp/tools/get_job_status.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/get_job_status.py",
    ),
    RuntimePatch(
        "src/mcp/tools/discover_models.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/discover_models.py",
    ),
    RuntimePatch(
        "src/mcp/tools/export_oecd_report.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/export_oecd_report.py",
    ),
    RuntimePatch(
        "src/mcp/tools/run_population_simulation.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/run_population_simulation.py",
    ),
    RuntimePatch(
        "src/mcp/tools/validate_model_manifest.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/validate_model_manifest.py",
    ),
    RuntimePatch(
        "src/mcp/tools/get_results.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/get_results.py",
    ),
    RuntimePatch(
        "src/mcp/tools/ingest_external_pbpk_bundle.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/ingest_external_pbpk_bundle.py",
    ),
    RuntimePatch(
        "src/mcp/tools/validate_simulation_request.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/validate_simulation_request.py",
    ),
    RuntimePatch(
        "docs/architecture/capability_matrix.json",
        "/app/var/contract/capability_matrix.json",
    ),
    RuntimePatch(
        "docs/architecture/contract_manifest.json",
        "/app/var/contract/contract_manifest.json",
    ),
    RuntimePatch(
        "schemas/assessmentContext.v1.json",
        "/app/var/contract/schemas/assessmentContext.v1.json",
    ),
    RuntimePatch(
        "schemas/berInputBundle.v1.json",
        "/app/var/contract/schemas/berInputBundle.v1.json",
    ),
    RuntimePatch(
        "schemas/internalExposureEstimate.v1.json",
        "/app/var/contract/schemas/internalExposureEstimate.v1.json",
    ),
    RuntimePatch(
        "schemas/pbpkQualificationSummary.v1.json",
        "/app/var/contract/schemas/pbpkQualificationSummary.v1.json",
    ),
    RuntimePatch(
        "schemas/pointOfDepartureReference.v1.json",
        "/app/var/contract/schemas/pointOfDepartureReference.v1.json",
    ),
    RuntimePatch(
        "schemas/uncertaintyHandoff.v1.json",
        "/app/var/contract/schemas/uncertaintyHandoff.v1.json",
    ),
    RuntimePatch(
        "schemas/uncertaintyRegisterReference.v1.json",
        "/app/var/contract/schemas/uncertaintyRegisterReference.v1.json",
    ),
    RuntimePatch(
        "schemas/uncertaintySummary.v1.json",
        "/app/var/contract/schemas/uncertaintySummary.v1.json",
    ),
    RuntimePatch(
        "schemas/examples/assessmentContext.v1.example.json",
        "/app/var/contract/schemas/examples/assessmentContext.v1.example.json",
    ),
    RuntimePatch(
        "schemas/examples/berInputBundle.v1.example.json",
        "/app/var/contract/schemas/examples/berInputBundle.v1.example.json",
    ),
    RuntimePatch(
        "schemas/examples/internalExposureEstimate.v1.example.json",
        "/app/var/contract/schemas/examples/internalExposureEstimate.v1.example.json",
    ),
    RuntimePatch(
        "schemas/examples/pbpkQualificationSummary.v1.example.json",
        "/app/var/contract/schemas/examples/pbpkQualificationSummary.v1.example.json",
    ),
    RuntimePatch(
        "schemas/examples/pointOfDepartureReference.v1.example.json",
        "/app/var/contract/schemas/examples/pointOfDepartureReference.v1.example.json",
    ),
    RuntimePatch(
        "schemas/examples/uncertaintyHandoff.v1.example.json",
        "/app/var/contract/schemas/examples/uncertaintyHandoff.v1.example.json",
    ),
    RuntimePatch(
        "schemas/examples/uncertaintyRegisterReference.v1.example.json",
        "/app/var/contract/schemas/examples/uncertaintyRegisterReference.v1.example.json",
    ),
    RuntimePatch(
        "schemas/examples/uncertaintySummary.v1.example.json",
        "/app/var/contract/schemas/examples/uncertaintySummary.v1.example.json",
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
