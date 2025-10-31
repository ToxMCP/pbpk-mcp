#!/usr/bin/env python3
"""LangGraph Agent Entry Point for Testing the Confirm-Before-Execute Workflow."""

from __future__ import annotations

import sys
import textwrap
import time
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from mcp.session_registry import registry, set_registry
from mcp_bridge.agent import create_agent_workflow, create_initial_agent_state
from mcp_bridge.config import load_config
from mcp_bridge.runtime.factory import build_adapter, build_population_store, build_session_registry
from mcp_bridge.services.job_service import BaseJobService, create_job_service


def _create_runtime() -> tuple[Any, dict, BaseJobService, Any]:
    app_config = load_config()
    population_store = build_population_store(app_config)
    adapter = build_adapter(app_config, population_store=population_store)
    adapter.init()

    session_registry = build_session_registry(app_config)
    set_registry(session_registry)

    job_service = create_job_service(
        config=app_config,
        audit_trail=None,
        population_store=population_store,
    )

    graph, tools, _ = create_agent_workflow(
        adapter=adapter,
        job_service=job_service,
        checkpointer_path=app_config.agent_checkpointer_path,
        max_tool_retries=app_config.job_max_retries,
        retry_backoff_seconds=app_config.job_retry_backoff_seconds
        if hasattr(app_config, "job_retry_backoff_seconds")
        else 0.25,
    )
    return graph, tools, job_service, adapter


def run_scripted_demo() -> None:
    print("=" * 70)
    print("LangGraph Agent - Scripted Workflow Demo")
    print("=" * 70)

    graph, tools, job_service, adapter = _create_runtime()
    try:
        print("\n[Demo] Step 1: Load simulation")
        load_result = tools["load_simulation"].invoke(
            {
                "filePath": "tests/fixtures/demo.pkml",
                "simulationId": "demo-sim",
            }
        )
        print(f"  ✓ Loaded: {load_result['simulationId']}")

        print("\n[Demo] Step 2: Set parameter value")
        set_result = tools["set_parameter_value"].invoke(
            {
                "simulationId": "demo-sim",
                "parameterPath": "Organism|Weight",
                "value": 75.0,
                "unit": "kg",
            }
        )
        parameter = set_result["parameter"]
        print(
            f"  ✓ Set parameter: {parameter['path']} = {parameter['value']} {parameter['unit']}"
        )

        print("\n[Demo] Step 3: Run simulation")
        run_result = tools["run_simulation"].invoke({"simulationId": "demo-sim"})
        job_id = run_result["jobId"]
        print(f"  ✓ Job submitted: {job_id}")

        print("\n[Demo] Step 4: Poll job status")
        for attempt in range(1, 11):
            status_result = tools["get_job_status"].invoke({"jobId": job_id})
            status = status_result["job"]["status"]
            print(f"  Poll {attempt}/10: {status}")
            if status.lower() not in {"queued", "running"}:
                break
            time.sleep(1)

        print("\n[Demo] Workflow completed!")
    finally:
        job_service.shutdown()
        adapter.shutdown()
        registry.clear()


def run_interactive_agent() -> None:
    print("=" * 70)
    print("LangGraph Agent - Interactive Workflow Demo")
    print("=" * 70)

    graph, _, job_service, adapter = _create_runtime()
    state = create_initial_agent_state()
    thread_id = "interactive-demo"
    config = {"configurable": {"thread_id": thread_id}}
    seen_messages = 0

    helper_text = textwrap.dedent(
        """
        Suggested workflow:
          • load tests/fixtures/demo.pkml as demo
          • set Organism|Weight to 2.5 kg for demo
          • run simulation demo
          • status <job-id>
        Type 'quit' to exit.
        """
    )
    print(helper_text)

    try:
        while True:
            user_input = input("\n[You] > ").strip()
            if user_input.lower() in {"quit", "exit", "q"}:
                print("\n[Agent] Goodbye!")
                break
            if not user_input:
                continue

            state["messages"].append(HumanMessage(content=user_input))
            state = graph.invoke(state, config=config)

            while state.get("awaiting_confirmation"):
                prompt = state.get("confirmation_prompt") or "Please confirm before I continue."
                print(f"\n[Agent] {prompt}")
                decision = input("[Confirm] > ").strip()
                state["user_feedback"] = decision or "no"
                state = graph.invoke(state, config=config)

            ai_messages = [
                msg for msg in state["messages"] if isinstance(msg, AIMessage)
            ]
            if len(ai_messages) > seen_messages:
                for message in ai_messages[seen_messages:]:
                    print(f"\n[Agent] {message.content}")
                seen_messages = len(ai_messages)
    finally:
        print("\n[Cleanup] Shutting down...")
        job_service.shutdown()
        adapter.shutdown()
        registry.clear()
        print("[Cleanup] Done.")


if __name__ == "__main__":
    import time

    mode = sys.argv[1] if len(sys.argv) > 1 else "interactive"

    if mode == "demo":
        run_scripted_demo()
    else:
        run_interactive_agent()
