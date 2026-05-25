# Memorial Day Handoff — letta-code commit/push on mom's machine

**Date:** 2026-05-25
**Author:** Claude (outgoing shift)
**Task:** Commit and push the local changes on "mom's machine," debugging any errors.

---

## TL;DR for the next team

Mom's machine (this host, `rosemary46-24`) has a `letta-code` clone that is **23 commits behind `origin/main`** and has a pile of uncommitted work. The user wants it **all committed (`git add -A`) and pushed**. The push will require a **merge with origin first** because the branch is behind. Watch for a merge conflict on `src/skills/custom/syncing-skills-across-machines/`.

The work was **NOT yet completed** — the final commit/push sequence was about to run when the shift ended.

---

## Connection details

- **Host:** mom's machine = Tailscale `rosemary46-24`, IP `100.72.34.38`, Linux, user `adamsl`. Key-based SSH works (no password).
- **Repo:** `/home/adamsl/letta-code`
- The remote shell does **not** start in the repo. Always target it explicitly:
  ```bash
  ssh adamsl@100.72.34.38 "git -C /home/adamsl/letta-code <cmd>"
  ```
  (A bare `ssh ... "git status"` runs in the home dir and fails with "not a git repository" — this already burned time once.)

---

## Current state of the repo (verified at start of shift)

- Branch `main` is **behind `origin/main` by 23 commits** (was fast-forwardable before any local commit).
- **Tracked, uncommitted edits:**
  - `.gitignore` (staged)
  - `src/agent/create.ts`
  - `src/agent/modify.ts`
  - `src/agent/prompts/remember.md`
  - `src/tests/agent/model-preset-refresh.wiring.test.ts`
- **~28 untracked items**, including:
  - Many `src/skills/custom/*` skill dirs
  - `external_agents/`
  - `scripts/sync-upstream-worktree.sh`, `scripts/windows-enable-ssh.ps1`, `scripts/windows-upgrade-letta-docker.ps1`

## Decision already made by the user

**Commit scope = EVERYTHING (`git add -A`).** The user explicitly chose to include `external_agents/` and the Windows `.ps1` scripts, not just the tracked changes or just skills.

---

## Exact sequence to run (resume here)

Run each step, check output before the next. **Do NOT skip hooks.**

1. Stage everything:
   ```bash
   ssh adamsl@100.72.34.38 "git -C /home/adamsl/letta-code add -A"
   ```
2. Commit (husky pre-commit runs lint-staged + typecheck; only typecheck gates the commit):
   ```bash
   ssh adamsl@100.72.34.38 'git -C /home/adamsl/letta-code commit -m "chore: sync local changes — agent create/modify, remember prompt, custom skills, and machine setup scripts"'
   ```
   - If typecheck fails, fix the TS errors and re-commit. Do **not** use `--no-verify`.
3. Push (will likely be **rejected, non-fast-forward**, because we were 23 behind — this is expected):
   ```bash
   ssh adamsl@100.72.34.38 "git -C /home/adamsl/letta-code push"
   ```
4. If rejected, integrate origin via **merge (not rebase)**:
   ```bash
   ssh adamsl@100.72.34.38 "git -C /home/adamsl/letta-code pull --no-rebase --no-edit"
   ```
5. Push again once merged cleanly:
   ```bash
   ssh adamsl@100.72.34.38 "git -C /home/adamsl/letta-code push"
   ```
6. Verify:
   ```bash
   ssh adamsl@100.72.34.38 "git -C /home/adamsl/letta-code status"
   ssh adamsl@100.72.34.38 "git -C /home/adamsl/letta-code log --oneline -3"
   ```

---

## Known risks / likely errors to debug

- **Merge conflict on `src/skills/custom/syncing-skills-across-machines/`.** This dir exists both as untracked here AND as a file added in the incoming 23 commits (it was just committed & pushed from the *other* clone — see below). After `add -A` + commit, the pull will try to merge two versions. If conflicted, resolve by hand; do not blow away mom's version.
- **"untracked working tree files would be overwritten by merge"** — if this appears during pull, STOP and report the filenames. Do not delete/move them.
- The repo runs **two live `letta.js` agents in `--yolo`** that write to the tree concurrently (per CLAUDE.md) — `git status` may shift under you. Re-check before assuming the tree is clean.

## Hard constraints (do not violate)

Never run, even to "fix" an error: `git reset --hard`, `git push --force/-f`, `git checkout --`, `git restore`, `git clean`, `rm` on repo files, branch deletion, `--no-verify`, `--no-gpg-sign`. If you think you need one of these, stop and ask the user.

---

## Context: what was already done on the OTHER clone

On the primary working machine (this is a *different* clone of the same repo), the outgoing shift already committed and pushed:

- Commit `b7a61192` → `origin/main`: "fix: unit test fixes and add syncing-skills-across-machines skill"
- That commit is part of the 23 commits mom's machine is behind by. That's why `syncing-skills-across-machines` is the likely conflict point.

---

## Definition of done

`git -C /home/adamsl/letta-code status` on mom's machine reports **"up to date with 'origin/main'"** and a **clean working tree**, with all the local changes landed on `origin/main`.
