# Sequence Diagrams

The following sequence diagrams describe how the MCP Bridge communicates with the host agent and the ospsuite-backed R adapter. Each interaction propagates the `X-Correlation-Id` header so logs can be stitched together across the boundary.

## Load Simulation

```mermaid
sequenceDiagram
    participant Client as MCP Host
    participant Bridge as MCP Bridge Server
    participant Adapter as R Adapter
    participant R as ospsuite R Runtime

    Client->>Bridge: POST /load_simulation {filePath}
    activate Bridge
    note right of Bridge: Validate path, ACL, and dedupe simulationId
    Bridge->>Adapter: init_if_needed()
    Adapter->>R: library(ospsuite)
    Adapter-->>Bridge: ok
    Bridge->>Adapter: load_simulation(filePath)
    Adapter->>R: loadSimulation(filePath)
    R-->>Adapter: SimulationRef
    Adapter-->>Bridge: {simulationId, metadata}
    Bridge-->>Client: 201 {simulationId, metadata}
    deactivate Bridge
```

## List Parameters

```mermaid
sequenceDiagram
    participant Client as MCP Host
    participant Bridge as MCP Bridge Server
    participant Adapter as R Adapter
    participant R as ospsuite R Runtime

    Client->>Bridge: POST /list_parameters {simulationId, searchPattern}
    activate Bridge
    Bridge->>Bridge: authorize + rate-limit
    Bridge->>Adapter: list_parameters(simulationId, pattern)
    Adapter->>R: getAllParametersMatching(sim, pattern)
    R-->>Adapter: ParameterSet
    Adapter-->>Bridge: [ParameterSummary]
    Bridge-->>Client: 200 {parameters, nextPageToken}
    deactivate Bridge
```

## Parameter Update With Validation

```mermaid
sequenceDiagram
    participant Client as MCP Host
    participant Bridge as MCP Bridge Server
    participant Adapter as R Adapter
    participant R as ospsuite R Runtime

    Client->>Bridge: POST /set_parameter_value {simulationId, path, value, unit}
    activate Bridge
    Bridge->>Bridge: validate payload + numeric guards
    alt invalid input
        Bridge-->>Client: 400 ErrorResponse(InvalidInput)
    else ok
        Bridge->>Adapter: set_parameter_value(simulationId, path, value, unit)
        Adapter->>R: setParameterValues(sim, path, value, unit)
        alt ospsuite raises error
            R-->>Adapter: error
            Adapter-->>Bridge: Error(InteropError)
            Bridge-->>Client: 502 ErrorResponse(InteropError)
        else success
            R-->>Adapter: ok
            Adapter-->>Bridge: ParameterValue
            Bridge-->>Client: 200 {parameter}
        end
    end
    deactivate Bridge
```

## Async Simulation Run and Result Retrieval

```mermaid
sequenceDiagram
    actor Scientist as User
    participant Client as MCP Host
    participant Bridge as MCP Bridge Server
    participant Queue as Job Queue
    participant Worker as Simulation Worker
    participant Adapter as R Adapter
    participant R as ospsuite R Runtime

    Scientist->>Client: Run simulation
    Client->>Bridge: POST /run_simulation {simulationId, runId}
    activate Bridge
    Bridge->>Queue: enqueue(jobDescriptor)
    Queue-->>Bridge: jobId
    Bridge-->>Client: 202 {jobId, queuedAt}
    deactivate Bridge
    loop Poll status
        Client->>Bridge: POST /get_job_status {jobId}
        Bridge->>Queue: get_status(jobId)
        Queue-->>Bridge: status=running
        Bridge-->>Client: 200 {status:\"running\"}
        alt cancellation requested
            Client->>Bridge: POST /cancel_job {jobId}
            Bridge->>Queue: cancel(jobId)
            Queue-->>Bridge: status=cancelled
            Bridge-->>Client: 200 {status:\"cancelled\", cancelledAt}
            break
        end
    end
    opt cancelled before execution
        Note over Queue,Worker: Worker does not receive the job; queue records terminal state.
    end
    Queue->>Worker: dispatch(jobId)
    Worker->>Adapter: run_simulation(simulationId, config)
    Adapter->>R: runSimulations(sim, config)
    R-->>Adapter: resultsHandle
    Adapter-->>Worker: {resultsId}
    Worker->>Queue: mark_succeeded(jobId, resultsId)
    Client->>Bridge: POST /get_job_status {jobId}
    Bridge->>Queue: get_status(jobId)
    Queue-->>Bridge: status=succeeded, resultsId
    Bridge-->>Client: 200 {status:\"succeeded\", resultHandle}
    Client->>Bridge: POST /get_simulation_results {resultsId}
    Bridge->>Adapter: get_results(resultsId)
    Adapter->>R: getOutputValues(resultsId)
    R-->>Adapter: ResultSet
    Adapter-->>Bridge: normalized JSON
    Bridge-->>Client: 200 {series}
```
