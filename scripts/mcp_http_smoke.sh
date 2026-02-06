#!/usr/bin/env bash
set -euo pipefail

ENDPOINT=${PBPK_MCP_ENDPOINT:-http://127.0.0.1:8000/mcp}
AUTH_HEADER=${PBPK_MCP_AUTH_HEADER:-}
TMP_SIM=${PBPK_MCP_SMOKE_SIM:-"smoke-$(date +%s)"}
PKML_PATH=${PBPK_MCP_SMOKE_PKML:-tests/fixtures/demo.pkml}

curl_rpc() {
  local payload="$1"
  if [[ -n "$AUTH_HEADER" ]]; then
    curl -sS "$ENDPOINT" -H "Content-Type: application/json" -H "$AUTH_HEADER" -d "$payload"
  else
    curl -sS "$ENDPOINT" -H "Content-Type: application/json" -d "$payload"
  fi
}

echo "[1/4] initialize"
curl_rpc '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"capabilities":{}}}' | jq '.result.protocolVersion'

echo "[2/4] tools.list"
LIST_OUT=$(curl_rpc '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}')
echo "$LIST_OUT" | jq '.result.tools | length' >/dev/null

echo "[3/4] load_simulation (critical=true)"
LOAD_PAYLOAD=$(cat <<JSON
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"load_simulation","arguments":{"filePath":"$PKML_PATH","simulationId":"$TMP_SIM"},"critical":true}}
JSON
)
LOAD_OUT=$(curl_rpc "$LOAD_PAYLOAD")
echo "$LOAD_OUT" | jq '.result.content[0].json.simulationId' >/dev/null

echo "[4/4] list_parameters"
LIST_PARAMS_PAYLOAD=$(cat <<JSON
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"list_parameters","arguments":{"simulationId":"$TMP_SIM"}}}
JSON
)
PARAMS_OUT=$(curl_rpc "$LIST_PARAMS_PAYLOAD")
echo "$PARAMS_OUT" | jq '.result.content[0].json.parameters[0]' >/dev/null

echo "Smoke test succeeded for simulation $TMP_SIM"
