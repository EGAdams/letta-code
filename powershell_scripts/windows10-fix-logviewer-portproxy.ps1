# windows10-fix-logviewer-portproxy.ps1
# Purpose: Repair Windows->WSL forwarding for dashboard/log-viewer on port 3030.
# Run in elevated PowerShell (Administrator) on Windows 10.

$ErrorActionPreference = 'Stop'

function Assert-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p = New-Object Security.Principal.WindowsPrincipal($id)
  if (-not $p.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
    throw 'Run this script in elevated PowerShell (Administrator).'
  }
}

function Print-Section([string]$title) {
  Write-Host "`n=== $title ===" -ForegroundColor Cyan
}

Assert-Admin

$port = 3030
$distro = 'Ubuntu-24.04'

Print-Section '1) Start dashboard in WSL on 0.0.0.0:3030'
$startCmd = "cd /home/adamsl/planner/dashboard && ADMIN_HOST=0.0.0.0 ADMIN_PORT=$port nohup npm start >/tmp/dashboard.log 2>&1 &"
wsl -d $distro -- bash -lc $startCmd
Start-Sleep -Seconds 3

Print-Section '2) Rebuild portproxy rule'
# Delete may report not found; that's fine.
cmd /c "netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=$port" | Out-Null
cmd /c "netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=$port connectaddress=127.0.0.1 connectport=$port"

Print-Section '3) Ensure Tailnet-only firewall rule'
Get-NetFirewallRule -DisplayName "Dashboard Tailnet $port" -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName "Dashboard Tailnet $port" `
  -Direction Inbound -Protocol TCP -LocalPort $port `
  -RemoteAddress "100.64.0.0/10,fd7a:115c:a1e0::/48" -Action Allow -Profile Any | Out-Null

Print-Section '4) Validate local endpoint and adjust proxy target if needed'
$localOk = $false
try {
  $status = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "http://127.0.0.1:$port").StatusCode
  Write-Host "Local 127.0.0.1:$port HTTP status: $status" -ForegroundColor Green
  $localOk = $true
} catch {
  Write-Warning "Local 127.0.0.1:$port failed: $($_.Exception.Message)"
}

if (-not $localOk) {
  Write-Host 'Trying WSL IP target for portproxy...' -ForegroundColor Yellow
  $wslIpRaw = wsl -d $distro -- hostname -I
  $wslIp = ($wslIpRaw | Out-String).Trim().Split(' ')[0]
  if ($wslIp) {
    cmd /c "netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=$port" | Out-Null
    cmd /c "netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=$port connectaddress=$wslIp connectport=$port"
    Write-Host "Portproxy target switched to WSL IP: $wslIp" -ForegroundColor Yellow
  }
}

Print-Section '5) Show diagnostics'
cmd /c "netsh interface portproxy show v4tov4"
Test-NetConnection 127.0.0.1 -Port $port | Select-Object ComputerName,RemotePort,TcpTestSucceeded | Format-Table -Auto

$tsExe = "$env:ProgramFiles\Tailscale\tailscale.exe"
if (-not (Test-Path $tsExe)) { $tsExe = "$env:ProgramFiles(x86)\Tailscale\tailscale.exe" }
$tsIp = $null
$tsDns = $null
if (Test-Path $tsExe) {
  try {
    $tsIp = (& $tsExe ip -4 | Select-Object -First 1).Trim()
    $tsDns = ((& $tsExe status --json | ConvertFrom-Json).Self.DNSName).TrimEnd('.')
  } catch {}
}

Print-Section '6) URL candidates'
if ($tsDns) { Write-Host "http://$tsDns`:$port" -ForegroundColor Green }
if ($tsIp)  { Write-Host "http://$tsIp`:$port" -ForegroundColor Green }
Write-Host "http://127.0.0.1:$port" -ForegroundColor Gray

Write-Host "`nDone." -ForegroundColor Green
