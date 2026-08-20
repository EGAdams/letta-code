# Rosemary46 (Mom's PC) — WSL Tailscale access

Two nodes, one machine:

| Node | IP | SSH user |
|---|---|---|
| `rosemary46-11` (Windows) | 100.106.176.58 | `rbarn` |
| `rosemary46-24` (WSL Ubuntu) | 100.72.34.38 | `adamsl` |

If the Linux node is offline but Windows answers, SSH to Windows and check
`wsl -l -v` plus `wsl -e sh -lc "tailscale status"`.

**Known fix, 2026-06-25.** `Ubuntu-24.04` was shutting down after each one-shot
WSL command, taking `tailscaled` with it. A Windows scheduled task,
`Rosemary46 WSL Tailscale Keepalive`, runs
`C:\Users\rbarn\start-rosemary46-wsl-tailscale.ps1` to hold the distro open
with a harmless `tailscale ip` loop.

Verify:

```powershell
Get-ScheduledTask -TaskName 'Rosemary46 WSL Tailscale Keepalive'
```

```bash
ssh adamsl@100.72.34.38 "echo LINUX_AUTH_OK && systemctl is-active tailscaled && tailscale ip -4"
```
