"""Integration-style unit tests for the confirm-before-execute workflow helpers."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from mcp_bridge.adapter.mock import InMemoryAdapter
from mcp_bridge.agent import create_agent_workflow, create_initial_agent_state
from mcp_bridge.services.job_service import JobService


def _setup_workflow() -> tuple[Any, dict, dict, JobService, InMemoryAdapter]:
    adapter = InMemoryAdapter()
    adapter.init()
    job_service = JobService()
    graph, tools, state = create_agent_workflow(adapter=adapter, job_service=job_service)
    return graph, tools, state, job_service, adapter


def test_load_simulation_requires_confirmation() -> None:
    graph, _, state, job_service, adapter = _setup_workflow()
    try:
        state = create_initial_agent_state()
        state["messages"].append(HumanMessage(content="load tests/fixtures/demo.pkml as demo-test"))
        config = {"configurable": {"thread_id": "wf-load"}}
        state = graph.invoke(state, config=config)
        assert state.get("awaiting_confirmation") is True
        prompt = state.get("confirmation_prompt") or ""
        assert "demo-test" in prompt

        state["user_feedback"] = "yes"
        state = graph.invoke(state, config=config)
        assert state.get("simulation_context", {}).get("simulationId") == "demo-test"
        ai_messages = [m for m in state["messages"] if isinstance(m, AIMessage)]
        assert ai_messages
        assert "Loaded" in ai_messages[-1].content
    finally:
        job_service.shutdown()
        adapter.shutdown()


def test_denied_confirmation_cancels_action() -> None:
    graph, _, state, job_service, adapter = _setup_workflow()
    try:
        state = create_initial_agent_state()
        state["messages"].append(
            HumanMessage(content="load tests/fixtures/demo.pkml as denied-test")
        )
        config = {"configurable": {"thread_id": "wf-deny"}}
        state = graph.invoke(state, config=config)
        assert state.get("awaiting_confirmation") is True
        state["user_feedback"] = "no"
        state = graph.invoke(state, config=config)
        ai_messages = [m for m in state["messages"] if isinstance(m, AIMessage)]
        assert ai_messages
        assert "cancelled" in ai_messages[-1].content.lower()
    finally:
        job_service.shutdown()
        adapter.shutdown()


def test_set_parameter_reports_error_when_simulation_missing() -> None:
    graph, _, state, job_service, adapter = _setup_workflow()
    try:
        state = create_initial_agent_state()
        state["messages"].append(
            HumanMessage(content="set Organism|Weight to 70 kg for phantom-sim")
        )
        config = {"configurable": {"thread_id": "wf-error"}}
        state = graph.invoke(state, config=config)
        state["user_feedback"] = "yes"
        state = graph.invoke(state, config=config)
        ai_messages = [m for m in state["messages"] if isinstance(m, AIMessage)]
        assert ai_messages
        assert "unable" in ai_messages[-1].content.lower()
    finally:
        job_service.shutdown()
        adapter.shutdown()
