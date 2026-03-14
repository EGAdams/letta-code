---
name: memory-health-check
description: Checks Letta agent memfs (git-backed memory) health: git status, remote reachability, pull/push readiness, and pre-commit hook presence. Use when a user reports memory sync issues, git errors in ~/.letta/agents/*/memory, or asks to verify memfs health.
---
# Memory Health Check

## When to use
- User reports memfs/git sync issues or asks to verify memory sync.
- Errors like "repo not found", "no upstream", "refusing to merge unrelated histories", or push/pull failures.

## Quick run (Basic)
Run from the memory repo:
```bash
cd "$MEMORY_DIR"

git status --short

git remote -v

git config --local --get-regexp '^credential\..*\.helper$'

git config --local --get core.hooksPath

# Remote reachability (no auth prompts)
AUTH_HEADER="Authorization: Basic $(printf 'letta:%s' "$LETTA_API_KEY" | base64 | tr -d '\n')"
GIT_URL="$LETTA_BASE_URL/v1/git/$AGENT_ID/state.git/info/refs?service=git-upload-pack"
curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$GIT_URL"; echo

# Verify remote refs (ssh or http)
git ls-remote origin | head -n 5
```

## Success criteria
- `git status --short` shows clean or expected changes.
- Remote is reachable (HTTP 200 or valid refs from `git ls-remote`).
- Local credential helper is set for LETTA_BASE_URL (if using HTTP).
- `core.hooksPath` set (pre-commit hook installed) or default hooks present.

## If failures occur
- 404 on info/refs: repo missing or wrong base URL/agent id.
- "no upstream": set tracking branch (`git push -u origin main`).
- "refusing to merge unrelated histories": use `git pull --allow-unrelated-histories` then resolve conflicts.
- Missing hooks: re-run CLI or reconfigure hooks path.

## Reporting
- Print a short summary with: status, remote, last error, next action.
