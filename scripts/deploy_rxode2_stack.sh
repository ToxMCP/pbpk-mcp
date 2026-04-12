#!/usr/bin/env bash
set -euo pipefail

workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="${workspace_root}/docker-compose.celery.yml"

docker compose \
  -f "${compose_file}" \
  -p pbpk_mcp \
  up -d --force-recreate --remove-orphans redis api worker

python3 "${workspace_root}/scripts/wait_for_runtime_ready.py" \
  --auth-dev-secret "pbpk-local-dev-secret" \
  --timeout-seconds 600 \
  --per-request-timeout-seconds 30 \
  --stable-successes 2
