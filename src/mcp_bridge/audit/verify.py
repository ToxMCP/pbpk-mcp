"""Audit trail verification utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from .trail import compute_event_hash


@dataclass
class VerificationResult:
    ok: bool
    checked_events: int
    message: str = ""


def iter_event_files(base_dir: Path, *, start: Optional[str] = None, end: Optional[str] = None) -> Iterable[Path]:
    base = Path(base_dir)
    for path in sorted(base.rglob("*.jsonl")):
        rel = path.relative_to(base)
        date_key = "/".join(rel.parts[:3]) if len(rel.parts) >= 3 else rel.stem
        if start and date_key < start:
            continue
        if end and date_key > end:
            continue
        yield path


def verify_audit_trail(base_dir: Path | str, *, start: str | None = None, end: str | None = None) -> VerificationResult:
    base = Path(base_dir)
    if not base.exists():
        return VerificationResult(ok=False, checked_events=0, message="Audit directory not found")

    previous_hash = "0" * 64
    checked = 0

    for path in iter_event_files(base, start=start, end=end):
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    return VerificationResult(
                        ok=False,
                        checked_events=checked,
                        message=f"Invalid JSON in {path} line {line_number}: {exc}",
                    )
                expected_prev = event.get("previousHash", "")
                if expected_prev != previous_hash:
                    return VerificationResult(
                        ok=False,
                        checked_events=checked,
                        message=(
                            "Hash chain mismatch in %s line %d: expected previousHash %s, found %s"
                            % (path, line_number, previous_hash, expected_prev)
                        ),
                    )
                actual_hash = compute_event_hash(event)
                if actual_hash != event.get("hash"):
                    return VerificationResult(
                        ok=False,
                        checked_events=checked,
                        message=(
                            "Hash mismatch in %s line %d: recomputed %s but stored %s"
                            % (path, line_number, actual_hash, event.get("hash"))
                        ),
                    )
                previous_hash = actual_hash
                checked += 1

    return VerificationResult(ok=True, checked_events=checked, message="Verified")


if __name__ == "__main__":  # pragma: no cover - CLI helper
    import argparse

    parser = argparse.ArgumentParser(description="Verify audit trail hash chain")
    parser.add_argument("path", help="Audit storage directory")
    parser.add_argument("--start", help="Optional start date key (YYYY/MM/DD)")
    parser.add_argument("--end", help="Optional end date key (YYYY/MM/DD)")
    args = parser.parse_args()

    result = verify_audit_trail(args.path, start=args.start, end=args.end)
    if result.ok:
        print(f"Audit verification succeeded: {result.checked_events} events")
    else:
        print(f"Audit verification failed after {result.checked_events} events: {result.message}")
        raise SystemExit(1)
