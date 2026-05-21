# windows10-dashboard-serve-diagnostic.ps1
# Diagnostic-first script for Windows 10 + WSL dashboard + Tailscale serve.
# Run in PowerShell (Admin recommended).

$ErrorActionPreference = 'Continue'
$distro = 'Ubuntu-24.04'
$dashboardDir = '/home/adamsl/planner/dashboard'
$port = 3031

function Find-TailscaleExe {
  $candidates = @(
    "$env:ProgramFiles\Tailscale\tailscale.exe",
    "$env:ProgramFiles(x86)\Tailscale\tailscale.exe",
    "$env:LocalAppData\Tailscale\tailscale.exe"
  )
  return ($candidates | Where-Object { Test-Path $_ } | Select-Object -First 1)
}

Write-Host "=== WSL identity/path check ===" -ForegroundColor Cyan
wsl -d $distro -- bash -lc "whoami; pwd; ls -ld $dashboardDir || true"

Write-Host "`n=== Stop old dashboard processes ===" -ForegroundColor Cyan
wsl -d $distro -- bash -lc "pkill -f 'node backend/dist/server.js' || true"
Start-Sleep -Seconds 1

Write-Host "`n=== Start dashboard on port $port ===" -ForegroundColor Cyan
wsl -d $distro -- bash -lc "cd $dashboardDir && ADMIN_HOST=0.0.0.0 ADMIN_PORT=$port nohup npm start >/tmp/dashboard.log 2>&1 &"
Start-Sleep -Seconds 4

Write-Host "`n=== Dashboard log (tail) ===" -ForegroundColor Cyan
wsl -d $distro -- bash -lc "tail -n 120 /tmp/dashboard.log || echo no-log"

Write-Host "`n=== Listener check in WSL ===" -ForegroundColor Cyan
wsl -d $distro -- bash -lc "ss -ltn | grep :$port || echo not-listening"

Write-Host "`n=== Local Windows test ===" -ForegroundColor Cyan
Test-NetConnection 127.0.0.1 -Port $port | Select-Object ComputerName,RemotePort,TcpTestSucceeded | Format-Table -Auto

$ts = Find-TailscaleExe
if (-not $ts) {
  Write-Host "`nTailscale not found; stopping here." -ForegroundColor Yellow
  exit 1
}

Write-Host "`n=== Tailscale status ===" -ForegroundColor Cyan
& $ts status

Write-Host "`n=== Configure tailscale serve ===" -ForegroundColor Cyan
& $ts serve reset
& $ts serve --bg $port
& $ts serve status

try {
  $dns = ((& $ts status --json | ConvertFrom-Json).Self.DNSName).TrimEnd('.')
  Write-Host "`nFinal URL: https://$dns/" -ForegroundColor Green
} catch {
  Write-Host "Could not determine DNSName from tailscale status --json" -ForegroundColor Yellow
}
