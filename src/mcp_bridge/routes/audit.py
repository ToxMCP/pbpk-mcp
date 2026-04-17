"""Audit trail read-only endpoints."""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from ..audit.trail import AuditTrail
from ..audit.verify import VerificationResult, verify_audit_trail, verify_s3_audit_trail
from ..config import AppConfig
from ..dependencies import get_audit_trail
from ..security.auth import AuthContext, require_roles

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditVerifyRequest(BaseModel):
    storage: Literal["local", "s3"] | None = Field(
        default=None,
        description="Audit storage backend to verify (defaults to app config)",
    )
    path: Optional[str] = Field(
        default=None,
        description="Filesystem path for local audit storage (overrides config)",
    )
    bucket: Optional[str] = Field(
        default=None,
        description="S3 bucket (overrides config)",
    )
    prefix: Optional[str] = Field(
        default=None,
        description="S3 prefix (overrides config)",
    )
    start: Optional[str] = Field(
        default=None,
        description="Optional start date key (YYYY/MM/DD)",
    )
    end: Optional[str] = Field(
        default=None,
        description="Optional end date key (YYYY/MM/DD)",
    )
    objectLockMode: Optional[str] = Field(
        default=None,
        description="Expected S3 Object Lock mode (governance or compliance)",
    )
    objectLockDays: Optional[int] = Field(
        default=None,
        ge=1,
        description="Expected retention days for S3 Object Lock",
    )


class AuditVerifyResponse(BaseModel):
    ok: bool
    checkedEvents: int
    message: str


@router.get("/events")
def list_audit_events(
    limit: int = Query(100, ge=1, le=1000),
    eventType: Optional[str] = Query(None, alias="eventType"),
    audit: AuditTrail = Depends(get_audit_trail),
    _auth: AuthContext = Depends(require_roles("admin")),
) -> dict[str, list[dict[str, object]]]:
    try:
        events = audit.fetch_events(limit=limit, event_type=eventType)
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Audit event listing is not supported for this storage backend",
        ) from None
    return {"events": events}


@router.post("/verify", response_model=AuditVerifyResponse)
def verify_audit(
    body: AuditVerifyRequest,
    request: Request,
    _auth: AuthContext = Depends(require_roles("admin")),
) -> AuditVerifyResponse:
    config: AppConfig = request.app.state.config

    storage = body.storage or config.audit_storage_backend or "local"

    if storage == "local":
        base_path = body.path or config.audit_storage_path
        result = verify_audit_trail(base_path, start=body.start, end=body.end)
    elif storage == "s3":
        bucket = body.bucket or config.audit_s3_bucket
        if not bucket:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="S3 bucket is required for S3 audit verification",
            )
        prefix = body.prefix or config.audit_s3_prefix
        result = verify_s3_audit_trail(
            bucket=bucket,
            prefix=prefix,
            region=config.audit_s3_region,
            endpoint_url=config.audit_s3_endpoint_url,
            force_path_style=config.audit_s3_force_path_style,
            start=body.start,
            end=body.end,
            expected_lock_mode=body.objectLockMode or config.audit_s3_object_lock_mode,
            expected_lock_days=body.objectLockDays or config.audit_s3_object_lock_days,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audit storage backend: {storage}",
        )

    return AuditVerifyResponse(
        ok=result.ok,
        checkedEvents=result.checked_events,
        message=result.message,
    )
