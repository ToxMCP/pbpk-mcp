from __future__ import annotations

from pathlib import Path

import pytest

from mcp.session_registry import registry
from mcp.tools.load_simulation import (
    LoadSimulationRequest,
    LoadSimulationValidationError,
    load_simulation,
)
from mcp_bridge.adapter.mock import InMemoryAdapter

FIXTURE_DIR = (Path.cwd() / "tests" / "fixtures").resolve()
DEMO_MODEL = FIXTURE_DIR / "demo.pkml"


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    registry.clear()
    yield
    registry.clear()


@pytest.fixture()
def adapter() -> InMemoryAdapter:
    instance = InMemoryAdapter()
    instance.init()
    return instance


def test_load_simulation_registers_in_session_store(adapter: InMemoryAdapter) -> None:
    request = LoadSimulationRequest(filePath=str(DEMO_MODEL), simulationId="sim-loaded")

    response = load_simulation(adapter, request, allowed_roots=[FIXTURE_DIR])

    assert response.simulation_id == "sim-loaded"
    assert registry.contains("sim-loaded")


def test_load_simulation_prevents_duplicates(adapter: InMemoryAdapter) -> None:
    first = LoadSimulationRequest(filePath=str(DEMO_MODEL), simulationId="dup-sim")
    load_simulation(adapter, first, allowed_roots=[FIXTURE_DIR])

    duplicate = LoadSimulationRequest(filePath=str(DEMO_MODEL), simulationId="dup-sim")

    with pytest.raises(LoadSimulationValidationError):
        load_simulation(adapter, duplicate, allowed_roots=[FIXTURE_DIR])
