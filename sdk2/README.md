# Optional stable SDK2 transport for PBPK MCP

**Unreleased review candidate.** This separate `pbpk-mcp-sdk2` package uses stable MCP Python SDK 2.2.0 for protocol `2026-07-28`. The PBPK backend remains v0.5.0 with its original dependencies, scientific contracts and deprecated Python `mcp` compatibility imports.

The environments must stay separate: the deprecated backend `mcp` package and official SDK `mcp` package share a name. Do not add the SDK dependency to the backend environment. The transport delegates domain calls to a fixed backend origin; simulations, authentication, role checks, confirmations, idempotency, jobs, deadlines, cancellation, audit and persistence remain owned by the backend. It does not implement new scientific algorithms or durable MCP tasks.

## Run locally

Start the existing backend on loopback port 8001 using its existing configuration. Install this transport separately with `uv sync --locked --project sdk2`. Remove the backend's `PYTHONPATH` from the transport environment so its deprecated namespace cannot shadow the SDK.

```sh
env -u PYTHONPATH PBPK_SDK2_BACKEND_URL=http://127.0.0.1:8001 sdk2/.venv/bin/pbpk-mcp-sdk2-http --port 8000
```

Existing HTTP clients keep `/mcp` or `/mcp/jsonrpc`: handshake-era requests pass through to the backend. Modern requests use the actual SDK2 server and callbacks. Local stdio uses `pbpk-mcp-sdk2-stdio`, with a valid backend bearer token supplied privately as `PBPK_SDK2_BEARER_TOKEN`. The configured token is used **only for stdio**; HTTP callers always supply their own credentials.

## Hosting and compatibility

`PBPK_SDK2_BACKEND_URL` must be an origin without credentials, path, query or fragment. Remote backends require HTTPS; HTTP is allowed only on loopback. Redirects are disabled and incoming URLs cannot select a backend. The transport has no read timeout, leaving execution deadlines to the existing backend; connection/pool acquisition timeouts are ten seconds.

Set comma-separated `PBPK_SDK2_ALLOWED_HOSTS` and `PBPK_SDK2_ALLOWED_ORIGINS` before public hosting. Defaults accept loopback authorities/origins with any port. Modern browser preflights allow the standard SDK routing headers and configured exact origins or wildcard ports. Existing legacy requests retain backend responses and CORS behavior. `PBPK_SDK2_MAX_REQUEST_BYTES` is positive and defaults to 4 MiB for both MCP HTTP paths, including chunked bodies.

Modern catalogs retain standard tool annotations. The existing `critical`, `requiresConfirmation` and `roles` extensions move to tool `_meta["org.toxmcp/toolPolicy"]`. Existing result annotations move to result `_meta["org.toxmcp/resultAnnotations"]`; scientific text/structured content are retained. Catalog/resource hints are private and zero-TTL so role/session changes stay visible. Handshake-era HTTP representations remain unchanged.

Modern callers send explicit confirmation/idempotency options through request `_meta["org.toxmcp/invocation"]`, using `critical` and `idempotencyKey`. The backend still enforces permissions before confirmation and owns idempotency. Existing `X-MCP-Confirm` headers and legacy top-level options remain available. Job timeout arguments, job IDs, cancellation and result retrieval pass to the existing tools.

Build this package independently with `uv build --project sdk2`. Its wheel contains `pbpk_mcp_sdk2`, with no backend `mcp` package. A public rollout requires separate review of gateway routing, both environments and backend configuration. No deployment or release is performed by this PR.
