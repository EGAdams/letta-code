---
name: syncing-fork-with-upstream
description: Sets a forked Git repo up to track an upstream GitHub repository over SSH and creates a dedicated worktree for syncing updates. Use when a fork needs an upstream remote, a clean sync branch/worktree, or a repeatable workflow for pulling upstream changes into the fork.
---

# Sync Fork With Upstream

## When to use
- The current repo is a fork and only has `origin`
- You want `upstream` to point at the canonical GitHub repo over SSH
- You want a separate worktree and branch for syncing upstream changes without touching the main checkout

## Default workflow
1. Inspect `git remote -v`, `git branch -vv`, and `git worktree list`.
2. Confirm the canonical upstream slug from repo metadata such as `package.json` or `README.md`.
3. Add or update `upstream` as `git@github.com:OWNER/REPO.git`.
4. Run the helper script to fetch `upstream` and create a sibling worktree from `upstream/main`.
5. Verify `origin` still points at the fork, `upstream` points at the canonical repo, and the worktree branch tracks `upstream/main`.

## Run
```bash
bash /home/adamsl/letta-code/src/skills/custom/syncing-fork-with-upstream/scripts/setup_upstream_worktree.sh \
  /home/adamsl/letta-code \
  letta-ai/letta-code \
  /home/adamsl/letta-code-upstream \
  sync-upstream
```

## Verify and publish
```bash
bash /home/adamsl/letta-code/src/skills/custom/syncing-fork-with-upstream/scripts/test_and_sync_worktree.sh \
  /home/adamsl/letta-code-upstream \
  verify-only
```

```bash
bash /home/adamsl/letta-code/src/skills/custom/syncing-fork-with-upstream/scripts/test_and_sync_worktree.sh \
  /home/adamsl/letta-code-upstream \
  push-sync
```

```bash
bash /home/adamsl/letta-code/src/skills/custom/syncing-fork-with-upstream/scripts/test_and_sync_worktree.sh \
  /home/adamsl/letta-code-upstream \
  merge-to-fork \
  main
```

## Notes
- Default branch assumptions are `main` on the upstream remote and `sync-upstream` for the worktree branch.
- Prefer a sibling worktree path so the current checkout can stay dirty.
- If `upstream` already exists with a different URL, update it instead of adding a duplicate remote.
- `test_and_sync_worktree.sh` runs Git safety checks first and only runs `bun run typecheck` automatically when dependencies already exist in the worktree.
- Set `SYNC_BOOTSTRAP_DEPS=1` to install dependencies before typechecking, or set `SYNC_TEST_CMD` to override the validation command.
