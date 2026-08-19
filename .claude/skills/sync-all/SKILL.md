---
name: sync-all
description: Bring every machine's letta-code checkout onto the same origin/main before doing any work. Use at the START of any session that will touch letta-code or dashboard/ — especially before editing the dashboard, because the machine serving it is usually not the machine you are typing on. Also use when work "disappeared", when an edit had no visible effect, or when two boxes disagree about what the code says.
---

# Sync All Machines

## The rule

**One line of history: `origin/main`. Never create a branch. Never leave work
sitting only in a working tree.**

Divergent copies on separate machines are the recurring failure in this
project. An edit lands on one box, the dashboard is served from another, and
the change appears to do nothing. Run this skill first, every time.

## Machines

Verified 2026-08-19. Re-verify with `tailscale status` — IPs are stable, reachability is not.

| Name | IP | SSH | Role |
|---|---|---|---|
| **DESKTOP-2OBSQMC** | 100.102.209.100 | `adamsl@` | **LIVE dashboard** on `:8765`. The one users see. Distro `Ubuntu-26.04` (`resolute`). |
| Rosemary46 | 100.72.34.38 | local / `adamsl@` | Dev checkout. WSL. |
| DESKTOP-SHDBATI | 100.80.49.10 | `adamsl@` | Letta server. Its `:8765` is only a proxy to the live box — a `curl` succeeding here proves nothing. |
| desktop-2obsqmc-11 | 100.118.122.75 | ✗ no key | Windows side of 2OBSQMC. Key auth refused for `adamsl`/`NewUser`/`EG`/`eg1972`. |
| desktop-shdbati-1 | 100.69.80.89 | ✗ no key | Windows side of SHDBATI. Same refusal. |
| desktop-2obsqmc-24 | 100.72.158.63 | `adamsl@` | Old WSL distro, superseded. Offline since ~2026-08-05. |
| rosemary46-11 | 100.106.176.58 | `rbarn@` | Mom's PC. Usually offline. |

The two Windows nodes are the Windows *sides* of machines whose WSL side is
already in the table. All `letta-code` work lives in WSL. Do not assume a
Windows checkout exists — confirm one before trying to sync it. If the user
says there is one, ask them for the login; there is no working key from here.

`dashboard/CLAUDE.md` cites a `windows11-ssh-connect` skill as canonical for
this. **That skill does not exist** — this table is the real record.

## Procedure

Run steps in order. Do not skip step 2 to save time; that is how work is lost.

### 1. Take inventory

For each reachable host:

```bash
cd ~/letta-code && \
  echo "$(hostname) $(git branch --show-current) $(git log --oneline -1)" && \
  echo "dirty: $(git status --short | wc -l)" && \
  git fetch -q origin && \
  echo "vs origin/main (main-only / here-only): $(git rev-list --left-right --count origin/main...HEAD)"
```

Report the table to the user before changing anything.

### 2. Rescue uncommitted work FIRST

Uncommitted files exist on exactly one disk. A merge or pull can destroy
them and they are in no backup. Before any merge, on every dirty box:

```bash
cd ~/letta-code && git add -A && git commit -m "sync: WIP from $(hostname)" && git push origin HEAD:main
```

If pushing to `main` is rejected because the box is behind, commit first,
**then** merge (step 3), then push. Commit before merge, always.

Two things to check before committing someone else's WIP:

- Another agent may be mid-edit. `git log -1 --format=%cr` on the box and a
  glance at file mtimes tells you whether it is active right now.
- The same work often already exists on another box. Compare before
  committing a duplicate — e.g. `grep -c "def <function>" dashboard/server.py`
  on both.

### 3. Converge on origin/main

If a box is on any branch other than `main`, its work still belongs on main:

```bash
cd ~/letta-code
git fetch origin
git checkout main 2>/dev/null || git checkout -b main origin/main
git merge <that-branch>        # resolve conflicts here, on the box that owns the work
git push origin main
```

Resolve conflicts on **the box whose work is authoritative for those files** —
for anything under `dashboard/`, that is the live box, where the result can be
loaded in a browser immediately.

Then every other box:

```bash
cd ~/letta-code && git checkout main && git pull --ff-only origin main
```

`--ff-only` is deliberate. If it refuses, that box still has unmerged local
commits — go back to step 2 rather than forcing it.

### 4. Verify convergence

Every box must print the same hash and `0`:

```bash
cd ~/letta-code && echo "$(hostname) $(git rev-parse --short HEAD) dirty=$(git status --short | wc -l)"
```

### 5. Restart the live dashboard if dashboard files moved

```bash
ssh adamsl@100.102.209.100 'systemctl --user restart dashboard-server.service'
cd /home/adamsl/letta-code/dashboard && ./verify-live.sh "<a string from your change>"
```

`verify-live.sh` curls the real live URL and fails loud if your marker is
absent. A pass is the only proof the edit reached the serving machine.

## Then, and only then, start the actual task.

## Notes

- `dashboard/server.py` is ~11.8k lines and both boxes edit it. Expect
  conflicts there; read both sides rather than taking one wholesale.
- For surgical edits over SSH, base64-pipe a script — nested shells mangle
  `$(...)`:
  ```bash
  B64=$(base64 -w0 script.sh)
  ssh adamsl@100.102.209.100 "echo $B64 | base64 -d > /tmp/s.sh && bash /tmp/s.sh"
  ```
- Never `scp` whole files between boxes. That is what created the divergence
  this skill exists to clean up.
