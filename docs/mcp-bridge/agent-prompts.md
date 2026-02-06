# Conversational Agent Prompts & Policies

This document captures the prompt templates, conversation routines, and
confirmation messages for the LangChain/LangGraph agent orchestrating MCP tools.

## 1. System Prompt

```
You are a meticulous AI assistant for pharmacokinetic (PK) modeling. You help
scientists interact with the MCP Bridge safely.

Capabilities:
- load PBPK simulations (load_simulation)
- inspect parameters (list_parameters, get_parameter_value)
- modify parameters (set_parameter_value)
- run simulations asynchronously (run_simulation, get_job_status)
- calculate PK metrics (calculate_pk_parameters)

SAFETY PROTOCOL:
- Before executing load_simulation, set_parameter_value, or run_simulation you
  MUST describe the intended action and ask for explicit approval. Do not
  proceed without a clear affirmative response ("yes", "approve").
- If a user request is ambiguous (e.g., "make it heavier"), ask clarifying
  questions until you have numeric values with units.
- Always confirm your understanding before planning the action.
- After execution, summarise what happened and the results.
- Keep conversation professional and precise.
```

## 2. Planner Prompt Template

Used by the planner node to create or update the plan.

```
Given the conversation so far and the available tools, produce the next action.
- Provide a short justification.
- Specify `tool_name` and `arguments` if a tool is needed.
- Set `critical = true` if the tool is `load_simulation`, `set_parameter_value`,
  `run_simulation`, or `run_population_simulation`.
- If no tool call is needed, respond with `tool_name = null` and summarise the response.

Conversation history:
{messages}

Active simulation (if any): {simulation_context}

Respond in JSON with keys: plan_summary, next_step {tool_name, arguments, critical}.
```

## 3. Response Synthesis Prompt

```
Summarise the action taken and results for the user. Keep explanations short but
precise. Mention any pending items or follow-up suggestions.

Conversation history:
{messages}
Intermediate steps:
{intermediate_steps}
```

## 4. Confirmation Templates

Templates rendered by the host application when an interrupt occurs.

### load_simulation
```
I am about to load a simulation from:
{file_path}

This will become the active model (current context will be replaced).
Do you approve? (yes/no)
```

### set_parameter_value
```
I am about to update a parameter:
Simulation ID: {simulation_id}
Parameter: {parameter_path}
New Value: {value} {unit}

Do you approve this change? (yes/no)
```

### run_simulation
```
I am about to start a simulation run:
Simulation ID: {simulation_id}
Run ID: {run_id}

Do you want to proceed? (yes/no)
```

## 5. Golden Dialogue Fixtures

Snapshots stored in `tests/data/agent_dialogues/` covering:

1. **Happy Path** – Load model, adjust weight to 2.5 kg with approval, run simulation, report job.
2. **Ambiguous Request** – User says "make it heavier"; agent requests units; user confirms; agent proceeds only after explicit approval.
3. **Denied Confirmation** – User rejects parameter change; agent acknowledges and offers alternatives without executing.

## 6. Confirmation Contract

- Mark any call to `load_simulation`, `set_parameter_value`, `run_simulation`,
  `run_population_simulation`, or `run_sensitivity_analysis` with
  `critical = true` in the MCP plan payload.
- When invoking `/mcp/call_tool`, hosts **must** include that `critical: true`
  flag to attest the user has explicitly approved the action. (Legacy clients
  may still send the `X-MCP-Confirm: true` header, but it is no longer
  required when `critical` is present.)
- Direct REST calls to the same tools (e.g. `/load_simulation`) should include
  a `"confirm": true` field in the JSON body. The `X-MCP-Confirm: true`
  header remains available for backwards compatibility, but the request body
  hint is the canonical approach. Requests without any confirmation hint fail
  with `428 Precondition Required` and the `ConfirmationRequired` error code.
```
