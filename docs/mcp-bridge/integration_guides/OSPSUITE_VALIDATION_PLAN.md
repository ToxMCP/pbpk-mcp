# ospsuite Backend Validation Plan

**Date**: November 9, 2025  
**Goal**: Validate full PBPK modeling capabilities with real ospsuite backend  
**Platform**: macOS Apple Silicon (amd64 emulation via QEMU)

## Current Status

### ✅ Completed
- In-memory adapter tested and validated
- HTTP smoke test passes (4/4 steps)
- Documentation created for both Gemini and Codex CLI
- Server configuration verified

### 🔄 In Progress
- **Docker build for linux/amd64 platform** (5-10 minutes)
  - Installing system dependencies
  - Will install .NET 8 runtime
  - Will install R 4.x
  - Will compile ospsuite R package

## Validation Steps

### Step 1: Build amd64 Docker Image ⏳ IN PROGRESS

**Command**:
```bash
docker build --pull --platform=linux/amd64 --tag mcp-bridge:amd64 .
```

**What it does**:
- Pulls Python 3.11-slim base image for amd64
- Installs system dependencies (build tools, libraries)
- Installs .NET 8 runtime (required by ospsuite's rClr bridge)
- Installs R and required packages
- Compiles ospsuite from GitHub
- Builds Python MCP bridge application

**Expected duration**: 5-10 minutes  
**Log file**: `/tmp/docker_build_ospsuite.log`

**Progress indicators**:
- `#10` - Installing curl, wget, gnupg (system tools)
- `#11` - Installing build dependencies (binutils, perl, etc.)
- Later: .NET installation
- Later: R installation
- Later: ospsuite compilation
- Final: "Successfully tagged mcp-bridge:amd64"

### Step 2: Run Container with Resource Caps

**Command**:
```bash
docker run --rm -p 8011:8000 \
  --memory=6g --memory-swap=6g --cpus=4 \
  -e JOB_BACKEND=thread \
  -e JOB_WORKER_THREADS=1 \
  -e UVICORN_NUM_WORKERS=1 \
  -e DOTNET_GCHeapLimitPercent=50 \
  -e R_MAX_VSIZE=2G \
  -e AUTH_ALLOW_ANONYMOUS=1 \
  mcp-bridge:amd64
```

**Resource caps explained**:
- `--memory=6g --memory-swap=6g`: Prevents memory spikes (Apple Silicon protection)
- `--cpus=4`: Limits CPU usage during QEMU emulation
- `JOB_WORKER_THREADS=1`: Single worker (avoids duplicating R/.NET stack)
- `UVICORN_NUM_WORKERS=1`: Single uvicorn worker
- `DOTNET_GCHeapLimitPercent=50`: Caps .NET garbage collector heap
- `R_MAX_VSIZE=2G`: Limits R vector heap size

**Port mapping**: 8011 (host) → 8000 (container)  
**Why**: Keeps same endpoint as in-memory mode for consistency

### Step 3: Verify ospsuite Backend

**Health check**:
```bash
curl http://127.0.0.1:8011/health | jq '.adapter'
```

**Expected response** (ospsuite mode):
```json
{
  "name": "subprocess",
  "populationSupported": true,
  "health": {
    "available": true,
    "r_version": "4.x.x",
    "ospsuite_version": "12.3.2",
    "r_path": "/usr/bin/R",
    "r_home": "/usr/lib/R",
    "ospsuite_library_path": "/usr/local/lib/R/site-library"
  }
}
```

**Key indicators**:
- `"name": "subprocess"` (not "inmemory") ✓
- `"populationSupported": true` ✓
- `"available": true` ✓
- ospsuite version reported ✓

**Compare with in-memory mode**:
```json
{
  "name": "inmemory",
  "populationSupported": false
}
```

### Step 4: Run MCP Smoke Test Against ospsuite

**Command**:
```bash
PBPK_MCP_ENDPOINT="http://127.0.0.1:8011/mcp" scripts/mcp_http_smoke.sh
```

**What it validates**:
1. `initialize` - MCP protocol handshake
2. `tools/list` - Tool discovery
3. `load_simulation` (critical) - Load .pkml with **real ospsuite**
4. `list_parameters` - Parameter inspection with **real ospsuite**

**Expected**: All 4 steps pass (same as in-memory, but using real engine)

**Difference from in-memory**:
- In-memory: Returns mock data
- ospsuite: Actual R/ospsuite processing of .pkml files

### Step 5: Test with MCP Clients

**HTTP-compatible clients** (ready to use):
- ✅ Direct curl/HTTP calls
- ✅ Codex CLI (if installed)
- ✅ Claude Desktop
- ✅ Cursor

**Gemini CLI status**:
- ⚠️ Version 0.13.0 primarily supports stdio transport
- ✅ HTTP endpoint works (validated via smoke test)
- 🔧 Needs: HTTP support update or stdio wrapper

**Test example** (curl):
```bash
# Load simulation
curl -s http://127.0.0.1:8011/mcp \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc":"2.0",
    "id":1,
    "method":"tools/call",
    "params":{
      "name":"load_simulation",
      "arguments":{"filePath":"tests/fixtures/demo.pkml","simulationId":"ospsuite-test"},
      "critical":true
    }
  }' | jq

# Run simulation
curl -s http://127.0.0.1:8011/mcp \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc":"2.0",
    "id":2,
    "method":"tools/call",
    "params":{
      "name":"run_simulation",
      "arguments":{"simulationId":"ospsuite-test"},
      "critical":true
    }
  }' | jq

# Get job status
curl -s http://127.0.0.1:8011/mcp \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc":"2.0",
    "id":3,
    "method":"tools/call",
    "params":{
      "name":"get_job_status",
      "arguments":{"jobId":"<job-id-from-previous>"}
    }
  }' | jq
```

### Step 6: Document Results

**Capture**:
- Health endpoint response
- Smoke test output
- Sample simulation run
- Performance metrics (startup time, memory usage)
- Any errors or warnings

**Update documentation**:
- CLI_TESTING_RESULTS.md
- gemini-cli-workflow.md
- codex-cli-workflow.md

## Performance Expectations

### In-Memory Mode (Baseline)
- Startup: < 3 seconds
- Memory: ~150MB
- CPU: Minimal

### ospsuite Mode (amd64 Container)
- Startup: 10-15 seconds (R/.NET initialization)
- Memory: 2-4GB (with 6GB cap)
- CPU: Higher (QEMU emulation overhead)
- Simulation time: Depends on model complexity

## Troubleshooting

### Build Issues
- **Long build time**: Normal for amd64 on Apple Silicon (QEMU emulation)
- **Memory errors during build**: Increase Docker memory limit in Docker Desktop
- **ospsuite install fails**: Check R and .NET installation logs in build output

### Runtime Issues
- **Container won't start**: Check resource limits, ensure Docker has enough memory
- **Health check shows inmemory**: Wrong image or missing platform flag
- **Simulation fails**: Check .pkml file path, verify ospsuite loaded correctly
- **Memory spikes**: Reduce worker threads, check resource caps are applied

### Performance Issues
- **Slow startup**: Expected on Apple Silicon (emulation overhead)
- **High CPU usage**: Normal for QEMU emulation, cap with `--cpus` flag
- **Out of memory**: Reduce `R_MAX_VSIZE` or increase container memory limit

## Success Criteria

✅ **Build Success**:
- Image tagged as `mcp-bridge:amd64`
- No build errors
- ospsuite package installed

✅ **Runtime Success**:
- Container starts without errors
- Health endpoint shows `"name": "subprocess"`
- ospsuite version reported

✅ **Functional Success**:
- Smoke test passes (4/4 steps)
- Can load .pkml files
- Can run simulations
- Job status tracking works

✅ **Integration Success**:
- HTTP clients can connect
- Tools execute correctly
- Results match expected format

## Next Steps After Validation

1. **Update documentation** with ospsuite findings
2. **Create stdio wrapper** for Gemini CLI (optional)
3. **Performance benchmarking** (compare in-memory vs ospsuite)
4. **CI/CD integration** (automated testing)
5. **Production deployment** guide with authentication

## Current Build Status

**Started**: ~5:08 PM  
**Log**: `/tmp/docker_build_ospsuite.log`  
**Progress**: Installing system dependencies (step #10, #11)  
**Next**: .NET installation, R installation, ospsuite compilation  
**ETA**: ~5:13-5:18 PM (5-10 minutes from start)

Monitor with:
```bash
tail -f /tmp/docker_build_ospsuite.log
```

Or check for completion:
```bash
docker images | grep mcp-bridge:amd64
