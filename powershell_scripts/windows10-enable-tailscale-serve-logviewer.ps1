# windows10-enable-tailscale-serve-logviewer.ps1
# Purpose: Expose local log viewer (127.0.0.1:3030) over Tailscale Serve.
# Run in elevated PowerShell on Windows 10.

$ErrorActionPreference = 'Stop'

function Find-TailscaleExe {
  $candidates = @(
    "$env:ProgramFiles\Tailscale\tailscale.exe",
    "$env:ProgramFiles(x86)\Tailscale\tailscale.exe",
    "$env:LocalAppData\Tailscale\tailscale.exe"
  )
  return ($candidates | Where-Object { Test-Path $_ } | Select-Object -First 1)
}

$ts = Find-TailscaleExe
if (-not $ts) { throw "Tailscale not found. Install first (winget install --id Tailscale.Tailscale --source winget -e)." }

# Ensure logged in
$state = (& $ts status --json | ConvertFrom-Json)
if (-not $state.Self -or -not $state.Self.Online) {
  Write-Host "Tailscale not online. Running tailscale up --reset..." -ForegroundColor Yellow
  & $ts up --reset
  $state = (& $ts status --json | ConvertFrom-Json)
}

# Verify local service
try {
  $code = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "http://127.0.0.1:3030").StatusCode
  Write-Host "Local service OK on 127.0.0.1:3030 (HTTP $code)" -ForegroundColor Green
} catch {
  throw "Local service on 127.0.0.1:3030 is not reachable. Start dashboard first."
}

# Reset serve config and publish
& $ts serve reset | Out-Null
& $ts serve --bg 3030

# Show status + URL
$status = & $ts serve status
$dns = ((& $ts status --json | ConvertFrom-Json).Self.DNSName).TrimEnd('.')

Write-Host "`nServe status:" -ForegroundColor Cyan
Write-Host $status

Write-Host "`nLog viewer URL:" -ForegroundColor Green
Write-Host "https://$dns/"
Write-Host "(HTTP fallback if needed): http://$dns:80/"
