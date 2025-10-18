"""LangChain/LangGraph scaffolding for the confirm-before-execute agent."""

from __future__ import annotations

import operator
import re
import time
from collections import defaultdict
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import StructuredTool
from langchain_core.utils.function_calling import convert_to_openai_function
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import INTERRUPT
from langgraph.graph import END, StateGraph
from langgraph.pregel import empty_checkpoint
from typing_extensions import Annotated

from mcp.tools.calculate_pk_parameters import (
    CalculatePkParametersRequest,
    calculate_pk_parameters,
)
from mcp.tools.get_job_status import (
    GetJobStatusRequest,
    get_job_status,
)
from mcp.tools.get_parameter_value import (
    GetParameterValueRequest,
    get_parameter_value,
)
from mcp.tools.list_parameters import (
    ListParametersRequest,
    list_parameters,
)
from mcp.tools.load_simulation import (
    LoadSimulationRequest,
    load_simulation,
)
from mcp.tools.run_simulation import (
    RunSimulationRequest,
    run_simulation,
)
from mcp.tools.set_parameter_value import (
    SetParameterValueRequest,
    set_parameter_value,
)
from mcp_bridge.adapter.interface import OspsuiteAdapter
from mcp_bridge.agent.prompts import (
    format_confirmation_prompt,
    format_error_response,
    format_success_response,
)
from mcp_bridge.services.job_service import JobService


class AgentState(TypedDict, total=False):
    """Shared state for the LangGraph agent."""

    messages: Annotated[List[BaseMessage], operator.add]
    simulation_context: Optional[Dict[str, Any]]
    pending_tool_call: Optional[Dict[str, Any]]
    user_feedback: Optional[str]
    plan: Optional[Dict[str, Any]]
    intermediate_steps: Annotated[List[Dict[str, Any]], operator.add]
    last_tool_result: Optional[Dict[str, Any]]
    last_tool_name: Optional[str]
    last_error: Optional[str]
    retry_counts: Dict[str, int]
    confirmation_prompt: Optional[str]
    awaiting_confirmation: bool


CRITICAL_TOOLS = {
    "set_parameter_value",
    "run_simulation",
    "load_simulation",
}

_APPROVAL_WORDS = {"yes", "y", "approve", "approved", "proceed", "ok", "okay"}


def _wrap_langchain_tool(
    func: Callable[..., Dict[str, Any]],
    name: str,
    args_schema: type[BaseModel],
    description: str,
) -> StructuredTool:
    """Create a StructuredTool with the provided schema and metadata."""

    return StructuredTool.from_function(
        func=func,
        name=name,
        description=description,
        args_schema=args_schema,
    )


def create_tool_registry(
    *,
    adapter: OspsuiteAdapter,
    job_service: JobService,
) -> Dict[str, StructuredTool]:
    """Register MCP bridge tools as LangChain structured tools."""

    class LoadSimulationArgs(BaseModel):
        filePath: str = Field(
            ..., description="Absolute path to the simulation .pkml file."
        )
        simulationId: Optional[str] = Field(
            default=None,
            description="Identifier to assign to the loaded simulation.",
        )

        class Config:
            allow_population_by_field_name = True

    def _load_simulation(
        *, filePath: str, simulationId: Optional[str] = None
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"filePath": filePath}
        if simulationId is not None:
            payload["simulationId"] = simulationId
        request = LoadSimulationRequest.model_validate(payload)
        response = load_simulation(adapter, request)
        return response.model_dump(by_alias=True)

    class SetParameterArgs(BaseModel):
        simulationId: str = Field(
            ..., description="Simulation identifier to update."
        )
        parameterPath: str = Field(
            ..., description="Path to the parameter in the simulation."
        )
        value: float = Field(..., description="New parameter value.")
        unit: Optional[str] = Field(
            default=None, description="Unit of the provided value."
        )
        updateMode: Optional[str] = Field(
            default="absolute",
            description="Update mode (absolute or relative).",
        )
        comment: Optional[str] = Field(
            default=None, description="Optional comment for the change."
        )

    def _set_parameter_value(
        *,
        simulationId: str,
        parameterPath: str,
        value: float,
        unit: Optional[str] = None,
        updateMode: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        raw_payload: Dict[str, Any] = {
            "simulationId": simulationId,
            "parameterPath": parameterPath,
            "value": value,
        }
        if unit is not None:
            raw_payload["unit"] = unit
        if updateMode is not None:
            raw_payload["updateMode"] = updateMode
        if comment is not None:
            raw_payload["comment"] = comment

        payload = SetParameterValueRequest.model_validate(raw_payload)
        response = set_parameter_value(adapter, payload)
        return response.model_dump(by_alias=True)

    class ListParametersArgs(BaseModel):
        simulationId: str = Field(
            ..., description="Simulation identifier to query."
        )
        searchPattern: Optional[str] = Field(
            default="*", description="Glob pattern for filtering parameters."
        )

    def _list_parameters(
        *, simulationId: str, searchPattern: Optional[str] = "*"
    ) -> Dict[str, Any]:
        raw_payload: Dict[str, Any] = {"simulationId": simulationId}
        if searchPattern is not None:
            raw_payload["searchPattern"] = searchPattern
        payload = ListParametersRequest.model_validate(raw_payload)
        response = list_parameters(adapter, payload)
        return response.model_dump(by_alias=True)

    class GetParameterArgs(BaseModel):
        simulationId: str = Field(...)
        parameterPath: str = Field(...)

    def _get_parameter_value(
        *, simulationId: str, parameterPath: str
    ) -> Dict[str, Any]:
        payload = GetParameterValueRequest.model_validate(
            {"simulationId": simulationId, "parameterPath": parameterPath}
        )
        response = get_parameter_value(adapter, payload)
        return response.model_dump(by_alias=True)

    class RunSimulationArgs(BaseModel):
        simulationId: str = Field(...)
        runId: Optional[str] = Field(
            default=None, description="Optional run identifier."
        )
        timeoutSeconds: Optional[float] = Field(
            default=None,
            description="Timeout override for job execution (seconds).",
        )
        maxRetries: Optional[int] = Field(
            default=None,
            description="Override for maximum job retries.",
        )

    def _run_simulation(
        *,
        simulationId: str,
        runId: Optional[str] = None,
        timeoutSeconds: Optional[float] = None,
        maxRetries: Optional[int] = None,
    ) -> Dict[str, Any]:
        raw_payload: Dict[str, Any] = {"simulationId": simulationId}
        if runId is not None:
            raw_payload["runId"] = runId
        if timeoutSeconds is not None:
            raw_payload["timeoutSeconds"] = timeoutSeconds
        if maxRetries is not None:
            raw_payload["maxRetries"] = maxRetries

        payload = RunSimulationRequest.model_validate(raw_payload)
        response = run_simulation(adapter, job_service, payload)
        return response.model_dump(by_alias=True)

    class JobStatusArgs(BaseModel):
        jobId: str = Field(...)

    def _get_job_status(*, jobId: str) -> Dict[str, Any]:
        payload = GetJobStatusRequest.model_validate({"jobId": jobId})
        response = get_job_status(job_service, payload)
        return response.model_dump(by_alias=True)

    class PkParametersArgs(BaseModel):
        resultsId: str = Field(...)
        outputPath: Optional[str] = Field(
            default=None,
            description="Optional parameter path to filter PK metrics.",
        )

    def _calculate_pk_parameters(
        *, resultsId: str, outputPath: Optional[str] = None
    ) -> Dict[str, Any]:
        raw_payload: Dict[str, Any] = {"resultsId": resultsId}
        if outputPath is not None:
            raw_payload["outputPath"] = outputPath
        payload = CalculatePkParametersRequest.model_validate(raw_payload)
        response = calculate_pk_parameters(adapter, payload)
        return response.model_dump(by_alias=True)

    registry = {
        "load_simulation": _wrap_langchain_tool(
            _load_simulation,
            name="load_simulation",
            args_schema=LoadSimulationArgs,
            description="Load a PBPK simulation (.pkml) into the shared registry.",
        ),
        "set_parameter_value": _wrap_langchain_tool(
            _set_parameter_value,
            name="set_parameter_value",
            args_schema=SetParameterArgs,
            description="Update a parameter value for a loaded simulation.",
        ),
        "list_parameters": _wrap_langchain_tool(
            _list_parameters,
            name="list_parameters",
            args_schema=ListParametersArgs,
            description="List parameter paths in a loaded simulation (supports glob patterns).",
        ),
        "get_parameter_value": _wrap_langchain_tool(
            _get_parameter_value,
            name="get_parameter_value",
            args_schema=GetParameterArgs,
            description="Retrieve the value of a parameter for a simulation.",
        ),
        "run_simulation": _wrap_langchain_tool(
            _run_simulation,
            name="run_simulation",
            args_schema=RunSimulationArgs,
            description="Submit a simulation job asynchronously and return job metadata.",
        ),
        "get_job_status": _wrap_langchain_tool(
            _get_job_status,
            name="get_job_status",
            args_schema=JobStatusArgs,
            description="Fetch the status and metadata for a previously submitted job.",
        ),
        "calculate_pk_parameters": _wrap_langchain_tool(
            _calculate_pk_parameters,
            name="calculate_pk_parameters",
            args_schema=PkParametersArgs,
            description="Compute PK metrics (Cmax, Tmax, AUC) for simulation results.",
        ),
    }

    for tool in registry.values():
        convert_to_openai_function(tool)

    return registry


def route_after_selection(state: AgentState) -> str:
    """Route to confirmation when the plan selects a critical tool."""

    plan = state.get("plan") or {}
    next_step = plan.get("next_step") or {}
    tool_name = next_step.get("tool_name") or plan.get("tool_name")

    if tool_name in CRITICAL_TOOLS:
        return "Confirmation_Gate_Node"
    if tool_name:
        return "Tool_Execution_Node"
    return "Response_Synthesis_Node"


def route_after_confirmation(state: AgentState) -> str:
    """Route based on user's response after a confirmation interrupt."""

    feedback = (state.get("user_feedback") or "").strip().lower()
    if state.get("awaiting_confirmation"):
        return "Response_Synthesis_Node"
    if feedback in _APPROVAL_WORDS:
        return "Tool_Execution_Node"
    if feedback:
        return "Response_Synthesis_Node"
    return "Planner_Node"


def build_agent_graph(
    *,
    planner_node: Callable[[AgentState], AgentState],
    tool_selection_node: Callable[[AgentState], AgentState],
    confirmation_node: Callable[[AgentState], Dict[str, Any]],
    tool_execution_node: Callable[[AgentState], AgentState],
    response_synthesis_node: Callable[[AgentState], AgentState],
    checkpointer: Optional[Any] = None,
) -> Any:
    """Create a LangGraph StateGraph with standard routing for confirmations."""

    builder: StateGraph = StateGraph(AgentState)
    builder.add_node("Planner_Node", planner_node)
    builder.add_node("Tool_Selection_Node", tool_selection_node)
    builder.add_node("Confirmation_Gate_Node", confirmation_node)
    builder.add_node("Tool_Execution_Node", tool_execution_node)
    builder.add_node("Response_Synthesis_Node", response_synthesis_node)

    builder.set_entry_point("Planner_Node")
    builder.add_edge("Planner_Node", "Tool_Selection_Node")
    builder.add_conditional_edges("Tool_Selection_Node", route_after_selection)
    builder.add_edge("Tool_Execution_Node", "Response_Synthesis_Node")
    builder.add_edge("Response_Synthesis_Node", END)
    builder.add_conditional_edges("Confirmation_Gate_Node", route_after_confirmation)

    if checkpointer is not None:
        return builder.compile(checkpointer=checkpointer)

    node_names = {
        "Planner_Node",
        "Tool_Selection_Node",
        "Confirmation_Gate_Node",
        "Tool_Execution_Node",
        "Response_Synthesis_Node",
    }

    return builder.compile(checkpointer=_BackwardCompatibleMemorySaver(node_names))


class _BackwardCompatibleMemorySaver(MemorySaver):
    """MemorySaver variant that tolerates older LangGraph call signatures."""

    def __init__(self, node_names: Iterable[str] | None = None) -> None:
        super().__init__()
        names = set(node_names or ())
        names.add("__start__")
        names.add("__end__")
        names.add("__interrupt__")
        self._node_names = names

    def put(self, config, checkpoint, metadata, new_versions=None):  # type: ignore[override]
        if new_versions is None or not new_versions:
            channel_versions = checkpoint.get("channel_versions", {})
            new_versions = dict(channel_versions)
        versions_seen = checkpoint.get("versions_seen")
        if isinstance(versions_seen, dict):
            for name in self._node_names:
                versions_seen.setdefault(name, {})
            if not isinstance(versions_seen, defaultdict):
                checkpoint["versions_seen"] = defaultdict(dict, versions_seen)
        configurable = dict(config.get("configurable", {}))
        configurable.setdefault("checkpoint_ns", "")
        safe_config = {**config, "configurable": configurable}
        return super().put(safe_config, checkpoint, metadata, new_versions)

    def put_writes(self, config, writes, task_id):  # type: ignore[override]
        configurable = dict(config.get("configurable", {}))
        configurable.setdefault("checkpoint_ns", "")
        safe_config = {**config, "configurable": configurable}
        return super().put_writes(safe_config, writes, task_id)

    def get_tuple(self, config):  # type: ignore[override]
        saved = super().get_tuple(config)
        if saved is None:
            checkpoint = empty_checkpoint()
            seed = {name: {} for name in self._node_names}
            checkpoint["versions_seen"] = defaultdict(dict, seed)
            metadata = {"source": "bootstrap", "step": -1, "writes": {}}
            from langgraph.checkpoint.base import CheckpointTuple

            return CheckpointTuple(
                config=config,
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=None,
                pending_writes=[],
            )
        checkpoint = dict(saved.checkpoint)
        versions_seen = checkpoint.get("versions_seen")
        if isinstance(versions_seen, dict) and not isinstance(versions_seen, defaultdict):
            for name in self._node_names:
                versions_seen.setdefault(name, {})
            checkpoint["versions_seen"] = defaultdict(dict, versions_seen)
        from langgraph.checkpoint.base import CheckpointTuple

        return CheckpointTuple(
            config=saved.config,
            checkpoint=checkpoint,
            metadata=saved.metadata,
            parent_config=saved.parent_config,
            pending_writes=saved.pending_writes,
        )


def create_initial_agent_state() -> AgentState:
    """Return an initial agent state structure."""

    return AgentState(
        messages=[],
        simulation_context=None,
        pending_tool_call=None,
        user_feedback=None,
        plan=None,
        intermediate_steps=[],
        last_tool_result=None,
        last_tool_name=None,
        last_error=None,
        retry_counts={},
        confirmation_prompt=None,
        awaiting_confirmation=False,
    )


def create_agent_workflow(
    *,
    adapter: OspsuiteAdapter,
    job_service: JobService,
    checkpointer: MemorySaver | None = None,
    max_tool_retries: int = 1,
    retry_backoff_seconds: float = 0.25,
) -> tuple[Any, Dict[str, StructuredTool], AgentState]:
    """Create a confirm-before-execute agent workflow and tool registry."""

    tool_registry = create_tool_registry(adapter=adapter, job_service=job_service)
    retry_limit = max(0, int(max_tool_retries))

    def planner_node(state: AgentState) -> AgentState:
        state = dict(state)
        state.pop(INTERRUPT, None)
        messages = state.get("messages") or []
        if not messages:
            return state
        last_message = messages[-1]
        if not isinstance(last_message, HumanMessage):
            return state
        if state.get("awaiting_confirmation"):
            return state

        derived_plan = _derive_plan(
            last_message.content, state.get("simulation_context")
        )
        state["confirmation_prompt"] = None

        if not derived_plan:
            clarification = (
                "I want to help but need more details. Please specify the command, "
                "including any identifiers, parameter paths, values, and units."
            )
            updated_messages = list(messages)
            if not updated_messages or not isinstance(updated_messages[-1], AIMessage) or updated_messages[-1].content != clarification:
                updated_messages.append(AIMessage(content=clarification))
            state["messages"] = updated_messages
            state["plan"] = None
            return state

        state["plan"] = derived_plan
        state["user_feedback"] = None
        state["pending_tool_call"] = None
        state.setdefault("retry_counts", {})
        return state

    def tool_selection_node(state: AgentState) -> AgentState:
        state = dict(state)
        state.pop(INTERRUPT, None)
        plan = state.get("plan") or {}
        tool_name = plan.get("tool_name")
        if not tool_name:
            next_step = plan.get("next_step", {})
            tool_name = next_step.get("tool_name")
            if tool_name:
                plan = dict(plan)
                plan.setdefault("args", next_step.get("args", {}))
        if not tool_name:
            return state
        call_payload = {
            "tool": tool_name,
            "args": dict(plan.get("args", {})),
            "description": plan.get("description"),
            "created_from": plan.get("created_from"),
        }
        state["pending_tool_call"] = call_payload
        state["awaiting_confirmation"] = False
        state["confirmation_prompt"] = None
        return state

    def confirmation_node(state: AgentState) -> Dict[str, Any]:
        pending = state.get("pending_tool_call") or {}
        tool_name = pending.get("tool")
        if not tool_name or tool_name not in CRITICAL_TOOLS:
            return {"awaiting_confirmation": False, "confirmation_prompt": None}

        feedback = (state.get("user_feedback") or "").strip()
        if feedback:
            return {
                "awaiting_confirmation": False,
                "confirmation_prompt": None,
                "user_feedback": feedback,
            }

        prompt = format_confirmation_prompt(tool_name, pending.get("args", {}))
        return {
            "awaiting_confirmation": True,
            "confirmation_prompt": prompt,
        }

    def tool_execution_node(state: AgentState) -> AgentState:
        pending = state.get("pending_tool_call") or {}
        tool_name = pending.get("tool")
        if not tool_name:
            return state
        args = pending.get("args", {})
        feedback = (state.get("user_feedback") or "").strip().lower()
        state = dict(state)
        state.pop(INTERRUPT, None)
        retry_counts = dict(state.get("retry_counts") or {})

        if tool_name in CRITICAL_TOOLS and feedback not in _APPROVAL_WORDS:
            state["last_tool_name"] = tool_name
            state["last_tool_result"] = {"status": "cancelled"}
            state["last_error"] = "Action cancelled by user."
            history = list(state.get("intermediate_steps") or [])
            history.append(
                {
                    "event": "cancelled",
                    "tool": tool_name,
                    "args": args,
                    "feedback": feedback,
                }
            )
            state["intermediate_steps"] = history
            state["plan"] = None
            state["pending_tool_call"] = None
            state["awaiting_confirmation"] = False
            state["confirmation_prompt"] = None
            state["user_feedback"] = None
            return state

        tool = tool_registry.get(tool_name)
        if tool is None:
            error_message = f"Unknown tool '{tool_name}'"
            state["last_tool_name"] = tool_name
            state["last_error"] = error_message
            state["last_tool_result"] = None
            history = list(state.get("intermediate_steps") or [])
            history.append(
                {
                    "event": "error",
                    "tool": tool_name,
                    "attempt": retry_counts.get(tool_name, 0) + 1,
                    "message": error_message,
                }
            )
            state["intermediate_steps"] = history
            state["plan"] = None
            state["pending_tool_call"] = None
            state["awaiting_confirmation"] = False
            state["user_feedback"] = None
            return state

        attempt_number = retry_counts.get(tool_name, 0) + 1
        try:
            result = tool.invoke(dict(args))
        except Exception as exc:  # pragma: no cover - error path evaluated in tests
            retry_counts[tool_name] = attempt_number
            state["retry_counts"] = retry_counts
            state["last_tool_name"] = tool_name
            state["last_error"] = str(exc)
            state["last_tool_result"] = None
            history = list(state.get("intermediate_steps") or [])
            history.append(
                {
                    "event": "error",
                    "tool": tool_name,
                    "attempt": attempt_number,
                    "message": str(exc),
                }
            )
            state["intermediate_steps"] = history
            if attempt_number <= retry_limit:
                state.setdefault("plan", {"tool_name": tool_name, "args": args})
                time.sleep(max(0.0, retry_backoff_seconds))
            else:
                state["plan"] = None
                state["pending_tool_call"] = None
                state["awaiting_confirmation"] = False
            return state

        retry_counts[tool_name] = 0
        state["retry_counts"] = retry_counts
        result_payload = result if isinstance(result, dict) else {"value": result}
        state["last_tool_result"] = result_payload
        state["last_tool_name"] = tool_name
        state["last_error"] = None

        state["user_feedback"] = None
        state["awaiting_confirmation"] = False
        state["confirmation_prompt"] = None

        history = list(state.get("intermediate_steps") or [])
        history.append(
            {
                "event": "completed",
                "tool": tool_name,
                "result": result_payload,
            }
        )
        state["intermediate_steps"] = history

        if tool_name == "load_simulation":
            simulation_id = result_payload.get("simulationId")
            state["simulation_context"] = {
                "simulationId": simulation_id,
                "filePath": args.get("filePath"),
            }
        elif tool_name == "run_simulation":
            context = dict(state.get("simulation_context") or {})
            if args.get("simulationId"):
                context.setdefault("simulationId", args["simulationId"])
            if job_id := result_payload.get("jobId"):
                context["lastJobId"] = job_id
            state["simulation_context"] = context

        state["plan"] = None
        state["pending_tool_call"] = None
        return state

    def response_synthesis_node(state: AgentState) -> AgentState:
        state = dict(state)
        messages = list(state.get("messages") or [])
        if state.get("awaiting_confirmation"):
            prompt = state.get("confirmation_prompt") or "Please confirm before I proceed."
            if not messages or messages[-1].content != prompt:
                messages.append(AIMessage(content=prompt))
            state["messages"] = messages
            pending = state.get("pending_tool_call") or {}
            state[INTERRUPT] = {
                "type": "confirmation_required",
                "tool": pending.get("tool"),
                "args": pending.get("args", {}),
                "prompt": prompt,
            }
            return state
        pending = state.get("pending_tool_call") or {}
        feedback = (state.get("user_feedback") or "").strip().lower()
        if pending and feedback and feedback not in _APPROVAL_WORDS:
            tool_name = pending.get("tool", "action")
            content = format_error_response(tool_name, "Action cancelled by user.")
            if not messages or messages[-1].content != content:
                messages.append(AIMessage(content=content))
            state["messages"] = messages
            state["pending_tool_call"] = None
            state["plan"] = None
            state["user_feedback"] = None
            state["last_tool_name"] = tool_name
            state["last_error"] = "Action cancelled by user."
            state.pop(INTERRUPT, None)
            return state
        tool_name = state.get("last_tool_name")
        if tool_name:
            if state.get("last_error"):
                content = format_error_response(tool_name, state["last_error"] or "")
            else:
                content = format_success_response(
                    tool_name, state.get("last_tool_result") or {}
                )
            messages.append(AIMessage(content=content))
            state["messages"] = messages
        state.pop(INTERRUPT, None)
        return state

    graph = build_agent_graph(
        planner_node=planner_node,
        tool_selection_node=tool_selection_node,
        confirmation_node=confirmation_node,
        tool_execution_node=tool_execution_node,
        response_synthesis_node=response_synthesis_node,
        checkpointer=checkpointer or _BackwardCompatibleMemorySaver(
            {
                "Planner_Node",
                "Tool_Selection_Node",
                "Confirmation_Gate_Node",
                "Tool_Execution_Node",
                "Response_Synthesis_Node",
            }
        ),
    )

    return graph, tool_registry, create_initial_agent_state()

def _derive_plan(
    message: str,
    simulation_context: Optional[Mapping[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    text = message.strip()
    if not text:
        return None

    lower = text.lower()
    sim_id = None
    if simulation_context:
        sim_id = simulation_context.get("simulationId")

    load_match = re.search(r"load\s+([^\s]+\.pkml)(?:\s+as\s+([\w\-]+))?", text, re.I)
    if load_match:
        file_path = load_match.group(1)
        simulation_id = load_match.group(2) or (sim_id or "auto-sim")
        return {
            "tool_name": "load_simulation",
            "args": {"filePath": file_path, "simulationId": simulation_id},
            "description": "Load simulation file",
            "created_from": "heuristic",
        }

    set_match = re.search(
        r"set\s+([\w.|]+)\s+(?:to|=)\s+([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z/%]*)",
        text,
        re.I,
    )
    if set_match:
        parameter_path = set_match.group(1)
        value = float(set_match.group(2))
        unit = set_match.group(3) or None
        target_sim = (
            re.search(r"for\s+([\w\-]+)", text, re.I).group(1)
            if re.search(r"for\s+([\w\-]+)", text, re.I)
            else sim_id
        )
        if not target_sim:
            return None
        return {
            "tool_name": "set_parameter_value",
            "args": {
                "simulationId": target_sim,
                "parameterPath": parameter_path,
                "value": value,
                "unit": unit,
            },
            "description": "Set simulation parameter",
            "created_from": "heuristic",
        }

    run_match = re.search(r"run\s+(?:simulation\s+)?([\w\-]+)?", text, re.I)
    if run_match:
        target_sim = run_match.group(1) or sim_id
        if not target_sim:
            return None
        return {
            "tool_name": "run_simulation",
            "args": {"simulationId": target_sim},
            "description": "Run loaded simulation",
            "created_from": "heuristic",
        }

    status_match = re.search(r"status\s+(?:of\s+)?([\w\-]+)", text, re.I)
    if status_match:
        job_id = status_match.group(1)
        return {
            "tool_name": "get_job_status",
            "args": {"jobId": job_id},
            "description": "Check job status",
            "created_from": "heuristic",
        }

    return None
