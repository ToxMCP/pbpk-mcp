"""MCP tool definitions and validation helpers for loading PBPK simulations."""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mcp_bridge.adapter import AdapterError
from mcp_bridge.adapter.interface import OspsuiteAdapter

from ..session_registry import SessionRegistry, SessionRegistryError, registry

SUPPORTED_EXTENSIONS = {".pkml", ".pksim5"}
MODEL_PATH_ENV = "MCP_MODEL_SEARCH_PATHS"
DEFAULT_ALLOWED_ROOTS = [
    (Path.cwd() / "tests" / "fixtures").resolve(),
    (Path.cwd() / "reference" / "models" / "standard").resolve(),
]


class LoadSimulationValidationError(ValueError):
    """Raised when load_simulation inputs fail validation."""


class DuplicateSimulationError(LoadSimulationValidationError):
    """Raised when attempting to register an existing simulation."""


class LoadSimulationRequest(BaseModel):
    """Payload accepted by the ``load_simulation`` MCP tool."""

    model_config = ConfigDict(populate_by_name=True)

    file_path: str = Field(alias="filePath")
    simulation_id: Optional[str] = Field(
        default=None,
        alias="simulationId",
        min_length=1,
        max_length=64,
    )

    @field_validator("file_path")
    @classmethod
    def _ensure_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("file_path must be provided")
        return value


class SimulationMetadataModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: Optional[str] = None
    model_version: Optional[str] = Field(default=None, alias="modelVersion")
    created_by: Optional[str] = Field(default=None, alias="createdBy")
    created_at: Optional[str] = Field(default=None, alias="createdAt")


class LoadSimulationResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    simulation_id: str = Field(alias="simulationId")
    metadata: SimulationMetadataModel = SimulationMetadataModel()
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def from_adapter_payload(
        cls,
        simulation_id: str,
        metadata: Optional[dict[str, object]] = None,
        warnings: Optional[Sequence[str]] = None,
    ) -> LoadSimulationResponse:
        """Helper to construct the response from adapter metadata."""

        meta = metadata or {}
        return cls(
            simulationId=simulation_id,
            metadata=SimulationMetadataModel.model_validate(meta, from_attributes=True),
            warnings=list(warnings or []),
        )


def _resolve_allowed_roots() -> list[Path]:
    raw = os.getenv(MODEL_PATH_ENV)
    if not raw:
        return [root for root in DEFAULT_ALLOWED_ROOTS if root.exists()]

    roots: list[Path] = []
    for chunk in raw.split(os.pathsep):
        candidate = chunk.strip()
        if not candidate:
            continue
        roots.append(Path(candidate).expanduser().resolve())
    fallback = [root for root in DEFAULT_ALLOWED_ROOTS if root.exists()]
    return roots or fallback


def resolve_model_path(file_path: str, *, allowed_roots: Optional[Iterable[Path]] = None) -> Path:
    """Resolve and validate the model path against the allowed roots."""

    candidate = Path(file_path).expanduser()
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if candidate.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise LoadSimulationValidationError("Only .pkml and .pksim5 files are supported")

    if not candidate.is_file():
        raise LoadSimulationValidationError(f"Simulation file '{candidate}' does not exist")

    roots = list(allowed_roots) if allowed_roots else _resolve_allowed_roots()
    if not roots:
        raise LoadSimulationValidationError("No model search paths configured")

    for root in roots:
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        else:
            return candidate

    raise LoadSimulationValidationError("Simulation path is outside the allowed directories")


def _normalise_simulation_id(simulation_id: Optional[str], resolved_path: Path) -> str:
    identifier = (simulation_id or resolved_path.stem).strip()
    if not identifier:
        raise LoadSimulationValidationError("simulation_id cannot be empty")
    if len(identifier) > 64:
        raise LoadSimulationValidationError("simulation_id must be at most 64 characters")
    return identifier


def validate_load_simulation_request(
    payload: LoadSimulationRequest,
    *,
    allowed_roots: Optional[Iterable[Path]] = None,
) -> Tuple[str, Path]:
    """Validate payload fields and return canonical values."""

    resolved = resolve_model_path(payload.file_path, allowed_roots=allowed_roots)
    simulation_id = _normalise_simulation_id(payload.simulation_id, resolved)

    if registry.contains(simulation_id):
        raise DuplicateSimulationError(f"Simulation '{simulation_id}' is already registered")

    return simulation_id, resolved


def load_simulation(
    adapter: OspsuiteAdapter,
    payload: LoadSimulationRequest,
    *,
    session_store: SessionRegistry | None = None,
    allowed_roots: Optional[Iterable[Path]] = None,
) -> LoadSimulationResponse:
    """Execute the load_simulation workflow against the adapter."""

    store = session_store or registry

    simulation_id, resolved_path = validate_load_simulation_request(
        payload, allowed_roots=allowed_roots
    )

    try:
        handle = adapter.load_simulation(str(resolved_path), simulation_id=simulation_id)
    except AdapterError as exc:
        raise LoadSimulationValidationError(str(exc)) from exc

    try:
        store.register(handle, metadata=handle.metadata)
    except SessionRegistryError as exc:
        raise LoadSimulationValidationError(str(exc)) from exc

    return LoadSimulationResponse.from_adapter_payload(
        simulation_id=handle.simulation_id,
        metadata=handle.metadata,
    )


__all__ = [
    "SUPPORTED_EXTENSIONS",
    "DuplicateSimulationError",
    "LoadSimulationRequest",
    "LoadSimulationResponse",
    "load_simulation",
    "LoadSimulationValidationError",
    "SimulationMetadataModel",
    "resolve_model_path",
    "validate_load_simulation_request",
]
