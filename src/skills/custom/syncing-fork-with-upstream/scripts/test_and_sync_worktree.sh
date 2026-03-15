#!/usr/bin/env bash

set -euo pipefail

worktree_path="${1:-}"
action="${2:-verify-only}"
target_branch="${3:-main}"

if [[ -z "$worktree_path" ]]; then
  echo "Usage: $0 <worktree-path> [verify-only|push-sync|merge-to-fork] [target-branch]" >&2
  exit 1
fi

if ! git -C "$worktree_path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git worktree: $worktree_path" >&2
  exit 1
fi

current_branch="$(git -C "$worktree_path" branch --show-current)"
upstream_ref="$(git -C "$worktree_path" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)"

require_clean_worktree() {
  if [[ -n "$(git -C "$worktree_path" status --porcelain)" ]]; then
    echo "Worktree has local changes: $worktree_path" >&2
    git -C "$worktree_path" status --short >&2
    exit 1
  fi
}

run_validation() {
  if [[ -n "${SYNC_TEST_CMD:-}" ]]; then
    echo "Running custom validation: $SYNC_TEST_CMD"
    (
      cd "$worktree_path"
      eval "$SYNC_TEST_CMD"
    )
    return
  fi

  if [[ -f "$worktree_path/package.json" ]]; then
    if [[ -d "$worktree_path/node_modules" ]]; then
      echo "Running validation: bun run typecheck"
      (cd "$worktree_path" && bun run typecheck)
      return
    fi

    if [[ "${SYNC_BOOTSTRAP_DEPS:-0}" == "1" ]]; then
      echo "Bootstrapping dependencies: bun install --frozen-lockfile"
      (cd "$worktree_path" && bun install --frozen-lockfile)
      echo "Running validation: bun run typecheck"
      (cd "$worktree_path" && bun run typecheck)
      return
    fi
  fi

  echo "Skipping dependency-based validation (set SYNC_BOOTSTRAP_DEPS=1 or SYNC_TEST_CMD to enable)"
}

verify_state() {
  require_clean_worktree
  git -C "$worktree_path" fetch origin
  git -C "$worktree_path" fetch upstream

  if [[ -z "$current_branch" ]]; then
    echo "Detached HEAD is not supported for sync operations" >&2
    exit 1
  fi

  if [[ "$upstream_ref" != "upstream/main" ]]; then
    echo "Expected $current_branch to track upstream/main, got: ${upstream_ref:-<none>}" >&2
    exit 1
  fi

  if ! git -C "$worktree_path" merge-base --is-ancestor upstream/main HEAD; then
    echo "Current HEAD does not include upstream/main" >&2
    exit 1
  fi

  run_validation

  echo "Verified worktree: $worktree_path"
  echo "branch:   $current_branch"
  echo "tracks:   $upstream_ref"
  echo "origin:   $(git -C "$worktree_path" remote get-url origin)"
  echo "upstream: $(git -C "$worktree_path" remote get-url upstream)"
}

push_sync_branch() {
  verify_state
  git -C "$worktree_path" push -u origin "$current_branch"
  echo "Pushed $current_branch to origin"
}

merge_to_fork_branch() {
  verify_state

  if ! git -C "$worktree_path" show-ref --verify --quiet "refs/remotes/origin/$target_branch"; then
    echo "Target branch does not exist on origin: $target_branch" >&2
    exit 1
  fi

  temp_branch="sync-merge-${target_branch//\//-}"

  cleanup() {
    git -C "$worktree_path" checkout "$current_branch" >/dev/null 2>&1 || true
    if git -C "$worktree_path" show-ref --verify --quiet "refs/heads/$temp_branch"; then
      git -C "$worktree_path" branch -D "$temp_branch" >/dev/null 2>&1 || true
    fi
  }
  trap cleanup EXIT

  git -C "$worktree_path" checkout -B "$temp_branch" "origin/$target_branch" >/dev/null

  if ! git -C "$worktree_path" merge --no-edit "$current_branch"; then
    git -C "$worktree_path" merge --abort >/dev/null 2>&1 || true
    echo "Merge into $target_branch failed. Resolve manually." >&2
    exit 1
  fi

  require_clean_worktree
  run_validation

  git -C "$worktree_path" push origin "HEAD:$target_branch"
  echo "Merged $current_branch into origin/$target_branch and pushed"
}

case "$action" in
  verify-only)
    verify_state
    ;;
  push-sync)
    push_sync_branch
    ;;
  merge-to-fork)
    merge_to_fork_branch
    ;;
  *)
    echo "Unknown action: $action" >&2
    exit 1
    ;;
esac
