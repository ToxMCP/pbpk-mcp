from __future__ import annotations

import pytest

from mcp.session_registry import registry
from mcp.tools.set_parameter_value import (
    SetParameterValueRequest,
    SetParameterValueResponse,
    SetParameterValueValidationError,
    set_parameter_value,
)
from mcp_bridge.adapter.mock import InMemoryAdapter


@pytest.fixture(autouse=True)
def clear_registry() -> None:
    registry.clear()
    yield
    registry.clear()


@pytest.fixture()
def adapter() -> InMemoryAdapter:
    instance = InMemoryAdapter()
    instance.init()
    handle = instance.load_simulation("tests/fixtures/demo.pkml", simulation_id="demo")
    registry.register(handle)
    instance.set_parameter_value("demo", "Organ.Liver.Weight", 1.0, unit="kg")
    return instance


def test_set_parameter_value_updates_value(adapter: InMemoryAdapter) -> None:
    payload = SetParameterValueRequest(
        simulationId="demo",
        parameterPath="Organ.Liver.Weight",
        value=2.5,
        unit="kg",
        comment="integration-test",
    )
    response = set_parameter_value(adapter, payload)
    assert isinstance(response, SetParameterValueResponse)
    assert response.parameter.value == 2.5


def test_set_parameter_value_unknown_simulation(adapter: InMemoryAdapter) -> None:
    payload = SetParameterValueRequest(
        simulationId="missing",
        parameterPath="Organ.Liver.Weight",
        value=1.0,
    )
    with pytest.raises(SetParameterValueValidationError):
        set_parameter_value(adapter, payload)


def test_set_parameter_value_invalid_path(adapter: InMemoryAdapter) -> None:
    with pytest.raises(ValueError):
        SetParameterValueRequest(
            simulationId="demo",
            parameterPath="\n",
            value=1.0,
        )
