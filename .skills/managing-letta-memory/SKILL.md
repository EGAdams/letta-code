---
name: managing-letta-memory
description: "Manages Letta Code memory workflows including /memfs enable/disable/sync/reset, local-only memfs setup, and troubleshooting memory filesystem issues. Use when the user mentions memfs, memory filesystem, syncing memory across machines, or asks how to initialize or maintain agent memory storage."
---

# Managing Letta Memory

## Overview

Use this skill to set up and troubleshoot filesystem-backed memory (memfs) for Letta Code agents, including local-only mode and sync guidance for multi-machine access.

**Cost guardrail:** If any action may exceed **$2.00 in LLM credits**, warn and get explicit approval before proceeding.

## Quick Start (Local-only memfs)

1. Enable local-only memfs:
   ```
   /memfs enable --local
   ```
2. Confirm status:
   ```
   /memfs status
   ```
3. Verify memory directory exists:
   - `~/.letta/agents/<agent-id>/memory/system/`

## Workflow: Memfs Setup & Sync

### A. Enable memfs
- **Local-only (self-hosted)**: `/memfs enable --local`
- **Cloud**: `/memfs enable`

### B. Sync memory across machines
Use this when you want the same agent memory available on any machine connected to the same Letta server.

1. On each machine, run:
   ```
   /memfs enable
   ```
2. Pull latest changes:
   ```
   /memfs sync
   ```
3. If sync fails, use `/memfs status` and check the local repo status:
   ```
   git -C ~/.letta/agents/<agent-id>/memory status
   ```

> **Note**: Local-only mode does not sync across machines. Use git-backed memfs (cloud or self-hosted git) if cross-machine sync is required.

### C. Reset local memfs (if corrupt)
```
/memfs reset
```
Then run `/memfs sync` to repopulate from the server.

### D. Custom SSH remote (self-hosted, no Letta Cloud)

1. Create a bare repo on the host:
   ```
   mkdir -p /home/adamsl/memfs/memory.git
   git -C /home/adamsl/memfs/memory.git init --bare
   ```
2. Enable memfs with the SSH remote:
   ```
   /memfs enable --remote ssh://adamsl@<host>/home/adamsl/memfs/memory.git
   ```
3. On other machines, run the same enable + `/memfs sync`.

> **Important**: Use the Tailscale MagicDNS hostname (not the LAN IP) for WSL machines — see section E.

### E. Tailscale SSH (required for WSL remotes)

When the git remote is a WSL instance, **always use the Tailscale MagicDNS hostname**, not the LAN IP. Tailscale SSH routes into WSL directly and uses Tailscale's identity-based key auth. The LAN IP hits Windows' sshd instead, which has a separate `authorized_keys` and will fail.

1. Get your Tailscale hostname:
   ```
   tailscale status --self
   ```
2. Use MagicDNS in the remote:
   ```
   /memfs enable --remote ssh://adamsl@desktop-2obsqmc-24.tailb8fc54.ts.net/home/adamsl/memfs/memory.git
   ```

> **This machine's remote**: `ssh://adamsl@desktop-2obsqmc-24.tailb8fc54.ts.net/home/adamsl/memfs/memory.git`

#### Verify SSH key auth works before enabling:
```bash
ssh adamsl@desktop-2obsqmc-24.tailb8fc54.ts.net echo ok
```
If this fails, SSH key auth is broken and memfs startup will hang. Fix it before proceeding.

## Troubleshooting

- **Terminal locks up at "Checking for pending approvals..."**
  - Root cause: SSH git clone/pull hanging because key auth failed (git was waiting for a password prompt).
  - Fix: Verify SSH key auth works — `ssh adamsl@<remote-host> echo ok`
  - If using a LAN IP for a WSL machine, switch to the Tailscale hostname instead (see section E).
  - Check `~/.letta/settings.json` → `agents[].memfsRemote` to see what remote is configured.

- **"memfs only available on Letta Cloud" error**
  - Use `/memfs enable --local` for self-hosted local-only mode.
  - Or use `--remote <ssh-url>` or `--selfhosted` flag for self-hosted git remotes.

- **SSH key auth broken to LAN IP but Tailscale works**
  - The LAN IP hits Windows sshd (separate `authorized_keys`). Use Tailscale hostname instead.
  - Update the stored remote: edit `~/.letta/settings.json`, find the agent entry, update `memfsRemote`.

- **No memory directory created**
  - Ensure `~/.letta/agents/<agent-id>/memory/` exists; rerun `/memfs enable --local`.

- **Need hierarchical memory files**
  - Run `/init` after memfs is enabled.
