# Gemini CLI Integration Workflow

Complete guide for exercising the PBPK MCP server from Gemini CLI, covering both lightweight in-memory development mode and full ospsuite-backed container validation.

## Prerequisites

1. **Gemini CLI installed**: Verify with `gemini --version`
2. **PBPK MCP server repository**: Clone and navigate to the project root
3. **Docker Desktop** (optional, only for ospsuite mode): Ensure it's running
4. **Access token** (optional): Only needed if authentication is enabled

## Step 1: Configure Gemini CLI

Gemini stores MCP provider definitions in `~/.config/gemini/mcp.json`. Run `gemini mcp config` to confirm the path.

Add the PBPK server entry:

```json
{
  "providers": {
    "pbpk-mcp": {
      "transport": "http",
      "endpoint": "http://127.0.0.1:8011/mcp",
      "headers": {
        "Authorization": "Bearer <ACCESS_TOKEN>"
      }
    }
  }
}
```

**For development/testing without authentication**, omit the `headers` block entirely and ensure the server runs with `AUTH_ALLOW_ANONYMOUS=1`.

**Note on `critical` flag**: Gemini automatically sets `critical:true` in the MCP payload when you pass `--critical` on tool calls. This satisfies the confirmation requirement for mutating operations.

## Step 2: Start the PBPK MCP Server

Choose the mode appropriate for your workflow:

### Option A: Fast In-Memory Dev Mode (Recommended)

**Best for**: Everyday CLI work, Gemini/Codex integration testing, rapid iteration

**Advantages**:
- Starts in seconds
- Low memory footprint on Apple Silicon
- No Docker/emulation overhead
- Perfect for MCP protocol testing

**Command**:
```bash
export ADAPTER_BACKEND=inmemory
export JOB_WORKER_THREADS=1
export AUTH_ALLOW_ANONYMOUS=1
uvicorn mcp_bridge.app:create_app --factory --host 127.0.0.1 --port 8011 --workers 1
```

**What this does**:
- Uses lightweight in-memory adapter (no ospsuite dependency)
- Single worker thread to minimize resource usage
- Allows anonymous access for testing
- Binds to localhost port 8011

### Option B: Full ospsuite Backend (Container)

**Best for**: End-to-end validation, verifying ospsuite integration, production parity testing

**When to use**: Only when you need to validate actual ospsuite behavior or test with real `.pkml` models

#### Build the Image (linux/amd64 required for ospsuite)

```bash
docker build --pull --platform=linux/amd64 --tag mcp-bridge .
```

**Note**: This build takes 5-10 minutes and requires the amd64 platform because ospsuite's R/.NET dependencies are x86_64-only.

#### Run with Resource Limits (Apple Silicon Protection)

```bash
docker run --rm -p 8011:8000 \
  --memory=6g --memory-swap=6g --cpus=4 \
  -e JOB_BACKEND=thread \
  -e JOB_WORKER_THREADS=1 \
  -e UVICORN_NUM_WORKERS=1 \
  -e DOTNET_GCHeapLimitPercent=50 \
  -e R_MAX_VSIZE=2G \
  -e AUTH_ALLOW_ANONYMOUS=1 \
  mcp-bridge
```

**Resource caps explained**:
- `--memory=6g --memory-swap=6g`: Prevents memory spikes from overwhelming the host
- `--cpus=4`: Limits CPU usage during emulation
- `JOB_WORKER_THREADS=1`: Single worker to avoid duplicating R/.NET stack
- `DOTNET_GCHeapLimitPercent=50`: Caps .NET garbage collector heap
- `R_MAX_VSIZE=2G`: Limits R vector heap size

**Warning**: This mode is slower due to QEMU emulation on Apple Silicon. Use Option A unless you specifically need ospsuite validation.

## Step 3: Verify the MCP Transport (Smoke Test)

Before using Gemini CLI, verify the server is responding correctly:

```bash
PBPK_MCP_ENDPOINT=http://127.0.0.1:8011/mcp scripts/mcp_http_smoke.sh
```

**Expected output**:
```
[1/4] initialize
"2025-03-26"
[2/4] tools.list
[3/4] load_simulation (critical=true)
[4/4] list_parameters
Smoke test succeeded for simulation smoke-<timestamp>
```

**What this validates**:
1. MCP protocol initialization
2. Tool discovery
3. Critical tool execution (load_simulation)
4. Parameter inspection

If this passes, the server is ready for Gemini CLI.

## Step 4: Use Gemini CLI to Drive the MCP

With the server running, try these commands:

### List Available Tools

```bash
gemini mcp call pbpk-mcp tools.list | jq '.tools | length'
```

**Expected**: Returns the count of available tools (should be 10+)

### Load a Simulation (Critical Operation)

```bash
gemini mcp call pbpk-mcp tools.call \
  --name load_simulation \
  --arguments '{"filePath":"tests/fixtures/demo.pkml","simulationId":"gemini-demo"}' \
  --critical
```

**Important**: The `--critical` flag is required for `load_simulation` because it's a mutating operation that requires confirmation.

**Expected response**:
```json
{
  "result": {
    "content": [
      {
        "type": "json",
        "json": {
          "simulationId": "gemini-demo",
          "status": "loaded",
          "message": "Simulation loaded successfully"
        }
      }
    ]
  }
}
```

### Inspect Parameters

```bash
gemini mcp call pbpk-mcp tools.call \
  --name list_parameters \
  --arguments '{"simulationId":"gemini-demo"}'
```

**Expected**: Returns a list of parameters with paths, values, and units.

### Run a Simulation

```bash
gemini mcp call pbpk-mcp tools.call \
  --name run_simulation \
  --arguments '{"simulationId":"gemini-demo"}' \
  --critical
```

**Expected**: Returns a job ID for tracking the simulation execution.

### Poll Job Status

```bash
gemini mcp call pbpk-mcp tools.call \
  --name get_job_status \
  --arguments '{"jobId":"<job-id-from-previous-call>"}'
```

**Expected**: Returns job status (`pending`, `running`, `completed`, or `failed`) and results when complete.

## Step 5: Verify ospsuite-Specific Behavior (Option B Only)

If running the ospsuite container, verify the backend is functioning:

### Check Health Endpoint

```bash
curl http://localhost:8011/health | jq '.adapter'
```

**Expected output**:
```json
{
  "name": "subprocess",
  "populationSupported": true,
  "health": {
    "status": "healthy",
    "r_version": "4.x.x",
    "ospsuite_version": "12.x.x"
  }
}
```

**Key indicators**:
- `name: "subprocess"` confirms ospsuite backend is active
- `populationSupported: true` indicates full functionality
- `health.status: "healthy"` means R and ospsuite are operational

### Run a Simulation with ospsuite

```bash
gemini mcp call pbpk-mcp tools.call \
  --name run_simulation \
  --arguments '{"simulationId":"gemini-demo"}' \
  --critical
```

Then poll for completion:

```bash
gemini mcp call pbpk-mcp tools.call \
  --name get_job_status \
  --arguments '{"jobId":"<job-id>"}'
```

If the job completes successfully and returns results, you've confirmed the ospsuite backend is functioning under emulation.

## Troubleshooting

### Authentication Errors

**Symptom**: `500 Internal Server Error` with message about authentication configuration

**Cause**: Server expects authentication but `AUTH_ALLOW_ANONYMOUS` is not set

**Fix**:
```bash
# Restart server with anonymous access
export AUTH_ALLOW_ANONYMOUS=1
uvicorn mcp_bridge.app:create_app --factory --host 127.0.0.1 --port 8011 --workers 1
```

Or provide a valid bearer token in the Gemini configuration.

### Memory Spikes (Option B)

**Symptom**: Docker container consumes excessive memory or system becomes unresponsive

**Cause**: Running ospsuite under emulation without resource limits, or multiple worker threads

**Fix**:
1. Ensure you're using the resource-capped `docker run` command from Step 2, Option B
2. Verify `JOB_WORKER_THREADS=1` and `UVICORN_NUM_WORKERS=1`
3. Consider switching to Option A (in-memory mode) if ospsuite validation isn't required

### Connection Failures

**Symptom**: `scripts/mcp_http_smoke.sh` fails to connect, or Gemini reports connection errors

**Cause**: Server isn't running, or firewall is blocking port 8011

**Fix**:
1. Verify server is running: `curl http://localhost:8011/health`
2. Check if port is in use: `lsof -i :8011`
3. Ensure no firewall rules block localhost connections
4. Verify the endpoint URL in `~/.config/gemini/mcp.json` matches the server port

### Tool Not Found Errors

**Symptom**: Gemini reports "Method not found" or tool doesn't exist

**Cause**: Typo in tool name, or server hasn't loaded tools correctly

**Fix**:
1. List available tools: `gemini mcp call pbpk-mcp tools.list | jq '.tools[].name'`
2. Verify exact tool name spelling
3. Check server logs for startup errors

### File Path Errors (Option B)

**Symptom**: `load_simulation` fails with "file not found" or "path not allowed"

**Cause**: `.pkml` file path is outside `MCP_MODEL_SEARCH_PATHS` or doesn't exist in container

**Fix**:
- For container mode, use paths that exist inside the container: `tests/fixtures/demo.pkml` is copied to `/app/tests/fixtures/demo.pkml`
- To use custom models, mount a volume: `-v /path/to/models:/models` and set `-e MCP_MODEL_SEARCH_PATHS=/models`

## Workflow Summary

**Quick iteration cycle** (Option A):
1. Start in-memory server (< 5 seconds)
2. Run smoke test to verify
3. Use Gemini CLI for rapid testing
4. Iterate on code changes
5. Restart server and repeat

**Full validation cycle** (Option B):
1. Build amd64 container (one-time, 5-10 minutes)
2. Run with resource caps
3. Verify health endpoint shows ospsuite
4. Run comprehensive tests with Gemini CLI
5. Validate results match expected behavior

## Next Steps

- **For development**: Stick with Option A for fast iteration
- **For CI/CD**: Use Option A for unit/integration tests, Option B for end-to-end validation
- **For production**: Deploy Option B with proper authentication and resource limits
- **For debugging**: Enable `LOG_LEVEL=DEBUG` to see detailed request/response logs

## Related Documentation

- [MCP Integration Overview](mcp_integration.md) - Multi-client setup guide
- [Codex CLI Workflow](codex-cli-workflow.md) - Parallel guide for Codex CLI
- [API Reference](../reference/api.md) - Complete REST and MCP endpoint documentation
- [Authentication Guide](../authentication.md) - JWT configuration and RBAC setup
