"""Resource quota estimation and enforcement for simulation jobs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from ..config import AppConfig


@dataclass(frozen=True)
class QuotaCheckResult:
    """Result of a resource quota validation."""

    allowed: bool
    message: str


class ResourceQuotaValidator:
    """Validate population simulation requests against configured resource quotas."""

    def __init__(self, config: AppConfig) -> None:
        self._max_population_size = config.max_population_size
        self._max_memory_per_job_mb = config.max_memory_per_job_mb

    def check_population_size(self, population_size: int) -> QuotaCheckResult:
        """Validate population size against the configured hard limit."""
        if population_size > self._max_population_size:
            return QuotaCheckResult(
                allowed=False,
                message=(
                    f"Population size {population_size} exceeds maximum "
                    f"{self._max_population_size}. Contact an administrator for large simulations."
                ),
            )
        return QuotaCheckResult(allowed=True, message="Valid")

    def estimate_memory_requirement(self, population_size: int) -> int:
        """Return a conservative memory estimate for a population simulation in MB.

        Calibrated from live rxode2 load testing (2026-04-16) on the reference
        compound population model at 100–2_000 subjects. Measured slope was
        ~0.25 MB/patient (R² = 0.95). The 1.5× safety factor keeps the estimate
        comfortably above observed peaks.
        """
        base_memory = 100  # MB for model overhead
        memory_per_patient = 0.25  # MB per subject (measured, see PBPK-05)
        safety_factor = 1.5
        estimated = (base_memory + population_size * memory_per_patient) * safety_factor
        return int(estimated)

    def check_memory_quota(self, population_size: int) -> QuotaCheckResult:
        """Validate estimated memory requirement against the configured quota."""
        estimated_mb = self.estimate_memory_requirement(population_size)
        if estimated_mb > self._max_memory_per_job_mb:
            return QuotaCheckResult(
                allowed=False,
                message=(
                    f"Estimated memory requirement ({estimated_mb} MB) exceeds "
                    f"quota ({self._max_memory_per_job_mb} MB) for population size "
                    f"{population_size}."
                ),
            )
        return QuotaCheckResult(allowed=True, message="Valid")

    def validate_job_request(self, population_size: int) -> Tuple[bool, list[str]]:
        """Run all quota checks for a population job request.

        Returns:
            (is_valid, list of error messages)
        """
        errors: list[str] = []

        size_result = self.check_population_size(population_size)
        if not size_result.allowed:
            errors.append(size_result.message)

        memory_result = self.check_memory_quota(population_size)
        if not memory_result.allowed:
            errors.append(memory_result.message)

        return (len(errors) == 0, errors)


class QuotaExceededError(RuntimeError):
    """Raised when a job request exceeds resource quotas."""


__all__ = [
    "QuotaCheckResult",
    "QuotaExceededError",
    "ResourceQuotaValidator",
]
