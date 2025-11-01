"""Regression tests for confirm-before-execute agent dialogues."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from mcp_bridge.adapter.mock import InMemoryAdapter
from mcp_bridge.agent import create_agent_workflow, create_initial_agent_state
from mcp_bridge.services.job_service import JobService

FIXTURE_DIR = Path("tests/fixtures/golden_dialogues")


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text())


def _last_ai_content(messages: list[Any]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return message.content
    raise AssertionError("Expected an AI message but none was recorded")


def _resolve_path(state: dict[str, Any], dotted: str) -> Any:
    current: Any = state
    for segment in dotted.split("."):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        else:
            return None
    return current


@pytest.mark.parametrize(
    "fixture_name",
    [
        "confirmation_approved.json",
        "confirmation_denied.json",
        "clarification_required.json",
    ],
)
def test_agent_golden_dialogues(fixture_name: str) -> None:
    payload = _load_fixture(fixture_name)

    adapter = InMemoryAdapter()
    adapter.init()
    job_service = JobService()
    try:
        graph, _tools, _state_template = create_agent_workflow(
            adapter=adapter,
            job_service=job_service,
        )
        state = create_initial_agent_state()
        config = {"configurable": {"thread_id": payload["id"]}}

        for turn in payload["turns"]:
            role = turn["role"].lower()
            if role == "user":
                message = turn["content"]
                state["messages"].append(HumanMessage(content=message))
                if turn.get("asFeedback"):
                    state["user_feedback"] = message
                state = graph.invoke(state, config=config)
            elif role == "assistant":
                check = turn.get("check", {})
                if "awaiting_confirmation" in check:
                    assert state.get("awaiting_confirmation") is check["awaiting_confirmation"]
                if "contains" in check:
                    ai_content = _last_ai_content(state["messages"])
                    for needle in check["contains"]:
                        assert needle in ai_content
                if "state" in check:
                    for path, expected in check["state"].items():
                        value = _resolve_path(state, path)
                        if expected == "!not-empty":
                            assert value not in (None, "")
                        else:
                            assert value == expected
            else:  # pragma: no cover - invalid fixture entry
                raise ValueError(f"Unsupported role '{role}' in fixture {fixture_name}")
    finally:
        job_service.shutdown()
        adapter.shutdown()
