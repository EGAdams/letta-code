# Windows Host Recon

## Quick checks

Host identity:
```powershell
hostname
whoami
Get-Date
ipconfig
```

Listening TCP ports:
```powershell
Get-NetTCPConnection -State Listen |
  Sort-Object LocalPort |
  Format-Table -Auto LocalAddress, LocalPort, OwningProcess
```

Process names for listeners:
```powershell
Get-NetTCPConnection -State Listen |
  Sort-Object LocalPort |
  Select-Object LocalAddress, LocalPort, OwningProcess,
    @{Name="ProcessName";Expression={(Get-Process -Id $_.OwningProcess).ProcessName}} |
  Format-Table -Auto
```

Firewall profiles:
```powershell
Get-NetFirewallProfile | Format-Table -Auto Name, Enabled, DefaultInboundAction, DefaultOutboundAction
```

## Enable SSH on Windows

Run as Administrator:
```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
New-NetFirewallRule -Name sshd-22 -DisplayName "OpenSSH Server (22)" -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
```

Verify:
```powershell
Get-Service sshd
Get-NetTCPConnection -State Listen | Where-Object LocalPort -eq 22
```

## Docker and Letta checks

Run after SSH access exists:
```powershell
docker ps
docker inspect <container-name-or-id>
docker logs --tail 200 <container-name-or-id>
```

If only HTTP access is available, verify server version directly:
```powershell
Invoke-WebRequest http://localhost:8283/openapi.json -UseBasicParsing | Select-Object -ExpandProperty Content
```

Check persistent storage before upgrade:
```powershell
docker inspect <container-name-or-id> | Select-String -Pattern "Mounts|Source|Destination|postgres|pgdata"
```

## Interpreting common results
- `8283` listening but memfs clone fails: Letta API is reachable; memfs git support may still be missing on the server.
- No listener on `22`: SSH is not enabled yet.
- Firewall default inbound `Block` is normal; explicit allow rules must exist for the needed ports.
- `openapi.json` reporting `0.16.x`: the Docker server is old enough that Git-backed memfs may not exist yet.
- `state.git` returning HTTP `501`: the route exists at the HTTP layer but the server still does not implement Git memfs operations; upgrade again to a newer Letta image.
