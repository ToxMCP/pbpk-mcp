from __future__ import annotations

from pathlib import Path

import pytest

from mcp.session_registry import registry
from mcp.tools.load_simulation import (
    LoadSimulationRequest,
    LoadSimulationValidationError,
    resolve_model_path,
    validate_load_simulation_request,
)
from mcp_bridge.adapter.schema import SimulationHandle

ALLOWED_ROOT = (Path.cwd() / "tests" / "fixtures").resolve()
DEMO_PATH = ALLOWED_ROOT / "demo.pkml"


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    registry.clear()
    yield
    registry.clear()


def test_validate_load_simulation_request_happy_path() -> None:
    payload = LoadSimulationRequest(filePath=str(DEMO_PATH))

    simulation_id, resolved = validate_load_simulation_request(
        payload,
        allowed_roots=[ALLOWED_ROOT],
    )

    assert simulation_id == "demo"
    assert resolved == DEMO_PATH


def test_validate_load_simulation_request_rejects_duplicate_id() -> None:
    handle = SimulationHandle(simulation_id="demo", file_path=str(DEMO_PATH))
    registry.register(handle)

    payload = LoadSimulationRequest(filePath=str(DEMO_PATH), simulationId="demo")

    with pytest.raises(LoadSimulationValidationError):
        validate_load_simulation_request(payload, allowed_roots=[ALLOWED_ROOT])


def test_resolve_model_path_rejects_invalid_extension(tmp_path: Path) -> None:
    bad_file = tmp_path / "model.txt"
    bad_file.write_text("not a pkml")

    with pytest.raises(LoadSimulationValidationError):
        resolve_model_path(str(bad_file), allowed_roots=[tmp_path])


def test_resolve_model_path_requires_existing_file() -> None:
    missing = ALLOWED_ROOT / "missing.pkml"

    with pytest.raises(LoadSimulationValidationError):
        resolve_model_path(str(missing), allowed_roots=[ALLOWED_ROOT])


def test_resolve_model_path_rejects_outside_allowlist(tmp_path: Path) -> None:
    outside = tmp_path / "external.pkml"
    outside.write_text("<pkml />")

    with pytest.raises(LoadSimulationValidationError):
        resolve_model_path(str(outside), allowed_roots=[ALLOWED_ROOT])
