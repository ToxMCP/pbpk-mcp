#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.config import Config as BotoConfig

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_bridge.audit.verify import verify_s3_audit_trail  # noqa: E402
from mcp_bridge.security.simple_jwt import jwt  # noqa: E402


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_S3_ENDPOINT_URL = "http://127.0.0.1:9000"
DEFAULT_BUCKET = "pbpk-mcp-audit-smoke"
DEFAULT_PREFIX = "bridge/audit"
DEFAULT_REGION = "us-east-1"
DEFAULT_MODEL_PATH = "/app/var/models/esqlabs/esqlabsR/simple.pkml"


def build_auth_headers(
    *,
    bearer_token: str | None,
    auth_dev_secret: str | None,
    auth_role: str,
) -> dict[str, str]:
    if bearer_token:
        return {"authorization": f"Bearer {bearer_token}"}
    if auth_dev_secret:
        token = jwt.encode(
            {
                "sub": "s3-audit-smoke",
                "roles": [auth_role],
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
            },
            auth_dev_secret,
            algorithm="HS256",
        )
        return {"authorization": f"Bearer {token}"}
    return {}


def build_s3_client(
    *,
    endpoint_url: str | None,
    region: str | None,
    force_path_style: bool,
    access_key_id: str | None,
    secret_access_key: str | None,
):
    kwargs: dict[str, object] = {}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    if region:
        kwargs["region_name"] = region
    if access_key_id:
        kwargs["aws_access_key_id"] = access_key_id
    if secret_access_key:
        kwargs["aws_secret_access_key"] = secret_access_key
    if force_path_style:
        kwargs["config"] = BotoConfig(s3={"addressing_style": "path"})
    return boto3.client("s3", **kwargs)


def http_json(
    url: str,
    payload: dict | None = None,
    *,
    timeout: int = 60,
    headers: dict[str, str] | None = None,
) -> dict:
    data = None
    request_headers = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode()
        request_headers["content-type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        raise RuntimeError(f"{url} returned HTTP {exc.code}: {json.dumps(parsed)}") from exc


def call_tool(
    base_url: str,
    tool: str,
    arguments: dict,
    *,
    critical: bool = False,
    timeout: int = 60,
    headers: dict[str, str] | None = None,
) -> dict:
    response = http_json(
        f"{base_url.rstrip('/')}/mcp/call_tool",
        payload={"tool": tool, "arguments": arguments, **({"critical": True} if critical else {})},
        timeout=timeout,
        headers=headers,
    )
    return response["structuredContent"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-check the packaged S3-backed audit path.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--s3-endpoint-url", default=DEFAULT_S3_ENDPOINT_URL)
    parser.add_argument("--s3-bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--s3-prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--s3-region", default=DEFAULT_REGION)
    parser.add_argument(
        "--force-path-style",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Force path-style S3 addressing. Enabled by default for local S3-compatible smoke.",
    )
    parser.add_argument("--aws-access-key-id", default="minioadmin")
    parser.add_argument("--aws-secret-access-key", default="minioadmin")
    parser.add_argument("--auth-dev-secret", default=None)
    parser.add_argument("--bearer-token", default=None)
    parser.add_argument("--auth-role", default="operator")
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    headers = build_auth_headers(
        bearer_token=args.bearer_token,
        auth_dev_secret=args.auth_dev_secret,
        auth_role=args.auth_role,
    )
    simulation_id = f"s3-audit-smoke-{uuid4().hex[:8]}"

    load_payload = call_tool(
        args.base_url,
        "load_simulation",
        {"filePath": args.model_path, "simulationId": simulation_id},
        critical=True,
        headers=headers,
        timeout=180,
    )
    signoff_payload = http_json(
        f"{args.base_url.rstrip('/')}/review_signoff",
        payload={
            "simulationId": simulation_id,
            "scope": "validate_simulation_request",
            "disposition": "acknowledged",
            "rationale": "Smoke-checked against bounded validation context.",
            "confirm": True,
        },
        headers=headers,
    )
    validation_payload = call_tool(
        args.base_url,
        "validate_simulation_request",
        {
            "simulationId": simulation_id,
            "request": {"route": "iv-infusion", "contextOfUse": "research-only"},
        },
        headers=headers,
        timeout=120,
    )
    history_payload = http_json(
        f"{args.base_url.rstrip('/')}/review_signoff/history?"
        + urllib.parse.urlencode(
            {"simulationId": simulation_id, "scope": "validate_simulation_request", "limit": 10}
        ),
        headers=headers,
    )

    s3_client = build_s3_client(
        endpoint_url=args.s3_endpoint_url,
        region=args.s3_region,
        force_path_style=bool(args.force_path_style),
        access_key_id=args.aws_access_key_id,
        secret_access_key=args.aws_secret_access_key,
    )
    listing = s3_client.list_objects_v2(Bucket=args.s3_bucket, Prefix=args.s3_prefix)
    object_keys = sorted(item["Key"] for item in listing.get("Contents", []))
    verification = verify_s3_audit_trail(
        bucket=args.s3_bucket,
        prefix=args.s3_prefix,
        client=s3_client,
        region=args.s3_region,
        endpoint_url=args.s3_endpoint_url,
        force_path_style=bool(args.force_path_style),
    )

    if signoff_payload["operatorReviewSignoff"]["status"] != "recorded":
        raise RuntimeError("Operator review signoff was not recorded")
    if validation_payload["operatorReviewSignoff"]["status"] != "recorded":
        raise RuntimeError("Trust-bearing validation payload did not carry recorded signoff")
    if history_payload["operatorReviewSignoffHistory"]["returnedEntryCount"] < 1:
        raise RuntimeError("Review signoff history did not remain readable")
    if not object_keys:
        raise RuntimeError("No audit objects were written to the S3-compatible backend")
    if not verification.ok:
        raise RuntimeError(f"S3 audit verification failed: {verification.message}")

    print(
        json.dumps(
            {
                "status": "ok",
                "simulationId": simulation_id,
                "backend": load_payload.get("backend"),
                "auditObjectCount": len(object_keys),
                "firstAuditObjectKey": object_keys[0],
                "signoffStatus": validation_payload["operatorReviewSignoff"]["status"],
                "historyEntries": history_payload["operatorReviewSignoffHistory"]["returnedEntryCount"],
                "verifiedEvents": verification.checked_events,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
