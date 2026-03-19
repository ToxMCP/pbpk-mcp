#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
PATCH_ROOT = WORKSPACE_ROOT / "patches"
if str(PATCH_ROOT) not in sys.path:
    sys.path.insert(0, str(PATCH_ROOT))

from mcp_bridge.model_manifest import validate_model_manifest  # noqa: E402

SUPPORTED_MODEL_EXTENSIONS = {".pkml", ".r"}
MODEL_PATH_ENV = "MCP_MODEL_SEARCH_PATHS"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate static PBPK model manifests for supported .pkml and MCP-ready .R files."
    )
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Model file to validate. Repeat to validate multiple paths. Defaults to all discovered models.",
    )
    parser.add_argument(
        "--backend",
        choices=("ospsuite", "rxode2"),
        default=None,
        help="Restrict validation to a single backend when scanning discovery roots.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 when any validated model is not manifestStatus='valid'.",
    )
    return parser.parse_args()


def resolve_model_roots() -> tuple[Path, ...]:
    raw = os.getenv(MODEL_PATH_ENV, "")
    if raw.strip():
        roots = [Path(chunk.strip()).expanduser() for chunk in raw.split(os.pathsep) if chunk.strip()]
    else:
        roots = [
            WORKSPACE_ROOT / "var",
            WORKSPACE_ROOT / "reference" / "models" / "standard",
            WORKSPACE_ROOT / "tests" / "fixtures",
        ]
    resolved = []
    seen = set()
    for root in roots:
        candidate = root.resolve()
        if not candidate.exists():
            continue
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        resolved.append(candidate)
    return tuple(resolved)


def _collect_targets(paths: list[str], backend: str | None) -> list[Path]:
    if paths:
        return [Path(path).expanduser().resolve() for path in paths]

    targets: list[Path] = []
    for root in resolve_model_roots():
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix not in SUPPORTED_MODEL_EXTENSIONS:
                continue
            if backend == "ospsuite" and suffix != ".pkml":
                continue
            if backend == "rxode2" and suffix != ".r":
                continue
            targets.append(path.resolve())
    targets.sort()
    return targets


def _summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = [str(item["manifest"].get("manifestStatus", "unknown")) for item in items]
    qualification_states = [
        str((item["manifest"].get("qualificationState") or {}).get("state", "unknown"))
        for item in items
    ]
    return {
        "total": len(items),
        "valid": sum(1 for status in statuses if status == "valid"),
        "partial": sum(1 for status in statuses if status == "partial"),
        "missing": sum(1 for status in statuses if status == "missing"),
        "states": {
            state: qualification_states.count(state)
            for state in sorted(set(qualification_states))
        },
    }


def main() -> int:
    args = parse_args()
    targets = _collect_targets(args.path, args.backend)
    items = [validate_model_manifest(path) for path in targets]
    payload = {
        "summary": _summary(items),
        "items": items,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    if args.strict and any(item["manifest"].get("manifestStatus") != "valid" for item in items):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
