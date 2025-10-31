#!/usr/bin/env python3
"""Retention and integrity report generator for artefacts under var/."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List


@dataclass
class Artefact:
    path: str
    size_bytes: int
    sha256: str
    mtime: str


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collect(root: Path) -> List[Artefact]:
    artefacts: List[Artefact] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        artefacts.append(
            Artefact(
                path=str(path.relative_to(root.parent)),
                size_bytes=stat.st_size,
                sha256=_hash_file(path),
                mtime=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            )
        )
    return artefacts


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate retention report for var artefacts")
    parser.add_argument("--root", default="var", help="Root directory to scan (default: var)")
    parser.add_argument("--output", default="var/reports/retention/report.json", help="Output report path")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"Root directory not found: {root}")

    artefacts = _collect(root)
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "artefacts": [asdict(item) for item in artefacts],
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote retention report to {output_path}")


if __name__ == "__main__":
    main()
