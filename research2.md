
Architectural Evaluation and Strategic Roadmap for the MCP Bridge Server


Introduction


Purpose and Scope

This report presents a dual-objective analysis of the Physiologically Based Pharmacokinetic (PBPK) Model Context Protocol (MCP) Bridge project. The first objective is to conduct a comprehensive architectural evaluation of the PBPK_MCP project in its current proof-of-concept stage, assessing its design, technology stack, and overall readiness for future development. The second objective is to deliver a deeply researched, forward-looking strategic roadmap that provides a technical blueprint for evolving the system into a scalable, secure, and intelligent platform. This document serves as both a validation of the significant work completed to date and a guide for realizing the project's ambitious long-term vision.1

Strategic Context

The foundational mission of this project, as articulated in the "Architectural Feasibility and Strategic Value of a Model Context Protocol (MCP) for the Open Systems Pharmacology (OSP) Suite" document, is to create a standardized, AI-native interface for PBPK modeling. The core strategy is to build an MCP server that acts as a bridge between the OSP Suite—leveraging the ospsuite R package as the critical integration point—and the rapidly expanding ecosystem of agentic Artificial Intelligence (AI). This initiative is not merely a technical integration but a strategic endeavor to transform PBPK modeling from a manual, Graphical User Interface (GUI)-driven process into a dynamic, conversational, and increasingly autonomous workflow. By adopting the MCP standard, this project aims to position PBPK modeling as a core, accessible capability for the next generation of AI-driven scientific discovery, ensuring its continued relevance and unlocking profound efficiency gains.2

Methodology

The evaluation process detailed in this report is multifaceted. It begins with a static analysis of the provided codebase and project artifacts, including source code, configuration files, documentation, and containerization specifications.1 This is followed by a thorough review of the project's foundational strategic documents to understand its guiding principles and long-term objectives.2 Finally, these project-specific findings are contextualized and expanded upon through an extensive synthesis of external research covering relevant architectural patterns, emerging technologies, and industry best practices in agentic AI, distributed systems, high-performance computing (HPC), and security for regulated environments.

Part I: Architectural Evaluation and Project Assessment

This section of the report provides a detailed, evidence-based assessment of the current state of the mcp-bridge service. The evaluation confirms that the project is built on a solid, modern foundation that aligns well with its initial goals and demonstrates a high degree of software engineering maturity.

Section 1: Analysis of Foundational Architecture and Technology Stack


Project Structure and Tooling

The project exhibits excellent software engineering discipline, establishing a robust and maintainable foundation. The use of pyproject.toml for dependency management aligns with modern Python standards (PEP 621), providing a single, declarative source for project metadata, dependencies, and build system configuration.1 This approach simplifies environment setup and ensures reproducible builds.
The inclusion of a Makefile provides clear, standardized entry points for common development tasks such as install, lint, format, test, and build-image. This automation promotes consistency across developer environments, reduces onboarding friction for new team members, and serves as executable documentation for the project's development lifecycle.1 The logical separation of concerns within the directory structure—with distinct folders for source code (src), tests (tests), and comprehensive documentation (docs)—is exemplary and follows widely accepted best practices for organizing complex software projects.

Web Framework and Data Modeling

The selection of FastAPI as the web framework is an outstanding choice for this application. Its high performance, which is on par with NodeJS and Go frameworks, is well-documented and stems from its foundation on Starlette (an ASGI framework) and Uvicorn (an ASGI server).3 FastAPI's native support for asynchronous operations is critical for building a responsive API server that can handle I/O-bound tasks, such as communicating with an external R process, without blocking the main event loop. Furthermore, its automatic generation of OpenAPI-compliant documentation from Python type hints and Pydantic models is a significant feature that enhances developer productivity and API clarity.4
The extensive and consistent use of Pydantic for data modeling is another major strength. This is evident throughout the API layer (src/mcp_bridge/routes/simulation.py) and the tool implementation layer (src/mcp/tools/). By defining strict data schemas, the project benefits from automatic request validation, serialization, and deserialization. This ensures type safety at the application's boundaries, significantly reducing the risk of data-related bugs and providing clear, enforceable data contracts between the service and its clients. This rigorous approach to data modeling is essential for building a reliable and maintainable system.1

Section 2: R Interoperability and the Adapter Design Pattern


Adapter Abstraction

A cornerstone of the system's robust design is the use of an abstract base class, OspsuiteAdapter, defined in src/mcp_bridge/adapter/interface.py.1 This abstraction effectively decouples the core application logic from the specific technical method of R interoperability. It allows for multiple, interchangeable implementations of the adapter interface, a classic and highly effective application of the Strategy design pattern. The project currently provides two such implementations: the InMemoryAdapter (src/mcp_bridge/adapter/mock.py), which is invaluable for unit testing and local development without an R dependency, and the SubprocessOspsuiteAdapter (src/mcp_bridge/adapter/ospsuite.py), which provides the actual integration with the ospsuite R package. This clean separation is a mark of architectural foresight, as it enables the system to evolve its R integration strategy without requiring a rewrite of the business logic in the service and tool layers.

Current Implementation: SubprocessOspsuiteAdapter

The decision to use an out-of-process subprocess call to an external R script is a sound and pragmatic choice for the project's current proof-of-concept phase. This architecture offers several key advantages, primarily centered on stability and isolation.
First, it provides strong process isolation. The Python-based FastAPI server and the R runtime operate in separate memory spaces. A crash, memory leak, or unhandled exception within the R environment will terminate only the subprocess, not the main API server. The Python application can catch the error, log it, and return a structured error response (e.g., a 502 Bad Gateway) to the client, thereby enhancing overall system stability and resilience. This is a critical feature for a service intended to be highly available.
Second, this approach simplifies dependency management. The R environment, including all its specific packages and their versions, can be configured and managed within the Docker container independently of the Python environment, reducing the risk of package conflicts.
The primary drawback of this architecture is performance overhead. Each call to an adapter method incurs the cost of creating a new R process, which involves loading the R interpreter and necessary libraries. Furthermore, all data passed between the Python and R processes must be serialized (e.g., from a Python dictionary to a JSON string) and then deserialized on the other side. This round-trip serialization and process creation introduces latency that, while acceptable for single, coarse-grained operations like running a full simulation, can become a significant bottleneck for workflows that require rapid, iterative tool calls, such as interactively fine-tuning multiple parameters.

Architectural Alternative: rpy2

The project's initial architectural documentation correctly identified rpy2 as a high-performance alternative for R interoperability.1 The rpy2 library provides an in-process bridge, embedding the R interpreter directly within the Python process. This allows for direct, low-overhead data exchange between Python and R objects, effectively eliminating the serialization and process-creation bottleneck of the subprocess approach.
However, this performance comes at the cost of tighter coupling and reduced stability. Because both runtimes share the same process space, an unrecoverable error or segmentation fault in the R code can crash the entire Python server. Additionally, managing the R environment and potential conflicts between Python's memory management (e.g., the Global Interpreter Lock) and R's single-threaded nature can be complex.
The choice between the subprocess model and an in-process model like rpy2 represents a fundamental architectural trade-off between stability and performance. The current implementation correctly prioritizes stability and isolation, which is the appropriate and risk-averse decision for an initial prototype. The modularity provided by the Adapter pattern, however, demonstrates significant foresight, as it leaves the door open to introduce an Rpy2OspsuiteAdapter in the future. This would allow the system to select the most appropriate adapter—perhaps even dynamically—based on the specific performance and stability requirements of a given task. The performance analysis in Section 8 will build upon this, recommending a profiling-driven approach to determine if and when such a transition becomes necessary.
Feature
SubprocessOspsuiteAdapter (Current)
Rpy2OspsuiteAdapter (Proposed Alternative)
Performance (Latency)
High (process creation + serialization overhead)
Low (in-process function calls, direct data conversion)
Process Isolation
Strong (R crash does not affect Python server)
None (R crash can terminate the entire Python process)
Stability/Fault Tolerance
High
Low to Medium (depends on R code quality)
Implementation Complexity
Medium (requires a separate R bridge script)
High (requires careful management of R environment and objects)
Dependency Management
Simpler (environments are isolated)
More Complex (potential for conflicts between Python/R packages)
Data Serialization Overhead
High (e.g., Python -> JSON -> R -> JSON -> Python)
Negligible (direct object conversion)


Section 3: API Contract and Documentation Suite Review


Comprehensive API Definition

The project's adherence to the OpenAPI standard, demonstrated by the thorough and well-structured openapi.json file, is a significant strength.1 This file serves as the canonical source of truth for the API's contract. It meticulously defines the request and response schemas for each tool, including data types, constraints, and field names. Crucially, it also specifies the potential error responses for different HTTP status codes, providing clients with a complete picture of both successful and unsuccessful interaction patterns. This rigorous, contract-first approach enables a host of powerful development practices, including the automatic generation of interactive documentation (via FastAPI's built-in Swagger and ReDoc UIs), automated client library generation for various languages, and robust contract-based testing.

Mature Design Artifacts

The presence of supplementary design documents, such as error-taxonomy.md and sequencediagrams.md, is a strong indicator of a mature and thoughtful design process that goes beyond mere implementation.1
The error-taxonomy.md document establishes a stable, predictable contract for how the service communicates failures. By defining a consistent set of error codes (e.g., InvalidInput, NotFound, InteropError), messages, and payload structures, it allows the client-side agent to programmatically handle errors in a robust and reliable manner. This is essential for building an autonomous agent that can recover from failures and re-plan its actions.
The sequencediagrams.md file provides invaluable clarity on the intended interaction flows, particularly for the asynchronous run_simulation workflow, which is inherently complex. These diagrams visually articulate the multi-step process of job submission, status polling, and result retrieval, making the system's behavior easier to understand for both developers and stakeholders. Together, these artifacts demonstrate a commitment to clear communication and robust design, explaining not just what the code does, but why it behaves the way it does.

Section 4: Asynchronous Workflow and Job Management Architecture


Current Implementation: Thread-Pooled JobService

The current implementation for handling long-running PBPK simulations is the JobService, located at src/mcp_bridge/services/job_service.py.1 This service utilizes Python's built-in concurrent.futures.ThreadPoolExecutor to manage a configurable pool of worker threads that execute simulation tasks in the background. When a simulation is requested via the API, the service submits the task to the thread pool and immediately returns a unique job_id. The client can then use this job_id to poll a separate endpoint to check the job's status. Since the initial proof-of-concept, the JobService has gained first-class features: retries, execution timeouts, cancellation, and structured job metadata, all governed by environment variables such as JOB_WORKER_THREADS, JOB_TIMEOUT_SECONDS, and JOB_MAX_RETRIES.

Evaluation and Identified Limitations

This implementation is a functional and entirely appropriate solution for a single-node, proof-of-concept deployment. It successfully demonstrates the asynchronous job pattern that is a core requirement of the project's strategic vision, proving that the high-level workflow is viable. However, its architectural design has several inherent limitations that make it unsuitable for a production environment or any scenario requiring high availability, scalability, or resilience.
The primary limitations are:
Lack of Persistence: The job queue and all job states are stored entirely in memory. If the server process restarts for any reason (e.g., a crash, deployment update, or planned maintenance), all information about queued, running, and completed jobs is permanently lost.
No Horizontal Scalability: The thread pool is confined to a single Python process on a single machine. The system cannot be scaled out by adding more server nodes, as there is no shared, distributed job queue for multiple instances to draw from. This creates a hard ceiling on the system's processing throughput.
Limited Observability: Beyond application logs, there are no built-in tools for monitoring key operational metrics such as queue length, worker utilization, task execution times, or failure rates. This makes it difficult to diagnose performance issues or manage capacity in a production setting.
Basic Error Handling: While the service implements a simple retry loop, it lacks the sophisticated mechanisms of dedicated task queues, such as configurable exponential backoff strategies, dead-letter queues for failed tasks, or complex task routing.
In its current form, the JobService is a lightweight but production-ready baseline for modest workloads. It validates the asynchronous API workflow (submit → get job_id → poll status) and already enforces resource bounds through configuration. As concurrency demands grow—especially for population simulations or large batch campaigns—the design can evolve to a distributed task queue. Section 8.1 therefore reframes Celery/RabbitMQ as the next scaling tier rather than an immediate correctness fix.

Section 5: Security Posture and Threat Model Validation


Proactive Security Planning

The existence of a formal threat-model.md document demonstrates a commendable and proactive approach to security.1 The use of the STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) framework is a standard and effective methodology for systematically identifying and categorizing potential security threats. This indicates that security is being considered as a foundational aspect of the design, rather than an afterthought.

Validation of Implemented Mitigations

A review of the codebase confirms that several key threats identified in the model have been effectively mitigated:
Tampering (File Path Traversal): The threat model correctly identifies the risk of an attacker using the load_simulation tool to read arbitrary files from the server's filesystem by supplying a malicious path (e.g., ../../../../etc/passwd). The implementation in src/mcp/tools/load_simulation.py directly addresses this. The resolve_model_path function ensures that any user-supplied file path is resolved to its absolute canonical path and then verified to be within the allow-listed directories configured via the MCP_MODEL_SEARCH_PATHS environment variable. This is a robust and effective control against path traversal attacks.1
Denial of Service (Resource Exhaustion): The threat model identifies the risk of a DoS attack caused by a flood of requests to the computationally expensive /run_simulation endpoint. The current JobService provides a partial mitigation for this by using a bounded worker pool, configured by the JOB_WORKER_THREADS setting. This prevents an unlimited number of concurrent simulations from consuming all available CPU and memory resources on the server.1

Analysis of Planned Mitigations

The threat model correctly defers several critical security controls to future tasks, which is appropriate for the project's current proof-of-concept phase. These deferred items represent the most significant remaining security gaps that must be addressed before any production deployment.
Authentication and Authorization (Task 17): The system currently lacks any form of authentication or authorization, meaning any entity with network access to the server can invoke any tool. This is the most critical security gap and is the primary focus of the research and recommendations in Section 10.1.
Immutable Audit Trail (Task 18): The threat model identifies the need to mitigate repudiation threats (i.e., preventing a user from denying they performed an action). This requires an immutable audit log, which is not yet implemented. This will be the focus of the detailed design in Section 10.2.

Container Security

The Dockerfile follows established best practices for container security.1 It utilizes a minimal python:3.11-slim base image, which reduces the container's attack surface by including fewer system libraries and tools. Crucially, it creates a dedicated, non-root user (mcp) and switches to this user before running the application. This is a critical security measure that ensures that even if an attacker were to compromise the application process, they would not have root privileges within the container, severely limiting their ability to cause further harm.

Part II: Deep Research and Strategic Roadmap for Next Steps

This part of the report transitions from evaluation to forward-looking research and design. It provides a detailed technical blueprint for evolving the MCP Bridge from a functional prototype into a scalable, secure, and intelligent platform capable of realizing the project's most ambitious strategic goals.

Section 6: Architecting the Agent: Orchestration, State Management, and Planning


The Need for an Agentic Framework

The MCP Bridge, in its current form, successfully exposes a set of powerful but primitive "tools" (e.g., load_simulation, set_parameter_value). To achieve the strategic goals of conversational modeling and autonomous analysis, a separate, intelligent "agent" component is required. This agent acts as the orchestrator, or the "brain," responsible for translating a high-level user intent (e.g., "Run a sensitivity analysis on body weight") into a concrete, multi-step plan of tool calls, managing the state of the interaction, and synthesizing the results into a coherent response.

Comparative Analysis of Agent Frameworks

Two leading paradigms for building such agents are the managed service approach offered by platforms like the OpenAI Assistants API and the open-source library approach exemplified by LangChain and its more advanced orchestration layer, LangGraph.
OpenAI Assistants API: This framework provides a high-level, managed solution for building agents. It abstracts away many of the complexities of agent development. The developer defines the available tools (functions), and the API automatically handles the management of conversational state (via "Threads"), the decision-making process of when to call a tool, and the lifecycle of tool execution (indicated by the requires_action status). This approach allows for very rapid development and prototyping but offers less granular control over the agent's internal logic and can lead to vendor lock-in.5
LangChain & LangGraph: LangChain provides a rich ecosystem of components and pre-built agent architectures (e.g., ReAct, Self-Ask) for building LLM applications.9 LangGraph, a library built on top of LangChain, extends this by providing a lower-level, more expressive framework for creating custom, stateful, multi-agent workflows as cyclical graphs. With LangGraph, the agent's logic is explicitly defined as a state machine, where nodes represent functions (e.g., call an LLM, execute a tool) and edges represent the transitions between them. This approach offers complete control, transparency, and customization of the agent's reasoning process.11
The complex, stateful, and often long-running nature of scientific analysis aligns better with the explicit control and transparency offered by LangGraph than with a more abstracted, managed service. Scientific workflows often involve custom logic, conditional branching, and iterative loops (e.g., looping through a list of parameters for a sensitivity analysis) that are more naturally expressed as a graph than as a simple tool-calling loop. Furthermore, the ability to explicitly define the state, inspect it at every step, and easily insert human-in-the-loop checkpoints is critical for ensuring the reliability, reproducibility, and safety required in a scientific domain. The transparency of a LangGraph implementation also aligns better with the project's open-source ethos.2

Proposed Agent Architecture using LangGraph

A robust agent for orchestrating PBPK modeling tasks can be constructed using LangGraph with the following architecture:
State Definition: A central AgentState object, likely a Pydantic model or a typed dictionary, will be defined to track the entire state of the interaction. This object will persist across all nodes in the graph and should include fields such as:
conversation_history: A list of all user and AI messages.
current_simulation_id: The identifier for the currently loaded simulation.
last_results_id: The identifier for the most recent simulation result.
plan: A list of steps the agent intends to execute.
intermediate_steps: A log of all tool calls made and their results.
Nodes (Functions): The graph will be composed of several key nodes, each representing a distinct step in the agent's processing loop:
planner_node: This node takes the user's latest query and the current state, and calls an LLM to formulate or update a high-level plan of action.
tool_selection_node: This node examines the next step in the plan and determines which specific MCP Bridge tool needs to be called and with what arguments.
tool_execution_node: This node takes the tool call request from the previous node, executes it by making an API call to the MCP Bridge, and appends the result to the intermediate_steps in the state.
human_in_the_loop_node: A special node that interrupts the graph's execution before a critical action (like run_simulation). It presents the planned action to the user and waits for explicit approval before allowing the graph to continue.
response_synthesis_node: This node calls an LLM to generate a final, human-readable response to the user based on the completed plan and the results of the tool calls.
Edges (Control Flow): Conditional edges will be used to direct the flow of logic through the graph. For example, after the tool_selection_node, a conditional edge will check the selected tool. If the tool is run_simulation, it will route to the human_in_the_loop_node. If it is get_parameter_value, it will route directly to the tool_execution_node. If no tool is selected, it will route to the response_synthesis_node.

Section 7: Ensuring Scientific Rigor: Human-in-the-Loop and Ambiguity Resolution


The Challenge of Ambiguity and Risk

A primary challenge in building a conversational interface for a precise scientific domain is bridging the gap between the inherent ambiguity of natural language and the deterministic precision required for scientific operations.14 A user prompt like "make the subject heavier" is ambiguous; the agent must not guess whether this means an increase of 10 kg or 10%. Misinterpretation could lead to scientifically invalid results, wasted computational resources on incorrect simulations, and an erosion of user trust.16 Therefore, the system's design must prioritize safety and clarity, ensuring that a human is always in control of critical actions.17

Design Pattern: The "Verify, Then Execute" Loop

To mitigate these risks, the agent's core interaction model must be built around a "Verify, Then Execute" loop. This involves two key components: prompt engineering for clarification and architectural patterns for confirmation.
Prompt Engineering for Clarification: The agent's primary system prompt must be engineered to handle ambiguity not by making assumptions, but by actively seeking clarification from the user. The "Conversation Routines" framework provides an excellent model for this, where the system prompt explicitly encodes the procedural logic for data collection and validation.18 The prompt should contain instructions such as:
"Before executing any action that modifies the simulation state (e.g., set_parameter_value), you must first state your understanding of the user's request and the exact action you plan to take."
"If a user's request is ambiguous (e.g., 'increase the dose'), you MUST ask clarifying questions to obtain a specific, numerical value and unit before proceeding."
"Always restate the user's issue or request to confirm understanding before proceeding with a solution".22
Human-in-the-Loop for Confirmation: For any critical or computationally expensive action, such as modifying a parameter (set_parameter_value) or initiating a simulation (run_simulation), the agent's workflow must include a mandatory confirmation step. This moves beyond simple clarification to require explicit user approval. LangGraph's built-in interrupt functionality is the ideal architectural mechanism to implement this. The agent's graph can be designed to pause execution before calling a critical tool, present the user with a clear summary of the intended action and its parameters (e.g., "I am about to set the parameter 'Organism|Weight' to 80 kg. Do you want to proceed?"), and wait for an explicit "yes" or "no" from the user before continuing or aborting the plan.9

Architectural Patterns for Error Recovery

Even with confirmation, tool calls can fail due to transient network issues, invalid inputs that passed initial validation, or errors in the underlying R runtime. A robust agent must be able to handle these failures gracefully.
Tool-Level Retries: For transient errors (e.g., HTTP 503 or 504 from the bridge), the agent's tool-calling logic should implement a retry mechanism with exponential backoff. This prevents temporary glitches from derailing an entire multi-step plan.24
Agent-Level Re-planning: If a tool call fails with a definitive error (e.g., an HTTP 400 InvalidInput or 404 NotFound from the bridge), the agent should not simply terminate. The structured error response from the MCP Bridge must be captured and fed back into the agent's context. The agent can then be prompted to analyze the error and either re-plan its approach (e.g., by trying a different parameter path) or inform the user of the specific failure and ask for guidance. This creates a resilient, self-correcting system that can navigate and recover from problems in the execution environment.24
By enforcing this comprehensive loop of clarification, confirmation, execution, and error recovery, the conversational history itself becomes a human-readable, time-stamped, and verifiable record of the entire scientific workflow. This "conversation as a lab notebook" paradigm directly addresses the critical need for traceability and reproducibility that was identified as a key strategic value in the project's feasibility study.2

Section 8: Designing for Scale: From Local Execution to High-Performance Computing

The enhanced JobService provides a dependable foundation for asynchronous execution within a single deployment. However, to handle the demands of real-world scientific computing—including population simulations, large-scale sensitivity analyses, and concurrent user workloads—the system's backend architecture must remain evolvable. This section outlines a three-stage roadmap for scaling the job execution framework when the workload outgrows the current thread-pooled approach.

8.1. Stage 1: Distributed Task Execution with Celery and RabbitMQ

When concurrency or reliability requirements exceed the limits of the built-in thread pool, the next scaling tier is a production-grade distributed task queue. Celery, paired with RabbitMQ, remains the industry-standard combination for building scalable and resilient asynchronous systems in Python.26
The proposed architecture would function as follows:
Task Dispatch: The FastAPI /run_simulation endpoint's responsibility will change. Instead of submitting the job to a local thread pool, it will serialize a task message (containing the simulation_id and other relevant parameters) and dispatch it to a RabbitMQ message broker by calling a Celery task function (e.g., run_simulation_task.delay(...)). The API will still immediately return a task ID to the client.
Message Brokering: RabbitMQ will receive the task message and place it in a persistent queue. It will hold the message until a worker is available to process it, ensuring that tasks are not lost even if all workers are busy or temporarily offline.
Task Execution: One or more independent Celery worker processes, which can be running on separate virtual machines or containers, will continuously monitor the RabbitMQ queue. When a new task message appears, a worker will consume it, deserialize the arguments, and execute the simulation by invoking the OspsuiteAdapter.
Result and Status Storage: The status of the task (PENDING, STARTED, SUCCESS, FAILURE) and its final result will be stored in a dedicated, shared result backend, such as Redis or a relational database. The FastAPI /get_job_status endpoint will then query this backend to retrieve the status for a given task ID.
This architecture provides immediate and significant benefits over the current implementation: horizontal scalability (throughput can be increased by simply adding more Celery worker nodes), fault tolerance (if a worker crashes mid-task, Celery can be configured to requeue the task for another worker), and persistence (the message broker and result backend ensure that job state survives server restarts).

8.2. Stage 2: Managing Large Scientific Data Payloads

PBPK simulations, especially population simulations involving hundreds of virtual individuals, can generate result files that are many gigabytes in size. Returning this data as a single JSON payload within an API response is inefficient, unreliable, and will not scale. It can exhaust server memory, saturate network bandwidth, and lead to extremely long response times for the client.
To address this, the system should adopt the Claim Check Pattern, an architectural pattern designed specifically for handling large message payloads in distributed systems.30
The workflow would be modified as follows:
Off-site Storage: Upon successfully completing a simulation, the Celery worker will not store the full result data in the result backend. Instead, it will save the large result file (ideally in an efficient, column-oriented format like Apache Parquet or HDF5) to a shared, high-performance, and scalable object storage location, such as Amazon S3, Azure Blob Storage, or a local network-attached storage (NAS) system.
Store the "Claim Check": The worker will then store only a "claim check"—a small, lightweight reference to the stored data, such as its S3 URI—as the task's result in the Celery result backend.
Client Retrieval: When the client application requests the simulation results, the FastAPI server will retrieve the claim check. Instead of loading the large file itself, the server will provide the client with a secure mechanism to access the data directly from object storage. A common and secure method for this is to generate a pre-signed URL, which grants the client temporary, time-limited permission to download the specific result file.
For client-side consumption, particularly for interactive visualization, loading an entire multi-gigabyte result file is often still impractical. The API should therefore also support data streaming and chunking. The /get_simulation_results endpoint could be enhanced with parameters allowing the client to request specific outputs (e.g., only the plasma concentration), specific individuals from a population, or a specific time range. The server would then read only the requested "chunks" or slices from the large file in object storage and stream them back to the client, minimizing memory usage and latency.31

8.3. Stage 3: Integration with High-Performance Computing (HPC) Environments

For truly massive computational tasks, such as large-scale population simulations or exhaustive sensitivity analyses, even a cluster of Celery workers may be insufficient. To achieve the required level of performance, the system must be able to leverage dedicated High-Performance Computing (HPC) resources, which are typically managed by workload managers like Slurm.
This can be achieved by evolving the architecture to a HPC Job Submitter Pattern. In this model, the Celery worker's role shifts from executing the task itself to submitting the task to a more powerful, specialized system. This creates a hierarchical and highly scalable execution architecture.
The workflow would be:
Specialized HPC Queue: A dedicated task queue (e.g., hpc_jobs) is configured in RabbitMQ.
HPC Submitter Worker: A specialized Celery worker is configured to listen exclusively to this queue. This worker must be running on a machine that has access to the Slurm submission commands (e.g., a login node of the HPC cluster).
Job Submission: When a task arrives, this worker does not run the R script directly. Instead, it dynamically generates a Slurm submission script (sbatch script) that contains the commands needed to run the ospsuite R simulation on a compute node. The worker then executes the sbatch command to submit the job to the Slurm scheduler and stores the returned Slurm job ID.
Asynchronous Status Monitoring: A separate monitoring component is required to track the status of the job within the Slurm queue. This can be done by periodically polling commands like squeue or sacct. A more sophisticated approach, inspired by architectures like the Kafka Slurm Agent, would be to have the Slurm job itself publish status updates (e.g., "started," "completed," "failed") to a message bus, allowing for event-driven status tracking.34
Result Retrieval: When the Slurm job completes, it writes its output to the HPC cluster's shared filesystem. The monitoring component detects this completion and updates the task's status in the result backend, populating it with a claim check pointing to the result file on the shared storage.
Feature
Stage 1: Thread-Pooled JobService
Stage 2: Distributed Celery/RabbitMQ
Stage 3: HPC Integration via Slurm
Scalability
Single Node (Vertical Only)
Multi-Node (Horizontal)
Massively Parallel (HPC Scale)
Persistence
None (In-Memory)
High (Broker & Result Backend)
High (Broker, Backend, & HPC Filesystem)
Fault Tolerance
Moderate (Retries, cancellation, bounded pool)
High (Task requeuing, worker redundancy)
Very High (Managed by HPC scheduler)
Monitoring
Basic (Application Logs, job metadata)
Advanced (e.g., Celery Flower, broker stats)
Comprehensive (Slurm accounting, custom monitors)
Resource Management
Bounded Thread Pool via JOB_WORKER_THREADS
Distributed Worker Pools
Centralized HPC Job Scheduling
Implementation Complexity
Low
Medium
High


Section 9: Enabling Transformative Use Cases: The Literature-to-Model Pipeline

A key strategic goal identified in the feasibility study is to automate the process of updating PBPK models with data extracted directly from scientific literature, a workflow that promises to radically accelerate model development and validation.2 Realizing this "Literature-to-Model" pipeline requires solving the complex problem of extracting structured information—including text, tables, and figures—from unstructured PDF documents.
A simplistic approach of extracting raw text from a PDF is a largely solved problem using libraries like PyPDF2. However, this method is insufficient for scientific papers because it discards the critical layout and visual information inherent in the document's structure. As highlighted in community discussions on this topic, this "flattening" of the document to a simple text stream fails reliably with complex tables, multi-column layouts, and, crucially, numerical values that are contextually placed but not explicitly labeled (e.g., a parameter value in a table cell without its header in the same line of text).37
To achieve the required fidelity, a more sophisticated, multi-modal approach is necessary. Modern techniques combine computer vision, layout analysis, and large language models to parse documents with a much higher degree of accuracy and structural awareness.
Layout-Aware Models: Open-source toolkits like PDF-Extract-Kit utilize a pipeline of specialized models. They first employ computer vision models (e.g., YOLO, LayoutLMv3) to perform layout detection, identifying the precise bounding boxes of different document elements such as text paragraphs, titles, tables, figures, and mathematical formulas. This crucial first step preserves the spatial structure of the document, allowing subsequent components to operate on semantically meaningful segments.40
Multimodal Large Language Models (LLMs): The advent of LLMs with vision capabilities (e.g., GPT-4V, Claude 3) has opened a new frontier for data extraction. These models can directly process an image of a document page and extract structured data, as they inherently understand the layout, proximity of text, and structure of tables and figures. The "PlotExtract" method provides a powerful example of a sophisticated workflow where a multimodal LLM is used not only to extract data points from a plot but also to generate Python code to re-plot the extracted data, which is then used for visual verification of the extraction's accuracy.41
Vector Embeddings for Retrieval: For answering specific questions over the textual content of a document, a common and effective pattern is to use Retrieval-Augmented Generation (RAG). The extracted text is first divided into smaller, semantically meaningful chunks. Vector embeddings are then generated for each chunk and stored in a specialized vector database. When a user asks a question, the question is also embedded, and a similarity search is performed to retrieve the most relevant text chunks. These chunks are then provided as context to a standard LLM, which uses them to generate a grounded and accurate answer.42
Based on this research, a viable technical pipeline for the Literature-to-Model use case would involve the following steps:
Layout Parsing and Segmentation: The input PDF is first processed by a layout-aware model, such as one from PDF-Extract-Kit, to segment the document into its constituent components: text paragraphs, tables, and figures, each with associated bounding box information.
Component-Specific Extraction: Each component is then routed to a specialized extraction tool:
Tables: The image of each detected table is passed to a specialized table recognition model (e.g., TableMaster or a multimodal LLM prompted for table extraction) to convert it into a structured format like CSV or Markdown.
Figures/Plots: The image of each plot is passed to a multimodal LLM instructed to perform data digitization, potentially using a verification workflow similar to PlotExtract.
Text: The extracted text paragraphs are chunked, embedded, and indexed in a vector database (e.g., Pinecone, Weaviate) to enable efficient semantic search.
Agent-Driven Synthesis and Tool Use: The AI agent, given a high-level goal (e.g., "Find the subject's body weight and the drug's oral dose from this paper"), orchestrates the process. It would first query the extracted structured data (from tables) and the vector database (for text) to find the relevant information. It would then synthesize the findings and use this information to call the appropriate MCP Bridge tools (e.g., set_parameter_value) to update the PBPK model.

Section 10: Hardening for Regulated Environments: Advanced Security and Compliance

As the MCP Bridge matures, it must be hardened to meet the stringent security and compliance requirements of scientific and regulated environments. This involves implementing robust authentication, ensuring the integrity of all recorded actions, and adhering to data governance policies.

10.1. Securing the API for Machine-to-Machine (M2M) Communication

The current architecture lacks any authentication mechanism, which is a critical vulnerability. As the agent and the MCP Bridge are distinct services, their communication must be secured to ensure that only authorized agents can access and manipulate PBPK models. This is a classic machine-to-machine (M2M) authentication scenario. A comparative analysis of common authentication schemes reveals the most suitable approach.43
API Keys: These are simple, static strings that are easy to implement but offer weak security. They are typically long-lived, do not contain any contextual information or permissions, and are vulnerable to leakage. Their revocation is also a manual process. They are not recommended for this application.
OAuth 2.0: This is an industry-standard authorization framework, primarily designed for delegated access (i.e., allowing a user to grant a third-party application limited access to their data on another service). While the Client Credentials flow is designed for M2M communication, the full OAuth 2.0 protocol can be more complex than necessary for securing internal service-to-service communication.
JSON Web Tokens (JWT): JWT is an open standard for creating compact, self-contained access tokens. A token is a JSON object that contains "claims" (e.g., the identity of the issuer, the subject/agent, permissions/scopes, and an expiration time) and is digitally signed by the identity provider. The recipient server (the MCP Bridge) can cryptographically verify the token's signature without needing to make a database lookup or a call back to the identity provider. This makes JWT-based authentication stateless, highly performant, and well-suited for distributed microservice architectures.
For this M2M architecture, JWTs are the ideal choice. The agent would first authenticate with a central identity service to receive a short-lived JWT. It would then include this JWT as a Bearer token in the Authorization header of every subsequent request to the MCP Bridge. FastAPI has excellent built-in support for integrating with OAuth2-compatible Bearer token schemes, making the implementation of token validation straightforward and standards-compliant.4

10.2. Designing an Immutable Audit Trail

For scientific reproducibility and regulatory compliance (e.g., under standards like 21 CFR Part 11), all actions performed via the API that create, modify, or delete data must be logged in a secure, tamper-evident manner.2 A simple log file is insufficient, as it can be altered or deleted by a malicious actor or even by accident. The system requires an immutable audit trail.
A robust and verifiable audit trail can be implemented using cryptographic hash chaining, a technique inspired by blockchain technology.51
The architectural blueprint for this system is as follows:
Dedicated Audit Service: A new service, the AuditService, will be created to handle all audit logging.
Structured Audit Events: Every critical tool call within the MCP Bridge (e.g., load_simulation, set_parameter_value, run_simulation) will generate a structured audit event. This event will be a JSON object containing comprehensive context: the user/agent identity (from the JWT), the timestamp (ISO 8601 format), the action performed, the input parameters, the outcome, and the request's correlation ID.
Hash Chaining Logic: When an event is sent to the AuditService, it will:
a. Retrieve the cryptographic hash of the most recent entry in the audit log.
b. Concatenate this previous hash with the new, serialized event data.
c. Compute a new hash (e.g., using SHA-256) of this combined data.
d. Atomically store the new event data along with its newly computed hash as the next entry in the log.
Immutable Storage: To provide the strongest guarantee of immutability, the audit log itself should be stored in a system with Write-Once-Read-Many (WORM) capabilities. This could be a cloud object storage service (like an Amazon S3 bucket with Object Lock enabled) or a specialized database that supports append-only, tamper-evident ledgers.56
This design ensures that any modification to a past log entry—even changing a single bit—would invalidate its hash, which would in turn cause a mismatch with the "previous hash" value stored in the subsequent entry, breaking the chain. A periodic verification process can traverse the chain to confirm its integrity, making any tampering immediately detectable.

10.3. Data Retention and Governance

Scientific data, particularly data generated in the context of federally funded research or for regulatory submissions, is subject to strict data retention policies. The system must be designed to accommodate these requirements.
Research into common policies in the United States indicates that while requirements vary, a common baseline retention period is three years after the submission of the final project or financial report, as stipulated by sponsors like the NIH and NSF. However, this period can be significantly longer under specific circumstances: data related to patents must be retained for the life of the patent, data subject to HIPAA may require retention for six years or more, and records related to research misconduct allegations must be kept until the case is fully resolved.58
Given this variability, the following recommendations should be implemented:
Configurable Retention Policies: The system must be designed with configurable retention policies for all generated data artifacts, including simulation result files, intermediate data, and the audit logs themselves. These policies should be manageable on a per-project or per-simulation basis.
Data Lifecycle Management: A data lifecycle management strategy should be implemented. For example, simulation results could be automatically moved from "hot" (immediately accessible, high-performance) storage to "cold" (archival, low-cost) storage after a defined period (e.g., one year). After the full retention period has expired, a process should be in place for the secure and verifiable deletion of the data.
Audit Trail Retention: The immutable audit trail, as the definitive record of all activities, should be retained for the longest applicable period required by any of the data it pertains to, as it is essential for demonstrating compliance and reconstructing the history of any given analysis.

Section 11: Synthesis and Prioritized Recommendations


Summary of Findings

The PBPK_MCP project, in its current state, is an exceptionally well-architected and promising proof-of-concept. It demonstrates mature software engineering practices, a clear separation of concerns, and a solid foundation for future growth. The choice of a modern technology stack (FastAPI, Pydantic), the proactive approach to security planning, and the creation of comprehensive API design artifacts are all significant strengths. With the thread-pooled JobService, MCP tools for simulation execution/status/PK analysis, and documented configuration flags, the platform already delivers reliable async workflows. The next major effort will be to layer the required intelligence (the agent), robust security (authentication and auditing), and advanced scientific workflows on top of the existing tool bridge while preserving a path to scale out the job execution layer when load demands it.

Prioritized Roadmap

To manage this evolution effectively, a phased approach is recommended, focusing on building out foundational capabilities before moving to more advanced features.
Phase 1: Foundation Hardening (Next 3-6 Months)
This phase focuses on transforming the prototype into a secure, scalable, and production-ready service.
Implement JWT Authentication: Secure all API endpoints for M2M communication between the agent and the bridge. This is the highest-priority security task.
Implement the Immutable Audit Trail Service: Establish the foundation for regulatory compliance and scientific traceability by implementing the hash-chained audit logging system.
Evaluate Celery and RabbitMQ Migration: Monitor workload characteristics and, when concurrency requirements exceed the single-node pool, transition to a distributed task queue for horizontal scale and persistence.
Phase 2: Agent Development and Safety (Months 6-9)
This phase focuses on building the intelligence layer that will consume the bridge's tools.
Develop the LangGraph Agent: Build the initial agent orchestrator based on the architecture proposed in Section 6.
Implement "Verify, Then Execute" Logic: Focus development on prompt engineering for ambiguity resolution and implement the human-in-the-loop confirmation workflow for critical tools like set_parameter_value and run_simulation.
Phase 3: Scaling and Advanced Workflows (Months 9-15)
This phase focuses on enabling the system to handle large-scale scientific problems and more complex use cases.
Implement the Claim Check Pattern: Re-architect the result handling mechanism to support large simulation output payloads by integrating with an object storage solution.
Prototype HPC Integration: Develop and test the specialized Celery worker for submitting and monitoring jobs on a Slurm-managed HPC cluster.
Prototype Literature-to-Model Pipeline: Begin integrating PDF extraction tools (PDF-Extract-Kit, multimodal models) to prove out the technical feasibility of the automated data extraction workflow.
Phase 4: Performance and Optimization (Continuous)
This phase runs in parallel with the others and focuses on continuous improvement.
Establish Performance Benchmarks: Create a suite of benchmarks to measure the end-to-end latency of key tool calls, particularly those involving the R adapter.
Conduct Performance Profiling: Use profiling tools like cProfile and py-spy to identify performance bottlenecks within the Python application and the R bridge script.63 This data will provide the evidence needed to make an informed decision about if and when to invest in developing an alternative, higher-performance rpy2-based adapter.
Works cited
_MCP_PBPK.txt
PBPK MCP Open-Source Feasibility
Benchmarks - FastAPI, accessed October 15, 2025, https://fastapi.tiangolo.com/benchmarks/
Security - FastAPI, accessed October 15, 2025, https://fastapi.tiangolo.com/tutorial/security/
Assistants Function Calling - OpenAI API - OpenAI Platform, accessed October 15, 2025, https://platform.openai.com/docs/assistants/tools/function-calling
Assistants API deep dive Deprecated - OpenAI Platform, accessed October 15, 2025, https://platform.openai.com/docs/assistants/deep-dive
Assistants API tools - OpenAI Platform, accessed October 15, 2025, https://platform.openai.com/docs/assistants/tools
Everything you need to know about OpenAI function calling and assistants API - Medium, accessed October 15, 2025, https://medium.com/the-modern-scientist/everything-you-need-to-know-about-openai-function-calling-and-assistants-api-55c02570a21c
Agents - LangChain, accessed October 15, 2025, https://www.langchain.com/agents
Agents - Docs by LangChain, accessed October 15, 2025, https://docs.langchain.com/oss/python/langchain/agents
LangGraph: Simplifying Agent Orchestration and State Management | by Sonal Mishra, accessed October 15, 2025, https://medium.com/@sonal.mishra1297/langgraph-simplifying-agent-orchestration-and-state-management-6e0484e3399c
LangGraph - LangChain, accessed October 15, 2025, https://www.langchain.com/langgraph
LangChain, accessed October 15, 2025, https://www.langchain.com/
Agentic Workflows for Conversational Human-AI Interaction Design - arXiv, accessed October 15, 2025, https://arxiv.org/html/2501.18002v1
Handling Ambiguous User Inputs in Kore.ai | by Sachin K Singh ..., accessed October 15, 2025, https://medium.com/@isachinkamal/handling-ambiguous-user-inputs-in-kore-ai-dca989016566
The novelty and acceptance of Conversational AI | by Tony Phillips ..., accessed October 15, 2025, https://uxdesign.cc/the-novelty-and-potential-acceptance-of-conversational-ai-5896a7020060
Tools - Model Context Protocol, accessed October 15, 2025, https://modelcontextprotocol.io/specification/2025-06-18/server/tools
Conversation Routines: A Prompt Engineering Framework for Task-Oriented Dialog Systems, accessed October 15, 2025, https://arxiv.org/html/2501.11613v2
(PDF) Conversation Routines: A Prompt Engineering Framework for Task-Oriented Dialog Systems - ResearchGate, accessed October 15, 2025, https://www.researchgate.net/publication/388232208_Conversation_Routines_A_Prompt_Engineering_Framework_for_Task-Oriented_Dialog_Systems
Conversation Routines: A Prompt Engineering Framework for Task ..., accessed October 15, 2025, https://arxiv.org/abs/2501.11613
Conversation Routines: A Prompt Engineering Framework for Task-Oriented Dialog Systems, accessed October 15, 2025, https://arxiv.org/html/2501.11613v3
Designing for AI: Crafting Human-AI Dialogues - Webandcrafts, accessed October 15, 2025, https://webandcrafts.com/blog/designing-for-ai
Human-in-the-loop - Overview, accessed October 15, 2025, https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/
Error Recovery and Fallback Strategies in AI Agent Development - GoCodeo, accessed October 15, 2025, https://www.gocodeo.com/post/error-recovery-and-fallback-strategies-in-ai-agent-development
How Contextual Error Recovery Works in AI Agents - My Framer Site - Convogenie AI, accessed October 15, 2025, https://convogenie.ai/blog/how-contextual-error-recovery-works-in-ai-agents
A Deep Dive into RabbitMQ & Python's Celery: How to Optimise Your Queues, accessed October 15, 2025, https://towardsdatascience.com/deep-dive-into-rabbitmq-pythons-celery-how-to-optimise-your-queues/
Scheduling Background Tasks in Python with Celery and RabbitMQ | AppSignal Blog, accessed October 15, 2025, https://blog.appsignal.com/2025/08/27/scheduling-background-tasks-in-python-with-celery-and-rabbitmq.html
Handling Long-Running Jobs in FastAPI with Celery & RabbitMQ ..., accessed October 15, 2025, https://medium.com/@mrcompiler/handling-long-running-jobs-in-fastapi-with-celery-rabbitmq-9c3d72944410
How to Set Up a Task Queue with Celery and RabbitMQ | Linode Docs, accessed October 15, 2025, https://www.linode.com/docs/guides/task-queue-celery-rabbitmq/
Dealing With Large Payloads When Using Messaging Systems ..., accessed October 15, 2025, https://akfpartners.com/growth-blog/dont-push-a-bowling-ball-down-a-garden-hose
Understanding Data Streaming | Databricks, accessed October 15, 2025, https://www.databricks.com/glossary/data-streaming
A Guide to Data Chunking - The Couchbase Blog, accessed October 15, 2025, https://www.couchbase.com/blog/data-chunking/
Chunking Strategies for LLM Applications - Pinecone, accessed October 15, 2025, https://www.pinecone.io/learn/chunking-strategies/
Python on HPC Environment | Research Cloud Computing, accessed October 15, 2025, https://wiki.hpc.odu.edu/Software/Python
Applying Large-Scale Distributed Computing to Structural Bioinformatics – Bridging Legacy HPC Clusters With Big Data Technologies Using kafka-slurm-agent - arXiv, accessed October 15, 2025, https://arxiv.org/html/2503.14806v1
Introduction to Slurm Scheduling Working with Python on Aristotle, accessed October 15, 2025, https://it.auth.gr/wp-content/uploads/2023/04/4-%CE%A7%CF%81%CE%BF%CE%BD%CE%BF%CE%B4%CF%81%CE%BF%CE%BC%CE%BF%CE%BB%CF%8C%CE%B3%CE%B7%CF%83%CE%B7-%CE%B5%CF%81%CE%B3%CE%B1%CF%83%CE%B9%CF%8E%CE%BD-%CE%BC%CE%B5-Slurm-%CE%BA%CE%B1%CE%B9-%CF%80%CE%B1%CF%81%CE%AC%CE%B4%CE%B5%CE%B9%CE%B3%CE%BC%CE%B1-Python-%CE%B5%CF%81%CE%B3%CE%B1%CF%83%CE%AF%CE%B1%CF%82.pdf
Looking for a better approach for structured data extraction from PDFs : r/automation - Reddit, accessed October 15, 2025, https://www.reddit.com/r/automation/comments/1mw94ke/looking_for_a_better_approach_for_structured_data/
Document Intelligence: The art of PDF information extraction, accessed October 15, 2025, https://www.statcan.gc.ca/en/data-science/network/pdf-extraction
Looking for a better approach for structured data extraction from ..., accessed October 15, 2025, https://www.reddit.com/r/automation/comments/1mw94ke/looking_for_a_better-approach-for-structured-data/
opendatalab/PDF-Extract-Kit: A Comprehensive Toolkit for ... - GitHub, accessed October 15, 2025, https://github.com/opendatalab/PDF-Extract-Kit
Leveraging Vision Capabilities of Multimodal LLMs for Automated Data Extraction from Plots, accessed October 15, 2025, https://arxiv.org/html/2503.12326v1
The Ultimate Guide to PDF Extraction using GPT-4 - Docsumo, accessed October 15, 2025, https://www.docsumo.com/blog/pdf-reading-with-gpt4
Top 7 API Authentication Methods Compared | Zuplo Learning Center, accessed October 15, 2025, https://zuplo.com/learning-center/top-7-api-authentication-methods-compared
OAuth vs. JWT: What Is the Difference & Using Them Together - Frontegg, accessed October 15, 2025, https://frontegg.com/blog/oauth-vs-jwt
API Authentication: Methods, Security & Best Practices, accessed October 15, 2025, https://www.digitalapi.ai/blogs/api-authentication
API key vs JWT: Secure B2B SaaS with modern M2M authentication - Scalekit, accessed October 15, 2025, https://www.scalekit.com/blog/apikey-jwt-comparison
Authentication and Authorization with FastAPI - GeeksforGeeks, accessed October 15, 2025, https://www.geeksforgeeks.org/python/authentication-and-authorization-with-fastapi/
Authentication and Authorization with FastAPI: A Complete Guide | Better Stack Community, accessed October 15, 2025, https://betterstack.com/community/guides/scaling-python/authentication-fastapi/
How do you ensure the integrity of an audit trail | SBN - Simple But Needed, accessed October 15, 2025, https://sbnsoftware.com/blog/how-do-you-ensure-the-integrity-of-an-audit-trail/
Audit Trail Requirements: Guidelines for Compliance and Best ..., accessed October 15, 2025, https://www.inscopehq.com/post/audit-trail-requirements-guidelines-for-compliance-and-best-practices
Securing Digital Assets with Cryptographic Hashing Explained - ScoreDetect, accessed October 15, 2025, https://www.scoredetect.com/blog/posts/securing-digital-assets-with-cryptographic-hashing-explained
Hashes and data integrity - Polymesh, accessed October 15, 2025, https://polymesh.network/blog/hashes-and-data-integrity
Tamper Detection in Audit Logs - VLDB Endowment, accessed October 15, 2025, https://www.vldb.org/conf/2004/RS13P1.PDF
Security Logs: Cryptographically Signed Audit Logging for Data ..., accessed October 15, 2025, https://dzone.com/articles/security-logs-cryptographically-signed-audit-loggi
Creating Verifiable Audit Trails for Legal Compliance - Attorney Aaron Hall, accessed October 15, 2025, https://aaronhall.com/creating-verifiable-audit-trails-for-legal-compliance/
Audit Trail Best Practices: Secure Compliance & Control | Whisperit, accessed October 15, 2025, https://whisperit.ai/blog/audit-trail-best-practices
Immutable Financial Data: A Deep Dive - HubiFi, accessed October 15, 2025, https://www.hubifi.com/blog/immutable-data-stripe
Data Management, Retention of Data - The Office of Research Integrity, accessed October 15, 2025, https://ori.hhs.gov/education/products/rcradmin/topics/data/tutorial_11.shtml
Full article: Disparate data retention standards in biomedical research, accessed October 15, 2025, https://www.tandfonline.com/doi/full/10.1080/08989621.2025.2543884
Data Retention - Columbia | Research, accessed October 15, 2025, https://research.columbia.edu/data-retention-0
Research Record Retention & Destruction: Tips and Best Practices - University of Maryland School of Nursing, accessed October 15, 2025, https://www.nursing.umaryland.edu/media/son/research/MRS-Research-Data-Destruction-June-2023.pdf
Retention of and Access to Research Data - DoResearch - Stanford University, accessed October 15, 2025, https://doresearch.stanford.edu/policies/research-policy-handbook/conduct-research/retention-and-access-research-data
Top 7 Python Profiling Tools for Performance - Daily.dev, accessed October 15, 2025, https://daily.dev/blog/top-7-python-profiling-tools-for-performance
Pinpointing Python Web Application Bottlenecks with py-spy and ..., accessed October 15, 2025, https://leapcell.io/blog/pinpointing-python-web-application-bottlenecks-with-py-spy-and-cprofile
