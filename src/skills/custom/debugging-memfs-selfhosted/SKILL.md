---
name: debugging-memfs-selfhosted
description: "Debugs Letta Code memfs failures on self-hosted servers, especially startup crashes or `repository .../state.git not found` errors. Use when `/memfs enable --selfhosted` or startup memfs sync fails."
---

# Debugging Memfs on Self-Hosted

## Known Good Command

Use this first for base self-hosted URL setups:

```text
/memfs enable --selfhosted http://10.0.0.143:8283
```

## Symptoms This Skill Covers

- Startup fails while resuming agent with git clone error
- `fatal: repository '.../v1/git/<agent-id>/state.git/' not found`
- `/memfs enable --selfhosted <url>` appears ignored

## Fast Recovery Workflow

1. Start the CLI and confirm it reaches a prompt.
2. Disable memfs to clear broken state:
   ```text
   /memfs disable
   ```
3. Re-enable with self-hosted base URL:
   ```text
   /memfs enable --selfhosted http://10.0.0.143:8283
   ```
4. Confirm:
   ```text
   /memfs status
   ```

## If Server Uses Custom Git Route

Use explicit remote URL:

```text
/memfs enable --remote http://<host>:<port>/v1/git/<agent-id>/state.git
```

If your server path is not `/v1/git/...`, provide the full `.git` endpoint required by that server.

## Code Areas to Check in This Repo

- `src/cli/App.tsx` (`/memfs` command parsing, including `--selfhosted <url>`)
- `src/agent/memoryGit.ts` (self-hosted remote URL resolution)
- `src/agent/memoryFilesystem.ts` (self-hosted startup fallback to local-only when no remote exists)
- `src/index.ts` (startup memfs sync error handling, non-fatal on normal resume)

## Validation Checklist

1. `letta-dev` reaches prompt (no crash on resume).
2. `/memfs enable --selfhosted http://10.0.0.143:8283` completes or gives actionable remote-path error.
3. Subsequent startup does not hard-crash due to memfs sync.
