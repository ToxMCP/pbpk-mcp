#!/usr/bin/env python3
from __future__ import annotations

import argparse
import py_compile
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from runtime_patch_manifest import iter_patch_mappings, python_target_paths, r_target_paths


def resolve_target_path(target_root: Path, absolute_target: str) -> Path:
    return target_root / absolute_target.lstrip("/")


def install_patches(source_root: Path, target_root: Path) -> None:
    for source_path, absolute_target in iter_patch_mappings(source_root):
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        target_path = resolve_target_path(target_root, absolute_target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)


def verify_python_targets(target_root: Path) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        for index, absolute_target in enumerate(python_target_paths()):
            py_compile.compile(
                str(resolve_target_path(target_root, absolute_target)),
                cfile=str(tmp_path / f"{index}.pyc"),
                doraise=True,
            )


def verify_r_targets(target_root: Path) -> None:
    parse_calls = "; ".join(
        f"invisible(parse(file={str(resolve_target_path(target_root, absolute_target))!r}))"
        for absolute_target in r_target_paths()
    )
    subprocess.run(
        ["Rscript", "-e", f"{parse_calls}; cat('ok\\n')"],
        check=True,
        capture_output=True,
        text=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install the PBPK MCP runtime patch set into a target root.")
    parser.add_argument(
        "--source-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Workspace root containing the patch sources.",
    )
    parser.add_argument(
        "--target-root",
        default=Path("/"),
        type=Path,
        help="Filesystem root under which the absolute patch targets should be materialized.",
    )
    parser.add_argument(
        "--compile-python",
        action="store_true",
        help="Compile installed Python targets after copying them.",
    )
    parser.add_argument(
        "--verify-r",
        action="store_true",
        help="Parse installed R targets after copying them.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_root = args.source_root.resolve()
    target_root = args.target_root.resolve()

    install_patches(source_root, target_root)
    if args.compile_python:
        verify_python_targets(target_root)
    if args.verify_r:
        verify_r_targets(target_root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
