#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

if ! command -v bun >/dev/null 2>&1; then
  echo "Error: bun is required but not found in PATH." >&2
  exit 1
fi

echo "[build-local] repo: ${REPO_ROOT}"
echo "[build-local] running: bun install"
bun install

echo "[build-local] running: bun run build"
bun run build

echo "[build-local] done"
