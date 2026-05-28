#!/usr/bin/env bash
set -euo pipefail

SOURCE_REPO="${1:-/home/adamsl/letta-code}"
TARGET_WORKTREE="${2:-/home/adamsl/letta-code-upstream}"

if [[ ! -d "${SOURCE_REPO}/.git" ]]; then
  echo "Error: source repo not found: ${SOURCE_REPO}" >&2
  exit 1
fi

if ! git -C "${TARGET_WORKTREE}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: target worktree not found: ${TARGET_WORKTREE}" >&2
  exit 1
fi

echo "[sync-upstream-worktree] source: ${SOURCE_REPO}"
echo "[sync-upstream-worktree] target: ${TARGET_WORKTREE}"
echo "[sync-upstream-worktree] rsync"

rsync -a --delete \
  --exclude '.git' \
  --exclude 'node_modules' \
  --exclude 'dist' \
  --exclude '.cursor' \
  "${SOURCE_REPO}/" "${TARGET_WORKTREE}/"

echo "[sync-upstream-worktree] bun install --frozen-lockfile"
(cd "${TARGET_WORKTREE}" && bun install --frozen-lockfile)

echo "[sync-upstream-worktree] bun run build"
(cd "${TARGET_WORKTREE}" && bun run build)

echo "[sync-upstream-worktree] done"
