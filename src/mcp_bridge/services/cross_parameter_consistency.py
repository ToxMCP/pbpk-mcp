"""Cross-parameter consistency validation for PBPK models.

Ensures that combinations of physiologically related parameters remain
internally consistent (e.g. organ blood flows do not exceed cardiac output).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp_bridge.adapter.errors import AdapterError

if TYPE_CHECKING:  # pragma: no cover
    from mcp_bridge.adapter.interface import OspsuiteAdapter


class CrossParameterConsistencyValidator:
    """Validates cross-parameter physiological consistency.

    The validator reads related parameters from the active simulation via the
    adapter. If a required related parameter cannot be read, the rule is
    skipped gracefully rather than failing the request.
    """

    # Candidate paths are tried in order; the first readable path wins.
    _CANDIDATE_PATHS: dict[str, list[str]] = {
        "body_weight": [
            "Organism|Weight",
            "Weight",
        ],
        "cardiac_output": [
            "Organism|CardiacOutput",
            "CardiacOutput",
        ],
        "liver_volume": [
            "Organism|Liver|Volume",
            "Liver|Volume",
        ],
        "kidney_volume": [
            "Organism|Kidney|Volume",
            "Kidney|Volume",
        ],
        "brain_volume": [
            "Organism|Brain|Volume",
            "Brain|Volume",
        ],
        "muscle_volume": [
            "Organism|Muscle|Volume",
            "Muscle|Volume",
        ],
        "adipose_volume": [
            "Organism|AdiposeTissue|Volume",
            "Organism|Adipose|Volume",
            "Organism|Fat|Volume",
            "AdiposeTissue|Volume",
            "Adipose|Volume",
            "Fat|Volume",
        ],
        "heart_volume": [
            "Organism|Heart|Volume",
            "Heart|Volume",
        ],
        "lung_volume": [
            "Organism|Lung|Volume",
            "Lung|Volume",
        ],
        "skin_volume": [
            "Organism|Skin|Volume",
            "Skin|Volume",
        ],
        "bone_volume": [
            "Organism|Bone|Volume",
            "Organism|Skeletal|Volume",
            "Bone|Volume",
            "Skeletal|Volume",
        ],
        "small_intestine_volume": [
            "Organism|SmallIntestine|Volume",
            "Organism|Small intestine|Volume",
            "SmallIntestine|Volume",
            "Small intestine|Volume",
        ],
        "large_intestine_volume": [
            "Organism|LargeIntestine|Volume",
            "Organism|Large intestine|Volume",
            "LargeIntestine|Volume",
            "Large intestine|Volume",
        ],
        "pancreas_volume": [
            "Organism|Pancreas|Volume",
            "Pancreas|Volume",
        ],
        "spleen_volume": [
            "Organism|Spleen|Volume",
            "Spleen|Volume",
        ],
        "liver_blood_flow": [
            "Organism|Liver|BloodFlow",
            "Liver|BloodFlow",
        ],
        "kidney_blood_flow": [
            "Organism|Kidney|BloodFlow",
            "Kidney|BloodFlow",
        ],
        "brain_blood_flow": [
            "Organism|Brain|BloodFlow",
            "Brain|BloodFlow",
        ],
        "heart_blood_flow": [
            "Organism|Heart|BloodFlow",
            "Organism|Coronary|BloodFlow",
            "Heart|BloodFlow",
            "Coronary|BloodFlow",
        ],
        "lung_blood_flow": [
            "Organism|Lung|BloodFlow",
            "Organism|Pulmonary|BloodFlow",
            "Lung|BloodFlow",
            "Pulmonary|BloodFlow",
        ],
        "skin_blood_flow": [
            "Organism|Skin|BloodFlow",
            "Skin|BloodFlow",
        ],
        "bone_blood_flow": [
            "Organism|Bone|BloodFlow",
            "Organism|Skeletal|BloodFlow",
            "Bone|BloodFlow",
            "Skeletal|BloodFlow",
        ],
        "small_intestine_blood_flow": [
            "Organism|SmallIntestine|BloodFlow",
            "Organism|Small intestine|BloodFlow",
            "SmallIntestine|BloodFlow",
            "Small intestine|BloodFlow",
        ],
        "large_intestine_blood_flow": [
            "Organism|LargeIntestine|BloodFlow",
            "Organism|Large intestine|BloodFlow",
            "LargeIntestine|BloodFlow",
            "Large intestine|BloodFlow",
        ],
        "pancreas_blood_flow": [
            "Organism|Pancreas|BloodFlow",
            "Pancreas|BloodFlow",
        ],
        "spleen_blood_flow": [
            "Organism|Spleen|BloodFlow",
            "Spleen|BloodFlow",
        ],
        "liver_clearance": [
            "Organism|Liver|Clearance",
            "Liver|Clearance",
        ],
    }

    def __init__(self, adapter: OspsuiteAdapter, simulation_id: str) -> None:
        self._adapter = adapter
        self._simulation_id = simulation_id

    @classmethod
    def _to_standard_unit(cls, value: float, unit: str | None, target_unit: str) -> float:
        """Convert a value to a standard unit for comparison."""
        source = (unit or "unitless").strip().lower()
        target = target_unit.strip().lower()
        if source == target:
            return value
        # Volume
        if target == "l" and source in {"ml", "milliliter", "milliliters"}:
            return value / 1000.0
        if target == "ml" and source in {"l", "liter", "liters", "litre", "litres"}:
            return value * 1000.0
        # Flow
        if target == "l/min" and source in {"l/h", "l/hr", "lh"}:
            return value / 60.0
        if target == "l/min" and source in {"ml/min", "ml/minute"}:
            return value / 1000.0
        if target == "l/h" and source in {"l/min", "l/minute"}:
            return value * 60.0
        # Mass (body weight) - treat kg as default; g needs conversion
        if target == "kg" and source in {"g", "gram", "grams"}:
            return value / 1000.0
        if target == "g" and source in {"kg", "kilogram", "kilograms"}:
            return value * 1000.0
        # Fallback: assume value is already in target unit
        return value

    def _read_parameter(self, logical_name: str) -> tuple[float, str] | None:
        """Try to read a parameter by its logical name using candidate paths."""
        candidates = self._CANDIDATE_PATHS.get(logical_name, [])
        for path in candidates:
            try:
                pv = self._adapter.get_parameter_value(self._simulation_id, path)
                return (pv.value, pv.unit or "unitless")
            except AdapterError:
                continue
        return None

    @staticmethod
    def _path_matches_candidate(proposed_path: str, candidate: str) -> bool:
        """Check whether a concrete parameter path matches a candidate pattern.

        Supports exact match or suffix match on the last one or two pipe-separated
        segments so that ``Organism|Liver|Volume`` matches ``Liver|Volume``.
        """
        if proposed_path == candidate:
            return True
        parts = candidate.split("|")
        suffix = "|".join(parts[-2:]) if len(parts) >= 2 else parts[-1]
        return proposed_path.endswith(suffix)

    def _read_volume(self, logical_name: str, proposed_path: str | None = None, proposed_value: float | None = None, proposed_unit: str | None = None) -> float | None:
        """Read a volume parameter, substituting the proposed value if paths match."""
        if proposed_path is not None:
            candidates = self._CANDIDATE_PATHS.get(logical_name, [])
            if any(self._path_matches_candidate(proposed_path, c) for c in candidates):
                if proposed_value is not None:
                    return self._to_standard_unit(proposed_value, proposed_unit, "L")
        result = self._read_parameter(logical_name)
        if result is None:
            return None
        value, unit = result
        return self._to_standard_unit(value, unit, "L")

    def _read_flow(self, logical_name: str, proposed_path: str | None = None, proposed_value: float | None = None, proposed_unit: str | None = None) -> float | None:
        """Read a flow parameter, substituting the proposed value if paths match."""
        if proposed_path is not None:
            candidates = self._CANDIDATE_PATHS.get(logical_name, [])
            if any(self._path_matches_candidate(proposed_path, c) for c in candidates):
                if proposed_value is not None:
                    return self._to_standard_unit(proposed_value, proposed_unit, "L/min")
        result = self._read_parameter(logical_name)
        if result is None:
            return None
        value, unit = result
        return self._to_standard_unit(value, unit, "L/min")

    def _read_clearance(self, logical_name: str, proposed_path: str | None = None, proposed_value: float | None = None, proposed_unit: str | None = None) -> float | None:
        """Read a clearance parameter, substituting the proposed value if paths match."""
        if proposed_path is not None:
            candidates = self._CANDIDATE_PATHS.get(logical_name, [])
            if any(self._path_matches_candidate(proposed_path, c) for c in candidates):
                if proposed_value is not None:
                    return self._to_standard_unit(proposed_value, proposed_unit, "L/min")
        result = self._read_parameter(logical_name)
        if result is None:
            return None
        value, unit = result
        return self._to_standard_unit(value, unit, "L/min")

    def _validate_organ_volumes(
        self,
        *,
        changed_logical: str | None = None,
        proposed_path: str | None = None,
        proposed_value: float | None = None,
        proposed_unit: str | None = None,
    ) -> list[str]:
        """Return volume consistency violations."""
        violations: list[str] = []
        bw_result = self._read_parameter("body_weight")
        if bw_result is None:
            return violations
        bw_value = self._to_standard_unit(bw_result[0], bw_result[1], "kg")
        organ_volumes: list[tuple[str, float]] = []
        for logical, label in [
            ("liver_volume", "Liver volume"),
            ("kidney_volume", "Kidney volume"),
            ("brain_volume", "Brain volume"),
            ("muscle_volume", "Muscle volume"),
            ("adipose_volume", "Adipose volume"),
            ("heart_volume", "Heart volume"),
            ("lung_volume", "Lung volume"),
            ("skin_volume", "Skin volume"),
            ("bone_volume", "Bone volume"),
            ("small_intestine_volume", "Small intestine volume"),
            ("large_intestine_volume", "Large intestine volume"),
            ("pancreas_volume", "Pancreas volume"),
            ("spleen_volume", "Spleen volume"),
        ]:
            vol = self._read_volume(
                logical,
                proposed_path=proposed_path if changed_logical == logical else None,
                proposed_value=proposed_value if changed_logical == logical else None,
                proposed_unit=proposed_unit if changed_logical == logical else None,
            )
            if vol is not None:
                organ_volumes.append((label, vol))
        if organ_volumes:
            total_volume = sum(v for _, v in organ_volumes)
            if total_volume > bw_value:
                violations.append(
                    f"Total organ volume ({total_volume:.3f} L) exceeds body weight "
                    f"({bw_value:.3f} kg). Organs: "
                    + ", ".join(f"{n}={v:.3f} L" for n, v in organ_volumes)
                )
        return violations

    def _validate_organ_flows(
        self,
        *,
        changed_logical: str | None = None,
        proposed_path: str | None = None,
        proposed_value: float | None = None,
        proposed_unit: str | None = None,
    ) -> list[str]:
        """Return blood flow consistency violations."""
        violations: list[str] = []
        co_result = self._read_parameter("cardiac_output")
        if co_result is None:
            return violations
        co_value = self._to_standard_unit(co_result[0], co_result[1], "L/min")
        organ_flows: list[tuple[str, float]] = []
        for logical, label in [
            ("liver_blood_flow", "Hepatic blood flow"),
            ("kidney_blood_flow", "Renal blood flow"),
            ("brain_blood_flow", "Cerebral blood flow"),
            ("heart_blood_flow", "Coronary blood flow"),
            ("lung_blood_flow", "Pulmonary blood flow"),
            ("skin_blood_flow", "Cutaneous blood flow"),
            ("bone_blood_flow", "Skeletal blood flow"),
            ("small_intestine_blood_flow", "Small intestinal blood flow"),
            ("large_intestine_blood_flow", "Large intestinal blood flow"),
            ("pancreas_blood_flow", "Pancreatic blood flow"),
            ("spleen_blood_flow", "Splenic blood flow"),
        ]:
            flow = self._read_flow(
                logical,
                proposed_path=proposed_path if changed_logical == logical else None,
                proposed_value=proposed_value if changed_logical == logical else None,
                proposed_unit=proposed_unit if changed_logical == logical else None,
            )
            if flow is not None:
                organ_flows.append((label, flow))
        if organ_flows:
            total_flow = sum(v for _, v in organ_flows)
            if total_flow > co_value:
                violations.append(
                    f"Total organ blood flow ({total_flow:.3f} L/min) exceeds cardiac output "
                    f"({co_value:.3f} L/min). Flows: "
                    + ", ".join(f"{n}={v:.3f} L/min" for n, v in organ_flows)
                )
        return violations

    def _validate_hepatic_clearance(
        self,
        *,
        changed_logical: str | None = None,
        proposed_path: str | None = None,
        proposed_value: float | None = None,
        proposed_unit: str | None = None,
    ) -> list[str]:
        """Return hepatic clearance consistency violations."""
        violations: list[str] = []
        # When checking a single proposed change, only run if relevant.
        if changed_logical is not None and changed_logical not in ("liver_clearance", "liver_blood_flow"):
            return violations
        hepatic_flow = self._read_flow(
            "liver_blood_flow",
            proposed_path=proposed_path if changed_logical == "liver_blood_flow" else None,
            proposed_value=proposed_value if changed_logical == "liver_blood_flow" else None,
            proposed_unit=proposed_unit if changed_logical == "liver_blood_flow" else None,
        )
        hepatic_clearance = self._read_clearance(
            "liver_clearance",
            proposed_path=proposed_path if changed_logical == "liver_clearance" else None,
            proposed_value=proposed_value if changed_logical == "liver_clearance" else None,
            proposed_unit=proposed_unit if changed_logical == "liver_clearance" else None,
        )
        if hepatic_flow is not None and hepatic_clearance is not None:
            if hepatic_clearance > hepatic_flow:
                violations.append(
                    f"Hepatic clearance ({hepatic_clearance:.3f} L/min) exceeds hepatic blood flow "
                    f"({hepatic_flow:.3f} L/min)"
                )
        return violations

    def validate(self, parameter_path: str, value: float, unit: str | None = None) -> tuple[bool, list[str]]:
        """Run all applicable consistency checks for the proposed parameter change.

        Returns:
            (is_valid, list_of_violation_messages)
        """
        changed_logical = self._resolve_logical_name(parameter_path)
        violations: list[str] = []
        violations.extend(
            self._validate_organ_volumes(
                changed_logical=changed_logical,
                proposed_path=parameter_path,
                proposed_value=value,
                proposed_unit=unit,
            )
        )
        violations.extend(
            self._validate_organ_flows(
                changed_logical=changed_logical,
                proposed_path=parameter_path,
                proposed_value=value,
                proposed_unit=unit,
            )
        )
        violations.extend(
            self._validate_hepatic_clearance(
                changed_logical=changed_logical,
                proposed_path=parameter_path,
                proposed_value=value,
                proposed_unit=unit,
            )
        )
        return (len(violations) == 0, violations)

    def validate_all(self) -> dict[str, Any]:
        """Run a full simulation-wide consistency check.

        Returns:
            {
                "ok": bool,
                "violationCount": int,
                "violations": list[str],
                "summary": str,
                "checkedRules": list[str],
            }
        """
        violations: list[str] = []
        checked_rules: list[str] = []

        vol_violations = self._validate_organ_volumes()
        checked_rules.append("organ_volumes_vs_body_weight")
        violations.extend(vol_violations)

        flow_violations = self._validate_organ_flows()
        checked_rules.append("organ_blood_flows_vs_cardiac_output")
        violations.extend(flow_violations)

        clearance_violations = self._validate_hepatic_clearance()
        checked_rules.append("hepatic_clearance_vs_blood_flow")
        violations.extend(clearance_violations)

        ok = len(violations) == 0
        summary = (
            "All checked consistency rules passed."
            if ok
            else f"{len(violations)} cross-parameter consistency violation(s) detected."
        )
        return {
            "ok": ok,
            "violationCount": len(violations),
            "violations": violations,
            "summary": summary,
            "checkedRules": checked_rules,
        }

    def _resolve_logical_name(self, parameter_path: str) -> str | None:
        """Map a concrete parameter path to its logical name, if known."""
        for logical, candidates in self._CANDIDATE_PATHS.items():
            for candidate in candidates:
                if self._path_matches_candidate(parameter_path, candidate):
                    return logical
        return None


__all__ = ["CrossParameterConsistencyValidator"]
