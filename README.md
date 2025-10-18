# MCP Bridge Server

Bridge service exposing Open Systems Pharmacology Suite capabilities via the Model Context Protocol.

## Getting Started

```bash
make install
make lint
make test
```

Detailed walkthroughs for REST and agent flows live under
`docs/mcp-bridge/getting-started/quickstart-cli.md` and
`docs/mcp-bridge/getting-started/quickstart-agent.md`.

### Agent Workflows

- `run_agent.py demo` executes the end-to-end confirm-before-execute pipeline using the in-memory adapter.
- `run_agent.py` (interactive mode) exercises the LangGraph agent loop and prompts for confirmation before
  mutating or running simulations.
- Follow the Quickstart guides in `docs/mcp-bridge/getting-started/` for step-by-step tutorials.
- REST surface area and configuration variables are documented in `docs/mcp-bridge/reference/api.md`
  and `docs/mcp-bridge/reference/configuration.md`.
- Documentation for prompt policies and tooling lives in `docs/mcp-bridge/agent-prompts.md`.
- Authentication/authorization behaviour and configuration is documented in `docs/mcp-bridge/authentication.md`.
- Immutable audit trail design and verification plan is in `docs/mcp-bridge/audit-trail.md`.

### Sensitivity Analysis

- The reusable sensitivity utilities live in `src/mcp_bridge/agent/sensitivity.py`.
- Refer to `docs/mcp-bridge/sensitivity-analysis.md` for configuration and workflow details.
- Unit coverage is provided via `tests/unit/test_sensitivity_analysis.py`.

## Project Layout

- `src/` – package source code.
- `tests/` – unit and integration tests.
- `docs/` – architecture, contracts, and threat model reference material.
- `docs/tools/` – per-tool documentation for the MCP surface.

## Configuration

Settings are supplied through environment variables (a `.env` file is supported):

- `HOST` – interface the HTTP server binds to (default `0.0.0.0`).
- `PORT` – TCP port for the HTTP server (default `8000`).
- `LOG_LEVEL` – log level for structlog output (default `INFO`).
- `SERVICE_NAME` – emitted service identifier (default `mcp-bridge`).
- `SERVICE_VERSION` – override for the version reported in `/health` (defaults to package version).
- `ENVIRONMENT` – environment tag (default `development`).
- `MCP_MODEL_SEARCH_PATHS` – optional colon-separated list of directories that contain PBPK
  `.pkml` files. If unset, the server allows paths under `tests/fixtures` for local testing.
- `ADAPTER_BACKEND` – `inmemory` (default) or `subprocess`. The latter shells out to an R/ospsuite bridge.
- `ADAPTER_REQUIRE_R_ENV` – set to `true` to fail startup if R/ospsuite cannot be detected (default `false`).
- `ADAPTER_TIMEOUT_MS` – default timeout (in milliseconds) for adapter operations (default `30000`).
- `ADAPTER_R_PATH` / `ADAPTER_R_HOME` / `ADAPTER_R_LIBS` – explicit R binary, home, and library locations.
- `OSPSUITE_LIBS` – absolute path to ospsuite R libraries when using the subprocess backend.
- `ADAPTER_MODEL_PATHS` – colon-separated allow list of `.pkml` directories when using the subprocess backend.
- `JOB_WORKER_THREADS` – size of the in-process job worker pool (default `2`).
- `JOB_TIMEOUT_SECONDS` – execution timeout for queued simulation jobs (default `300`).
- `JOB_MAX_RETRIES` – automatic retry attempts for failed jobs (default `0`).
- `AUDIT_ENABLED` – toggles immutable audit logging (default `true`).
- `AUDIT_STORAGE_PATH` – filesystem path used for audit JSONL logs (default `var/audit`).
- `MCP_RUN_R_TESTS` – opt-in flag for R-dependent integration tests (`1` runs them, default `0` skips).
- `AUTH_ISSUER_URL` / `AUTH_AUDIENCE` / `AUTH_JWKS_URL` / `AUTH_JWKS_CACHE_SECONDS` – configure JWT validation against your IdP.
- `AUTH_DEV_SECRET` – optional HS256 secret for local development/testing tokens.

Refer to `docs/mcp-bridge/reference/configuration.md` for an exhaustive table of supported variables.

### R / ospsuite Integration

By default the application uses the in-memory adapter suitable for local development and CI without
an R toolchain. To exercise the subprocess-backed adapter, set:

```bash
export ADAPTER_BACKEND=subprocess
export MCP_MODEL_SEARCH_PATHS=/path/to/models
export MCP_RUN_R_TESTS=1
```

You can then run the full test suite (including R-dependent integrations) with:

```bash
make test
```

If the R environment is optional, leave `ADAPTER_REQUIRE_R_ENV` unset so the service continues to
start even when ospsuite is unavailable. Setting `ADAPTER_REQUIRE_R_ENV=true` enforces a hard failure.

## Container Workflow

```bash
make build-image          # Build the runtime image
make run-image            # Run locally (binds :8000)
curl http://localhost:8000/health
```

The image runs as a non-root user and includes an embedded health check that polls `/health` every 30 seconds.
