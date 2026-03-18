#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_IMAGE="${BASE_IMAGE:-pbpk_mcp-worker:latest}"
IMAGE_TAG="${IMAGE_TAG:-pbpk_mcp-worker-rxode2:latest}"
PLATFORM="${PLATFORM:-linux/amd64}"
DOCKERFILE_PATH="${ROOT_DIR}/docker/rxode2-worker.Dockerfile"

docker build \
  --platform "${PLATFORM}" \
  --build-arg "BASE_IMAGE=${BASE_IMAGE}" \
  --file "${DOCKERFILE_PATH}" \
  --tag "${IMAGE_TAG}" \
  "${ROOT_DIR}"

printf 'Built %s from %s on %s\n' "${IMAGE_TAG}" "${BASE_IMAGE}" "${PLATFORM}"
printf 'Validate with:\n'
printf '  docker run --rm %s Rscript -e "cat(requireNamespace('\\''rxode2'\\'', quietly=TRUE), '\\''\\\\n'\\'')"\n' "${IMAGE_TAG}"
