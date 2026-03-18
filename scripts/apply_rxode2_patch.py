#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
PATCH_FILES = (
    (
        WORKSPACE_ROOT / "patches" / "mcp" / "__init__.py",
        "/usr/local/lib/python3.11/site-packages/mcp/__init__.py",
    ),
    (
        WORKSPACE_ROOT / "patches" / "mcp_bridge" / "adapter" / "ospsuite.py",
        "/usr/local/lib/python3.11/site-packages/mcp_bridge/adapter/ospsuite.py",
    ),
    (
        WORKSPACE_ROOT / "patches" / "mcp_bridge" / "model_catalog.py",
        "/usr/local/lib/python3.11/site-packages/mcp_bridge/model_catalog.py",
    ),
    (
        WORKSPACE_ROOT / "patches" / "mcp_bridge" / "routes" / "resources.py",
        "/usr/local/lib/python3.11/site-packages/mcp_bridge/routes/resources.py",
    ),
    (
        WORKSPACE_ROOT / "patches" / "mcp_bridge" / "tools" / "registry.py",
        "/usr/local/lib/python3.11/site-packages/mcp_bridge/tools/registry.py",
    ),
    (
        WORKSPACE_ROOT / "patches" / "mcp" / "tools" / "load_simulation.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/load_simulation.py",
    ),
    (
        WORKSPACE_ROOT / "patches" / "mcp" / "tools" / "get_job_status.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/get_job_status.py",
    ),
    (
        WORKSPACE_ROOT / "patches" / "mcp" / "tools" / "discover_models.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/discover_models.py",
    ),
    (
        WORKSPACE_ROOT / "patches" / "mcp" / "tools" / "get_results.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/get_results.py",
    ),
    (
        WORKSPACE_ROOT / "patches" / "mcp" / "tools" / "validate_simulation_request.py",
        "/usr/local/lib/python3.11/site-packages/mcp/tools/validate_simulation_request.py",
    ),
    (
        WORKSPACE_ROOT / "scripts" / "ospsuite_bridge.R",
        "/app/scripts/ospsuite_bridge.R",
    ),
    (
        WORKSPACE_ROOT / "cisplatin_models" / "cisplatin_population_rxode2_model.R",
        "/app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R",
    ),
)


def run(cmd: list[str], *, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        capture_output=capture,
    )


def ensure_container_dirs(container: str) -> None:
    run(
        [
            "docker",
            "exec",
            container,
            "sh",
            "-lc",
            "mkdir -p /app/scripts /app/var/models/rxode2/cisplatin "
            "/usr/local/lib/python3.11/site-packages/mcp_bridge/adapter "
            "/usr/local/lib/python3.11/site-packages/mcp_bridge/routes "
            "/usr/local/lib/python3.11/site-packages/mcp_bridge/tools "
            "/usr/local/lib/python3.11/site-packages/mcp/tools "
            "/usr/local/lib/python3.11/site-packages/mcp",
        ]
    )


def copy_files(container: str) -> None:
    for source, target in PATCH_FILES:
        if not source.is_file():
            raise FileNotFoundError(source)
        run(["docker", "cp", str(source), f"{container}:{target}"])


def verify_python(container: str) -> None:
    run(
        [
            "docker",
            "exec",
            container,
            "python",
            "-c",
            (
                "import py_compile, tempfile; "
                "files = ["
                "'/usr/local/lib/python3.11/site-packages/mcp/__init__.py', "
                "'/usr/local/lib/python3.11/site-packages/mcp_bridge/adapter/ospsuite.py', "
                "'/usr/local/lib/python3.11/site-packages/mcp_bridge/model_catalog.py', "
                "'/usr/local/lib/python3.11/site-packages/mcp_bridge/routes/resources.py', "
                "'/usr/local/lib/python3.11/site-packages/mcp_bridge/tools/registry.py', "
                "'/usr/local/lib/python3.11/site-packages/mcp/tools/load_simulation.py', "
                "'/usr/local/lib/python3.11/site-packages/mcp/tools/get_job_status.py', "
                "'/usr/local/lib/python3.11/site-packages/mcp/tools/discover_models.py', "
                "'/usr/local/lib/python3.11/site-packages/mcp/tools/get_results.py', "
                "'/usr/local/lib/python3.11/site-packages/mcp/tools/validate_simulation_request.py'"
                "]; "
                "tmp = tempfile.mkdtemp(); "
                "[(py_compile.compile(path, cfile=f'{tmp}/{index}.pyc', doraise=True)) for index, path in enumerate(files)]"
            ),
        ]
    )


def verify_r_parsing(container: str) -> None:
    run(
        [
            "docker",
            "exec",
            container,
            "Rscript",
            "-e",
            (
                "invisible(parse(file='/app/scripts/ospsuite_bridge.R')); "
                "invisible(parse(file='/app/var/models/rxode2/cisplatin/cisplatin_population_rxode2_model.R')); "
                "cat('ok\\n')"
            ),
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
        help="Container to patch. Repeat for multiple containers. Defaults to pbpk_mcp-worker-1.",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Restart patched containers after copying the files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    containers = args.container or ["pbpk_mcp-worker-1"]

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
