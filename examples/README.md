# PBPK MCP Agent Examples

This directory contains comprehensive examples demonstrating the full capabilities of the PBPK Model Context Protocol (MCP) server. All examples execute against the **Real OSPSuite Physics Engine**.

## Prerequisites

- The MCP Server must be running (`docker compose up`).
- `Acetaminophen_Pregnancy.pkml` must be in `var/` (auto-provisioned).

## Use Cases

### 1. Brain Barrier Distribution (`01_brain_barrier_distribution.py`)
**Goal:** Validate physiological distribution of a drug.
- Loads model.
- Configures adult physiology.
- Runs simulation.
- Extracts Brain vs Blood exposure (AUC) to confirm BBB crossing.

### 2. Manual Sensitivity Analysis (`02_liver_volume_sensitivity.py`)
**Goal:** Analyze impact of Liver Volume on clearance using a custom workflow.
- Sweeps Liver Volume (0.75L, 1.5L, 3.0L).
- Runs simulations sequentially.
- Demonstrates how reduced liver volume increases brain exposure (lower clearance).

### 3. Virtual Population (`03_virtual_population_variability.py`)
**Goal:** Simulate a cohort with varying Age and BMI.
- Creates a virtual cohort.
- Runs individuals.
- Aggregates population statistics.

### 4. Parameter Exploration (`04_parameter_exploration.py`)
**Goal:** Inspect and validate model parameters.
- Uses `list_parameters` with search patterns.
- Uses `get_parameter_value` to inspect units.
- Uses `set_parameter_value` to modify state.

### 5. Job Control (`05_job_control.py`)
**Goal:** Demonstrate asynchronous job management.
- Submits a job.
- Polls status (`queued`, `running`, `succeeded`).
- Demonstrates cancellation workflow.

### 6. Automated Sensitivity Tool (`06_sensitivity_tool_demo.py`)
**Goal:** Use the high-level `run_sensitivity_analysis` tool.
- Defines parameter configuration (Liver Volume deltas).
- Offloads the entire sweep to the server.
- Returns a structured report and CSV data.

## Running

```bash
python3 examples/01_brain_barrier_distribution.py
python3 examples/02_liver_volume_sensitivity.py
python3 examples/03_virtual_population_variability.py
python3 examples/04_parameter_exploration.py
python3 examples/05_job_control.py
python3 examples/06_sensitivity_tool_demo.py
```

Outputs are saved to `examples/output_XX.txt`.