# windows10-start-dashboard-and-enable-tailscale-serve.ps1
# Run in PowerShell on Windows 10 (Admin recommended)

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

Write-Host "Starting dashboard in WSL..." -ForegroundColor Cyan
$startCmd = "cd $dashboardDir && ADMIN_HOST=0.0.0.0 ADMIN_PORT=$port nohup npm start >/tmp/dashboard.log 2>&1 &"
wsl -d $distro -- bash -lc $startCmd

$ok = $false
for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 1
  try {
    $status = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "http://127.0.0.1:$port").StatusCode
    if ($status) { $ok = $true; break }
  } catch {}
}

if (-not $ok) {
  Write-Host "Dashboard did not come up on 127.0.0.1:$port. Recent log:" -ForegroundColor Yellow
  wsl -d $distro -- bash -lc "tail -n 120 /tmp/dashboard.log || true"
  throw "Dashboard failed to start."
}

Write-Host "Dashboard is up on 127.0.0.1:$port" -ForegroundColor Green

$ts = Find-TailscaleExe
if (-not $ts) { throw "Tailscale not found. Install first." }

$state = (& $ts status --json | ConvertFrom-Json)
if (-not $state.Self -or -not $state.Self.Online) {
  Write-Host "Tailscale not online. Running tailscale up --reset..." -ForegroundColor Yellow
  & $ts up --reset
}

Write-Host "Configuring tailscale serve..." -ForegroundColor Cyan
& $ts serve reset | Out-Null
& $ts serve --bg $port | Out-Null

$dns = ((& $ts status --json | ConvertFrom-Json).Self.DNSName).TrimEnd('.')
Write-Host "`nServe status:" -ForegroundColor Cyan
& $ts serve status

Write-Host "`nLog viewer URL:" -ForegroundColor Green
Write-Host "https://$dns/"
