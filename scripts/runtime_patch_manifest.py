from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class RuntimePatch:
    source: str
    target: str


@dataclass(frozen=True)
class RuntimePatchTree:
    source: str
    target: str


PATCHES: tuple[RuntimePatch, ...] = (
    RuntimePatch(
        "scripts/runtime_src_overlay.pth",
        "/usr/local/lib/python3.11/site-packages/pbpk_mcp_runtime_src.pth",
    ),
    RuntimePatch("scripts/ospsuite_bridge.R", "/app/scripts/ospsuite_bridge.R"),
    RuntimePatch(
        "cisplatin_models/cisplatin_population_rxode2_model.R",
        "/app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R",
    ),
)

PATCH_TREES: tuple[RuntimePatchTree, ...] = (
    RuntimePatchTree("src/mcp", "/app/src/mcp"),
    RuntimePatchTree("src/mcp_bridge", "/app/src/mcp_bridge"),
)

DEFAULT_PATCH_CONTAINERS: tuple[str, ...] = ("pbpk_mcp-api-1", "pbpk_mcp-worker-1")


def iter_patch_mappings(workspace_root: Path) -> Iterable[tuple[Path, str]]:
    for patch in PATCHES:
        yield workspace_root / patch.source, patch.target


def iter_patch_tree_mappings(workspace_root: Path) -> Iterable[tuple[Path, str]]:
    for patch in PATCH_TREES:
        yield workspace_root / patch.source, patch.target


def target_directories() -> tuple[str, ...]:
    directories = {str(Path(patch.target).parent) for patch in PATCHES}
    directories.update(str(Path(patch.target)) for patch in PATCH_TREES)
    directories.update(str(Path(patch.target).parent) for patch in PATCH_TREES)
    directories = sorted(directories)
    return tuple(directories)


def python_target_paths() -> tuple[str, ...]:
    return tuple(patch.target for patch in PATCHES if patch.target.endswith(".py"))


def python_tree_targets() -> tuple[str, ...]:
    return tuple(
        patch.target for patch in PATCH_TREES if patch.target.startswith("/app/src/")
    )


def r_target_paths() -> tuple[str, ...]:
    return tuple(patch.target for patch in PATCHES if patch.target.endswith(".R"))


__all__ = [
    "DEFAULT_PATCH_CONTAINERS",
    "PATCHES",
    "PATCH_TREES",
    "RuntimePatch",
    "RuntimePatchTree",
    "iter_patch_mappings",
    "iter_patch_tree_mappings",
    "python_target_paths",
    "python_tree_targets",
    "r_target_paths",
    "target_directories",
]
