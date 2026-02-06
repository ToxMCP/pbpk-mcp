# Integrating the PBPK MCP Server with Coding Agents

The PBPK MCP server exposes JSON-RPC 2.0 over HTTP at `POST /mcp`. Any MCP-aware
client (Codex CLI, Gemini CLI, Claude Code, etc.) can connect as soon as the
transport is reachable and you supply the appropriate headers.

## Quick Start Guides

For detailed, end-to-end workflows with specific CLI tools:

- **[Gemini CLI Workflow](gemini-cli-workflow.md)** - Complete guide for Gemini CLI integration, including in-memory and ospsuite modes, smoke testing, and troubleshooting
- **[Codex CLI Workflow](codex-cli-workflow.md)** - Parallel guide for Codex CLI with advanced usage examples and command chaining

These guides provide step-by-step instructions for both lightweight development (in-memory adapter) and full validation (ospsuite container) modes.

## Prerequisites

1. Install and start the PBPK MCP server (see `README.md` or `docs/mcp-bridge/getting-started/`).
2. Ensure the server can reach your `.pkml` models (set `MCP_MODEL_SEARCH_PATHS`).
3. Obtain an access token if authentication is enabled (development mode allows anonymous access when `AUTH_ALLOW_ANONYMOUS=1`).

## Codex CLI

Create or edit `~/.config/openai/mcp.json`:

```json
{
  "providers": [
    {
      "name": "pbpk-mcp",
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp",
      "headers": {
        "Authorization": "Bearer <ACCESS_TOKEN>"
      }
    }
  ]
}
```

Reload Codex, then:

```bash
codex tools list pbpk-mcp
codex tools call pbpk-mcp tools.call --name load_simulation --arguments '{"filePath":"tests/fixtures/demo.pkml","simulationId":"codex-demo"}' --critical
codex tools call pbpk-mcp tools.call --name list_parameters --arguments '{"simulationId":"codex-demo"}'
```

> Pass `--critical` when the tool is marked `requiresConfirmation: true`. Codex automatically sets `critical:true` in the JSON-RPC payload.

## Gemini CLI

Update `~/.config/gemini/mcp.json` (path reported by `gemini mcp config`):

```json
{
  "providers": {
    "pbpk-mcp": {
      "transport": "http",
      "endpoint": "http://127.0.0.1:8000/mcp",
      "headers": {
        "Authorization": "Bearer <ACCESS_TOKEN>"
      }
    }
  }
}
```

Smoke test:

```bash
gemini mcp call pbpk-mcp tools.list | jq '.tools | length'
gemini mcp call pbpk-mcp tools.call --name load_simulation --arguments '{"filePath":"tests/fixtures/demo.pkml","simulationId":"gemini-demo"}' --critical
gemini mcp call pbpk-mcp tools.call --name list_parameters --arguments '{"simulationId":"gemini-demo"}'
```

## Claude Code / Cursor

Add a provider (CLI: `~/.config/claude/mcp.json`, Cursor: MCP settings panel):

```json
{
  "name": "pbpk-mcp",
  "type": "http",
  "url": "http://127.0.0.1:8000/mcp",
  "headers": {
    "Authorization": "Bearer <ACCESS_TOKEN>"
  }
}
```

Critical tools prompt for confirmation in the chat UI; Claude sets `critical:true` automatically.

## HTTP smoke test

Run `scripts/mcp_http_smoke.sh` after exporting any required auth headers:

```bash
PBPK_MCP_ENDPOINT="http://127.0.0.1:8000/mcp" PBPK_MCP_AUTH_HEADER="Authorization: Bearer $TOKEN" \
  scripts/mcp_http_smoke.sh
```

The script performs `initialize`, `tools/list`, and a small `load_simulation` / `list_parameters` workflow. Exit code is non-zero on failure.

## Confirmation recap

- **JSON-RPC**: set `critical:true` for `load_simulation`, `set_parameter_value`, `run_simulation`, `run_population_simulation`, and `run_sensitivity_analysis`. The legacy `X-MCP-Confirm` header is optional.
- **REST**: include `{ "confirm": true }` in the request body for the endpoints above.
- Missing confirmation hints yield HTTP `428` with the `ConfirmationRequired` error code.

## Troubleshooting

| Symptom | Likely cause | Suggested fix |
| --- | --- | --- |
| `401 Unauthorized` | Missing/expired token | Refresh the bearer token or enable `AUTH_ALLOW_ANONYMOUS` in dev. |
| `428 ConfirmationRequired` | Tool flagged `requiresConfirmation` without `critical:true`/`confirm:true` | Set `critical:true` (JSON-RPC) or `confirm:true` (REST). |
| `404 NotFound` after `load_simulation` | Model path outside `MCP_MODEL_SEARCH_PATHS` | Update `MCP_MODEL_SEARCH_PATHS` to include the directory containing `.pkml` files. |
| `Method not found` | Typo in tool name | Run `tools.list` to inspect exact names. |

For deeper debugging, enable structured logs (`LOG_LEVEL=DEBUG`) and inspect the server output.
