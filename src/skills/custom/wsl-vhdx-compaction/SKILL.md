---
name: wsl-vhdx-compaction
description: Reclaim Windows disk space by shrinking a WSL2 distro’s ext4.vhdx using cleanup + wsl --shutdown + diskpart compact vdisk (optionally toggling sparse mode).
---

# WSL VHDX Compaction (Shrink ext4.vhdx)

## Overview
This skill reclaims host Windows disk space when WSL2’s `ext4.vhdx` has grown large and does not shrink after deleting files. The workflow is:

1) free space inside Linux  
2) shutdown WSL  
3) compact the VHDX with DiskPart  
4) (optional) toggle sparse mode off/on

## When to Use
- “WSL is hogging space”
- `ext4.vhdx` is huge
- Inside WSL, `du` looks small but Windows disk usage is large

## Safety / Guardrails
- Disk operations can be destructive if pointed at the wrong file.
- Always target the distro’s `ext4.vhdx` path.
- DiskPart should run in an elevated (Admin) shell.
- Close Docker Desktop first if it uses WSL; locks can prevent compaction.

## Canonical Command Sequence (what we used)

### A) Inside WSL (cleanup)
Run:

- `sudo apt clean`
- `sudo journalctl --vacuum-time=1d`
- `rm -rf ~/.cache/*`

Optional but recommended:
- `sudo fstrim -av`

### B) On Windows PowerShell (shutdown WSL)
- `wsl --shutdown`

### C) (Optional) Toggle sparse off before compacting
- `wsl --manage <distro> --set-sparse false`

### D) DiskPart compaction
In an elevated shell:

- `diskpart`

Then:

- `select vdisk file="<FULL_PATH_TO_ext4.vhdx>"`
- `attach vdisk readonly`
- `compact vdisk`
- `detach vdisk`
- `exit`

### E) (Optional) Turn sparse back on
- `wsl --manage <distro> --set-sparse true`

If sparse re-enable fails, the script now **auto-skips** and leaves sparse disabled (no `--allow-unsafe`).

## How to Locate ext4.vhdx
You can find the path using the Lxss registry entries:

`HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss`

Look for `DistributionName` matching your distro and use:
`BasePath\ext4.vhdx`

## Deterministic Scripts
- `scripts/cleanup_wsl_space.sh` (run inside WSL)
- `scripts/compact_wsl_vhdx.ps1` (run from elevated PowerShell)

## Troubleshooting
- DiskPart says “in use”: ensure WSL is shutdown and Docker Desktop is closed.
- Compaction shrinks little: run `fstrim` inside WSL and try again.
- If sparse mode causes issues, toggle it off before compaction and back on after.