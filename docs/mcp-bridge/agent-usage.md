# Confirm-Before-Execute Agent: Operator Guide

This guide explains how to run the LangChain/LangGraph agent that mediates all
MCP tool calls through an explicit confirm-before-execute workflow.

## 1. Runtime Setup

1. **Environment** – ensure the MCP bridge dependencies are installed (see
   `pyproject.toml`) and the following environment variables are configured:

   | Variable | Purpose |
   |----------|---------|
   | `ADAPTER_BACKEND` | Select `inmemory` for local tests or `subprocess` to talk to the R bridge. |
   | `JOB_WORKER_THREADS` | Number of in-process worker threads available to the async job service. |
   | `JOB_TIMEOUT_SECONDS` / `JOB_MAX_RETRIES` | Default timeout and retry budget for submitted jobs. |
   | `POPULATION_STORAGE_PATH` | Filesystem root for chunked population-simulation artefacts. |

2. **Instantiate components** – both the FastAPI app and the CLI demo
   (`run_agent.py`) follow the same pattern:

   ```python
   adapter = build_adapter_from_config(app_config)
   adapter.init()
   job_service = JobService(
       max_workers=app_config.job_worker_threads,
       default_timeout=float(app_config.job_timeout_seconds),
       max_retries=app_config.job_max_retries,
   )
   graph, tools, state_template = create_agent_workflow(
       adapter=adapter,
       job_service=job_service,
       max_tool_retries=app_config.job_max_retries,
   )
   ```

3. **Threading model** – every independent conversation must supply a stable
   `thread_id` via `config = {"configurable": {"thread_id": <id>}}`. Reuse the
   same ID when resuming after a confirmation.

## 2. Handling Confirmation Interrupts

After each user message (or feedback) invoke the graph:

```python
state = graph.invoke(state, config=config)
```

Inspect the returned state for the confirmation signals:

- `state["awaiting_confirmation"]` – `True` when a critical tool is paused.
- `state["confirmation_prompt"]` – human-readable summary that **must** be
  presented verbatim to the user.
- `state["pending_tool_call"]` – structured payload containing the tool name
  and arguments about to be executed.

Resume execution only when the user explicitly approves or denies:

```python
state["messages"].append(HumanMessage(content=user_reply))
state["user_feedback"] = user_reply
state = graph.invoke(state, config=config)
```

Approval continues to the execution node and appends a success summary; denial
clears the pending action and the agent confirms that no change was performed.

## 3. Conversation Safety Checklist

- **Critical tools** – the confirmation gate is hard-coded for
  `load_simulation`, `set_parameter_value`, and `run_simulation`. Extend
  `CRITICAL_TOOLS` if additional mutations are introduced.
- **Prompts** – the rewritten system/planner/executor prompts
  (`src/mcp_bridge/agent/prompts.py`) emphasise clarification, confirmation, and
  auditability. Any changes should be accompanied by updated golden dialogues.
- **History integrity** – confirmation prompts, approvals, and cancellations are
  logged in `state["messages"]`, ensuring downstream audit trails capture the
  entire decision process.

## 4. Regression Coverage

`tests/integration/test_agent_dialogues.py` executes golden dialogues stored in
`tests/fixtures/golden_dialogues/` covering:

- Approved flow: load a simulation, confirm, run it, and verify the job handle.
- Denied flow: reject a parameter update and ensure no mutation occurs.
- Clarification flow: ambiguous instructions trigger safe follow-up questions.

Run the suite with:

```
pytest tests/integration/test_agent_dialogues.py
```

The regression tests should pass locally and in CI before deploying prompt or
workflow changes.

## 5. Shutdown

Always shut down resources gracefully to avoid orphaned R sessions or worker
threads:

```python
adapter.shutdown()
job_service.shutdown()
```

This mirrors the FastAPI application lifecycle (`@app.on_event("shutdown")`).
