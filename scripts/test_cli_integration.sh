#!/usr/bin/env bash
set -euo pipefail

# Test script for Gemini and Codex CLI integration with PBPK MCP server
# This script starts the server in in-memory mode, runs tests, and cleans up

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVER_PORT=8011
SERVER_PID=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

cleanup() {
    if [[ -n "$SERVER_PID" ]]; then
        log_info "Stopping server (PID: $SERVER_PID)..."
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
}

trap cleanup EXIT INT TERM

# Check prerequisites
log_info "Checking prerequisites..."

if ! command -v gemini &> /dev/null; then
    log_warn "Gemini CLI not found in PATH"
    GEMINI_AVAILABLE=false
else
    log_info "✓ Gemini CLI found: $(which gemini)"
    GEMINI_AVAILABLE=true
fi

if ! command -v codex &> /dev/null; then
    log_warn "Codex CLI not found in PATH"
    CODEX_AVAILABLE=false
else
    log_info "✓ Codex CLI found: $(which codex)"
    CODEX_AVAILABLE=true
fi

if [[ "$GEMINI_AVAILABLE" == "false" ]] && [[ "$CODEX_AVAILABLE" == "false" ]]; then
    log_error "Neither Gemini nor Codex CLI found. Please install at least one."
    exit 1
fi

# Start the server
log_info "Starting PBPK MCP server in in-memory mode on port $SERVER_PORT..."

cd "$PROJECT_ROOT"

export ADAPTER_BACKEND=inmemory
export JOB_WORKER_THREADS=1
export AUTH_ALLOW_ANONYMOUS=1

uvicorn mcp_bridge.app:create_app --factory --host 127.0.0.1 --port "$SERVER_PORT" --workers 1 > /tmp/pbpk_mcp_server.log 2>&1 &
SERVER_PID=$!

log_info "Server started with PID: $SERVER_PID"

# Wait for server to be ready
log_info "Waiting for server to be ready..."
for i in {1..30}; do
    if curl -s "http://127.0.0.1:$SERVER_PORT/health" > /dev/null 2>&1; then
        log_info "✓ Server is ready!"
        break
    fi
    if [[ $i -eq 30 ]]; then
        log_error "Server failed to start within 30 seconds"
        log_error "Server logs:"
        cat /tmp/pbpk_mcp_server.log
        exit 1
    fi
    sleep 1
done

# Run smoke test
log_info "Running HTTP smoke test..."
if PBPK_MCP_ENDPOINT="http://127.0.0.1:$SERVER_PORT/mcp" "$SCRIPT_DIR/mcp_http_smoke.sh"; then
    log_info "✓ HTTP smoke test passed"
else
    log_error "HTTP smoke test failed"
    exit 1
fi

# Test with Gemini CLI
if [[ "$GEMINI_AVAILABLE" == "true" ]]; then
    log_info "Testing with Gemini CLI..."
    
    # Check if Gemini is configured
    GEMINI_CONFIG="$HOME/.config/gemini/mcp.json"
    if [[ ! -f "$GEMINI_CONFIG" ]]; then
        log_warn "Gemini MCP config not found at $GEMINI_CONFIG"
        log_warn "Skipping Gemini CLI tests. See docs/mcp-bridge/integration_guides/gemini-cli-workflow.md for setup."
    else
        # Test tools.list
        log_info "  Testing tools.list..."
        if TOOL_COUNT=$(gemini mcp call pbpk-mcp tools.list 2>/dev/null | jq -r '.result.tools | length' 2>/dev/null); then
            log_info "  ✓ Found $TOOL_COUNT tools"
        else
            log_warn "  Failed to list tools (may need configuration)"
        fi
        
        # Test load_simulation
        log_info "  Testing load_simulation..."
        if gemini mcp call pbpk-mcp tools.call \
            --name load_simulation \
            --arguments '{"filePath":"tests/fixtures/demo.pkml","simulationId":"gemini-test"}' \
            --critical 2>/dev/null | jq -e '.result.content[0].json.simulationId' > /dev/null 2>&1; then
            log_info "  ✓ load_simulation succeeded"
            
            # Test list_parameters
            log_info "  Testing list_parameters..."
            if gemini mcp call pbpk-mcp tools.call \
                --name list_parameters \
                --arguments '{"simulationId":"gemini-test"}' 2>/dev/null | jq -e '.result.content[0].json.parameters' > /dev/null 2>&1; then
                log_info "  ✓ list_parameters succeeded"
            else
                log_warn "  list_parameters failed"
            fi
        else
            log_warn "  load_simulation failed (may need configuration)"
        fi
    fi
fi

# Test with Codex CLI
if [[ "$CODEX_AVAILABLE" == "true" ]]; then
    log_info "Testing with Codex CLI..."
    
    # Check if Codex is configured
    CODEX_CONFIG="$HOME/.config/openai/mcp.json"
    if [[ ! -f "$CODEX_CONFIG" ]]; then
        log_warn "Codex MCP config not found at $CODEX_CONFIG"
        log_warn "Skipping Codex CLI tests. See docs/mcp-bridge/integration_guides/codex-cli-workflow.md for setup."
    else
        # Test tools list
        log_info "  Testing tools list..."
        if codex tools list pbpk-mcp > /dev/null 2>&1; then
            log_info "  ✓ tools list succeeded"
        else
            log_warn "  tools list failed (may need configuration)"
        fi
        
        # Test load_simulation
        log_info "  Testing load_simulation..."
        if codex tools call pbpk-mcp tools.call \
            --name load_simulation \
            --arguments '{"filePath":"tests/fixtures/demo.pkml","simulationId":"codex-test"}' \
            --critical 2>/dev/null | jq -e '.result.content[0].json.simulationId' > /dev/null 2>&1; then
            log_info "  ✓ load_simulation succeeded"
            
            # Test list_parameters
            log_info "  Testing list_parameters..."
            if codex tools call pbpk-mcp tools.call \
                --name list_parameters \
                --arguments '{"simulationId":"codex-test"}' 2>/dev/null | jq -e '.result.content[0].json.parameters' > /dev/null 2>&1; then
                log_info "  ✓ list_parameters succeeded"
            else
                log_warn "  list_parameters failed"
            fi
        else
            log_warn "  load_simulation failed (may need configuration)"
        fi
    fi
fi

log_info "All tests completed!"
log_info "Server logs available at: /tmp/pbpk_mcp_server.log"
