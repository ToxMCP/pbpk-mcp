"""Physiologically plausible parameter bounds for PBPK model guardrails (PBPK-01)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from mcp_bridge.adapter.interface import OspsuiteAdapter


class ParameterCategory(str, Enum):
    """Categories of PBPK parameters."""

    PHYSICOCHEMICAL = "physicochemical"
    ANATOMICAL = "anatomical"
    PHYSIOLOGICAL = "physiological"
    ENZYME_KINETICS = "enzyme_kinetics"


@dataclass(frozen=True)
class ParameterBounds:
    """Bounds for a single parameter.

    Supports optional allometric scaling based on body weight. When
    ``scale_reference_weight`` is provided, the effective bounds are computed
    dynamically from the simulation's body weight using:

        scaled = scale_reference_value * (weight / scale_reference_weight) ** scale_exponent
        min_eff = max(scaled / scale_tolerance_factor, min_value)
        max_eff = min(scaled * scale_tolerance_factor, max_value)

    This ensures that pediatric models receive tighter, physiologically
    appropriate bounds while static bounds continue to serve as absolute
    floors and ceilings.
    """

    min_value: float
    max_value: float
    default_value: float
    unit: str
    category: ParameterCategory
    description: str
    references: list[str] = field(default_factory=list)
    scale_reference_weight: float | None = None
    scale_reference_value: float | None = None
    scale_exponent: float = 1.0
    scale_tolerance_factor: float = 2.5

    def get_effective_bounds(self, body_weight: float | None = None) -> tuple[float, float]:
        """Return effective (min, max) bounds for the given body weight."""
        if (
            self.scale_reference_weight is None
            or self.scale_reference_value is None
            or body_weight is None
        ):
            return (self.min_value, self.max_value)

        factor = (body_weight / self.scale_reference_weight) ** self.scale_exponent
        ref_scaled = self.scale_reference_value * factor
        min_eff = max(ref_scaled / self.scale_tolerance_factor, self.min_value)
        max_eff = min(ref_scaled * self.scale_tolerance_factor, self.max_value)
        # Ensure min doesn't exceed max in pathological cases
        if min_eff > max_eff:
            min_eff = self.min_value
            max_eff = self.max_value
        return (min_eff, max_eff)

    def validate(self, value: float, body_weight: float | None = None) -> tuple[bool, Optional[str]]:
        """Check if value is within effective bounds."""
        min_eff, max_eff = self.get_effective_bounds(body_weight)
        if min_eff <= value <= max_eff:
            return True, None
        return (
            False,
            (
                f"Value {value} for parameter outside plausible range "
                f"[{min_eff:.4f}, {max_eff:.4f}] {self.unit}"
            ),
        )


class ParameterBoundsRegistry:
    """Lightweight registry of physiologically plausible parameter bounds.

    The registry uses path suffix matching so that adapter-specific naming
    conventions (e.g. ``Organism|Liver|Volume`` or ``Liver``) are handled
    without requiring an exact match.
    """

    _BOUNDS: dict[str, ParameterBounds] = {
        # Organ volumes (L) - based on ICRP 89
        "Liver": ParameterBounds(

            min_value=0.01,
            max_value=3.0,
            default_value=1.5,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Liver volume",
            references=["ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=1.5,
            scale_exponent=1.0,
            scale_tolerance_factor=2.5,
        ),
        "Kidney": ParameterBounds(

            min_value=0.005,
            max_value=0.6,
            default_value=0.31,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Kidney volume (both kidneys)",
            references=["ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=0.31,
            scale_exponent=1.0,
            scale_tolerance_factor=2.5,
        ),
        "Brain": ParameterBounds(
            min_value=0.05,
            max_value=1.8,
            default_value=1.4,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Brain volume",
            references=["ICRP 89"],
            # Brain volume does not scale linearly with body weight (it is
            # roughly constant after early childhood), so weight-based scaling
            # is disabled and static bounds are used across all ages.
        ),
        "Muscle": ParameterBounds(

            min_value=0.1,
            max_value=35.0,
            default_value=24.0,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Muscle volume",
            references=["ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=24.0,
            scale_exponent=1.0,
            scale_tolerance_factor=2.5,
        ),
        "Adipose": ParameterBounds(

            min_value=0.05,
            max_value=30.0,
            default_value=15.0,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Adipose tissue volume",
            references=["ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=15.0,
            scale_exponent=1.0,
            scale_tolerance_factor=2.5,
        ),
        "Fat": ParameterBounds(

            min_value=0.05,
            max_value=30.0,
            default_value=15.0,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Adipose (fat) tissue volume",
            references=["ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=15.0,
            scale_exponent=1.0,
            scale_tolerance_factor=2.5,
        ),
        # Blood flows (L/min) - based on Davies 1993
        "Liver|BloodFlow": ParameterBounds(

            min_value=0.01,
            max_value=2.0,
            default_value=1.0,
            unit="L/min",
            category=ParameterCategory.PHYSIOLOGICAL,
            description="Hepatic blood flow",
            references=["Davies 1993"],
            scale_reference_weight=70.0,
            scale_reference_value=1.0,
            scale_exponent=0.75,
            scale_tolerance_factor=2.5,
        ),
        "Kidney|BloodFlow": ParameterBounds(

            min_value=0.01,
            max_value=1.5,
            default_value=1.0,
            unit="L/min",
            category=ParameterCategory.PHYSIOLOGICAL,
            description="Renal blood flow",
            references=["Davies 1993"],
            scale_reference_weight=70.0,
            scale_reference_value=1.0,
            scale_exponent=0.75,
            scale_tolerance_factor=2.5,
        ),
        "Brain|BloodFlow": ParameterBounds(

            min_value=0.01,
            max_value=1.0,
            default_value=0.7,
            unit="L/min",
            category=ParameterCategory.PHYSIOLOGICAL,
            description="Cerebral blood flow",
            references=["Davies 1993"],
            scale_reference_weight=70.0,
            scale_reference_value=0.7,
            scale_exponent=0.75,
            scale_tolerance_factor=2.5,
        ),
        # Clearance parameters
        "Liver|Clearance": ParameterBounds(
            min_value=0.0,
            max_value=100.0,
            default_value=1.0,
            unit="L/h",
            category=ParameterCategory.ENZYME_KINETICS,
            description="Hepatic clearance",
            references=["Rowland 1973"],
        ),
        "Kidney|Clearance": ParameterBounds(
            min_value=0.0,
            max_value=50.0,
            default_value=1.0,
            unit="L/h",
            category=ParameterCategory.ENZYME_KINETICS,
            description="Renal clearance",
            references=["Rowland 1973"],
        ),
        # Physicochemical properties
        "Lipophilicity": ParameterBounds(
            min_value=-5.0,
            max_value=10.0,
            default_value=1.0,
            unit="logP",
            category=ParameterCategory.PHYSICOCHEMICAL,
            description="Octanol-water partition coefficient",
            references=["Leo 1971"],
        ),
        "MolecularWeight": ParameterBounds(
            min_value=50.0,
            max_value=1000.0,
            default_value=300.0,
            unit="g/mol",
            category=ParameterCategory.PHYSICOCHEMICAL,
            description="Molecular weight",
        ),
        "FractionUnbound": ParameterBounds(
            min_value=0.0,
            max_value=1.0,
            default_value=0.1,
            unit="dimensionless",
            category=ParameterCategory.PHYSICOCHEMICAL,
            description="Fraction unbound in plasma",
        ),
        # Additional organ volumes (L) - ICRP 89 adult reference values
        "Heart": ParameterBounds(

            min_value=0.002,
            max_value=0.6,
            default_value=0.33,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Heart volume",
            references=["ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=0.33,
            scale_exponent=1.0,
            scale_tolerance_factor=2.5,
        ),
        "Lung": ParameterBounds(

            min_value=0.005,
            max_value=2.0,
            default_value=1.2,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Lung volume (both lungs)",
            references=["ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=1.2,
            scale_exponent=1.0,
            scale_tolerance_factor=2.5,
        ),
        "Skin": ParameterBounds(

            min_value=0.01,
            max_value=5.0,
            default_value=3.3,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Skin volume",
            references=["ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=3.3,
            scale_exponent=1.0,
            scale_tolerance_factor=2.5,
        ),
        "Bone": ParameterBounds(

            min_value=0.01,
            max_value=5.0,
            default_value=3.0,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Bone volume (skeleton excluding marrow)",
            references=["ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=3.0,
            scale_exponent=1.0,
            scale_tolerance_factor=2.5,
        ),
        "SmallIntestine": ParameterBounds(

            min_value=0.005,
            max_value=2.0,
            default_value=0.8,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Small intestine volume",
            references=["ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=0.8,
            scale_exponent=1.0,
            scale_tolerance_factor=2.5,
        ),
        "LargeIntestine": ParameterBounds(

            min_value=0.002,
            max_value=1.0,
            default_value=0.5,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Large intestine volume",
            references=["ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=0.5,
            scale_exponent=1.0,
            scale_tolerance_factor=2.5,
        ),
        "Pancreas": ParameterBounds(

            min_value=0.001,
            max_value=0.2,
            default_value=0.1,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Pancreas volume",
            references=["ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=0.1,
            scale_exponent=1.0,
            scale_tolerance_factor=2.5,
        ),
        "Spleen": ParameterBounds(

            min_value=0.001,
            max_value=0.4,
            default_value=0.2,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Spleen volume",
            references=["ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=0.2,
            scale_exponent=1.0,
            scale_tolerance_factor=2.5,
        ),
        # Additional blood flows (L/min) - Davies 1993 / ICRP 89
        "Heart|BloodFlow": ParameterBounds(

            min_value=0.001,
            max_value=0.5,
            default_value=0.25,
            unit="L/min",
            category=ParameterCategory.PHYSIOLOGICAL,
            description="Coronary blood flow",
            references=["Davies 1993", "ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=0.25,
            scale_exponent=0.75,
            scale_tolerance_factor=2.5,
        ),
        "Lung|BloodFlow": ParameterBounds(

            min_value=0.05,
            max_value=8.0,
            default_value=5.0,
            unit="L/min",
            category=ParameterCategory.PHYSIOLOGICAL,
            description="Pulmonary blood flow",
            references=["Davies 1993", "ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=5.0,
            scale_exponent=0.75,
            scale_tolerance_factor=2.5,
        ),
        "Skin|BloodFlow": ParameterBounds(

            min_value=0.001,
            max_value=0.8,
            default_value=0.3,
            unit="L/min",
            category=ParameterCategory.PHYSIOLOGICAL,
            description="Cutaneous blood flow",
            references=["Davies 1993", "ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=0.3,
            scale_exponent=0.75,
            scale_tolerance_factor=2.5,
        ),
        "Bone|BloodFlow": ParameterBounds(

            min_value=0.001,
            max_value=0.8,
            default_value=0.3,
            unit="L/min",
            category=ParameterCategory.PHYSIOLOGICAL,
            description="Skeletal blood flow",
            references=["Davies 1993", "ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=0.3,
            scale_exponent=0.75,
            scale_tolerance_factor=2.5,
        ),
        "SmallIntestine|BloodFlow": ParameterBounds(

            min_value=0.005,
            max_value=2.0,
            default_value=1.0,
            unit="L/min",
            category=ParameterCategory.PHYSIOLOGICAL,
            description="Small intestinal blood flow",
            references=["Davies 1993", "ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=1.0,
            scale_exponent=0.75,
            scale_tolerance_factor=2.5,
        ),
        "LargeIntestine|BloodFlow": ParameterBounds(

            min_value=0.002,
            max_value=0.8,
            default_value=0.3,
            unit="L/min",
            category=ParameterCategory.PHYSIOLOGICAL,
            description="Large intestinal blood flow",
            references=["Davies 1993", "ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=0.3,
            scale_exponent=0.75,
            scale_tolerance_factor=2.5,
        ),
        "Pancreas|BloodFlow": ParameterBounds(

            min_value=0.001,
            max_value=0.3,
            default_value=0.1,
            unit="L/min",
            category=ParameterCategory.PHYSIOLOGICAL,
            description="Pancreatic blood flow",
            references=["Davies 1993", "ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=0.1,
            scale_exponent=0.75,
            scale_tolerance_factor=2.5,
        ),
        "Spleen|BloodFlow": ParameterBounds(

            min_value=0.001,
            max_value=0.4,
            default_value=0.2,
            unit="L/min",
            category=ParameterCategory.PHYSIOLOGICAL,
            description="Splenic blood flow",
            references=["Davies 1993", "ICRP 89"],
            scale_reference_weight=70.0,
            scale_reference_value=0.2,
            scale_exponent=0.75,
            scale_tolerance_factor=2.5,
        ),
    }

    @classmethod
    def lookup(cls, parameter_path: str) -> Optional[ParameterBounds]:
        """Return bounds for a parameter path using suffix matching."""
        # Exact match first
        if parameter_path in cls._BOUNDS:
            return cls._BOUNDS[parameter_path]
        # Prefer longer/more specific keys to avoid e.g. "Liver" masking "Liver|BloodFlow"
        sorted_items = sorted(cls._BOUNDS.items(), key=lambda item: len(item[0]), reverse=True)
        # Suffix match (handles Organism|Liver|Volume -> Liver)
        for key, bounds in sorted_items:
            if parameter_path.endswith(key):
                return bounds
        # Substring fallback
        for key, bounds in sorted_items:
            if key in parameter_path:
                return bounds
        return None

    @classmethod
    def validate(
        cls,
        parameter_path: str,
        value: float,
        *,
        adapter: OspsuiteAdapter | None = None,
        simulation_id: str | None = None,
    ) -> tuple[bool, Optional[ParameterBounds], Optional[str]]:
        """Validate a parameter value against registered bounds.

        If ``adapter`` and ``simulation_id`` are provided, the validator will
        attempt to read ``Organism|Weight`` and compute allometrically scaled
        bounds for anatomical and physiological parameters.

        Returns:
            (is_valid, bounds_or_none, message_or_none)
        """
        bounds = cls.lookup(parameter_path)
        if bounds is None:
            return True, None, None

        body_weight: float | None = None
        if adapter is not None and simulation_id is not None and bounds.scale_reference_weight is not None:
            try:
                weight_param = adapter.get_parameter_value(simulation_id, "Organism|Weight")
                body_weight = float(weight_param.value)
            except Exception:
                body_weight = None

        is_valid, message = bounds.validate(value, body_weight=body_weight)
        return is_valid, bounds, message


__all__ = [
    "ParameterBounds",
    "ParameterBoundsRegistry",
    "ParameterCategory",
]
