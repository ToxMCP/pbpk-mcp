"""Sweep detection heuristics for parameter change audit events (PBPK-01)."""

from __future__ import annotations

from typing import Any


def detect_parameter_sweep(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Analyze a sequence of parameter changes for systematic exploration.

    Args:
        changes: List of audit event payloads for ``parameter.changed`` events,
            ordered oldest-first. Each payload should contain at least
            ``parameterPath`` and ``newValue``.

    Returns:
        A list of alert dictionaries. Empty if no suspicious patterns are found.
    """
    if len(changes) < 2:
        return []

    # Group by parameter path
    by_param: dict[str, list[dict[str, Any]]] = {}
    for change in changes:
        path = str(change.get("parameterPath") or "")
        if not path:
            continue
        by_param.setdefault(path, []).append(change)

    alerts: list[dict[str, Any]] = []

    for path, param_changes in by_param.items():
        values = [c.get("newValue") for c in param_changes if isinstance(c.get("newValue"), (int, float))]
        if len(values) < 2:
            continue

        # Pattern 1: Frequent changes to the same parameter
        if len(param_changes) > 5:
            alerts.append(
                {
                    "type": "frequent_changes",
                    "parameterPath": path,
                    "count": len(param_changes),
                    "recommendation": (
                        "Frequent parameter changes detected - possible optimization bias"
                    ),
                }
            )

        # Pattern 2: Oscillating values (searching for a target)
        if len(values) >= 3:
            diffs = [values[i + 1] - values[i] for i in range(len(values) - 1)]
            sign_changes = sum(
                1 for i in range(len(diffs) - 1) if diffs[i] * diffs[i + 1] < 0
            )
            if sign_changes >= 2:
                alerts.append(
                    {
                        "type": "oscillating_values",
                        "parameterPath": path,
                        "count": len(values),
                        "recommendation": (
                            "Oscillating parameter values - possible target-seeking behavior"
                        ),
                    }
                )

        # Pattern 3: Large relative magnitude changes
        large_changes = 0
        for i, change in enumerate(param_changes):
            new_val = change.get("newValue")
            old_val = change.get("oldValue")
            if not isinstance(new_val, (int, float)):
                continue
            if isinstance(old_val, (int, float)) and old_val != 0:
                rel_change = abs(new_val - old_val) / abs(old_val)
                if rel_change > 0.5:
                    large_changes += 1
            elif old_val is None and i == 0:
                # First change with no prior value: skip magnitude check
                continue

        if large_changes > 2:
            alerts.append(
                {
                    "type": "large_changes",
                    "parameterPath": path,
                    "count": large_changes,
                    "recommendation": (
                        "Large parameter changes detected - review physiological plausibility"
                    ),
                }
            )

    return alerts


__all__ = ["detect_parameter_sweep"]
