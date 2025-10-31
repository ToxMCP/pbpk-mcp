"""Audit trail read-only endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..audit import AuditTrail
from ..dependencies import get_audit_trail
from ..security.auth import AuthContext, require_roles

router = APIRouter(prefix="/audit", tags=["audit"])


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
