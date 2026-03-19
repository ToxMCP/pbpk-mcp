# MCP Payload Conventions

This workspace now uses a small stable response contract for the OECD-enhanced MCP tools that are patched in-repo.

Current contract version:

- `pbpk-mcp.v1`

Applied tools:

- `discover_models`
- `validate_model_manifest`
- `load_simulation`
- `validate_simulation_request`
- `export_oecd_report`
- `get_job_status`
- `get_results`

## Stable Top-Level Fields

All enhanced tool responses now include:

- `tool`
  - exact MCP tool name that produced the payload
- `contractVersion`
  - stable payload contract version for client-side branching

Model-bound enhanced responses also flatten backend information when available:

- `backend`
  - `ospsuite` or `rxode2`

## Tool-Specific Notes

- `load_simulation`
  - returns `simulationId`, `backend`, `metadata`, `capabilities`, `profile`, `validation`, `qualificationState`, and `warnings`
- `discover_models`
  - returns paginated discoverable model entries from disk, including `filePath`, `backend`, `discoveryState`, and `loadedSimulationIds`
- `validate_model_manifest`
  - returns `filePath`, `backend`, `runtimeFormat`, and `manifest`
  - `manifest` includes `manifestStatus`, `qualificationState`, section coverage, and static issues
- `validate_simulation_request`
  - returns `simulationId`, `backend`, `validation`, `profile`, `capabilities`, `qualificationState`, and `warnings`
- `export_oecd_report`
  - returns `simulationId`, `backend`, `generatedAt`, `qualificationState`, and `report`
  - `report` includes `qualificationState`, `profile`, `validation`, `oecdChecklist`, `oecdChecklistScore`, `missingEvidence`, `performanceEvidence`, and an optional `parameterTable`
- `get_job_status`
  - returns top-level `jobId`, `status`, `resultId`, and `resultHandle.resultsId`
  - still includes nested `job` for backward compatibility
- `get_results`
  - returns `resultsId`, `simulationId`, `backend`, `generatedAt`, `metadata`, and `series`

## Compatibility Rule

New convenience fields may be added, but existing stable fields in `pbpk-mcp.v1` should not be removed or renamed without bumping `contractVersion`.
