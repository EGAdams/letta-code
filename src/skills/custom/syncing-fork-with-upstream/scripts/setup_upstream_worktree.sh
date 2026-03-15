#!/usr/bin/env bash

set -euo pipefail

repo_path="${1:-$PWD}"
upstream_slug="${2:-letta-ai/letta-code}"
worktree_path="${3:-}"
branch_name="${4:-sync-upstream}"
upstream_branch="${UPSTREAM_BRANCH:-main}"

if [[ -z "$worktree_path" ]]; then
  repo_name="$(basename "$repo_path")"
  worktree_path="$(dirname "$repo_path")/${repo_name}-upstream"
fi

if ! git -C "$repo_path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repository: $repo_path" >&2
  exit 1
fi

upstream_url="git@github.com:${upstream_slug}.git"
upstream_ref="upstream/${upstream_branch}"

if git -C "$repo_path" remote get-url upstream >/dev/null 2>&1; then
  git -C "$repo_path" remote set-url upstream "$upstream_url"
else
  git -C "$repo_path" remote add upstream "$upstream_url"
fi

git -C "$repo_path" fetch upstream

if [[ -e "$worktree_path" ]]; then
  if ! git -C "$worktree_path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Worktree path exists but is not a git worktree: $worktree_path" >&2
    exit 1
  fi
fi

if git -C "$repo_path" show-ref --verify --quiet "refs/heads/${branch_name}"; then
  if [[ -e "$worktree_path/.git" ]]; then
    echo "Worktree already exists at $worktree_path"
  else
    git -C "$repo_path" worktree add "$worktree_path" "$branch_name"
  fi
else
  git -C "$repo_path" worktree add -b "$branch_name" "$worktree_path" "$upstream_ref"
fi

git -C "$worktree_path" branch --set-upstream-to="$upstream_ref" "$branch_name" >/dev/null

echo "origin:   $(git -C "$repo_path" remote get-url origin)"
echo "upstream: $(git -C "$repo_path" remote get-url upstream)"
echo "worktree: $worktree_path"
echo "branch:   $(git -C "$worktree_path" branch --show-current)"
echo "tracks:   $(git -C "$worktree_path" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}')"
