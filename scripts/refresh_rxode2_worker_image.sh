#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_IMAGE="${BASE_IMAGE:-pbpk_mcp-worker-rxode2:latest}"
IMAGE_TAG="${IMAGE_TAG:-pbpk_mcp-worker-rxode2:latest}"
PLATFORM="${PLATFORM:-linux/amd64}"
DOCKERFILE_PATH="${ROOT_DIR}/docker/runtime-refresh.Dockerfile"

docker build \
  --platform "${PLATFORM}" \
  --build-arg "BASE_IMAGE=${BASE_IMAGE}" \
  --file "${DOCKERFILE_PATH}" \
  --tag "${IMAGE_TAG}" \
  "${ROOT_DIR}"

printf 'Refreshed %s from %s on %s\n' "${IMAGE_TAG}" "${BASE_IMAGE}" "${PLATFORM}"
