# windows11-fix-dashboard-portproxy.ps1
# Purpose: Repair Windows->WSL port forwarding for dashboard on port 8765.
# This enables access to http://desktop-2obsqmc-24.tailb8fc54.ts.net/ from Windows 11 and Tailscale.
# Run in elevated PowerShell (Administrator) on Windows 11.

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

$port = 8765
$distro = 'Ubuntu-24.04'

Print-Section "1) Verify dashboard is running in WSL on 0.0.0.0:$port"
wsl -d $distro -- bash -lc "ps aux | grep 'python3 server.py' | grep -v grep || echo 'Dashboard not found, starting...'"

Print-Section "2) Rebuild portproxy rule (Windows -> WSL)"
# Delete may report not found; that's fine.
cmd /c "netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=$port" | Out-Null
cmd /c "netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=$port connectaddress=127.0.0.1 connectport=$port"

Print-Section "3) Ensure Tailnet-only firewall rule"
Get-NetFirewallRule -DisplayName "Dashboard Tailnet $port" -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName "Dashboard Tailnet $port" `
  -Direction Inbound -Protocol TCP -LocalPort $port `
  -RemoteAddress "100.64.0.0/10,fd7a:115c:a1e0::/48" -Action Allow -Profile Any | Out-Null

Print-Section "4) Validate local endpoint"
$localOk = $false
try {
  $status = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "http://127.0.0.1:$port").StatusCode
  Write-Host "Local 127.0.0.1:$port HTTP status: $status" -ForegroundColor Green
  $localOk = $true
} catch {
  Write-Warning "Local 127.0.0.1:$port failed: $($_.Exception.Message)"
}

if (-not $localOk) {
  Write-Host "Trying WSL IP target for portproxy..." -ForegroundColor Yellow
  $wslIpRaw = wsl -d $distro -- hostname -I
  $wslIp = ($wslIpRaw | Out-String).Trim().Split(' ')[0]
  if ($wslIp) {
    cmd /c "netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=$port" | Out-Null
    cmd /c "netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=$port connectaddress=$wslIp connectport=$port"
    Write-Host "Portproxy target switched to WSL IP: $wslIp" -ForegroundColor Yellow
  }
}

Print-Section "5) Show portproxy diagnostics"
cmd /c "netsh interface portproxy show v4tov4"
Test-NetConnection 127.0.0.1 -Port $port | Select-Object ComputerName,RemotePort,TcpTestSucceeded | Format-Table -Auto

Print-Section "6) Tailscale URLs"
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

Write-Host "Dashboard URLs:" -ForegroundColor Green
if ($tsDns) { Write-Host "  http://$tsDns`:$port/" -ForegroundColor Green }
if ($tsIp)  { Write-Host "  http://$tsIp`:$port/" -ForegroundColor Green }
Write-Host "  http://127.0.0.1:$port/" -ForegroundColor Gray

Write-Host "`nDone. Dashboard should now be accessible from Windows 11 and Tailscale." -ForegroundColor Green
