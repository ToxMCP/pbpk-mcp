#!/usr/bin/env bash
set -euo pipefail

workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_base="${workspace_root}/docker-compose.celery.yml"
compose_s3_smoke="${workspace_root}/docker-compose.s3-audit-smoke.yml"
project_name="pbpk_mcp"

wait_for_service_exit_zero() {
  local service="$1"
  local timeout_seconds="${2:-90}"
  local deadline=$((SECONDS + timeout_seconds))

  while (( SECONDS < deadline )); do
    local container_id
    container_id="$(docker compose -f "${compose_base}" -f "${compose_s3_smoke}" -p "${project_name}" ps -a -q "${service}" 2>/dev/null || true)"
    if [[ -n "${container_id}" ]]; then
      local status
      status="$(docker inspect -f '{{.State.Status}}' "${container_id}" 2>/dev/null || true)"
      if [[ "${status}" == "exited" ]]; then
        local exit_code
        exit_code="$(docker inspect -f '{{.State.ExitCode}}' "${container_id}" 2>/dev/null || true)"
        if [[ "${exit_code}" == "0" ]]; then
          return 0
        fi
        docker logs "${container_id}" >&2 || true
        echo "Service ${service} exited with code ${exit_code}" >&2
        return 1
      fi
    fi
    sleep 1
  done

  echo "Timed out waiting for ${service} to complete successfully" >&2
  return 1
}

docker compose \
  -f "${compose_base}" \
  -f "${compose_s3_smoke}" \
  -p "${project_name}" \
  up -d --force-recreate --remove-orphans redis minio minio-init api worker

wait_for_service_exit_zero minio-init 90

python3 "${workspace_root}/scripts/wait_for_runtime_ready.py" \
  --auth-dev-secret "pbpk-local-dev-secret-32bytes-long" \
  --timeout-seconds 600 \
  --per-request-timeout-seconds 30 \
  --stable-successes 2
