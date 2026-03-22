#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


COPY_IGNORE_GLOBS = (
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    ".tox",
    ".nox",
    ".venv",
    "venv",
    "env",
    ".tmp_codex_*",
    "build",
    "dist",
    "*.egg-info",
)


def _is_virtualenv_root(path: Path) -> bool:
    return path.is_dir() and (path / "pyvenv.cfg").exists()


def stage_copy_ignore(directory: str, names: list[str]) -> set[str]:
    ignored = set(shutil.ignore_patterns(*COPY_IGNORE_GLOBS)(directory, names))
    directory_path = Path(directory)
    for name in names:
        candidate = directory_path / name
        if _is_virtualenv_root(candidate):
            ignored.add(name)
    return ignored


def stage_source_tree(source_root: Path, destination: Path) -> Path:
    staged_root = destination / "source-tree"
    shutil.copytree(source_root, staged_root, ignore=stage_copy_ignore)
    return staged_root


__all__ = ["COPY_IGNORE_GLOBS", "stage_copy_ignore", "stage_source_tree"]
