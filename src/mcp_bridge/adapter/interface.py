"""Typed interface for ospsuite adapter implementation."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - used for type checking only
    from ..storage.population_store import PopulationResultStore

from .errors import AdapterError
from .schema import (
    ParameterSummary,
    ParameterValue,
    PopulationSimulationConfig,
    PopulationSimulationResult,
    SimulationHandle,
    SimulationResult,
)


@dataclass(frozen=True)
class AdapterConfig:
    ospsuite_libs: str | None = None
    default_timeout_seconds: float = 30.0
    r_path: str | None = None
    r_home: str | None = None
    r_libs: str | None = None
    require_r_environment: bool = False
    model_search_paths: tuple[str, ...] = ()


class OspsuiteAdapter(abc.ABC):
    """Abstract interface defining adapter responsibilities."""

    def __init__(
        self,
        config: AdapterConfig | None = None,
        *,
        population_store: PopulationResultStore | None = None,
    ) -> None:
        self.config = config or AdapterConfig()
        self.population_store = population_store

    # Session lifecycle -------------------------------------------------
    @abc.abstractmethod
    def init(self) -> None:
        """Initialize the R/ospsuite runtime."""

    @abc.abstractmethod
    def shutdown(self) -> None:
        """Tear down resources and stop the R runtime."""

    @abc.abstractmethod
    def health(self) -> dict[str, object]:
        """Return adapter health metadata such as versions."""

    # Simulation management ---------------------------------------------
    @abc.abstractmethod
    def load_simulation(self, file_path: str, simulation_id: str | None = None) -> SimulationHandle:
        """Load a PBPK simulation from disk and return handle metadata."""

    @abc.abstractmethod
    def list_parameters(
        self, simulation_id: str, pattern: str | None = None
    ) -> list[ParameterSummary]:
        """List parameters matching the pattern for the given simulation."""

    @abc.abstractmethod
    def get_parameter_value(self, simulation_id: str, parameter_path: str) -> ParameterValue:
        """Return the value of a specific parameter."""

    @abc.abstractmethod
    def set_parameter_value(
        self,
        simulation_id: str,
        parameter_path: str,
        value: float,
        unit: str | None = None,
        *,
        comment: str | None = None,
    ) -> ParameterValue:
        """Update a parameter in the active simulation."""

    # Simulation execution ----------------------------------------------
    @abc.abstractmethod
    def run_simulation_sync(
        self, simulation_id: str, *, run_id: str | None = None
    ) -> SimulationResult:
        """Execute the simulation synchronously and return results handle."""

    @abc.abstractmethod
    def get_results(self, results_id: str) -> SimulationResult:
        """Retrieve stored results by handle."""

    # Population simulation -------------------------------------------
    @abc.abstractmethod
    def run_population_simulation_sync(
        self, config: PopulationSimulationConfig
    ) -> PopulationSimulationResult:
        """Execute a population simulation synchronously and return aggregated results."""

    @abc.abstractmethod
    def get_population_results(self, results_id: str) -> PopulationSimulationResult:
        """Retrieve stored population results by handle."""

    # Error boundary ----------------------------------------------------
    def _raise(self, error: AdapterError) -> None:
        raise error
