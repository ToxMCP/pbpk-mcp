"""Contracts and helper for the set_parameter_value MCP tool."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from prometheus_client import Counter

from mcp.session_registry import SessionRegistryError, registry
from mcp_bridge.adapter import AdapterError
from mcp_bridge.adapter.interface import OspsuiteAdapter
from mcp_bridge.audit.sweep_detection import detect_parameter_sweep
from mcp_bridge.logging import get_logger
from mcp_bridge.parameter_bounds import ParameterBoundsRegistry
from mcp_bridge.services.cross_parameter_consistency import CrossParameterConsistencyValidator
from mcp_bridge.storage.snapshot_store import SimulationSnapshotStore

from .get_parameter_value import ParameterValuePayload


logger = get_logger(__name__)

_PARAMETER_BOUNDS_VIOLATIONS = Counter(
    "mcp_parameter_bounds_violations_total",
    "Total parameter values rejected for violating physiological bounds.",
)
_PARAMETER_SWEEP_ALERTS = Counter(
    "mcp_parameter_sweep_alerts_total",
    "Total sweep alerts detected across parameter changes.",
    ("alert_type",),
)
_CROSS_PARAMETER_VIOLATIONS = Counter(
    "mcp_cross_parameter_violations_total",
    "Total cross-parameter consistency violations detected.",
)


class SetParameterValueRequest(BaseModel):
    """Payload for updating a parameter in a loaded simulation."""

    model_config = ConfigDict(populate_by_name=True)

    simulation_id: str = Field(alias="simulationId", min_length=1, max_length=64)
    parameter_path: str = Field(alias="parameterPath", min_length=1)
    value: float
    unit: Optional[str] = None
    update_mode: Optional[str] = Field(default="absolute", alias="updateMode")
    comment: Optional[str] = None

    @field_validator("parameter_path")
    @classmethod
    def _normalise_path(cls, value: str) -> str:
        path = value.strip()
        if not path:
            raise ValueError("parameter_path must be provided")
        if any(char in path for char in {"\0", "\n"}):
            raise ValueError("Invalid parameter path")
        return path

    @field_validator("update_mode")
    @classmethod
    def _validate_update_mode(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return "absolute"
        normalised = value.strip().lower()
        if normalised not in {"absolute", "relative"}:
            raise ValueError("updateMode must be 'absolute' or 'relative'")
        return normalised


class ParameterGovernancePayload(BaseModel):
    """Governance metadata returned with a successful parameter change."""

    model_config = ConfigDict(populate_by_name=True)

    snapshot_id: Optional[str] = Field(default=None, alias="snapshotId")
    sweep_alerts: list[dict[str, Any]] = Field(default_factory=list, alias="sweepAlerts")
    bounds_reference: list[str] = Field(default_factory=list, alias="boundsReference")


class SetParameterValueResponse(BaseModel):
    parameter: ParameterValuePayload
    governance: ParameterGovernancePayload = Field(
        default_factory=ParameterGovernancePayload, alias="governance"
    )


class SetParameterValueValidationError(ValueError):
    """Raised when validation fails for set_parameter_value."""


def _ensure_simulation(simulation_id: str) -> None:
    try:
        registry.get(simulation_id)
    except SessionRegistryError as exc:
        raise SetParameterValueValidationError(str(exc)) from exc


def _fetch_parameter_changes(audit: Any, simulation_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Fetch recent parameter.changed audit events for a simulation."""
    if audit is None or not getattr(audit, "enabled", False):
        return []
    try:
        events = audit.fetch_events(limit=limit, event_type="parameter.changed")
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(
            "parameter_change.audit_fetch_failed",
            simulationId=simulation_id,
            reason=str(exc),
        )
        return []
    return [e for e in events if str(e.get("simulationId")) == simulation_id]


def set_parameter_value(
    adapter: OspsuiteAdapter,
    payload: SetParameterValueRequest,
    *,
    audit_trail: Any = None,
    snapshot_store: SimulationSnapshotStore | None = None,
) -> SetParameterValueResponse:
    _ensure_simulation(payload.simulation_id)

    # 1. Validate physiological bounds (with dynamic weight scaling)
    is_valid, bounds, message = ParameterBoundsRegistry.validate(
        payload.parameter_path,
        payload.value,
        adapter=adapter,
        simulation_id=payload.simulation_id,
    )
    if not is_valid:
        _PARAMETER_BOUNDS_VIOLATIONS.inc()
        raise SetParameterValueValidationError(
            f"Parameter bounds violation: {message}"
        )
    if bounds is None:
        logger.warning(
            "parameter_bounds.unknown",
            simulationId=payload.simulation_id,
            parameterPath=payload.parameter_path,
        )

    # 1b. Validate cross-parameter consistency
    consistency_validator = CrossParameterConsistencyValidator(
        adapter, payload.simulation_id
    )
    consistent, violations = consistency_validator.validate(
        payload.parameter_path, payload.value, payload.unit
    )
    if not consistent:
        _CROSS_PARAMETER_VIOLATIONS.inc()
        raise SetParameterValueValidationError(
            "Cross-parameter consistency violation: " + "; ".join(violations)
        )

    # 2. Capture old value for audit trail
    old_value: float | None = None
    try:
        old = adapter.get_parameter_value(payload.simulation_id, payload.parameter_path)
        old_value = old.value
    except AdapterError as exc:
        # If the parameter cannot be read, we still attempt to set it and
        # let the adapter raise if the path is truly invalid.
        logger.debug(
            "parameter_change.old_value_unavailable",
            simulationId=payload.simulation_id,
            parameterPath=payload.parameter_path,
            reason=str(exc),
        )

    # 3. Auto-save snapshot before mutation
    snapshot_id: str | None = None
    if snapshot_store is not None:
        try:
            state = adapter.export_simulation_state(payload.simulation_id)
            record = snapshot_store.save(payload.simulation_id, state)
            snapshot_id = record.snapshot_id
        except Exception as exc:
            logger.warning(
                "parameter_change.snapshot_failed",
                simulationId=payload.simulation_id,
                reason=str(exc),
            )

    # 4. Apply the change
    try:
        result = adapter.set_parameter_value(
            payload.simulation_id,
            payload.parameter_path,
            payload.value,
            payload.unit,
            comment=payload.comment,
        )
    except AdapterError as exc:
        raise SetParameterValueValidationError(str(exc)) from exc

    # 5. Emit dedicated parameter change audit event
    if audit_trail is not None and getattr(audit_trail, "enabled", False):
        audit_trail.record_event(
            "parameter.changed",
            {
                "simulationId": payload.simulation_id,
                "parameterPath": payload.parameter_path,
                "oldValue": old_value,
                "newValue": payload.value,
                "unit": payload.unit,
                "comment": payload.comment,
                "boundsReference": bounds.references if bounds else None,
            },
        )

    # 6. Detect sweep patterns from recent audit history
    changes = _fetch_parameter_changes(audit_trail, payload.simulation_id)
    # fetch_events returns newest-first; sweep detection expects oldest-first
    sweep_alerts = detect_parameter_sweep(list(reversed(changes)))
    if sweep_alerts:
        for alert in sweep_alerts:
            _PARAMETER_SWEEP_ALERTS.labels(alert_type=alert["type"]).inc()
        logger.info(
            "parameter_change.sweep_detected",
            simulationId=payload.simulation_id,
            alertCount=len(sweep_alerts),
            alertTypes=[a["type"] for a in sweep_alerts],
        )

    governance = ParameterGovernancePayload(
        snapshotId=snapshot_id,
        sweepAlerts=sweep_alerts,
        boundsReference=bounds.references if bounds else [],
    )

    return SetParameterValueResponse(
        parameter=ParameterValuePayload.model_validate(result.model_dump()),
        governance=governance,
    )


__all__ = [
    "SetParameterValueRequest",
    "SetParameterValueResponse",
    "SetParameterValueValidationError",
    "set_parameter_value",
]
