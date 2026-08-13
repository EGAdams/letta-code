#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APS_DIR="${1:-$ROOT_DIR/.cache/acceptance-pipeline-specification}"
APS_URL="https://github.com/unclebob/Acceptance-Pipeline-Specification.git"

if [[ -d "$APS_DIR/.git" ]]; then
  git -C "$APS_DIR" fetch origin main
  git -C "$APS_DIR" checkout --detach origin/main
else
  git clone --depth 1 "$APS_URL" "$APS_DIR"
fi

git -C "$APS_DIR" log -1 --format='APS %H %cI %s'
