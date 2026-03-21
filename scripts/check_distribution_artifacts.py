#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
CHECK_INSTALLED_PACKAGE_CONTRACT = WORKSPACE_ROOT / "scripts" / "check_installed_package_contract.py"
CHECK_RELEASE_METADATA = WORKSPACE_ROOT / "scripts" / "check_release_metadata.py"
COPY_IGNORE_PATTERNS = shutil.ignore_patterns(
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
    "src/mcp_bridge.egg-info",
)


def _load_release_metadata_module():
    spec = importlib.util.spec_from_file_location(
        "pbpk_check_release_metadata_for_distribution",
        CHECK_RELEASE_METADATA,
    )
    if spec is None or spec.loader is None:  # pragma: no cover - import guard
        raise SystemExit(f"Unable to load release metadata helper from {CHECK_RELEASE_METADATA}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd is not None else None,
    )
    if completed.returncode == 0:
        if completed.stdout.strip():
            print(completed.stdout.strip())
        return

    if completed.stdout.strip():
        print(completed.stdout.strip(), file=sys.stderr)
    if completed.stderr.strip():
        print(completed.stderr.strip(), file=sys.stderr)
    raise SystemExit(completed.returncode)


def _ensure_build_available() -> None:
    try:
        importlib.import_module("build")
    except Exception:
        print("Distribution artifact check failed.", file=sys.stderr)
        print("", file=sys.stderr)
        print(
            "The `build` package is required to validate the sdist and wheel distribution boundary.",
            file=sys.stderr,
        )
        print("", file=sys.stderr)
        print(
            "Install the project dependencies first, for example with `python -m pip install -e '.[dev]'`.",
            file=sys.stderr,
        )
        raise SystemExit(1)


def _stage_source_tree(source_root: Path, destination: Path) -> Path:
    staged_root = destination / "source-tree"
    shutil.copytree(source_root, staged_root, ignore=COPY_IGNORE_PATTERNS)
    return staged_root


def _required_sdist_paths(source_root: Path) -> set[str]:
    manifest = json.loads(
        (source_root / "docs" / "architecture" / "contract_manifest.json").read_text(encoding="utf-8")
    )
    paths = {
        "README.md",
        "pyproject.toml",
        "MANIFEST.in",
        "src/mcp_bridge/contract/__init__.py",
        "src/mcp_bridge/contract/artifacts.py",
    }
    contract_manifest = manifest.get("contractManifest") or {}
    capability_matrix = manifest.get("capabilityMatrix") or {}
    if contract_manifest.get("relativePath"):
        paths.add(contract_manifest["relativePath"])
    if capability_matrix.get("relativePath"):
        paths.add(capability_matrix["relativePath"])
    for schema_entry in manifest.get("schemas") or []:
        if schema_entry.get("relativePath"):
            paths.add(schema_entry["relativePath"])
        if schema_entry.get("exampleRelativePath"):
            paths.add(schema_entry["exampleRelativePath"])
    for artifact in manifest.get("supportingArtifacts") or []:
        if artifact.get("relativePath"):
            paths.add(artifact["relativePath"])
    return paths


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strip_archive_prefix(name: str) -> str:
    parts = Path(name).parts
    if len(parts) <= 1:
        return ""
    return str(Path(*parts[1:]))


def _sdist_members(path: Path) -> set[str]:
    members: set[str] = set()
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            relative = _strip_archive_prefix(member.name)
            if relative:
                members.add(relative)
    return members


def _wheel_members(path: Path) -> set[str]:
    members: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        members.update(archive.namelist())
    return members


def _assert_paths_present(label: str, members: set[str], required: set[str]) -> None:
    missing = sorted(required.difference(members))
    if missing:
        print(f"{label} is missing required files:", file=sys.stderr)
        for path in missing:
            print(f"- {path}", file=sys.stderr)
        raise SystemExit(1)


def _build_release_artifact_report(source_root: Path, sdist_path: Path, wheel_path: Path) -> dict[str, object]:
    manifest = json.loads(
        (source_root / "docs" / "architecture" / "contract_manifest.json").read_text(encoding="utf-8")
    )
    release_metadata_module = _load_release_metadata_module()
    release_metadata = release_metadata_module.collect_release_metadata(source_root)
    capability_matrix = manifest.get("capabilityMatrix") or {}
    contract_manifest = manifest.get("contractManifest") or {}
    artifact_counts = manifest.get("artifactCounts") or {}
    return {
        "packageVersion": release_metadata["version"],
        "contractVersion": manifest.get("contractVersion"),
        "releaseNotePath": release_metadata["releaseNotePath"],
        "contractManifest": {
            "relativePath": contract_manifest.get("relativePath"),
            "sha256": _sha256(source_root / contract_manifest["relativePath"]),
        },
        "capabilityMatrix": {
            "relativePath": capability_matrix.get("relativePath"),
            "sha256": capability_matrix.get("sha256"),
        },
        "artifactCounts": {
            "schemas": artifact_counts.get("schemas", 0),
            "examples": artifact_counts.get("examples", 0),
            "supporting": artifact_counts.get("supporting", 0),
        },
        "artifacts": {
            "sdist": {
                "filename": sdist_path.name,
                "sha256": _sha256(sdist_path),
                "sizeBytes": sdist_path.stat().st_size,
            },
            "wheel": {
                "filename": wheel_path.name,
                "sha256": _sha256(wheel_path),
                "sizeBytes": wheel_path.stat().st_size,
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=WORKSPACE_ROOT,
        help="Project root to build and validate. Defaults to the current workspace root.",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Optional output directory that should retain the validated sdist and wheel artifacts.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Optional JSON path that should retain a release-artifact integrity report.",
    )
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    _ensure_build_available()

    with tempfile.TemporaryDirectory(prefix="pbpk_distribution_artifacts_") as temp_dir:
        temp_root = Path(temp_dir)
        outdir = (
            args.artifact_dir.resolve()
            if args.artifact_dir is not None
            else temp_root / "dist"
        )
        runner = temp_root / "runner"
        staged_root = _stage_source_tree(source_root, temp_root)
        outdir.mkdir(parents=True, exist_ok=True)
        for artifact in list(outdir.glob("*.tar.gz")) + list(outdir.glob("*.whl")):
            artifact.unlink()
        outdir.mkdir(parents=True, exist_ok=True)
        runner.mkdir(parents=True, exist_ok=True)

        _run(
            [
                sys.executable,
                "-m",
                "build",
                "--sdist",
                "--wheel",
                "--outdir",
                str(outdir),
                str(staged_root),
            ],
            cwd=runner,
        )

        sdists = sorted(outdir.glob("*.tar.gz"))
        wheels = sorted(outdir.glob("*.whl"))
        if len(sdists) != 1 or len(wheels) != 1:
            print("Distribution artifact check failed.", file=sys.stderr)
            print(
                f"Expected exactly one sdist and one wheel, found {len(sdists)} sdists and {len(wheels)} wheels.",
                file=sys.stderr,
            )
            return 1

        sdist_path = sdists[0]
        wheel_path = wheels[0]

        _assert_paths_present("sdist", _sdist_members(sdist_path), _required_sdist_paths(source_root))
        _assert_paths_present(
            "wheel",
            _wheel_members(wheel_path),
            {
                "mcp_bridge/contract/__init__.py",
                "mcp_bridge/contract/artifacts.py",
            },
        )

        _run(
            [
                sys.executable,
                str(CHECK_INSTALLED_PACKAGE_CONTRACT),
                "--source",
                str(wheel_path),
                "--repo-root",
                str(source_root),
            ],
            cwd=runner,
        )

        report_path = args.report_path.resolve() if args.report_path is not None else None
        if report_path is not None:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report = _build_release_artifact_report(source_root, sdist_path, wheel_path)
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        print("Distribution artifact check passed.")
        print(f"- sdist {sdist_path.name}")
        print(f"- wheel {wheel_path.name}")
        if report_path is not None:
            print(f"- report {report_path}")
        if args.artifact_dir is not None:
            print(f"- retained artifacts {outdir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
