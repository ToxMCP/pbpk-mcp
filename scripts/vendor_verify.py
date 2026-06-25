#!/usr/bin/env python3
"""vendor:verify — digest-integrity gate for the vendored schema-spine engine.

The Track-B scientific-invariants gate vendors a digest-pinned copy of the
ToxMCP/toxmcp-schema-spine policy engine under ``vendor/schema-spine/``. This
script is the tamper-evidence layer: it recomputes the SHA-256 of every vendored
file and compares it against the ``fileDigests`` map recorded in
``vendor/schema-spine/VENDORED_FROM.json``.

It HARD-FAILS (exit 1) on any of:
  * a vendored file whose recomputed digest differs from the recorded one
    (tamper / accidental edit of a vendored engine file);
  * a file present on disk under the vendor root but absent from the manifest
    (an untracked addition that would otherwise dodge the digest check);
  * a file recorded in the manifest but missing on disk.

``--write`` regenerates ``VENDORED_FROM.json`` from the current tree (used once,
at vendor time; not run in CI). ``vendoredAt`` is held to a fixed string so the
manifest is reproducible.

Exit codes:
    0 — every vendored file matches its recorded digest (pristine)
    1 — drift / tamper / missing / untracked file detected

This gate is ADVISORY on the free-plan private repo (no required-status-checks),
but the *bridge* additionally fails closed at runtime on VENDOR_DIGEST_MISMATCH,
so a tampered engine blocks the gate even if CI is only advisory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_ROOT = REPO_ROOT / "vendor" / "schema-spine"
MANIFEST_PATH = VENDOR_ROOT / "VENDORED_FROM.json"
MANIFEST_NAME = "VENDORED_FROM.json"

# Pinned provenance (the canonical spine HEAD this engine was vendored from).
SPINE_REPO = "https://github.com/ToxMCP/toxmcp-schema-spine"
SPINE_GIT_SHA = "e0a6a0581efd8dfd5b10c2de14435d87769c5944"
VENDORED_AT = "2026-06-22T00:00:00Z"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _vendored_files() -> list[Path]:
    """Every file under the vendor root except the manifest itself."""
    return sorted(
        p
        for p in VENDOR_ROOT.rglob("*")
        if p.is_file() and p.name != MANIFEST_NAME
    )


def _rel(path: Path) -> str:
    return path.relative_to(VENDOR_ROOT).as_posix()


def write_manifest() -> int:
    files = _vendored_files()
    file_digests = {_rel(p): _sha256(p) for p in files}
    manifest = {
        "repo": SPINE_REPO,
        "gitSha": SPINE_GIT_SHA,
        "vendoredAt": VENDORED_AT,
        "note": (
            "Digest-pinned vendored copy of the ToxMCP schema-spine policy "
            "engine for the pbpk-mcp Track-B scientific-invariants gate. "
            "vendor:verify recomputes sha256 of every listed file and "
            "hard-fails on mismatch. Do not edit vendored files by hand."
        ),
        "digestAlgorithm": "sha256",
        "fileDigests": file_digests,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    print(
        f"[vendor:verify] wrote {MANIFEST_NAME} with {len(file_digests)} "
        f"file digests; gitSha {SPINE_GIT_SHA}"
    )
    return 0


def verify() -> int:
    if not MANIFEST_PATH.exists():
        print(f"[vendor:verify] FAIL: missing {MANIFEST_PATH}", file=sys.stderr)
        return 1
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    recorded: dict[str, str] = manifest.get("fileDigests", {})
    if not recorded:
        print("[vendor:verify] FAIL: empty fileDigests map", file=sys.stderr)
        return 1

    on_disk = {_rel(p): p for p in _vendored_files()}
    problems: list[str] = []

    # Untracked files on disk (would dodge the digest check).
    for rel in sorted(set(on_disk) - set(recorded)):
        problems.append(f"UNTRACKED vendored file not in manifest: {rel}")

    # Missing / mismatched files.
    for rel, expected in sorted(recorded.items()):
        path = on_disk.get(rel)
        if path is None:
            problems.append(f"MISSING vendored file recorded in manifest: {rel}")
            continue
        actual = _sha256(path)
        if actual != expected:
            problems.append(
                f"DIGEST MISMATCH {rel}: expected {expected[:12]}… got {actual[:12]}…"
            )

    if problems:
        print("[vendor:verify] FAIL — vendored engine integrity check failed:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(
        f"[vendor:verify] OK — {len(recorded)} vendored files match "
        f"VENDORED_FROM.json (gitSha {manifest.get('gitSha', '?')[:12]}…)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="(re)generate VENDORED_FROM.json from the current vendor tree",
    )
    args = parser.parse_args(argv)
    if args.write:
        return write_manifest()
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
