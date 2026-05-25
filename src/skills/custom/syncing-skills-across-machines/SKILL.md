---
name: syncing-skills-across-machines
description: Syncs src/skills/custom/ and ~/.letta/agents/ from this machine to mom's machine (rosemary46, 100.72.34.38). Use whenever new skills or agents are added here and need to be pushed to mom's machine, or when the user says "keep skills in sync", "copy skills to mom's machine", or "sync agents".
---

# Syncing Skills Across Machines

## Overview

This machine and mom's machine (rosemary46) both run letta-code and maintain their own sets of custom skills and agent local data. Run this sync whenever new skills or agents are added to this machine.

**Direction: this machine → mom's machine only.**  
Skills that exist only on mom's machine are intentionally left alone.

## Machines

| Role | Tailscale IP | Hostname | OS |
|---|---|---|---|
| This machine (source) | 100.72.158.63 | desktop-2obsqmc-24 | Linux/WSL |
| Mom's machine (target) | 100.72.34.38 | rosemary46-24 | Linux/WSL |

SSH user on both: `adamsl`  
SSH key: `~/.ssh/id_ed25519`

## Run the sync

```bash
bash /home/adamsl/letta-code/src/skills/custom/syncing-skills-across-machines/scripts/sync_skills.sh
```

Preview what would be copied without touching anything:

```bash
bash /home/adamsl/letta-code/src/skills/custom/syncing-skills-across-machines/scripts/sync_skills.sh --dry-run
```

## What gets synced

- `~/letta-code/src/skills/custom/` — all custom skill directories
- `~/.letta/agents/` — agent local data (memory files, settings, per-agent skills)

Builtin skills (`src/skills/builtin/`) are checked into git and stay in sync via normal `git pull` — no manual copy needed.

## If mom's WSL is offline

The script will fail fast with a connectivity error. Ask the user to start WSL on mom's machine, then retry. The Windows side of rosemary46 (100.106.176.58) does not accept the SSH key — always target the Linux/WSL side.

## Manual one-liner (single skill)

```bash
rsync -av /home/adamsl/letta-code/src/skills/custom/<skill-name>/ adamsl@100.72.34.38:~/letta-code/src/skills/custom/<skill-name>/
```

## Notes

- The script never overwrites existing directories — it only copies what's missing on the target.
- Agent UUIDs that already exist on mom's machine are skipped automatically.
- After syncing, no rebuild is needed — skills are read at runtime from the filesystem.
