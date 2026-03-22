#!/usr/bin/env bash
set -euo pipefail

workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_base="${workspace_root}/docker-compose.celery.yml"
compose_overlay="${workspace_root}/docker-compose.overlay.yml"

docker compose \
  -f "${compose_base}" \
  -f "${compose_overlay}" \
  -p pbpk_mcp \
  up -d --force-recreate --remove-orphans redis api worker

python3 "${workspace_root}/scripts/wait_for_runtime_ready.py"
