#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="${RUNTIME_CONTAINER_IMAGE:-headmaster-hermes-runtime:latest}"

docker build \
  --pull \
  -f "${ROOT_DIR}/backend/runtime.Dockerfile" \
  -t "${IMAGE_NAME}" \
  "${ROOT_DIR}"
