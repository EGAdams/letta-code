# windows10-start-dashboard-autoport-and-serve.ps1
# Starts dashboard in WSL on a free port, then exposes it via tailscale serve.
# Run in PowerShell on Windows 10 (Admin recommended).

$ErrorActionPreference = 'Stop'
$distro = 'Ubuntu-24.04'
$dashboardDir = '/home/adamsl/planner/dashboard'
$portCandidates = @(3030,3031,3032,3040,3050)

function Find-TailscaleExe {
  $candidates = @(
    "$env:ProgramFiles\Tailscale\tailscale.exe",
    "$env:ProgramFiles(x86)\Tailscale\tailscale.exe",
    "$env:LocalAppData\Tailscale\tailscale.exe"
  )
  return ($candidates | Where-Object { Test-Path $_ } | Select-Object -First 1)
}

function Test-WslPortOpen([int]$port) {
  $probe = wsl -d $distro -- bash -lc "python3 - <<'PY'
import socket
s=socket.socket(); s.settimeout(0.4)
try:
    s.connect(('127.0.0.1',$port)); print('open')
except Exception:
    print('closed')
finally:
    s.close()
PY"
  return (($probe | Out-String).Trim() -eq 'open')
}

Write-Host "Stopping old dashboard processes in WSL..." -ForegroundColor Cyan
wsl -d $distro -- bash -lc "pkill -f 'node backend/dist/server.js' || true"
Start-Sleep -Seconds 1

$chosenPort = $null
foreach ($p in $portCandidates) {
  Write-Host "Trying port $p..." -ForegroundColor Cyan
  $startCmd = "cd $dashboardDir && ADMIN_HOST=0.0.0.0 ADMIN_PORT=$p nohup npm start >/tmp/dashboard.log 2>&1 &"
  wsl -d $distro -- bash -lc $startCmd

  $ok = $false
  for ($i=0; $i -lt 10; $i++) {
    Start-Sleep -Seconds 1
    if (Test-WslPortOpen $p) { $ok = $true; break }
  }

  if ($ok) { $chosenPort = $p; break }

  # stop failed attempt before next port
  wsl -d $distro -- bash -lc "pkill -f 'node backend/dist/server.js' || true"
  Start-Sleep -Milliseconds 500
}

if (-not $chosenPort) {
  Write-Host "Dashboard failed on all candidate ports. Recent log:" -ForegroundColor Yellow
  wsl -d $distro -- bash -lc "tail -n 160 /tmp/dashboard.log || true"
  throw "Could not start dashboard on any candidate port."
}

Write-Host "Dashboard is listening in WSL on 127.0.0.1:$chosenPort" -ForegroundColor Green

$ts = Find-TailscaleExe
if (-not $ts) { throw "Tailscale not found." }

# Ensure tailscale online
$state = (& $ts status --json | ConvertFrom-Json)
if (-not $state.Self -or -not $state.Self.Online) {
  Write-Host "Tailscale is offline; running tailscale up --reset..." -ForegroundColor Yellow
  & $ts up --reset
}

Write-Host "Configuring tailscale serve -> localhost:$chosenPort" -ForegroundColor Cyan
& $ts serve reset | Out-Null
& $ts serve --bg "localhost:$chosenPort" | Out-Null

$dns = ((& $ts status --json | ConvertFrom-Json).Self.DNSName).TrimEnd('.')

Write-Host "`nServe status:" -ForegroundColor Cyan
& $ts serve status

Write-Host "`nFinal URL:" -ForegroundColor Green
Write-Host "https://$dns/"
Write-Host "(Local WSL dashboard port: $chosenPort)"
