#!/usr/bin/env bash
set -euo pipefail

workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="${workspace_root}/docker-compose.celery.yml"

docker compose \
  -f "${compose_file}" \
  -p pbpk_mcp \
  up -d --force-recreate --remove-orphans redis api worker

python3 "${workspace_root}/scripts/apply_rxode2_patch.py" --restart
python3 "${workspace_root}/scripts/wait_for_runtime_ready.py"
