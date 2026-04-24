"""Audit trail verification utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

try:  # pragma: no cover - optional dependency
    import boto3  # type: ignore
    from botocore.exceptions import ClientError
    from botocore.response import StreamingBody
except ImportError:  # pragma: no cover - optional dependency
    boto3 = None  # type: ignore
    ClientError = Exception  # type: ignore
    StreamingBody = None  # type: ignore

from .trail import build_s3_client, compute_event_hash


@dataclass
class VerificationResult:
    ok: bool
    checked_events: int
    message: str = ""


def iter_event_files(base_dir: Path, *, start: Optional[str] = None, end: Optional[str] = None) -> Iterable[Path]:
    base = Path(base_dir)
    for path in sorted(base.rglob("*.jsonl")):
        date_key = _local_date_key(base, path)
        if start and date_key < start:
            continue
        if end and date_key > end:
            continue
        yield path


def verify_audit_trail(base_dir: Path | str, *, start: str | None = None, end: str | None = None) -> VerificationResult:
    base = Path(base_dir)
    if not base.exists():
        return VerificationResult(ok=False, checked_events=0, message="Audit directory not found")

    previous_hash = _initial_previous_hash(base, start=start)
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


def _initial_previous_hash(base: Path, *, start: str | None) -> str:
    if not start:
        return "0" * 64
    previous_path: Path | None = None
    for path in sorted(base.rglob("*.jsonl")):
        date_key = _local_date_key(base, path)
        if date_key >= start:
            break
        previous_path = path
    if previous_path is None:
        return "0" * 64
    try:
        lines = previous_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return "0" * 64
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        return str(event.get("hash") or ("0" * 64))
    return "0" * 64


def _iter_s3_keys(
    client,
    bucket: str,
    prefix: str,
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Iterable[str]:
    continuation = None
    while True:
        params = {"Bucket": bucket, "Prefix": prefix}
        if continuation:
            params["ContinuationToken"] = continuation
        response = client.list_objects_v2(**params)
        for obj in response.get("Contents", []):
            key = obj["Key"]
            date_key = "/".join(key[len(prefix.strip("/")) + 1 :].split("/")[:3])
            if start and date_key < start:
                continue
            if end and date_key > end:
                continue
            yield key
        if not response.get("IsTruncated"):
            break
        continuation = response.get("NextContinuationToken")


def verify_s3_audit_trail(
    *,
    bucket: str,
    prefix: str,
    client=None,
    region: Optional[str] = None,
    endpoint_url: Optional[str] = None,
    force_path_style: bool = False,
    start: Optional[str] = None,
    end: Optional[str] = None,
    expected_lock_mode: Optional[str] = None,
    expected_lock_days: Optional[int] = None,
) -> VerificationResult:
    if boto3 is None:  # pragma: no cover - defensive
        raise RuntimeError("boto3 is required to verify S3 audit trails")

    client = client or build_s3_client(
        region=region,
        endpoint_url=endpoint_url,
        force_path_style=force_path_style,
    )
    lock_mode = expected_lock_mode.upper() if expected_lock_mode else None
    min_delta = None
    if expected_lock_days:
        from datetime import timedelta

        min_delta = timedelta(days=expected_lock_days)

    previous_hash = _initial_s3_previous_hash(
        client,
        bucket=bucket,
        prefix=prefix.rstrip("/"),
        start=start,
    )
    checked = 0

    for key in _iter_s3_keys(client, bucket, prefix.rstrip("/"), start=start, end=end):
        try:
            head = client.head_object(Bucket=bucket, Key=key)
        except ClientError as exc:  # pragma: no cover - defensive
            return VerificationResult(
                ok=False,
                checked_events=checked,
                message=f"Failed to head object {key}: {exc}",
            )

        object_lock = head.get("ObjectLockMode")
        retain_until = head.get("ObjectLockRetainUntilDate")

        if lock_mode and object_lock != lock_mode:
            return VerificationResult(
                ok=False,
                checked_events=checked,
                message=f"Object {key} missing expected Object Lock mode {lock_mode}",
            )
        if min_delta and retain_until is None:
            return VerificationResult(
                ok=False,
                checked_events=checked,
                message=f"Object {key} missing retain-until date",
            )

        try:
            response = client.get_object(Bucket=bucket, Key=key)
        except ClientError as exc:  # pragma: no cover - defensive
            return VerificationResult(
                ok=False,
                checked_events=checked,
                message=f"Failed to fetch object {key}: {exc}",
            )

        body: StreamingBody = response["Body"]
        data = body.read().decode("utf-8").splitlines()

        max_event_ts = None

        from datetime import datetime, timezone

        for line_number, line in enumerate(data, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                return VerificationResult(
                    ok=False,
                    checked_events=checked,
                    message=f"Invalid JSON in s3://{bucket}/{key} line {line_number}: {exc}",
                )
            expected_prev = event.get("previousHash", "")
            if expected_prev != previous_hash:
                return VerificationResult(
                    ok=False,
                    checked_events=checked,
                    message=(
                        "Hash chain mismatch in s3://%s/%s line %d: expected previousHash %s, found %s"
                        % (bucket, key, line_number, previous_hash, expected_prev)
                    ),
                )
            actual_hash = compute_event_hash(event)
            if actual_hash != event.get("hash"):
                return VerificationResult(
                    ok=False,
                    checked_events=checked,
                    message=(
                        "Hash mismatch in s3://%s/%s line %d: recomputed %s but stored %s"
                        % (bucket, key, line_number, actual_hash, event.get("hash"))
                    ),
                )
            previous_hash = actual_hash
            checked += 1

            try:
                event_ts = datetime.fromisoformat(event.get("timestamp"))
            except Exception:  # pragma: no cover - defensive
                event_ts = None
            if event_ts is not None:
                if event_ts.tzinfo is None:
                    event_ts = event_ts.replace(tzinfo=timezone.utc)
                max_event_ts = event_ts if max_event_ts is None else max(max_event_ts, event_ts)

        if min_delta and retain_until is not None and max_event_ts is not None:
            if retain_until < max_event_ts + min_delta:
                return VerificationResult(
                    ok=False,
                    checked_events=checked,
                    message=(
                        f"Object {key} retain-until {retain_until} is earlier than expected minimum"
                    ),
                )

    return VerificationResult(ok=True, checked_events=checked, message="Verified")


def _initial_s3_previous_hash(
    client,
    *,
    bucket: str,
    prefix: str,
    start: Optional[str],
) -> str:
    if not start:
        return "0" * 64
    previous_key: Optional[str] = None
    for key in _iter_s3_keys(client, bucket, prefix):
        date_key = "/".join(key[len(prefix.strip("/")) + 1 :].split("/")[:3])
        if date_key >= start:
            break
        previous_key = key
    if previous_key is None:
        return "0" * 64
    try:
        response = client.get_object(Bucket=bucket, Key=previous_key)
    except ClientError:
        return "0" * 64
    body: StreamingBody = response["Body"]
    data = body.read().decode("utf-8").splitlines()
    for line in reversed(data):
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        return str(event.get("hash") or ("0" * 64))
    return "0" * 64


def _local_date_key(base: Path, path: Path) -> str:
    rel = path.relative_to(base)
    if len(rel.parts) >= 3:
        year, month, day_file = rel.parts[:3]
        return f"{year}/{month}/{Path(day_file).stem}"
    return path.stem


def _main() -> None:  # pragma: no cover - CLI helper
    import argparse
    from urllib.parse import urlparse

    parser = argparse.ArgumentParser(description="Verify audit trail hash chain")
    parser.add_argument("path", help="Audit storage location (directory or s3://bucket/prefix)")
    parser.add_argument("--start", help="Optional start date key (YYYY/MM/DD)")
    parser.add_argument("--end", help="Optional end date key (YYYY/MM/DD)")
    parser.add_argument("--object-lock-mode", help="Expected S3 Object Lock mode (governance/compliance)")
    parser.add_argument("--object-lock-days", type=int, help="Expected retention days for S3 Object Lock")
    parser.add_argument("--region", help="S3 region override")
    parser.add_argument("--endpoint-url", help="Custom S3 endpoint URL for S3-compatible stores")
    parser.add_argument(
        "--force-path-style",
        action="store_true",
        help="Force path-style S3 addressing for S3-compatible endpoints",
    )
    args = parser.parse_args()

    if args.path.startswith("s3://"):
        parsed = urlparse(args.path)
        bucket = parsed.netloc
        prefix = parsed.path.lstrip("/")
        if not bucket:
            raise SystemExit("Invalid S3 URI; bucket required")
        result = verify_s3_audit_trail(
            bucket=bucket,
            prefix=prefix,
            start=args.start,
            end=args.end,
            region=args.region,
            endpoint_url=args.endpoint_url,
            force_path_style=args.force_path_style,
            expected_lock_mode=args.object_lock_mode,
            expected_lock_days=args.object_lock_days,
        )
    else:
        result = verify_audit_trail(args.path, start=args.start, end=args.end)

    if result.ok:
        print(f"Audit verification succeeded: {result.checked_events} events")
    else:
        print(f"Audit verification failed after {result.checked_events} events: {result.message}")
        raise SystemExit(1)


if __name__ == "__main__":  # pragma: no cover - CLI helper
    _main()
