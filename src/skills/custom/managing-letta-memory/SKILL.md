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

### D. Custom SSH remote (self-hosted, no Letta Cloud)

1. Create a bare repo on a LAN host:
   ```
   mkdir -p /home/adamsl/memfs/memory.git
   git -C /home/adamsl/memfs/memory.git init --bare
   ```
2. Enable memfs with the SSH remote (example):
   ```
   /memfs enable --remote ssh://adamsl@10.0.0.7/home/adamsl/memfs/memory.git
   ```
3. On other machines, run the same enable + `/memfs sync`.

> **Note**: SSH must be reachable from each machine (port 22). Key-based auth is recommended.

### E. Tailscale SSH (recommended for WSL)

When Tailscale runs inside WSL, use the Tailscale IP or MagicDNS name so SSH hits WSL (not Windows sshd).

1. Get Tailscale IP:
   ```
   tailscale ip -4
   ```
2. Use MagicDNS or the IP in the remote:
   ```
   /memfs enable --remote ssh://adamsl@desktop-2obsqmc-24.tailb8fc54.ts.net/home/adamsl/memfs/memory.git
   ```

### C. Reset local memfs (if corrupt)
```
/memfs reset
```
Then run `/memfs sync` to repopulate from the server.

## Troubleshooting

- **“memfs only available on Letta Cloud” error**
  - Use `/memfs enable --local` for self-hosted local-only mode.
- **No memory directory created**
  - Ensure `~/.letta/agents/<agent-id>/memory/` exists; rerun `/memfs enable --local`.
- **Need hierarchical memory files**
  - Run `/init` after memfs is enabled.

## Resources

This skill is documentation-only; remove unused example directories if desired.
