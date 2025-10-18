# Quickstart: LangGraph Agent with Confirm-Before-Execute

This guide demonstrates the LangChain/LangGraph agent that orchestrates MCP tools
through a confirm-before-execute workflow. You will:

1. Launch the agent in scripted and interactive modes.
2. Approve or deny critical tool calls.
3. Run a full simulation workflow via natural language.
4. Extend the session with sensitivity and population actions.

## Prerequisites

- Follow the [REST quickstart](quickstart-cli.md) to install dependencies.
- Optional: configure R/ospsuite if you want to switch the adapter backend to `subprocess`.
- Ensure environment variables mirror the ones used by the server (`AUTH_DEV_SECRET`, `ADAPTER_BACKEND`, etc.).
- Configuration details are catalogued in `../reference/configuration.md`.

## 1. Scripted demo (`run_agent.py demo`)

The scripted mode runs a deterministic workflow that mirrors the CLI quickstart.

```bash
export ADAPTER_BACKEND=inmemory
PYTHONPATH=src python run_agent.py demo
```

Output highlights:

```
[Demo] Step 1: Load simulation
  ✓ Loaded: demo-sim
[Demo] Step 2: Set parameter value
  ✓ Set parameter: Organism|Weight = 75.0 kg
[Demo] Step 3: Run simulation
  ✓ Job submitted: job-5d5a8260
...
```

The script uses the same adapter configuration as the FastAPI app (via `load_config()`), so switching `ADAPTER_BACKEND=subprocess` exercises the ospsuite bridge.

## 2. Interactive loop (`run_agent.py`)

Run the agent in interactive mode to experience confirmation prompts and contextual reasoning:

```bash
PYTHONPATH=src python run_agent.py
```

You will see helper text and a REPL-style prompt:

```
Suggested workflow:
  • load tests/fixtures/demo.pkml as demo
  • set Organism|Weight to 2.5 kg for demo
  • run simulation demo
  • status <job-id>
```

### 2.1 Approvals

Enter:

```
load tests/fixtures/demo.pkml as demo
```

The agent summarises the action and pauses:

```
[Agent] I will load tests/fixtures/demo.pkml into simulation ID demo. OK to continue? (yes/no)
```

Respond with `yes` (or `no` to abort). The same gate applies to `set_parameter_value` and `run_simulation`. All approvals/denials are logged in the agent state for audit trails.

### 2.2 Monitoring jobs

After running a simulation the agent returns a `jobId`. Ask:

```
status <job-id>
```

The agent will invoke `get_job_status`, summarise the queue/runtime, and continue polling if needed.

## 3. Agent-driven workflows

Try multi-step instructions:

```
load tests/fixtures/demo.pkml as qstart
set the Organism|Weight to 70 kilograms for qstart
run qstart
once the job finishes calculate pk parameters
```

The planner decomposes the request into tool calls, pausing for approvals on critical mutations. If `calculate_pk_parameters` is requested, results are summarised in Markdown tables.

## 4. Sensitivity analysis from the agent

Issue:

```
for qstart run a sensitivity analysis on Organism|Weight at +/- 10 percent and summarise cmax changes
```

The agent reuses the utility in `mcp_bridge.agent.sensitivity` and returns a structured result, highlighting percentage deltas. Approve the confirmation prompt covering the multi-run workflow.

## 5. Population simulations via natural language

Ask:

```
launch a population simulation called qstart-pop with 200 subjects and report mean and 95th percentile exposure
```

The agent:

1. Builds a population configuration.
2. Calls `run_population_simulation`.
3. Polls the job until completion.
4. Calls `get_population_results` and summarises aggregates.

The final message includes chunk metadata when claim-check outputs exist. Use `get chunk <chunkId>` to request specific slices if you extend the prompt templates.

## 6. Troubleshooting tips

- If the agent warns about missing simulations, ensure `MCP_MODEL_SEARCH_PATHS` includes the directory containing your `.pkml` files.
- Confirm-before-execute prompts persist until you answer `yes` or `no`. Blank responses default to `no`.
- To reset state, exit (`quit`) and rerun the script; it clears the session registry and shuts down background threads.

## 7. Next steps

- Review prompt design and safety rails in [`../agent-prompts.md`](../agent-prompts.md).
- Explore advanced workflows in [`../sensitivity-analysis.md`](../sensitivity-analysis.md) and [`../population-simulation.md`](../population-simulation.md).
- If you plan to embed the agent inside LangServe or a bespoke application, start from `create_agent_workflow()` in `src/mcp_bridge/agent/__init__.py`.
