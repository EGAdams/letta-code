# windows10-restart-dashboard-and-enable-serve.ps1
# Run on Windows 10 (PowerShell). Admin recommended.

$ErrorActionPreference = 'Stop'
$distro = 'Ubuntu-24.04'
$dashboardDir = '/home/adamsl/planner/dashboard'
$port = 3030

function Find-TailscaleExe {
  $candidates = @(
    "$env:ProgramFiles\Tailscale\tailscale.exe",
    "$env:ProgramFiles(x86)\Tailscale\tailscale.exe",
    "$env:LocalAppData\Tailscale\tailscale.exe"
  )
  return ($candidates | Where-Object { Test-Path $_ } | Select-Object -First 1)
}

Write-Host "Stopping old dashboard processes in WSL..." -ForegroundColor Cyan
wsl -d $distro -- bash -lc "pkill -f 'node backend/dist/server.js' || true"
Start-Sleep -Seconds 1

Write-Host "Starting dashboard on $port in WSL..." -ForegroundColor Cyan
$startCmd = "cd $dashboardDir && ADMIN_HOST=0.0.0.0 ADMIN_PORT=$port nohup npm start >/tmp/dashboard.log 2>&1 &"
wsl -d $distro -- bash -lc $startCmd

$ok = $false
for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 1
  $probe = wsl -d $distro -- bash -lc "python3 - <<'PY'
import socket
s=socket.socket(); s.settimeout(0.5)
try:
    s.connect(('127.0.0.1',3030)); print('open')
except Exception:
    print('closed')
finally:
    s.close()
PY"
  if (($probe | Out-String).Trim() -eq 'open') { $ok = $true; break }
}

if (-not $ok) {
  Write-Host "Dashboard failed to listen. Recent log:" -ForegroundColor Yellow
  wsl -d $distro -- bash -lc "tail -n 120 /tmp/dashboard.log || true"
  throw "Dashboard failed to start/listen on 127.0.0.1:$port in WSL."
}

Write-Host "Dashboard is listening in WSL on 127.0.0.1:$port" -ForegroundColor Green

$ts = Find-TailscaleExe
if (-not $ts) { throw "Tailscale not found." }

Write-Host "Configuring tailscale serve..." -ForegroundColor Cyan
& $ts serve reset | Out-Null
& $ts serve --bg $port | Out-Null

$dns = ((& $ts status --json | ConvertFrom-Json).Self.DNSName).TrimEnd('.')

Write-Host "`nServe status:" -ForegroundColor Cyan
& $ts serve status

Write-Host "`nFinal URL:" -ForegroundColor Green
Write-Host "https://$dns/"
