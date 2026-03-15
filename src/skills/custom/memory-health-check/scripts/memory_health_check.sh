#!/usr/bin/env bash
set -euo pipefail

cd "${MEMORY_DIR:?MEMORY_DIR not set}"

print_section() {
  echo
  echo "== $1 =="
}

print_section "git status"
git status --short || true

print_section "remotes"
git remote -v || true

print_section "credential helper"
git config --local --get-regexp '^credential\..*\.helper$' || true

print_section "hooks"
git config --local --get core.hooksPath || true

print_section "remote reachability (http)"
if [[ -n "${LETTA_BASE_URL:-}" && -n "${LETTA_API_KEY:-}" && -n "${AGENT_ID:-}" ]]; then
  AUTH_HEADER="Authorization: Basic $(printf 'letta:%s' "$LETTA_API_KEY" | base64 | tr -d '\n')"
  GIT_URL="$LETTA_BASE_URL/v1/git/$AGENT_ID/state.git/info/refs?service=git-upload-pack"
  code=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$GIT_URL" || true)
  echo "HTTP $code"
else
  echo "LETTA_BASE_URL/LETTA_API_KEY/AGENT_ID not set"
fi

print_section "remote refs"
git ls-remote origin | head -n 5 || true
