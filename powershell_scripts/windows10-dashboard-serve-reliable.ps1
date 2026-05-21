# windows10-dashboard-serve-reliable.ps1
# Reliable starter: launches dashboard in WSL and exposes it via Tailscale Serve.
# Run on Windows 10 PowerShell (Admin recommended).

$ErrorActionPreference = 'Stop'
$distro = 'Ubuntu-24.04'
$dashboardDir = '/home/adamsl/planner/dashboard'
$ports = @(3031,3032,3040,3050)

function Find-TailscaleExe {
  $candidates = @(
    "$env:ProgramFiles\Tailscale\tailscale.exe",
    "$env:ProgramFiles(x86)\Tailscale\tailscale.exe",
    "$env:LocalAppData\Tailscale\tailscale.exe"
  )
  return ($candidates | Where-Object { Test-Path $_ } | Select-Object -First 1)
}

function Is-WslPortListening([int]$port) {
  $out = wsl -d $distro -- bash -lc "ss -ltn | grep -E ':[0-9]+' | grep ':$port ' || true"
  return -not [string]::IsNullOrWhiteSpace(($out | Out-String))
}

Write-Host 'Stopping old dashboard processes in WSL...' -ForegroundColor Cyan
wsl -d $distro -- bash -lc "pkill -f 'node backend/dist/server.js' || true"
Start-Sleep -Seconds 1

$chosen = $null
foreach ($p in $ports) {
  Write-Host "Trying dashboard port $p..." -ForegroundColor Cyan
  $cmd = "cd $dashboardDir && ADMIN_HOST=0.0.0.0 ADMIN_PORT=$p nohup npm start >/tmp/dashboard.log 2>&1 &"
  wsl -d $distro -- bash -lc $cmd
  Start-Sleep -Seconds 3
  if (Is-WslPortListening $p) {
    $chosen = $p
    break
  }
  # cleanup failed start before next try
  wsl -d $distro -- bash -lc "pkill -f 'node backend/dist/server.js' || true"
  Start-Sleep -Milliseconds 500
}

if (-not $chosen) {
  Write-Host 'Dashboard failed on all ports. Last log:' -ForegroundColor Yellow
  wsl -d $distro -- bash -lc "tail -n 150 /tmp/dashboard.log || true"
  throw 'Could not start dashboard in WSL.'
}

Write-Host "Dashboard listening in WSL on port $chosen" -ForegroundColor Green

$ts = Find-TailscaleExe
if (-not $ts) {
  throw 'Tailscale not found. Install first.'
}

$state = (& $ts status --json | ConvertFrom-Json)
if (-not $state.Self -or -not $state.Self.Online) {
  Write-Host 'Tailscale offline; running tailscale up --reset...' -ForegroundColor Yellow
  & $ts up --reset
}

Write-Host 'Configuring tailscale serve...' -ForegroundColor Cyan
& $ts serve reset | Out-Null
& $ts serve --bg $chosen | Out-Null

$dns = ((& $ts status --json | ConvertFrom-Json).Self.DNSName).TrimEnd('.')

Write-Host "`nServe status:" -ForegroundColor Cyan
& $ts serve status

Write-Host "`nFinal URL:" -ForegroundColor Green
Write-Host "https://$dns/"
Write-Host "(Dashboard port in WSL: $chosen)"
