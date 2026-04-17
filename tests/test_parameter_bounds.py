"""Tests for parameter bounds validation and sweep detection (PBPK-01 remediation)."""

from __future__ import annotations

import pytest

from mcp_bridge.audit.sweep_detection import detect_parameter_sweep
from mcp_bridge.parameter_bounds import ParameterBoundsRegistry


def test_valid_parameter_within_bounds() -> None:
    is_valid, bounds, message = ParameterBoundsRegistry.validate("Organism|Liver|Volume", 1.5)
    assert is_valid is True
    assert bounds is not None
    assert message is None


def test_invalid_parameter_outside_bounds() -> None:
    is_valid, bounds, message = ParameterBoundsRegistry.validate("Organism|Liver|Volume", 10.0)
    assert is_valid is False
    assert bounds is not None
    assert "outside plausible range" in (message or "")


def test_unknown_parameter_is_allowed() -> None:
    is_valid, bounds, message = ParameterBoundsRegistry.validate("Custom|Parameter|XYZ", 42.0)
    assert is_valid is True
    assert bounds is None
    assert message is None


def test_fraction_unbound_bounds() -> None:
    is_valid, bounds, message = ParameterBoundsRegistry.validate("FractionUnbound", 0.5)
    assert is_valid is True

    is_valid, bounds, message = ParameterBoundsRegistry.validate("FractionUnbound", 1.5)
    assert is_valid is False


def test_sweep_detection_empty() -> None:
    assert detect_parameter_sweep([]) == []


def test_sweep_detection_frequent_changes() -> None:
    changes = [
        {"parameterPath": "Liver|Volume", "newValue": 1.0, "oldValue": 1.5},
        {"parameterPath": "Liver|Volume", "newValue": 1.1, "oldValue": 1.0},
        {"parameterPath": "Liver|Volume", "newValue": 1.2, "oldValue": 1.1},
        {"parameterPath": "Liver|Volume", "newValue": 1.3, "oldValue": 1.2},
        {"parameterPath": "Liver|Volume", "newValue": 1.4, "oldValue": 1.3},
        {"parameterPath": "Liver|Volume", "newValue": 1.5, "oldValue": 1.4},
    ]
    alerts = detect_parameter_sweep(changes)
    assert any(a["type"] == "frequent_changes" for a in alerts)


def test_sweep_detection_oscillating_values() -> None:
    changes = [
        {"parameterPath": "Liver|Volume", "newValue": 1.0, "oldValue": 1.5},
        {"parameterPath": "Liver|Volume", "newValue": 1.5, "oldValue": 1.0},
        {"parameterPath": "Liver|Volume", "newValue": 1.2, "oldValue": 1.5},
        {"parameterPath": "Liver|Volume", "newValue": 1.4, "oldValue": 1.2},
    ]
    alerts = detect_parameter_sweep(changes)
    assert any(a["type"] == "oscillating_values" for a in alerts)


def test_sweep_detection_large_changes() -> None:
    changes = [
        {"parameterPath": "Liver|Volume", "newValue": 1.0, "oldValue": 1.5},
        {"parameterPath": "Liver|Volume", "newValue": 3.0, "oldValue": 1.0},
        {"parameterPath": "Liver|Volume", "newValue": 6.0, "oldValue": 3.0},
        {"parameterPath": "Liver|Volume", "newValue": 12.0, "oldValue": 6.0},
    ]
    alerts = detect_parameter_sweep(changes)
    assert any(a["type"] == "large_changes" for a in alerts)


def test_dynamic_bounds_scale_with_body_weight() -> None:
    bounds = ParameterBoundsRegistry.lookup("Organism|Liver|Volume")
    assert bounds is not None
    # Adult 70 kg -> should match reference scaling
    min_70, max_70 = bounds.get_effective_bounds(body_weight=70.0)
    assert min_70 == pytest.approx(0.6, abs=0.01)
    assert max_70 == pytest.approx(3.0, abs=0.01)  # capped by static max

    # Infant 6.75 kg -> scaled down
    min_inf, max_inf = bounds.get_effective_bounds(body_weight=6.75)
    assert min_inf == pytest.approx(0.0578, abs=0.001)
    assert max_inf == pytest.approx(0.3619, abs=0.001)


def test_dynamic_bounds_fallback_without_body_weight() -> None:
    bounds = ParameterBoundsRegistry.lookup("Organism|Liver|Volume")
    assert bounds is not None
    min_eff, max_eff = bounds.get_effective_bounds(body_weight=None)
    assert min_eff == bounds.min_value
    assert max_eff == bounds.max_value


def test_dynamic_bounds_for_blood_flow_uses_exponent() -> None:
    bounds = ParameterBoundsRegistry.lookup("Organism|Liver|BloodFlow")
    assert bounds is not None
    assert bounds.scale_exponent == 0.75

    # Adult
    min_70, max_70 = bounds.get_effective_bounds(body_weight=70.0)
    assert min_70 == pytest.approx(0.4, abs=0.01)
    assert max_70 == pytest.approx(2.0, abs=0.01)  # capped by static max

    # Infant 6.75 kg
    min_inf, max_inf = bounds.get_effective_bounds(body_weight=6.75)
    assert min_inf == pytest.approx(0.0692, abs=0.001)
    assert max_inf == pytest.approx(0.433, abs=0.001)
