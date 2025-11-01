"""Tests for LangChain/LangGraph agent scaffolding."""

from __future__ import annotations

from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage

from mcp.session_registry import registry
from mcp_bridge.adapter.errors import AdapterError, AdapterErrorCode
from mcp_bridge.adapter.interface import AdapterConfig, OspsuiteAdapter
from mcp_bridge.adapter.schema import (
    ParameterSummary,
    ParameterValue,
    PopulationSimulationConfig,
    PopulationSimulationResult,
    PopulationChunkHandle,
    SimulationHandle,
    SimulationResult,
)
from mcp_bridge.agent import (
    CRITICAL_TOOLS,
    AgentState,
    build_agent_graph,
    create_tool_registry,
    route_after_confirmation,
    route_after_selection,
)
from mcp_bridge.services.job_service import JobService


class StubAdapter(OspsuiteAdapter):
    """Minimal adapter used for unit tests."""

    def __init__(self) -> None:
        super().__init__(AdapterConfig())
        self._simulations: Dict[str, Dict[str, Any]] = {}

    def init(self) -> None:  # pragma: no cover - not used
        return

    def shutdown(self) -> None:  # pragma: no cover - not used
        return

    def health(self) -> Dict[str, Any]:  # pragma: no cover - not used
        return {"status": "ok"}

    def load_simulation(self, file_path: str, simulation_id: str | None = None) -> SimulationHandle:
        sim_id = simulation_id or "sim-test"
        handle = SimulationHandle(simulation_id=sim_id, file_path=file_path)
        self._simulations[sim_id] = {
            "parameters": {
                "Organ.Liver.Weight": ParameterValue(
                    path="Organ.Liver.Weight",
                    value=1.0,
                    unit="kg",
                )
            }
        }
        return handle

    def list_parameters(
        self, simulation_id: str, pattern: str | None = None
    ) -> list[ParameterSummary]:
        if simulation_id not in self._simulations:
            raise AdapterError(AdapterErrorCode.NOT_FOUND, "Simulation not found")
        return [
            ParameterSummary(path=param.path, display_name=None, unit=param.unit)
            for param in self._simulations[simulation_id]["parameters"].values()
        ]

    def get_parameter_value(self, simulation_id: str, parameter_path: str) -> ParameterValue:
        try:
            return self._simulations[simulation_id]["parameters"][parameter_path]
        except KeyError as exc:
            raise AdapterError(AdapterErrorCode.NOT_FOUND, "Parameter not found") from exc

    def set_parameter_value(
        self,
        simulation_id: str,
        parameter_path: str,
        value: float,
        unit: str | None = None,
        *,
        comment: str | None = None,
    ) -> ParameterValue:
        if simulation_id not in self._simulations:
            raise AdapterError(AdapterErrorCode.NOT_FOUND, "Simulation not found")
        parameter = ParameterValue(
            path=parameter_path,
            value=value,
            unit=unit or "unitless",
            source=comment,
        )
        self._simulations[simulation_id]["parameters"][parameter_path] = parameter
        return parameter

    def run_simulation_sync(
        self, simulation_id: str, *, run_id: str | None = None
    ) -> SimulationResult:
        if simulation_id not in self._simulations:
            raise AdapterError(AdapterErrorCode.NOT_FOUND, "Simulation not found")
        return SimulationResult(
            results_id=f"{simulation_id}-{run_id or 'default'}",
            simulation_id=simulation_id,
            generated_at="2025-01-01T00:00:00Z",
            metadata={},
            series=[],
        )

    def get_results(self, results_id: str) -> SimulationResult:
        sim_id = results_id.split("-")[0]
        return SimulationResult(
            results_id=results_id,
            simulation_id=sim_id,
            generated_at="2025-01-01T00:00:00Z",
            metadata={},
            series=[],
        )

    def run_population_simulation_sync(
        self, config: PopulationSimulationConfig
    ) -> PopulationSimulationResult:
        chunk = PopulationChunkHandle(
            chunk_id=f"pop-chunk-{config.simulation_id}",
            subject_range=(1, min(5, config.cohort.size)),
            preview={"subjects": [1, 2], "values": [0.1, 0.2]},
        )
        return PopulationSimulationResult(
            results_id=f"pop-{config.simulation_id}",
            simulation_id=config.simulation_id,
            generated_at="2025-01-01T00:00:00Z",
            cohort=config.cohort,
            aggregates={"meanCmax": 1.23},
            chunk_handles=[chunk],
            metadata=config.metadata,
        )

    def get_population_results(self, results_id: str) -> PopulationSimulationResult:
        cohort = PopulationSimulationConfig(
            model_path="tests/fixtures/demo.pkml",
            simulation_id="pop-stub",
            cohort={"size": 10},
        ).cohort
        chunk = PopulationChunkHandle(
            chunk_id=f"{results_id}-chunk",
            subject_range=(1, 5),
            preview={"subjects": [1, 2], "values": [0.1, 0.2]},
        )
        return PopulationSimulationResult(
            results_id=results_id,
            simulation_id="pop-stub",
            generated_at="2025-01-01T00:00:00Z",
            cohort=cohort,
            aggregates={"meanCmax": 1.0},
            chunk_handles=[chunk],
        )

    def export_simulation_state(self, simulation_id: str) -> Dict[str, Any]:
        if simulation_id not in self._simulations:
            raise AdapterError(AdapterErrorCode.NOT_FOUND, "Simulation not found")
        parameters = {
            path: value.model_dump(mode="json")
            for path, value in self._simulations[simulation_id]["parameters"].items()
        }
        return {
            "simulationId": simulation_id,
            "parameters": parameters,
        }


def _make_default_state() -> AgentState:
    return AgentState(
        messages=[HumanMessage(content="Hello"), AIMessage(content="Hi")],
        simulation_context=None,
        pending_tool_call=None,
        user_feedback=None,
        plan=None,
        intermediate_steps=[],
    )


def test_create_tool_registry_loads_and_runs_jobs() -> None:
    adapter = StubAdapter()
    adapter.load_simulation("tests/fixtures/demo.pkml", simulation_id="sim-1")
    registry.clear()
    job_service = JobService()

    try:
        tools = create_tool_registry(adapter=adapter, job_service=job_service)
        assert set(CRITICAL_TOOLS).issubset(set(tools.keys()))

        load_result = tools["load_simulation"].invoke(
            {"filePath": "tests/fixtures/demo.pkml", "simulationId": "sim-2"}
        )
        assert load_result["simulationId"] == "sim-2"

        set_result = tools["set_parameter_value"].invoke(
            {
                "simulationId": "sim-2",
                "parameterPath": "Organ.Liver.Weight",
                "value": 2.5,
                "unit": "kg",
            }
        )
        assert set_result["parameter"]["value"] == 2.5

        job_response = tools["run_simulation"].invoke({"simulationId": "sim-2"})
        assert "jobId" in job_response
        status = tools["get_job_status"].invoke({"jobId": job_response["jobId"]})
        assert status["job"]["status"].lower() in {"running", "succeeded"}
    finally:
        job_service.shutdown()
        registry.clear()


def test_route_helpers_respect_confirmation_protocol() -> None:
    state: AgentState = _make_default_state()
    state["plan"] = {"next_step": {"tool_name": "set_parameter_value"}}
    assert route_after_selection(state) == "Confirmation_Gate_Node"

    state["plan"] = {"next_step": {"tool_name": "list_parameters"}}
    assert route_after_selection(state) == "Tool_Execution_Node"

    state["plan"] = None
    assert route_after_selection(state) == "Response_Synthesis_Node"

    state["user_feedback"] = "yes"
    assert route_after_confirmation(state) == "Tool_Execution_Node"
    state["user_feedback"] = "no"
    assert route_after_confirmation(state) == "Response_Synthesis_Node"


def test_build_agent_graph_returns_compiled_graph() -> None:
    def planner(state: AgentState) -> AgentState:
        state = dict(state)
        state["plan"] = {"next_step": {"tool_name": "list_parameters"}}
        return state  # type: ignore[return-value]

    def selector(state: AgentState) -> AgentState:
        return state

    def confirmation(state: AgentState) -> Dict[str, Any]:
        return {}

    def executor(state: AgentState) -> AgentState:
        state = dict(state)
        state["intermediate_steps"].append({"tool": "list_parameters"})
        return state  # type: ignore[return-value]

    def synthesiser(state: AgentState) -> AgentState:
        return state

    graph = build_agent_graph(
        planner_node=planner,
        tool_selection_node=selector,
        confirmation_node=confirmation,
        tool_execution_node=executor,
        response_synthesis_node=synthesiser,
    )

    initial_state = _make_default_state()
    result = graph.invoke(initial_state, config={"configurable": {"thread_id": "test-thread"}})
    assert isinstance(result, dict)
