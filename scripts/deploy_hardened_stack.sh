#!/usr/bin/env bash
set -euo pipefail

workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_base="${workspace_root}/docker-compose.celery.yml"
compose_hardened="${workspace_root}/docker-compose.hardened.yml"

bind_host="${PBPK_BIND_HOST:-127.0.0.1}"
bind_port="${PBPK_BIND_PORT:-8000}"
base_url="http://${bind_host}:${bind_port}"

docker compose \
  -f "${compose_base}" \
  -f "${compose_hardened}" \
  -p pbpk_mcp \
  up -d --force-recreate --remove-orphans redis api worker

python3 "${workspace_root}/scripts/wait_for_runtime_ready.py" --base-url "${base_url}"
