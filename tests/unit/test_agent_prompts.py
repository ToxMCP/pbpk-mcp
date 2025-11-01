"""Validation tests for agent prompt assets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_bridge.agent.prompts import executor_prompt, planner_prompt, system_prompt


def test_system_prompt_emphasises_safety_and_clarification() -> None:
    prompt = system_prompt()
    assert "Safety first" in prompt
    assert "clarifying questions" in prompt
    assert "Respect confirmations" in prompt


def test_planner_prompt_marks_critical_tools() -> None:
    prompt = planner_prompt()
    assert "critical" in prompt
    assert "load_simulation" in prompt
    assert "clarifying question" in prompt


def test_executor_prompt_references_confirmation_pause() -> None:
    prompt = executor_prompt()
    assert "Before calling a critical tool" in prompt
    assert "summarise the outcome" in prompt
    assert "cancellation" in prompt or "cancel" in prompt


@pytest.mark.parametrize(
    "fixture_name",
    [
        "confirmation_approved.json",
        "confirmation_denied.json",
        "clarification_required.json",
    ],
)
def test_golden_dialogue_fixtures_are_well_formed(fixture_name: str) -> None:
    fixture_path = Path("tests/fixtures/golden_dialogues") / fixture_name
    assert fixture_path.is_file(), f"Missing golden dialogue: {fixture_name}"
    payload = json.loads(fixture_path.read_text())
    assert "id" in payload and payload["id"], "Fixture must include an id"
    assert isinstance(payload.get("turns"), list) and payload["turns"], "Fixture must contain turns"
    for turn in payload["turns"]:
        assert "role" in turn
        assert turn["role"] in {"user", "assistant"}
        if turn["role"] == "user":
            assert "content" in turn, "User turns must include content"
        else:
            assert any(
                key in turn for key in ("content", "check")
            ), "Assistant turns must include content or check metadata"
