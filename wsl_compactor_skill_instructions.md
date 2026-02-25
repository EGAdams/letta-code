# Letta Code Skill Handoff: `wsl-vhdx-compaction`

This document is a **team handoff** for creating a Letta Code **skill** that guides a user through shrinking a WSL2 distro’s `ext4.vhdx` (WSL disk compaction) using the workflow we previously used:
- cleanup inside WSL
- `wsl --shutdown`
- optional `wsl --manage ... --set-sparse false/true`
- DiskPart: `compact vdisk`

> **Important constraint:** If the agent is running *inside* the WSL distro being compacted, it **cannot** safely run `wsl --shutdown` itself (it will kill its own runtime). In that case, the skill should instruct the user to run the Windows-side commands from **PowerShell (Admin)**.

---

## 1) What Letta Code expects for a skill

A Letta Code skill is a **directory** containing a `SKILL.md` file (with YAML frontmatter). Recommended location for team-distributed skills:

- **Project-local:** `.skills/<skill-name>/SKILL.md`

Optional directories are fine:
- `scripts/` (shell / PowerShell helpers)
- `references/` (notes / links)
- `assets/` (images, etc.)

---

## 2) Folder structure to create

From your repo root:

```bash
mkdir -p .skills/wsl-vhdx-compaction/{scripts,references,assets}
```

Result:

```text
.skills/wsl-vhdx-compaction/
  SKILL.md
  scripts/
    cleanup_wsl_space.sh
    compact_wsl_vhdx.ps1
```

---

## 3) `SKILL.md` (copy/paste)

Create:

`/.skills/wsl-vhdx-compaction/SKILL.md`

```markdown
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
```

---

## 4) `scripts/cleanup_wsl_space.sh`

Create:

`/.skills/wsl-vhdx-compaction/scripts/cleanup_wsl_space.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "[cleanup] apt cache"
sudo apt clean

echo "[cleanup] journal (last 1 day)"
sudo journalctl --vacuum-time=1d || true

echo "[cleanup] user cache"
rm -rf "${HOME}/.cache/"* || true

echo "[cleanup] fstrim (recommended)"
sudo fstrim -av || true

echo "[cleanup] done"
```

Make executable (inside WSL):

```bash
chmod +x .skills/wsl-vhdx-compaction/scripts/cleanup_wsl_space.sh
```

---

## 5) `scripts/compact_wsl_vhdx.ps1`

Create:

`/.skills/wsl-vhdx-compaction/scripts/compact_wsl_vhdx.ps1`

```powershell
param(
  [Parameter(Mandatory=$true)]
  [string]$DistroName,

  [switch]$SkipSparseToggle
)

function Assert-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p  = New-Object Security.Principal.WindowsPrincipal($id)
  if (-not $p.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
    throw "Run this script in an elevated (Admin) PowerShell."
  }
}

function Get-Ext4VhdxPath([string]$Name) {
  $lxss = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss"
  foreach ($k in Get-ChildItem $lxss) {
    $p = Get-ItemProperty $k.PSPath
    if ($p.DistributionName -eq $Name) {
      return (Join-Path $p.BasePath "ext4.vhdx")
    }
  }
  throw "Could not find distro '$Name' in $lxss"
}

Assert-Admin

$vhdx = Get-Ext4VhdxPath $DistroName
if (-not (Test-Path $vhdx)) { throw "VHDX not found: $vhdx" }

Write-Host "[wsl] shutting down WSL..."
wsl.exe --shutdown

if (-not $SkipSparseToggle) {
  Write-Host "[wsl] set-sparse false..."
  wsl.exe --manage $DistroName --set-sparse false
}

Write-Host "[diskpart] compacting: $vhdx"
$dp = @"
select vdisk file="$vhdx"
attach vdisk readonly
compact vdisk
detach vdisk
exit
"@

$dpFile = Join-Path $env:TEMP "wsl_compact_diskpart.txt"
Set-Content -Path $dpFile -Value $dp -Encoding ASCII

diskpart /s $dpFile

if (-not $SkipSparseToggle) {
  Write-Host "[wsl] set-sparse true..."
  wsl.exe --manage $DistroName --set-sparse true
}

Write-Host "[done] Compaction complete."
```

### Run the PowerShell script (example)

Open **PowerShell (Admin)**:

```powershell
# from repo root:
powershell -ExecutionPolicy Bypass -File .\.skills\wsl-vhdx-compaction\scripts\compact_wsl_vhdx.ps1 -DistroName "Ubuntu-24.04"
```

---

## 6) How to use the skill in Letta Code

1) Ensure the skill folder exists in `.skills/`.
2) Restart Letta Code (or reload skills depending on your setup).
3) Prompt your agent:

**Example prompt:**
> “Use the `wsl-vhdx-compaction` skill. My distro is Ubuntu-24.04. Walk me through shrinking ext4.vhdx and tell me exactly what to run in WSL vs. Windows PowerShell (Admin).”

---

## 7) Notes for team implementation

- Keep the skill primarily as **safe instructions**.
- If you add automation, make sure the agent **does not** accidentally run DiskPart against the wrong file.
- Prefer scripts that require the user to explicitly pass the distro name (and show the resolved vhdx path before compacting).

---

**End of handoff.**
