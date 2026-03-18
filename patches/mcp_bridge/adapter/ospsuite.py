from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import ValidationError

if TYPE_CHECKING:
    from ..storage.population_store import PopulationResultStore

from .environment import REnvironmentStatus, detect_environment
from .errors import AdapterError, AdapterErrorCode
from .interface import AdapterConfig, OspsuiteAdapter
from .schema import (
    ParameterSummary,
    ParameterValue,
    PopulationChunkHandle,
    PopulationSimulationConfig,
    PopulationSimulationResult,
    SimulationHandle,
    SimulationResult,
)
from ..logging import get_logger

logger = get_logger(__name__)


class CommandResult:
    """Response payload returned by a bridge command."""

    def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class CommandRunner(Protocol):
    """Callable used to execute bridge commands."""

    def __call__(self, action: str, payload: Mapping[str, Any]) -> CommandResult: ...


class PersistentSubprocessCommandRunner:
    """Runner that maintains a persistent R subprocess."""

    def __init__(self, command: Sequence[str]):
        self._command = tuple(command)
        self._process: subprocess.Popen[str] | None = None
        self._lock = RLock()

    def start(self) -> None:
        with self._lock:
            if self._process is not None:
                return
            try:
                logger.info("adapter.subprocess.start", command=self._command)
                self._process = subprocess.Popen(
                    self._command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
            except OSError as exc:
                raise AdapterError(
                    AdapterErrorCode.INTEROP_ERROR,
                    f"Failed to start adapter bridge: {exc}",
                ) from exc

    def stop(self) -> None:
        with self._lock:
            if self._process is None:
                return
            logger.info("adapter.subprocess.stop")
            if self._process.stdin:
                self._process.stdin.close()
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None

    def __call__(self, action: str, payload: Mapping[str, Any]) -> CommandResult:
        with self._lock:
            if self._process is None:
                self.start()

            process = self._process
            assert process is not None

            if process.poll() is not None:
                returncode = process.poll() or 1
                stderr_content = process.stderr.read() if process.stderr else ""
                logger.warning(
                    "adapter.subprocess.died",
                    returncode=returncode,
                    stderr=stderr_content,
                )
                self._process = None
                self.start()
                process = self._process
                assert process is not None

            request = json.dumps({"action": action, "payload": payload})
            try:
                assert process.stdin is not None
                assert process.stdout is not None

                logger.debug("adapter.subprocess.send", action=action)
                process.stdin.write(request + "\n")
                process.stdin.flush()

                while True:
                    response_line = process.stdout.readline()
                    if not response_line:
                        stderr_content = process.stderr.read() if process.stderr else ""
                        returncode = process.poll() or 1
                        logger.error(
                            "adapter.subprocess.eof",
                            returncode=returncode,
                            stderr=stderr_content,
                        )
                        self._process = None
                        return CommandResult(
                            returncode=returncode,
                            stdout="",
                            stderr=stderr_content or "Process exited unexpectedly",
                        )

                    line_stripped = response_line.strip()
                    if not line_stripped:
                        continue

                    try:
                        json.loads(line_stripped)
                    except json.JSONDecodeError:
                        logger.debug("adapter.subprocess.noise", content=line_stripped)
                        continue

                    return CommandResult(returncode=0, stdout=response_line, stderr="")
            except (BrokenPipeError, OSError) as exc:
                logger.error("adapter.subprocess.io_error", error=str(exc))
                self._process = None
                raise AdapterError(
                    AdapterErrorCode.INTEROP_ERROR,
                    f"Communication with bridge failed: {exc}",
                ) from exc


class SubprocessOspsuiteAdapter(OspsuiteAdapter):
    """Hybrid subprocess adapter for OSPSuite .pkml and rxode2 .R models."""

    SUPPORTED_EXTENSIONS = {".pkml", ".r"}

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
        self._command_runner = command_runner or PersistentSubprocessCommandRunner(
            bridge_command or ("Rscript", "scripts/ospsuite_bridge.R")
        )
        self._status: REnvironmentStatus | None = None
        self._initialised = False
        self._handles: dict[str, SimulationHandle] = {}
        self._parameters: dict[str, dict[str, ParameterValue]] = {}
        self._results: dict[str, SimulationResult] = {}
        self._population_results: dict[str, PopulationSimulationResult] = {}
        self._allowed_roots = self._compile_allowed_roots(self.config.model_search_paths)

    def init(self) -> None:
        status = self._env_detector(self.config)
        if self.config.require_r_environment and not status.available:
            raise AdapterError(
                AdapterErrorCode.ENVIRONMENT_MISSING,
                "R environment unavailable",
                details={"issues": "; ".join(status.issues)},
            )
        self._status = status
        if hasattr(self._command_runner, "start"):
            self._command_runner.start()  # type: ignore[call-arg]
        self._initialised = True

    def shutdown(self) -> None:
        self._initialised = False
        if hasattr(self._command_runner, "stop"):
            self._command_runner.stop()  # type: ignore[call-arg]
        self._handles.clear()
        self._parameters.clear()
        self._results.clear()
        self._population_results.clear()

    def health(self) -> dict[str, object]:
        status = "initialised" if self._initialised else "stopped"
        env = self._status.to_dict() if self._status else {}
        return {"status": status, "environment": env}

    def load_simulation(self, file_path: str, simulation_id: str | None = None) -> SimulationHandle:
        self._ensure_initialised()
        resolved_path = self._resolve_model_path(file_path)
        identifier = simulation_id or Path(resolved_path).stem
        response = self._call_backend(
            "load_simulation",
            {"filePath": resolved_path, "simulationId": identifier},
        )
        handle_payload = dict(response["handle"])
        metadata = response.get("metadata")
        if isinstance(metadata, Mapping):
            handle_payload["metadata"] = dict(metadata)
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

    def list_parameters(self, simulation_id: str, pattern: str | None = None) -> list[ParameterSummary]:
        handle = self._get_handle(simulation_id)
        cached = self._parameters.get(handle.simulation_id)
        if cached and pattern in (None, "*"):
            return sorted(
                [
                    ParameterSummary(
                        path=value.path,
                        display_name=value.display_name,
                        unit=value.unit,
                        is_editable=True,
                    )
                    for value in cached.values()
                ],
                key=lambda item: item.path,
            )

        response = self._call_backend(
            "list_parameters",
            {"simulationId": handle.simulation_id, "pattern": pattern},
        )
        return sorted(
            [
                ParameterSummary.model_validate(item)
                for item in response.get("parameters", [])
                if isinstance(item, Mapping)
            ],
            key=lambda item: item.path,
        )

    def get_parameter_value(self, simulation_id: str, parameter_path: str) -> ParameterValue:
        handle = self._get_handle(simulation_id)
        cached = self._parameters.get(handle.simulation_id, {})
        if parameter_path in cached:
            return cached[parameter_path]

        response = self._call_backend(
            "get_parameter_value",
            {"simulationId": handle.simulation_id, "parameterPath": parameter_path},
        )
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
        response = self._call_backend(
            "set_parameter_value",
            {
                "simulationId": handle.simulation_id,
                "parameterPath": parameter_path,
                "value": value,
                "unit": unit,
                "comment": comment,
            },
        )
        updated = ParameterValue.model_validate(response["parameter"])
        self._parameters.setdefault(handle.simulation_id, {})[parameter_path] = updated
        return updated

    def run_simulation_sync(self, simulation_id: str, *, run_id: str | None = None) -> SimulationResult:
        handle = self._get_handle(simulation_id)
        response = self._call_backend(
            "run_simulation_sync",
            {"simulationId": handle.simulation_id, "runId": run_id},
        )
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

    def validate_simulation_request(
        self,
        simulation_id: str,
        *,
        request: Mapping[str, Any] | None = None,
        stage: str | None = None,
    ) -> dict[str, Any]:
        handle = self._get_handle(simulation_id)
        response = self._call_backend(
            "validate_simulation_request",
            {
                "simulationId": handle.simulation_id,
                "request": dict(request or {}),
                "stage": stage,
            },
        )

        if isinstance(handle.metadata, Mapping):
            updated_metadata = dict(handle.metadata)
        else:
            updated_metadata = {}

        for key in ("validation", "profile", "capabilities"):
            payload = response.get(key)
            if isinstance(payload, Mapping):
                updated_metadata[key] = dict(payload)

        if isinstance(response.get("backend"), str):
            updated_metadata["backend"] = response["backend"]

        handle.metadata = updated_metadata
        self._handles[handle.simulation_id] = handle
        return dict(response)

    def run_population_simulation_sync(
        self,
        config: PopulationSimulationConfig,
    ) -> PopulationSimulationResult:
        self._ensure_initialised()
        if config.simulation_id not in self._handles:
            self.load_simulation(config.model_path, simulation_id=config.simulation_id)

        response = self._call_backend(
            "run_population_simulation_sync",
            {
                "modelPath": config.model_path,
                "simulationId": config.simulation_id,
                "cohort": config.cohort.model_dump(mode="json"),
                "outputs": config.outputs.model_dump(mode="json"),
                "metadata": config.metadata,
            },
        )
        result_payload = dict(response["result"])
        raw_chunks = result_payload.pop("chunk_handles", []) or result_payload.pop("chunks", [])
        result_payload["chunk_handles"] = self._persist_population_chunks(
            result_payload["results_id"],
            raw_chunks,
        )

        result = PopulationSimulationResult.model_validate(result_payload)
        self._population_results[result.results_id] = result
        self._persist_population_result(result)
        return result

    def get_population_results(self, results_id: str) -> PopulationSimulationResult:
        cached = self._population_results.get(results_id)
        if cached is not None:
            return cached

        persisted = self._load_population_result(results_id)
        if persisted is not None:
            self._population_results[results_id] = persisted
            return persisted

        response = self._call_backend("get_population_results", {"resultsId": results_id})
        result = PopulationSimulationResult.model_validate(response["result"])
        self._population_results[result.results_id] = result
        self._persist_population_result(result)
        return result

    def export_simulation_state(self, simulation_id: str) -> dict[str, Any]:
        handle = self._get_handle(simulation_id)
        parameters = [
            {"path": item.path, "value": item.value, "unit": item.unit}
            for item in self._parameters.get(handle.simulation_id, {}).values()
        ]
        return {
            "simulationId": handle.simulation_id,
            "filePath": handle.file_path,
            "parameters": parameters,
        }

    def _ensure_initialised(self) -> None:
        if not self._initialised:
            raise AdapterError(
                AdapterErrorCode.ENVIRONMENT_MISSING,
                "Adapter not initialised. Call init() first.",
            )

    def _get_handle(self, simulation_id: str) -> SimulationHandle:
        self._ensure_initialised()
        try:
            return self._handles[simulation_id]
        except KeyError as exc:
            raise AdapterError(
                AdapterErrorCode.NOT_FOUND,
                f"Simulation '{simulation_id}' not loaded",
            ) from exc

    def _call_backend(self, action: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        result = self._command_runner(action, payload)
        data: dict[str, Any] = {}

        if result.stdout.strip():
            try:
                decoded = json.loads(result.stdout)
            except ValueError as exc:
                logger.error("adapter.json_decode_failed", stdout=result.stdout)
                raise AdapterError(
                    AdapterErrorCode.INTEROP_ERROR,
                    f"Failed to decode backend response for '{action}': {exc}",
                ) from exc
            if not isinstance(decoded, dict):
                raise AdapterError(
                    AdapterErrorCode.INTEROP_ERROR,
                    f"Backend response for '{action}' must be a JSON object",
                )
            data = decoded

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
        try:
            code = AdapterErrorCode(str(raw.get("code", AdapterErrorCode.INTEROP_ERROR.value)))
        except ValueError:
            code = AdapterErrorCode.INTEROP_ERROR
        details_field = raw.get("details")
        details: dict[str, str] = {}
        if isinstance(details_field, Mapping):
            details = {str(key): str(value) for key, value in details_field.items()}
        return AdapterError(code, str(raw.get("message", "Adapter error")), details=details)

    def _resolve_model_path(self, file_path: str) -> str:
        candidate = Path(file_path).expanduser()
        candidate = (Path.cwd() / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        extension = candidate.suffix.lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(self.SUPPORTED_EXTENSIONS))
            raise AdapterError(
                AdapterErrorCode.INVALID_INPUT,
                f"Simulation files must use one of: {supported}",
            )
        if not candidate.is_file():
            raise AdapterError(
                AdapterErrorCode.INVALID_INPUT,
                f"Simulation file '{candidate.name}' was not found",
            )
        return str(candidate)

    def _compile_allowed_roots(self, configured: Iterable[str]) -> tuple[Path, ...]:
        roots = [Path(entry).expanduser().resolve() for entry in configured if entry]
        if not roots:
            env_paths = os.getenv("MCP_MODEL_SEARCH_PATHS", "")
            for chunk in env_paths.split(os.pathsep):
                if chunk.strip():
                    roots.append(Path(chunk).expanduser().resolve())
        if not roots:
            roots.append(Path.cwd())
        return tuple(roots)

    def _population_metadata_path(self, results_id: str) -> Path | None:
        if self.population_store is None:
            return None
        return self.population_store.base_path / results_id / "metadata.json"

    def _persist_population_result(self, result: PopulationSimulationResult) -> None:
        metadata_path = self._population_metadata_path(result.results_id)
        if metadata_path is None:
            return
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(
            json.dumps(result.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )

    def _load_population_result(self, results_id: str) -> PopulationSimulationResult | None:
        metadata_path = self._population_metadata_path(results_id)
        if metadata_path is None or not metadata_path.is_file():
            return None
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            return PopulationSimulationResult.model_validate(payload)
        except (OSError, ValidationError, json.JSONDecodeError):
            logger.warning("adapter.population_metadata_invalid", resultsId=results_id)
            return None

    def _persist_population_chunks(
        self,
        results_id: str,
        raw_chunks: Sequence[Any],
    ) -> list[PopulationChunkHandle]:
        handles: list[PopulationChunkHandle] = []
        for index, chunk in enumerate(raw_chunks, start=1):
            if not isinstance(chunk, Mapping):
                continue
            chunk_id = str(chunk.get("chunkId") or chunk.get("chunk_id") or f"chunk-{index:03d}")
            subject_range = self._coerce_tuple(chunk.get("subjectRange") or chunk.get("subject_range"))
            time_range = self._coerce_float_tuple(chunk.get("timeRange") or chunk.get("time_range"))
            preview = chunk.get("preview")
            payload = chunk.get("payload")

            uri = None
            content_type = None
            size_bytes = None
            if self.population_store is not None and payload is not None:
                stored = self.population_store.store_json_chunk(results_id, chunk_id, payload)
                uri = stored.uri
                content_type = stored.content_type
                size_bytes = stored.size_bytes

            handles.append(
                PopulationChunkHandle(
                    chunk_id=chunk_id,
                    uri=uri,
                    content_type=content_type,
                    size_bytes=size_bytes,
                    subject_range=subject_range,
                    time_range=time_range,
                    preview=preview if isinstance(preview, dict) else None,
                )
            )
        return handles

    @staticmethod
    def _coerce_tuple(value: Any) -> tuple[int, int] | None:
        if value is None:
            return None
        items = list(value)
        if len(items) != 2:
            return None
        return int(items[0]), int(items[1])

    @staticmethod
    def _coerce_float_tuple(value: Any) -> tuple[float, float] | None:
        if value is None:
            return None
        items = list(value)
        if len(items) != 2:
            return None
        return float(items[0]), float(items[1])


__all__ = [
    "CommandResult",
    "CommandRunner",
    "PersistentSubprocessCommandRunner",
    "SubprocessOspsuiteAdapter",
]
