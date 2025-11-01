"""Concrete Ospsuite adapter that shells out to an external runtime.

The real implementation is expected to invoke an R script (or equivalent bridge)
via subprocess.  For unit tests we allow injection of a fake command runner so we
can exercise validation, error mapping, and serialization logic without requiring
the R toolchain.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..storage.population_store import PopulationResultStore

from .environment import REnvironmentStatus, detect_environment
from .errors import AdapterError, AdapterErrorCode
from .interface import AdapterConfig, OspsuiteAdapter
from .schema import (
    ParameterSummary,
    ParameterValue,
    PopulationSimulationConfig,
    PopulationSimulationResult,
    SimulationHandle,
    SimulationResult,
)


@dataclass
class CommandResult:
    """Response payload returned by a command runner."""

    returncode: int
    stdout: str
    stderr: str = ""


class CommandRunner(Protocol):
    """Callable used to execute bridge commands."""

    def __call__(self, action: str, payload: Mapping[str, Any]) -> CommandResult: ...


class SubprocessCommandRunner:
    """Default runner that shells out to a bridge script."""

    def __init__(self, command: Sequence[str]):
        self._command = tuple(command)

    def __call__(self, action: str, payload: Mapping[str, Any]) -> CommandResult:
        request = json.dumps({"action": action, "payload": payload})
        try:
            proc = subprocess.run(  # noqa: S603,S607 - intentional subprocess usage
                self._command,
                input=request.encode("utf-8"),
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            raise AdapterError(
                AdapterErrorCode.INTEROP_ERROR,
                f"Failed to execute adapter bridge: {exc}",
            ) from exc

        return CommandResult(
            returncode=proc.returncode,
            stdout=proc.stdout.decode("utf-8"),
            stderr=proc.stderr.decode("utf-8"),
        )


class SubprocessOspsuiteAdapter(OspsuiteAdapter):
    """Adapter implementation that interacts with an external bridge process."""

    def __init__(
        self,
        config: AdapterConfig | None = None,
        *,
        command_runner: CommandRunner | None = None,
        bridge_command: Sequence[str] | None = None,
        env_detector: Callable[[AdapterConfig], REnvironmentStatus] = detect_environment,
        population_store: PopulationResultStore | None = None,
    ) -> None:
        super().__init__(config, population_store=population_store)
        self._env_detector = env_detector
        self._command_runner = command_runner or SubprocessCommandRunner(
            bridge_command or ("Rscript", "scripts/ospsuite_bridge.R")
        )
        self._status: REnvironmentStatus | None = None
        self._initialised = False
        self._handles: dict[str, SimulationHandle] = {}
        self._parameters: dict[str, dict[str, ParameterValue]] = {}
        self._results: dict[str, SimulationResult] = {}
        self._allowed_roots = self._compile_allowed_roots(self.config.model_search_paths)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def init(self) -> None:
        status = self._env_detector(self.config)
        if self.config.require_r_environment and not status.available:
            raise AdapterError(
                AdapterErrorCode.ENVIRONMENT_MISSING,
                "R environment unavailable",
                details={"issues": "; ".join(status.issues)},
            )
        self._status = status
        self._initialised = True

    def shutdown(self) -> None:
        self._initialised = False
        self._handles.clear()
        self._parameters.clear()
        self._results.clear()

    def health(self) -> dict[str, object]:
        status = "initialised" if self._initialised else "stopped"
        env = self._status.to_dict() if self._status else {}
        return {"status": status, "environment": env}

    # ------------------------------------------------------------------ #
    # Adapter operations
    # ------------------------------------------------------------------ #
    def load_simulation(self, file_path: str, simulation_id: str | None = None) -> SimulationHandle:
        self._ensure_initialised()
        resolved_path = self._resolve_model_path(file_path)
        identifier = simulation_id or Path(resolved_path).stem
        payload = {"filePath": resolved_path, "simulationId": identifier}
        response = self._call_backend("load_simulation", payload)
        handle_payload = dict(response["handle"])
        metadata = response.get("metadata")
        if isinstance(metadata, Mapping):
            handle_payload["metadata"] = metadata
        handle = SimulationHandle.model_validate(handle_payload)
        parameters = {
            item["path"]: ParameterValue.model_validate(item)
            for item in response.get("parameters", [])
            if isinstance(item, Mapping)
        }
        self._handles[handle.simulation_id] = handle
        if parameters:
            self._parameters[handle.simulation_id] = parameters
        return handle

    def list_parameters(
        self, simulation_id: str, pattern: str | None = None
    ) -> list[ParameterSummary]:
        handle = self._get_handle(simulation_id)
        cached = self._parameters.get(handle.simulation_id)
        if cached and pattern in (None, "*"):
            summaries = [
                ParameterSummary(
                    path=value.path,
                    display_name=value.display_name,
                    unit=value.unit,
                    is_editable=True,
                )
                for value in cached.values()
            ]
            return sorted(summaries, key=lambda item: item.path)

        payload = {"simulationId": handle.simulation_id, "pattern": pattern}
        response = self._call_backend("list_parameters", payload)
        summaries = [
            ParameterSummary.model_validate(item) for item in response.get("parameters", [])
        ]
        return sorted(summaries, key=lambda item: item.path)

    def get_parameter_value(self, simulation_id: str, parameter_path: str) -> ParameterValue:
        handle = self._get_handle(simulation_id)
        cached = self._parameters.get(handle.simulation_id, {})
        if parameter_path in cached:
            return cached[parameter_path]

        payload = {"simulationId": handle.simulation_id, "parameterPath": parameter_path}
        response = self._call_backend("get_parameter_value", payload)
        value = ParameterValue.model_validate(response["parameter"])
        cached[parameter_path] = value
        self._parameters[handle.simulation_id] = cached
        return value

    def set_parameter_value(
        self,
        simulation_id: str,
        parameter_path: str,
        value: float,
        unit: str | None = None,
        *,
        comment: str | None = None,
    ) -> ParameterValue:
        handle = self._get_handle(simulation_id)
        current = self._parameters.get(handle.simulation_id, {})
        payload = {
            "simulationId": handle.simulation_id,
            "parameterPath": parameter_path,
            "value": value,
            "unit": unit,
            "comment": comment,
        }
        response = self._call_backend("set_parameter_value", payload)
        updated = ParameterValue.model_validate(response["parameter"])
        current[parameter_path] = updated
        self._parameters[handle.simulation_id] = current
        return updated

    def run_simulation_sync(
        self, simulation_id: str, *, run_id: str | None = None
    ) -> SimulationResult:
        handle = self._get_handle(simulation_id)
        payload = {"simulationId": handle.simulation_id, "runId": run_id}
        response = self._call_backend("run_simulation_sync", payload)
        result = SimulationResult.model_validate(response["result"])
        self._results[result.results_id] = result
        return result

    def get_results(self, results_id: str) -> SimulationResult:
        if results_id in self._results:
            return self._results[results_id]

        response = self._call_backend("get_results", {"resultsId": results_id})
        result = SimulationResult.model_validate(response["result"])
        self._results[result.results_id] = result
        return result

    def run_population_simulation_sync(
        self, config: PopulationSimulationConfig
    ) -> PopulationSimulationResult:
        raise AdapterError(
            AdapterErrorCode.INTEROP_ERROR,
            "Population simulations are not implemented for the subprocess adapter",
        )

    def get_population_results(self, results_id: str) -> PopulationSimulationResult:
        raise AdapterError(
            AdapterErrorCode.NOT_FOUND,
            "Population results are not available for the subprocess adapter",
        )

    def export_simulation_state(self, simulation_id: str) -> dict[str, object]:
        handle = self._get_handle(simulation_id)
        parameters = [
            {
                "path": value.path,
                "value": value.value,
                "unit": value.unit,
            }
            for value in self._parameters.get(handle.simulation_id, {}).values()
        ]
        return {
            "simulationId": handle.simulation_id,
            "filePath": handle.file_path,
            "parameters": parameters,
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _ensure_initialised(self) -> None:
        if not self._initialised:
            raise AdapterError(
                AdapterErrorCode.ENVIRONMENT_MISSING, "Adapter not initialised. Call init() first."
            )

    def _get_handle(self, simulation_id: str) -> SimulationHandle:
        self._ensure_initialised()
        try:
            return self._handles[simulation_id]
        except KeyError as exc:
            raise AdapterError(
                AdapterErrorCode.NOT_FOUND, f"Simulation '{simulation_id}' not loaded"
            ) from exc

    def _call_backend(self, action: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        result = self._command_runner(action, payload)
        data: dict[str, Any] = {}

        if result.stdout.strip():
            try:
                decoded = json.loads(result.stdout)
                if isinstance(decoded, dict):
                    data = decoded
                else:
                    raise ValueError("Backend response must be a JSON object")
            except ValueError as exc:
                raise AdapterError(
                    AdapterErrorCode.INTEROP_ERROR,
                    f"Failed to decode backend response for '{action}': {exc}",
                ) from exc

        if result.returncode != 0:
            error_payload = data.get("error") if data else None
            if not error_payload:
                error_payload = {
                    "code": AdapterErrorCode.INTEROP_ERROR.value,
                    "message": result.stderr.strip() or "Bridge command failed",
                }
            raise self._build_error(error_payload)

        if "error" in data:
            raise self._build_error(data["error"])

        return data

    @staticmethod
    def _build_error(raw: Mapping[str, Any]) -> AdapterError:
        code_raw = str(raw.get("code", AdapterErrorCode.INTEROP_ERROR.value))
        try:
            code = AdapterErrorCode(code_raw)
        except ValueError:
            code = AdapterErrorCode.INTEROP_ERROR
        message = str(raw.get("message", "Adapter error"))
        details_field = raw.get("details")
        details: dict[str, str] = {}
        if isinstance(details_field, Mapping):
            details = {str(key): str(value) for key, value in details_field.items()}
        return AdapterError(code, message, details=details)

    def _resolve_model_path(self, file_path: str) -> str:
        candidate = Path(file_path).expanduser()
        if not candidate.is_absolute():
            candidate = (Path.cwd() / candidate).resolve()
        else:
            candidate = candidate.resolve()

        if candidate.suffix.lower() != ".pkml":
            raise AdapterError(
                AdapterErrorCode.INVALID_INPUT, "Simulation files must use the .pkml extension"
            )
        if not candidate.is_file():
            raise AdapterError(
                AdapterErrorCode.INVALID_INPUT,
                f"Simulation file '{candidate.name}' was not found",
            )
        if not self._is_within_allowed_roots(candidate):
            raise AdapterError(
                AdapterErrorCode.INVALID_INPUT,
                f"Simulation path '{candidate.name}' is outside the allowed model search paths",
            )
        return str(candidate)

    def _compile_allowed_roots(self, configured: Iterable[str]) -> tuple[Path, ...]:
        roots = [Path(entry).expanduser().resolve() for entry in configured if entry]
        if not roots:
            env_paths = os.getenv("MCP_MODEL_SEARCH_PATHS", "")
            for chunk in env_paths.split(os.pathsep):
                chunk = chunk.strip()
                if chunk:
                    roots.append(Path(chunk).expanduser().resolve())

        if not roots:
            roots.append(Path.cwd())
        return tuple(roots)

    def _is_within_allowed_roots(self, candidate: Path) -> bool:
        for root in self._allowed_roots:
            try:
                candidate.relative_to(root)
            except ValueError:
                continue
            return True
        return False


__all__ = ["CommandResult", "CommandRunner", "SubprocessCommandRunner", "SubprocessOspsuiteAdapter"]
