#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

from runtime_patch_manifest import (
    DEFAULT_PATCH_CONTAINERS,
    iter_patch_mappings,
    iter_patch_tree_mappings,
    python_target_paths,
    python_tree_targets,
    r_target_paths,
    target_directories,
)

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], *, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        capture_output=capture,
    )


def ensure_container_dirs(container: str) -> None:
    directories = " ".join(target_directories())
    run(
        [
            "docker",
            "exec",
            container,
            "sh",
            "-lc",
            f"mkdir -p {directories}",
        ]
    )


def copy_files(container: str) -> None:
    for source, target in iter_patch_mappings(WORKSPACE_ROOT):
        if not source.is_file():
            raise FileNotFoundError(source)
        run(["docker", "cp", str(source), f"{container}:{target}"])
    for source, target in iter_patch_tree_mappings(WORKSPACE_ROOT):
        if not source.is_dir():
            raise NotADirectoryError(source)
        run(
            [
                "docker",
                "exec",
                container,
                "sh",
                "-lc",
                f"mkdir -p {shlex.quote(target)}",
            ]
        )
        run(["docker", "cp", f"{source}/.", f"{container}:{target}"])


def verify_python(container: str) -> None:
    file_list = ", ".join(repr(path) for path in python_target_paths())
    tree_list = ", ".join(repr(path) for path in python_tree_targets())
    run(
        [
            "docker",
            "exec",
            container,
            "python",
            "-c",
            (
                "import py_compile, tempfile; from pathlib import Path; "
                f"files = [{file_list}]; "
                f"trees = [{tree_list}]; "
                "tmp = tempfile.mkdtemp(); "
                "overlay = [str(path) for tree in trees for path in sorted(Path(tree).rglob('*.py'))]; "
                "all_paths = list(files) + overlay; "
                "[(py_compile.compile(path, cfile=f'{tmp}/{index}.pyc', doraise=True)) for index, path in enumerate(all_paths)]"
            ),
        ]
    )


def verify_r_parsing(container: str) -> None:
    parse_calls = "; ".join(
        f"invisible(parse(file='{path}'))" for path in r_target_paths()
    )
    run(
        [
            "docker",
            "exec",
            container,
            "Rscript",
            "-e",
            f"{parse_calls}; cat('ok\\n')",
        ]
    )


def check_rxode2(container: str) -> bool:
    result = subprocess.run(
        [
            "docker",
            "exec",
            container,
            "Rscript",
            "-e",
            "quit(status = if (requireNamespace('rxode2', quietly = TRUE)) 0 else 2)",
        ],
        text=True,
        capture_output=True,
    )
    return result.returncode == 0


def restart_container(container: str) -> None:
    run(["docker", "restart", container], capture=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy the rxode2 bridge and server patches into a PBPK MCP container."
    )
    parser.add_argument(
        "--container",
        action="append",
        default=[],
        help="Container to patch. Repeat for multiple containers. Defaults to patching the API and worker containers.",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Restart patched containers after copying the files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    containers = args.container or list(DEFAULT_PATCH_CONTAINERS)

    for container in containers:
        ensure_container_dirs(container)
        copy_files(container)
        verify_python(container)
        verify_r_parsing(container)
        rxode2_available = check_rxode2(container)
        if args.restart:
            restart_container(container)
        print(
            f"{container}: patched successfully"
            + ("" if rxode2_available else " (rxode2 package still missing in container)")
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
