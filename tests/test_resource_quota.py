"""Tests for resource quota validation (PBPK-02 remediation)."""

from __future__ import annotations

import pytest

from mcp_bridge.config import AppConfig
from mcp_bridge.services.resource_quota import QuotaExceededError, ResourceQuotaValidator


def test_population_size_within_limit() -> None:
    config = AppConfig(max_population_size=100, max_memory_per_job_mb=2048)
    validator = ResourceQuotaValidator(config)
    result = validator.check_population_size(50)
    assert result.allowed is True


def test_population_size_exceeds_limit() -> None:
    config = AppConfig(max_population_size=100, max_memory_per_job_mb=2048)
    validator = ResourceQuotaValidator(config)
    result = validator.check_population_size(101)
    assert result.allowed is False
    assert "exceeds maximum 100" in result.message


def test_memory_quota_within_limit() -> None:
    config = AppConfig(max_population_size=5000, max_memory_per_job_mb=2048)
    validator = ResourceQuotaValidator(config)
    result = validator.check_memory_quota(100)
    assert result.allowed is True


def test_memory_quota_exceeds_limit() -> None:
    config = AppConfig(max_population_size=5000, max_memory_per_job_mb=100)
    validator = ResourceQuotaValidator(config)
    # A large population should exceed the 100 MB quota
    result = validator.check_memory_quota(5000)
    assert result.allowed is False
    assert "exceeds quota" in result.message


def test_validate_job_request_all_pass() -> None:
    config = AppConfig(max_population_size=5000, max_memory_per_job_mb=2048)
    validator = ResourceQuotaValidator(config)
    is_valid, errors = validator.validate_job_request(100)
    assert is_valid is True
    assert errors == []


def test_validate_job_request_multiple_failures() -> None:
    config = AppConfig(max_population_size=10, max_memory_per_job_mb=50)
    validator = ResourceQuotaValidator(config)
    is_valid, errors = validator.validate_job_request(5000)
    assert is_valid is False
    assert len(errors) == 2
    assert any("exceeds maximum" in e for e in errors)
    assert any("exceeds quota" in e for e in errors)


def test_memory_estimation_monotonic() -> None:
    config = AppConfig()
    validator = ResourceQuotaValidator(config)
    small = validator.estimate_memory_requirement(10)
    large = validator.estimate_memory_requirement(1000)
    assert large > small


def test_memory_estimation_is_conservative_against_measured_data() -> None:
    """Estimator must sit above live rxode2 load-test peaks (PBPK-05)."""
    config = AppConfig()
    validator = ResourceQuotaValidator(config)

    # Peaks observed during live load test on reference compound rxode2 model
    # (2026-04-16, cohort sizes 100–2_000)
    measured = {
        100: 122.2,
        500: 196.5,
        1000: 442.7,
        1500: 501.2,
        2000: 615.7,
    }

    for size, peak_mb in measured.items():
        estimated = validator.estimate_memory_requirement(size)
        assert estimated >= peak_mb, (
            f"Estimated memory {estimated} MB for size {size} is below "
            f"measured peak {peak_mb} MB"
        )


def test_memory_estimation_slope_matches_regression() -> None:
    """The per-patient slope should reflect the calibrated 0.25 MB × 1.5 safety factor."""
    config = AppConfig()
    validator = ResourceQuotaValidator(config)

    # The estimator formula is (100 + size * 0.25) * 1.5, so the marginal slope
    # per patient is 0.25 * 1.5 = 0.375 MB/patient.
    delta_size = 2000 - 100
    delta_estimate = validator.estimate_memory_requirement(2000) - validator.estimate_memory_requirement(100)
    slope = delta_estimate / delta_size

    assert 0.35 <= slope <= 0.40, f"Estimated slope {slope} MB/patient is outside expected range"
