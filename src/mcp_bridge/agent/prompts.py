"""Prompt assets and helpers for the confirm-before-execute agent."""

from __future__ import annotations

from typing import Any, Mapping

_SYSTEM_POLICY = """
You are a meticulous pharmacokinetic modelling assistant supporting the PBPK MCP bridge. Follow
these principles:
- **Safety first**: treat every model change or execution as high stakes. Never mutate data or run
  simulations without explicit user approval captured during the current conversation.
- **Transparency**: before proposing an action, restate the plan, inputs, identifiers, units, and
  assumptions so the user can validate them.
- **Clarify missing context**: when the request is ambiguous or required arguments are absent,
  respond with targeted clarifying questions instead of guessing.
- **Regulatory discipline**: log noteworthy decisions, keep conversations factual, and flag
  potential compliance risks (e.g., unverified data, unusual dosing).
- **Respect confirmations**: once a user declines a critical action, acknowledge the refusal and
  offer safe alternatives rather than retrying automatically.
""".strip()

_PLANNER_GUIDANCE = """
Build an explicit plan for the next turn:
1. Summarise the user goal in one sentence using their vocabulary.
2. Decide which MCP tool (if any) is appropriate and mark it as `critical` when it is in
   {load_simulation, set_parameter_value, run_simulation}.
3. List every argument the tool requires; for each missing value, write the clarifying question you
   will ask instead of executing.
4. Capture safety considerations (e.g., unit conversions, previously loaded simulation) so the
   executor can mention them.
Return the plan as concise bullet points or a short JSON-like structure that the downstream nodes
can follow without improvising.
""".strip()

_EXECUTION_GUIDANCE = """
During execution, speak plainly and uphold safety:
- Before calling a critical tool, present the confirmation message verbatim and pause until the
  user approves.
- After success, summarise the outcome, highlight important identifiers/values, and describe the
  next recommended step.
- After failure or cancellation, clearly state what happened, capture the error message, and offer
  actionable remediation ideas.
- If prerequisites remain unresolved (e.g., missing model, denied confirmation), remind the user of
  the outstanding requirement rather than attempting the action again.
""".strip()

_CONFIRMATION_TEMPLATES = {
    "load_simulation": (
        "I am about to load the simulation file {filePath} and register it as '{simulationId}'. "
        "This will make it the active context and may replace any currently loaded simulation. "
        "Do you approve?"
    ),
    "set_parameter_value": (
        "I am ready to update {parameterPath} in simulation '{simulationId}' to {value}{unit_suffix}. "
        "This will permanently change the parameter value used in subsequent runs. Do you approve?"
    ),
    "run_simulation": (
        "I am about to run the simulation '{simulationId}'. This may take time and consume compute "
        "resources. Do you want me to proceed?"
    ),
}

_GENERIC_CONFIRMATION = (
    "I am prepared to execute the '{tool}' tool with the following arguments: {args}. "
    "Should I continue?"
)


def system_prompt() -> str:
    """Return the system prompt that anchors the agent persona."""

    return _SYSTEM_POLICY


def planner_prompt() -> str:
    """Return guidance for the planning step."""

    return _PLANNER_GUIDANCE


def executor_prompt() -> str:
    """Return guidance for the execution/response step."""

    return _EXECUTION_GUIDANCE


def _format_unit(args: Mapping[str, Any]) -> str:
    unit = args.get("unit")
    if not unit:
        return ""
    return f" {unit}"


def format_confirmation_prompt(tool: str, args: Mapping[str, Any]) -> str:
    """Create a confirmation message for the provided tool and arguments."""

    template = _CONFIRMATION_TEMPLATES.get(tool, GENERIC_CONFIRMATION)
    payload = {
        "tool": tool,
        "args": _truncate_args(args),
        "filePath": args.get("filePath", "unknown path"),
        "simulationId": args.get("simulationId", "unknown"),
        "parameterPath": args.get("parameterPath", "unknown parameter"),
        "value": args.get("value", "unknown"),
        "unit_suffix": _format_unit(args),
    }
    return template.format(**payload)


GENERIC_CONFIRMATION = _GENERIC_CONFIRMATION


def format_success_response(tool: str, result: Mapping[str, Any]) -> str:
    """Summarise a successful tool execution for user-facing output."""

    if tool == "load_simulation":
        return (
            "Loaded simulation '{simulationId}' from {filePath}."
        ).format(
            simulationId=result.get("simulationId", "unknown"),
            filePath=result.get("metadata", {}).get("filePath") or result.get("filePath", "the provided path"),
        )

    if tool == "set_parameter_value":
        parameter = result.get("parameter", {})
        return (
            "Updated {path} to {value}{unit}."
        ).format(
            path=parameter.get("path", "the parameter"),
            value=parameter.get("value", "?"),
            unit=f" {parameter.get('unit')}" if parameter.get("unit") else "",
        )

    if tool == "run_simulation":
        return (
            "Simulation job {jobId} queued. Check status when ready."
        ).format(jobId=result.get("jobId", "unknown"))

    if tool == "get_job_status":
        job = result.get("job", {})
        status = job.get("status", "unknown")
        if status.lower() == "succeeded" and job.get("resultHandle"):
            return (
                "Job {jobId} succeeded. Retrieve results with ID {resultsId}."
            ).format(
                jobId=job.get("jobId", "unknown"),
                resultsId=job.get("resultHandle", {}).get("resultsId", "unknown"),
            )
        return (
            "Job {jobId} status: {status}."
        ).format(jobId=job.get("jobId", "unknown"), status=status)

    if tool == "calculate_pk_parameters":
        return "PK parameters calculated successfully."

    return f"Executed {tool} successfully."


def format_error_response(tool: str, message: str) -> str:
    """Summarise a tool failure for the user."""

    return f"Unable to complete {tool}: {message}" if message else f"{tool} did not complete."


def _truncate_args(args: Mapping[str, Any]) -> str:
    if not args:
        return "{}"
    pairs = [f"{key}={value}" for key, value in args.items()]
    text = ", ".join(pairs)
    return text if len(text) <= 120 else text[:117] + "..."


__all__ = [
    "system_prompt",
    "planner_prompt",
    "executor_prompt",
    "format_confirmation_prompt",
    "format_success_response",
    "format_error_response",
]
