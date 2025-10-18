
Architectural Blueprint for a Confirm-Before-Execute Agentic Workflow


Introduction: From Tools to a Trustworthy Agent


Purpose and Scope

This document presents a comprehensive architectural blueprint for a "confirm-before-execute" agent designed to interact with the Physiologically Based Pharmacokinetic (PBPK) Model Context Protocol (MCP) Bridge service. The primary objective is to define a robust, stateful agent using the LangGraph framework that ensures critical actions are explicitly approved by a human user before execution. This design addresses the core requirements of safety, control, and user trust, providing a detailed and actionable specification for the development outlined in Task 13.1. The architecture detailed herein will serve as the foundational design for an intelligent agent capable of translating high-level scientific intent into a series of verified, precise tool calls.

The Foundational Layer: The PBPK_MCP Bridge Service

The successful development of any intelligent agent is predicated on the quality and reliability of the tools it consumes. The existing PBPK_MCP bridge service represents a mature, well-architected foundational layer, making it an ideal platform for agentic control.1 The service exposes its capabilities via a stable, clearly defined REST API, the contract for which is meticulously documented in an OpenAPI specification (openapi.json). This contract-first approach, combined with a comprehensive suite of design artifacts including a detailed error taxonomy and sequence diagrams, provides the necessary stability and predictability for building a reliable agent. The service's robust implementation of asynchronous job handling, parameter management, and simulation lifecycle control forms the solid ground upon which a more sophisticated control layer can be constructed.

The Strategic Imperative for Confirmation

In scientific and regulated domains, the "confirm-before-execute" pattern is not merely a desirable feature but a critical architectural requirement. The strategic vision for the MCP project is to transform PBPK modeling into a conversational, AI-driven workflow.1 This transformation, however, introduces the risk of ambiguity inherent in natural language, where a user's intent might be misinterpreted by the agent. An unverified action could lead to scientifically invalid model configurations, the waste of significant computational resources on incorrect simulations, and a fundamental erosion of user trust in the system. Therefore, architecting an explicit confirmation loop is paramount. It serves multiple strategic purposes: it ensures scientific reproducibility by creating a clear decision trail; it enhances safety by preventing erroneous or unintended state mutations; it promotes efficient resource management by avoiding costly, misconfigured computations; and, most importantly, it builds the user's confidence in the agent's actions, fostering a collaborative human-AI partnership.

Section 1: Architecting the Agentic Control Layer with LangGraph

To orchestrate the complex, stateful interactions required for PBPK modeling, the agent will be implemented as a state machine using LangGraph. This framework provides the low-level control necessary to build custom, cyclical workflows with explicit state management and checkpoints for human intervention.2 The agent's logic will be defined as a graph where nodes represent discrete processing functions and edges control the flow between them, ensuring a transparent and controllable execution model.

The Central AgentState

The single source of truth for the agent's entire workflow is the graph's state. A central AgentState object will track the history of the interaction, the current context, and any pending actions. Adhering to the rigorous data modeling practices established by the underlying PBPK_MCP bridge service, which extensively uses Pydantic for type-safe data contracts, the AgentState will be defined as a TypedDict or Pydantic model to ensure clarity and type safety throughout the graph.1
The schema for the AgentState will include the following fields:
messages: List: This field will maintain the complete, ordered history of the conversation between the user and the agent. It is essential for providing the LLM with the necessary context to understand follow-up questions and multi-turn interactions. The reducer function for this field will be operator.add, ensuring that new messages are appended to the list, preserving the chronological record.
simulation_context: Optional[dict]: This dictionary will store critical metadata about the currently loaded simulation. After a successful call to the load_simulation tool, this field will be populated with the simulationId, the model's file path, and potentially other key metadata returned by the bridge. This provides the agent with a persistent understanding of its current working context.
pending_tool_call: Optional[dict]: This structured object acts as a temporary holding area for a critical action that is awaiting human confirmation. It will contain the name of the tool to be executed (e.g., set_parameter_value) and a dictionary of its arguments. This ensures that the exact, fully-formed action is preserved while the graph is paused.
user_feedback: Optional[str]: This field captures the user's explicit response from a confirmation prompt (e.g., 'approve', 'reject', 'yes', 'no'). This value is used by conditional edges to route the graph's execution flow after a human-in-the-loop interruption.

Core Functional Nodes

The agent's workflow is composed of several key nodes, each implemented as a distinct Python function that receives the current AgentState as input and returns a dictionary of updates. This modular design, a core principle of LangGraph, allows for a clean separation of concerns.3
Planner_Node: This node serves as the agent's primary reasoning engine. It takes the latest user message and the full conversation history from AgentState.messages and invokes an LLM. The LLM's task is to analyze the user's intent and formulate a high-level, multi-step plan to achieve the stated goal. This plan might involve a sequence of tool calls and logical operations.
Tool_Selection_Node: This node inspects the plan generated by the Planner_Node and the current AgentState. It determines if the next logical step in the plan requires the execution of a tool. If so, it identifies the specific tool from the PBPK_MCP toolset and constructs the necessary arguments. A crucial function of this node is to consult the tool taxonomy (defined in Section 2) to determine if the selected tool is classified as "critical" and requires confirmation.
Tool_Execution_Node: This node is responsible for the actual interaction with the external service. It takes a validated and (if necessary) approved tool call request, formats it into an HTTP request, and calls the appropriate endpoint on the PBPK_MCP bridge. Upon receiving a response, it parses the result—whether success or a structured error—and appends a summary of the outcome to the messages list in the AgentState, providing a record of the action taken.
Confirmation_Gate_Node: This is the dedicated human-in-the-loop (HITL) node. It is invoked exclusively when the Tool_Selection_Node identifies a critical tool for execution. The sole purpose of this node is to call LangGraph's built-in interrupt() function. This action pauses the entire graph's execution, persisting its state via a checkpointer, and awaits external input from the user. This mechanism is the core of the "confirm-before-execute" pattern and is a key capability of LangGraph.4
Response_Synthesis_Node: After a plan has been fully executed, a user query has been answered, or an unrecoverable error has occurred, this node is called. It synthesizes the final outcome, including the results of any tool calls, into a coherent, natural language response for the user, effectively closing the interaction loop.
The architecture's safety is not merely dependent on instructing the LLM to behave cautiously; it is programmatically enforced by the graph's structure. While prompt engineering is essential for guiding the agent, an LLM in the Planner_Node could potentially ignore or misinterpret instructions in its system prompt. The true safety mechanism is the non-negotiable, programmatic guardrail provided by the graph's topology.
When a user requests a critical action, the workflow proceeds as follows:
The Planner_Node correctly identifies the need to call a critical tool, such as set_parameter_value.
The Tool_Selection_Node receives this plan. It consults the tool taxonomy and confirms that set_parameter_value is classified as CRITICAL_STATE_MUTATION.
Based on this classification, the conditional edge logic following this node forces the graph to transition to the Confirmation_Gate_Node. It is architecturally impossible for the graph to proceed directly to execution.
The Confirmation_Gate_Node invokes interrupt(), pausing the graph. The Tool_Execution_Node remains dormant and cannot be called.
Only after the user provides an explicit 'approve' response and resumes the graph can a subsequent conditional edge validate this feedback and route the flow to the Tool_Execution_Node.
This architectural pattern elevates the system's safety from a "soft" constraint (a set of instructions in a prompt) to a "hard" constraint (the immutable logic of the graph's wiring). This distinction is fundamental to building trustworthy and reliable agents for deployment in high-stakes scientific environments.

Section 2: A Taxonomy of Critical Actions in the MCP Toolset

To implement the safety-critical routing logic described above, the agent requires a definitive classification of every available tool. This taxonomy provides the ground truth for the Tool_Selection_Node and its subsequent conditional edge, enabling the agent to programmatically distinguish between benign read-only operations and significant, state-altering actions. This classification is derived from a systematic analysis of the PBPK_MCP bridge's OpenAPI contract.1

Table 1: Classification of MCP Bridge API Tools

The following table categorizes each tool exposed by the PBPK_MCP bridge API, providing a clear rationale for whether it requires user confirmation before execution. This table serves as the canonical reference for the agent's safety logic.
Tool (Endpoint)
Classification
Rationale for Confirmation
POST /load_simulation
CRITICAL (CONTEXT_MUTATION)
This action fundamentally changes the agent's active working context by loading a new simulation model into the server's session registry. Any unsaved changes to a previously loaded model could be lost. Confirmation is required to prevent accidental context switching and potential data loss.
POST /set_parameter_value
CRITICAL (STATE_MUTATION)
This is the most sensitive operation, as it directly modifies the scientific parameters of the loaded simulation. An incorrect parameter change can invalidate the model's results. Explicit user approval is mandatory to ensure scientific validity, rigor, and traceability.
POST /run_simulation
CRITICAL (RESOURCE_COMMITMENT)
This action initiates an asynchronous job that can be computationally expensive and long-running. Confirmation is necessary to prevent the accidental or premature execution of misconfigured simulations, thereby saving valuable time and computational resources.
POST /list_parameters
Read-Only
Retrieves a list of parameters from the currently loaded simulation without altering its state. No confirmation is required.
POST /get_parameter_value
Read-Only
Retrieves the value of a single parameter without altering the simulation state. No confirmation is required.
POST /get_job_status
Read-Only
Retrieves the status of a previously submitted asynchronous job without altering any state. No confirmation is required.
POST /get_simulation_results
Read-Only
Retrieves the stored results of a completed simulation job. This is a read operation and does not require confirmation.
POST /calculate_pk_parameters
Read-Only
Performs a calculation on an existing result set and returns the output to the user. It does not persist any changes to the model or the results. No confirmation is required.

The robust design of the PBPK_MCP bridge service, particularly its mature error handling, directly enables the development of a more intelligent and resilient agent. The service's error-taxonomy.md document defines a stable and predictable contract for communicating failures, which the agent can leverage to perform sophisticated error analysis and re-planning.1
For instance, consider a scenario where the agent attempts to call get_parameter_value but provides a simulationId that is not currently loaded in the server's session registry.
The PBPK_MCP bridge will respond with a 404 Not Found HTTP status and a structured JSON payload: {"error": {"code": "NotFound", "message": "Simulation 'X' not found"}}.
The agent's Tool_Execution_Node can be designed to catch this specific, structured error, rather than treating it as a generic failure.
The node can then update the AgentState with the precise error information and pass control back to the Planner_Node.
The Planner_Node can then be invoked with an augmented prompt, such as: "Your previous action failed with a 'NotFound' error for the simulation identified as 'X'. This indicates the user has not loaded this simulation yet. Formulate a helpful response to the user, informing them of the problem and guiding them to use the load_simulation tool first."
This creates a powerful, self-correcting feedback loop. The explicit and well-designed error contract of the underlying service allows the agent to move beyond simple execution to perform intelligent problem diagnosis, enhancing its utility and creating a more seamless user experience.

Section 3: Implementing the "Confirm-Before-Execute" Workflow

The "Confirm-Before-Execute" pattern is realized through the specific wiring of the LangGraph state machine, which orchestrates the flow of control and data through the confirmation loop. The following worked example demonstrates this process in detail, tracing a user's request from initial intent to confirmed execution.

The Confirmation Loop in Action: A Worked Example

Consider a user issuing the following request: "Increase the liver weight by 10% and run the simulation."
Planning: The request is received by the agent. The Planner_Node is invoked, which calls the LLM to decompose the natural language request into a concrete, multi-step plan. The LLM determines that it first needs the current liver weight to calculate the 10% increase. The initial plan is:.
Initial Read Operation: The agent proceeds to the Tool_Selection_Node. It identifies get_parameter_value as the first step. Consulting the tool taxonomy, it classifies this as a "Read-Only" operation. The conditional edge routes the graph directly to the Tool_Execution_Node, which successfully retrieves the current liver weight from the PBPK_MCP bridge. The agent updates its state and re-evaluates the plan.
First Critical Action Identified: The agent returns to the Tool_Selection_Node. The next step in the plan is to call set_parameter_value with the newly calculated weight. The node consults the taxonomy and identifies this tool as CRITICAL (STATE_MUTATION).
Routing to Confirmation: Because the tool is critical, the conditional edge function routes the graph's execution to the Confirmation_Gate_Node.
Pausing with interrupt(): The Confirmation_Gate_Node populates the AgentState.pending_tool_call field with the details of the set_parameter_value action. It then calls LangGraph's interrupt() function. For this to work, the graph must have been compiled with a checkpointer, such as InMemorySaver for development, which persists the graph's state.6 The graph is now paused, awaiting human input.
User Approval: The application layer presents the pending action to the user in a clear format. The user reviews the proposed change and responds with "approve". The application resumes the graph by invoking it with Command(resume="approve").5
Conditional Routing Post-Confirmation: A conditional edge function, route_after_confirmation, is now executed. It inspects the AgentState.user_feedback field. Since the value is "approve", it returns the name of the Tool_Execution_Node.
Execution: The graph transitions to the Tool_Execution_Node, which retrieves the action details from AgentState.pending_tool_call and makes the API call to the PBPK_MCP bridge, successfully updating the parameter.
Second Critical Action: The agent's plan is not yet complete. It loops back to the Tool_Selection_Node, which now identifies run_simulation as the next step. This is classified as CRITICAL (RESOURCE_COMMITMENT). The entire confirmation process, from step 4 through 8, is repeated for this second action, ensuring that both the state mutation and the resource commitment are explicitly approved by the user.

Workflow Visualization

The following sequence diagram provides a visual representation of this multi-step, multi-confirmation workflow, clarifying the interactions between the user, the different nodes of the agent graph, and the external API. This visualization follows the best practices for documenting complex interactions, as seen in the PBPK_MCP project's own documentation.1

Code snippet


sequenceDiagram
    participant User
    participant AgentGraph
    participant Planner_Node
    participant Tool_Selection_Node
    participant Confirmation_Gate_Node
    participant Tool_Execution_Node
    participant MCP_Bridge_API

    User->>AgentGraph: "Increase liver weight by 10% and run."
    AgentGraph->>Planner_Node: Formulate plan
    Planner_Node-->>AgentGraph: Plan: [get_value, set_value, run_sim]
    AgentGraph->>Tool_Selection_Node: Next step: get_value (Read-Only)
    Tool_Selection_Node-->>AgentGraph: Route to Tool_Execution_Node
    AgentGraph->>Tool_Execution_Node: Call get_parameter_value
    Tool_Execution_Node->>MCP_Bridge_API: POST /get_parameter_value
    MCP_Bridge_API-->>Tool_Execution_Node: Returns current weight
    Tool_Execution_Node-->>AgentGraph: Update state with weight
    AgentGraph->>Planner_Node: Recalculate plan with new weight
    Planner_Node-->>AgentGraph: Plan: [set_value, run_sim]
    AgentGraph->>Tool_Selection_Node: Next step: set_value (Critical)
    Tool_Selection_Node-->>AgentGraph: Route to Confirmation_Gate_Node
    AgentGraph->>Confirmation_Gate_Node: interrupt()
    Note right of Confirmation_Gate_Node: Graph Pauses
    Confirmation_Gate_Node-->>User: "Confirm: set_parameter_value(...)"
    User->>AgentGraph: "approve"
    Note left of AgentGraph: Graph Resumes
    AgentGraph->>Tool_Selection_Node: Route after confirmation
    Tool_Selection_Node-->>AgentGraph: Route to Tool_Execution_Node
    AgentGraph->>Tool_Execution_Node: Call set_parameter_value
    Tool_Execution_Node->>MCP_Bridge_API: POST /set_parameter_value
    MCP_Bridge_API-->>Tool_Execution_Node: Success
    Tool_Execution_Node-->>AgentGraph: Update state
    AgentGraph->>Tool_Selection_Node: Next step: run_simulation (Critical)
    Tool_Selection_Node-->>AgentGraph: Route to Confirmation_Gate_Node
    AgentGraph->>Confirmation_Gate_Node: interrupt()
    Note right of Confirmation_Gate_Node: Graph Pauses
    Confirmation_Gate_Node-->>User: "Confirm: run_simulation(...)"
    User->>AgentGraph: "approve"
    Note left of AgentGraph: Graph Resumes
    AgentGraph->>Tool_Selection_Node: Route after confirmation
    Tool_Selection_Node-->>AgentGraph: Route to Tool_Execution_Node
    AgentGraph->>Tool_Execution_Node: Call run_simulation
    Tool_Execution_Node->>MCP_Bridge_API: POST /run_simulation
    MCP_Bridge_API-->>Tool_Execution_Node: Job ID returned
    Tool_Execution_Node-->>AgentGraph: Update state



Section 4: Prompt Engineering for Clarity and Control

While the graph's structure provides the hard safety guarantees, prompt engineering remains crucial for guiding the agent's behavior, ensuring it communicates clearly with the user and correctly formulates plans that align with the confirmation workflow. The prompts define the agent's persona, its understanding of its capabilities, and its adherence to the safety protocol.

The Agent's System Prompt

The system prompt is the foundational instruction set provided to the LLM at the beginning of every interaction. It establishes the agent's core identity and operational constraints.
Persona: "You are a helpful and meticulous AI assistant for pharmacokinetic (PK) modeling. Your purpose is to help scientists interact with the Open Systems Pharmacology (ospsuite) via a conversational interface. You are precise, careful, and always prioritize safety and clarity."
Capabilities: "You can load simulation models, inspect and modify their parameters, run simulations, and analyze the results by calling a set of available tools. You must formulate a step-by-step plan to address the user's request and execute it one step at a time."
Core Directive (The Confirmation Protocol):"CRITICAL SAFETY PROTOCOL: Before you formulate a plan that involves executing an action that modifies the simulation state (set_parameter_value) or consumes significant computational resources (run_simulation, load_simulation), you MUST first state your intended action clearly and ask the user for explicit approval. Do not proceed with these actions until you receive a positive confirmation (e.g., 'yes', 'approve', 'proceed'). If the user's request is ambiguous (e.g., 'make it heavier' or 'increase the dose'), you MUST ask clarifying questions to obtain specific, numerical values and units before formulating a tool call. Always confirm your understanding of the request before proceeding."

Dynamic Prompts for the Confirmation Gate

When the graph is paused at the Confirmation_Gate_Node, the application layer is responsible for presenting the pending action to the user. This is not an LLM-generated prompt but a structured, template-based message formatted from the pending_tool_call data in the AgentState. This ensures the user is shown a clear, unambiguous, and consistent confirmation request every time.
Template for set_parameter_value:"I am about to execute the following action:\nTool: set_parameter_value\nSimulation ID: {simulation_id}\nParameter Path: {parameter_path}\nNew Value: {value} {unit}\n\nDo you approve this change?"
Template for run_simulation:"I am about to start a new simulation run for Simulation ID: {simulation_id}.\n\nDo you want to proceed?"
Template for load_simulation:"I am about to load a new simulation from the file {file_path}. This will replace the current simulation context. Any unsaved changes will be lost.\n\nDo you want to proceed?"
The structured and explicit nature of this confirmation dialogue provides a significant secondary benefit: the conversation history itself becomes a verifiable audit trail. The PBPK_MCP project's threat model identifies the need for an immutable audit trail to mitigate repudiation threats, a requirement typically addressed by a backend logging system.1 The agent's workflow naturally complements this formal requirement.
A typical interaction in the conversation transcript would appear as follows:
User: "Increase the liver weight to 2.5 kg."
Agent: "I am about to execute the following action: Tool: set_parameter_value, Simulation ID: sim-123, Parameter Path: Organ.Liver.Weight, New Value: 2.5 kg. Do you approve this change?"
User: "Yes."
Agent: "Action approved. The parameter has been updated successfully."
This conversational snippet serves as a complete, self-contained, and human-readable record of the user's request, the precise action the agent intended to take, and the user's explicit authorization for that action. This "conversation as a lab notebook" paradigm provides a powerful, user-centric layer of traceability that directly supports the goals of scientific reproducibility and regulatory compliance in a naturally emergent and intuitive way.

Section 5: Architectural Blueprint and Implementation Guidance

This section synthesizes the preceding design principles into a concrete implementation plan, providing illustrative code snippets and a step-by-step guide for constructing the LangGraph agent. These artifacts serve as a direct starting point for the development of Task 13.1.

Code-Level Architecture (Illustrative Snippets)

The following Python code snippets illustrate the core components of the LangGraph implementation.
AgentState Definition: A TypedDict is used to define the schema for the graph's state, ensuring type hints and clarity.
Python
from typing import List, Optional, TypedDict
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    """
    Represents the state of our agent.

    Attributes:
        messages: The history of messages in the conversation.
        simulation_context: Metadata about the currently loaded simulation.
        pending_tool_call: A tool call awaiting human confirmation.
        user_feedback: The user's response to a confirmation request.
    """
    messages: Annotated, operator.add]
    simulation_context: Optional[dict]
    pending_tool_call: Optional[dict]
    user_feedback: Optional[str]


Confirmation_Gate_Node Implementation: This node's sole responsibility is to invoke the interrupt function, pausing the graph.
Python
from langgraph.types import interrupt

def confirmation_gate_node(state: AgentState) -> dict:
    """
    Pauses the graph to await human confirmation for a critical tool call.
    The pending_tool_call must be populated in the state before entering this node.
    """
    # The interrupt function pauses execution and surfaces the pending tool call
    # to the application layer for presentation to the user.
    interrupt(state["pending_tool_call"])

    # This node does not modify the state itself; the user's feedback
    # will be handled by the subsequent conditional edge.
    return {}


route_after_selection Conditional Edge: This function directs the flow based on whether the next planned tool is critical.
Python
CRITICAL_TOOLS = {"set_parameter_value", "run_simulation", "load_simulation"}

def route_after_selection(state: AgentState) -> str:
    """
    Routes to the confirmation gate if the next tool is critical,
    otherwise routes directly to execution.
    """
    # This is a simplified representation; in a full implementation,
    # this function would parse the plan from the LLM's output.
    next_tool_name = state.get("plan", {}).get("next_step", {}).get("tool_name")

    if next_tool_name in CRITICAL_TOOLS:
        return "Confirmation_Gate_Node"
    elif next_tool_name:
        return "Tool_Execution_Node"
    else:
        return "Response_Synthesis_Node"


route_after_confirmation Conditional Edge: This function processes the user's feedback after an interrupt and routes accordingly.
Python
def route_after_confirmation(state: AgentState) -> str:
    """
    Processes user feedback after a confirmation pause. Routes to execution
    on approval or back to the planner on rejection.
    """
    user_feedback = state.get("user_feedback", "").strip().lower()

    if user_feedback in ["yes", "approve", "proceed", "y"]:
        # If approved, proceed to execute the tool.
        return "Tool_Execution_Node"
    else:
        # If rejected, clear the pending call and return to the planner
        # to formulate a new response or plan.
        return "Planner_Node"



Key Implementation Steps

The development process for this agent can be broken down into the following discrete steps:
Graph Initialization: Instantiate the StateGraph with the defined AgentState schema: builder = StateGraph(AgentState).
Node Registration: Register each of the five core functional nodes (Planner_Node, Tool_Selection_Node, Tool_Execution_Node, Confirmation_Gate_Node, Response_Synthesis_Node) with the graph builder using builder.add_node("node_name", node_function).
Edge Wiring: Define the control flow by connecting the nodes:
Set the graph's entry point to the Planner_Node: builder.set_entry_point("Planner_Node").
Add a conditional edge from the Tool_Selection_Node to either the Confirmation_Gate_Node or the Tool_Execution_Node, using the route_after_selection function.
Add a conditional edge from the Confirmation_Gate_Node to either the Tool_Execution_Node or back to the Planner_Node, using the route_after_confirmation function.
Wire the remaining nodes using normal, non-conditional edges (e.g., builder.add_edge("Planner_Node", "Tool_Selection_Node")).
Checkpointer Configuration: Compile the graph with a configured checkpointer. This step is mandatory for the interrupt() functionality to work, as it relies on the persistence layer to save and resume the graph's state. For initial development, InMemorySaver is sufficient: graph = builder.compile(checkpointer=InMemorySaver()).6
Application Loop Integration: The main application logic that interacts with the compiled graph must be designed to handle the interrupt mechanism. This involves:
Invoking the graph with a persistent thread_id.
Checking the output of each invocation for the special __interrupt__ key.
When an interrupt is detected, presenting the confirmation prompt (using the templates from Section 4) to the user.
Capturing the user's response and resuming the graph by invoking it again with the appropriate Command(resume=...) payload.
Works cited
_MCP_PBPK_1.txt
Learn LangGraph basics - Overview, accessed October 15, 2025, https://langchain-ai.github.io/langgraph/concepts/why-langgraph/
Overview - GitHub Pages, accessed October 15, 2025, https://langchain-ai.github.io/langgraph/concepts/low_level/
LangGraph Uncovered:AI Agent and Human-in-the-Loop ..., accessed October 15, 2025, https://dev.to/sreeni5018/langgraph-uncoveredai-agent-and-human-in-the-loop-enhancing-decision-making-with-intelligent-3dbc
Human-in-the-loop - Overview, accessed October 15, 2025, https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/
LangGraph 201: Adding Human Oversight to Your Deep Research ..., accessed October 15, 2025, https://towardsdatascience.com/langgraph-201-adding-human-oversight-to-your-deep-research-agent/
