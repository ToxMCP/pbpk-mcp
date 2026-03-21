#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


VERSION_RE = r"\d+\.\d+\.\d+"


class ReleaseMetadataError(RuntimeError):
    """Raised when the public release metadata is inconsistent."""


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _search(pattern: str, text: str, *, label: str, path: Path) -> re.Match[str]:
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    if match is None:
        raise ReleaseMetadataError(f"Could not find {label} in {path}.")
    return match


def collect_release_metadata(workspace_root: Path) -> dict[str, str]:
    workspace_root = workspace_root.resolve()
    pyproject_path = workspace_root / "pyproject.toml"
    package_init_path = workspace_root / "src" / "mcp_bridge" / "__init__.py"
    env_path = workspace_root / ".env.example"
    compose_path = workspace_root / "docker-compose.celery.yml"
    readme_path = workspace_root / "README.md"
    changelog_path = workspace_root / "CHANGELOG.md"

    pyproject_text = _read_text(pyproject_path)
    project_block = _search(
        r"^\[project\]\n(?P<block>.*?)(?=^\[|\Z)",
        pyproject_text,
        label="the [project] block",
        path=pyproject_path,
    ).group("block")
    project_version = _search(
        rf'^version = "(?P<version>{VERSION_RE})"$',
        project_block,
        label="project.version",
        path=pyproject_path,
    ).group("version")

    package_fallback_version = _search(
        rf'^    __version__ = "(?P<version>{VERSION_RE})"$',
        _read_text(package_init_path),
        label="fallback __version__",
        path=package_init_path,
    ).group("version")

    env_service_version = _search(
        rf'^SERVICE_VERSION="(?P<version>{VERSION_RE})"$',
        _read_text(env_path),
        label="SERVICE_VERSION",
        path=env_path,
    ).group("version")

    compose_service_version = _search(
        rf'SERVICE_VERSION: "(?P<version>{VERSION_RE})"',
        _read_text(compose_path),
        label="compose SERVICE_VERSION",
        path=compose_path,
    ).group("version")

    readme_text = _read_text(readme_path)
    readme_whats_new_version = _search(
        rf"^## What's new in v(?P<version>{VERSION_RE})$",
        readme_text,
        label="README release heading",
        path=readme_path,
    ).group("version")
    readme_service_version = _search(
        rf"^\| `SERVICE_VERSION` \| `(?P<version>{VERSION_RE})` \|",
        readme_text,
        label="README SERVICE_VERSION table entry",
        path=readme_path,
    ).group("version")

    changelog_matches = re.findall(
        rf"^## v(?P<version>{VERSION_RE}) - (?P<date>\d{{4}}-\d{{2}}-\d{{2}})$",
        _read_text(changelog_path),
        flags=re.MULTILINE,
    )
    if not changelog_matches:
        raise ReleaseMetadataError(f"Could not find a versioned release heading in {changelog_path}.")
    changelog_version, changelog_date = changelog_matches[0]

    release_note_path = workspace_root / "docs" / "releases" / f"v{project_version}.md"
    if not release_note_path.is_file():
        raise ReleaseMetadataError(
            f"Release note file for v{project_version} is missing: {release_note_path}."
        )
    release_note_version = _search(
        rf"^# PBPK MCP v(?P<version>{VERSION_RE})$",
        _read_text(release_note_path),
        label="release note heading",
        path=release_note_path,
    ).group("version")

    return {
        "version": project_version,
        "projectVersion": project_version,
        "packageFallbackVersion": package_fallback_version,
        "envServiceVersion": env_service_version,
        "composeServiceVersion": compose_service_version,
        "readmeWhatsNewVersion": readme_whats_new_version,
        "readmeServiceVersion": readme_service_version,
        "changelogTopVersion": changelog_version,
        "changelogTopDate": changelog_date,
        "releaseNoteVersion": release_note_version,
        "releaseNotePath": str(release_note_path.relative_to(workspace_root)),
    }


def validate_release_metadata(workspace_root: Path) -> dict[str, str]:
    summary = collect_release_metadata(workspace_root)
    version = summary["version"]
    checks = {
        "packageFallbackVersion": summary["packageFallbackVersion"],
        "envServiceVersion": summary["envServiceVersion"],
        "composeServiceVersion": summary["composeServiceVersion"],
        "readmeWhatsNewVersion": summary["readmeWhatsNewVersion"],
        "readmeServiceVersion": summary["readmeServiceVersion"],
        "changelogTopVersion": summary["changelogTopVersion"],
        "releaseNoteVersion": summary["releaseNoteVersion"],
    }
    errors = [
        f"{field} is {actual}, expected {version}."
        for field, actual in checks.items()
        if actual != version
    ]
    if errors:
        raise ReleaseMetadataError("Release metadata is inconsistent:\n- " + "\n- ".join(errors))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Workspace root to validate. Defaults to the current repository root.",
    )
    args = parser.parse_args()

    try:
        summary = validate_release_metadata(args.root)
    except ReleaseMetadataError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
