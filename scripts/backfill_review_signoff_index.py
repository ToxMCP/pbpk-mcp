#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_bridge.audit.trail import LocalAuditTrail, S3AuditTrail  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill the review-signoff audit index from existing raw audit events.",
    )
    parser.add_argument(
        "path",
        help="Local audit directory or s3://bucket/prefix audit location.",
    )
    parser.add_argument("--region", default=None, help="S3 region override.")
    parser.add_argument("--endpoint-url", default=None, help="S3-compatible endpoint override.")
    parser.add_argument(
        "--force-path-style",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Force path-style S3 addressing for local S3-compatible backends.",
    )
    parser.add_argument(
        "--object-lock-mode",
        default=None,
        help="Optional S3 Object Lock mode to apply to newly indexed objects.",
    )
    parser.add_argument(
        "--object-lock-days",
        type=int,
        default=None,
        help="Optional S3 Object Lock retention days for newly indexed objects.",
    )
    parser.add_argument(
        "--kms-key-id",
        default=None,
        help="Optional S3 KMS key ID for newly indexed objects.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be indexed without writing new index entries.",
    )
    return parser.parse_args()


def _parse_s3_path(path: str) -> tuple[str, str]:
    if not path.startswith("s3://"):
        raise ValueError(f"Expected s3://bucket/prefix, got: {path}")
    remainder = path[5:]
    bucket, _, prefix = remainder.partition("/")
    if not bucket:
        raise ValueError(f"Missing S3 bucket in path: {path}")
    return bucket, prefix.strip("/")


def main() -> int:
    args = parse_args()
    if args.path.startswith("s3://"):
        bucket, prefix = _parse_s3_path(args.path)
        audit = S3AuditTrail(
            bucket=bucket,
            prefix=prefix,
            region=args.region,
            endpoint_url=args.endpoint_url,
            force_path_style=bool(args.force_path_style),
            object_lock_mode=args.object_lock_mode,
            object_lock_retain_days=args.object_lock_days,
            kms_key_id=args.kms_key_id,
        )
    else:
        audit = LocalAuditTrail(args.path)

    result = audit.backfill_review_signoff_index(dry_run=bool(args.dry_run))
    result["path"] = args.path
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
