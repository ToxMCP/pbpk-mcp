# Configuration Reference

The MCP Bridge reads configuration from environment variables (optionally via
`.env`). Defaults originate from `src/mcp_bridge/config.py` and are validated by
`AppConfig`. This page groups settings by concern and lists the corresponding
environment variables, defaults, and notes.

## Server & logging

| Variable | Default | Notes |
| --- | --- | --- |
| `HOST` | `0.0.0.0` | Bind address for Uvicorn. |
| `PORT` | `8000` | TCP port exposed by the API. |
| `LOG_LEVEL` | `INFO` | Accepts standard logging levels (`DEBUG`, `INFO`, `WARNING`, ...). |
| `SERVICE_NAME` | `mcp-bridge` | Service identifier emitted in logs and `/health`. |
| `SERVICE_VERSION` | package version | Override reported version (useful for CI builds). |
| `ENVIRONMENT` | `development` | Arbitrary tag captured in `/health` and structured logs. |
| `UVICORN_RELOAD` | `0` | When set to `1`, enables hot-reload for local development (module guard in `main.py`). |

## Adapter & model discovery

| Variable | Default | Notes |
| --- | --- | --- |
| `ADAPTER_BACKEND` | `inmemory` | Either `inmemory` (mock) or `subprocess` (ospsuite bridge). |
| `ADAPTER_REQUIRE_R_ENV` | `false` | Fail startup if R/ospsuite is unavailable. |
| `ADAPTER_TIMEOUT_MS` | `30000` | Default adapter call timeout (milliseconds). |
| `ADAPTER_R_PATH` | unset | Explicit path to the R binary. |
| `ADAPTER_R_HOME` | unset | Override `R_HOME` when spawning subprocesses. |
| `ADAPTER_R_LIBS` | unset | Additional R library lookup path. |
| `OSPSUITE_LIBS` | unset | Absolute path to ospsuite R libraries. |
| `ADAPTER_MODEL_PATHS` | unset | Colon-separated allow list of directories for `.pkml` files (used by the subprocess adapter). |
| `MCP_MODEL_SEARCH_PATHS` | repo fixtures | Colon-separated directories allowed for `load_simulation`; respected by both adapters and defensive checks. |
| `R_PATH`, `R_HOME`, `R_LIBS` | inherited | Evaluated during environment detection as fallbacks. |

## Job service & async execution

| Variable | Default | Notes |
| --- | --- | --- |
| `JOB_WORKER_THREADS` | `2` | Thread count for the in-process worker pool. |
| `JOB_TIMEOUT_SECONDS` | `300` | Default job timeout (seconds). |
| `JOB_MAX_RETRIES` | `0` | Automatic retry attempts for failed jobs. |
| `JOB_RETENTION_SECONDS` | `604800` | Retention window (seconds) for completed job metadata and stored results; `0` disables purging. |

## Storage, population workloads, and audit

| Variable | Default | Notes |
| --- | --- | --- |
| `POPULATION_STORAGE_PATH` | `var/population-results` | Root directory for claim-check population artefacts. Relative paths resolve against the working directory. |
| `POPULATION_RETENTION_SECONDS` | `604800` | Retention window (seconds) for population artefacts before automatic cleanup. |
| `AUDIT_ENABLED` | `true` | Toggle immutable audit logging for tool invocations. |
| `AUDIT_STORAGE_PATH` | `var/audit` | Directory for JSONL audit chain files (supports hash chaining). |
| `AGENT_CHECKPOINTER_PATH` | `var/agent/checkpoints.sqlite` | SQLite database used by the LangGraph agent checkpointer to persist conversation state. |

## Authentication & authorisation

| Variable | Default | Notes |
| --- | --- | --- |
| `AUTH_ISSUER_URL` | unset | OIDC issuer to validate `iss` claims. |
| `AUTH_AUDIENCE` | unset | Expected `aud` claim. |
| `AUTH_JWKS_URL` | unset | JWKS endpoint for public keys. |
| `AUTH_JWKS_CACHE_SECONDS` | `900` | Cache TTL for JWKS responses. |
| `AUTH_DEV_SECRET` | unset | HS256 secret for development tokens (see quickstart guides). |
| `AUTH_RATE_LIMIT_PER_MINUTE` | `120` | Per-client request ceiling; exceeding the limit returns `429 Too Many Requests`. |
| `AUTH_CLOCK_SKEW_SECONDS` | `60` | Allowed clock skew when validating `exp`, `iat`, and `nbf` claims. |
| `AUTH_REPLAY_WINDOW_SECONDS` | `300` | Time window used to flag reused `jti` values (token replay protection). |
| `AUTH_ALLOW_ANONYMOUS` | `false` | Permit anonymous access (development/testing only). |

## Testing & CI helpers

| Variable | Default | Notes |
| --- | --- | --- |
| `MCP_RUN_R_TESTS` | `0` | When `1`, enables R-dependent integration tests (CI job `r-tests`). |
| `PYTHONPATH` | varies | Add `src/` to leverage the CLI tools without installation. |

## Configuration tips

- Use `.env` for local overrides; `AppConfig.from_env()` loads it automatically.
- Always ensure `MCP_MODEL_SEARCH_PATHS` points to trusted directories to prevent path traversal attacks.
- When swapping to the subprocess adapter, set `ADAPTER_REQUIRE_R_ENV=true` in production to fail fast if R/ospsuite is unavailable.
- For population workloads, provision fast storage for `POPULATION_STORAGE_PATH`; the agent quickstart demonstrates downloads using claim-check URIs.
