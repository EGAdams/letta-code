# windows11-enable-tailscale-serve-dashboard.ps1
# Purpose: Expose dashboard (127.0.0.1:8765) over Tailscale Serve.
# This restores access to http://desktop-2obsqmc-24.tailb8fc54.ts.net/ (no port needed)
# Run in elevated PowerShell on Windows 11.

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

Write-Host "`n=== Tailscale Serve Dashboard Fix ===" -ForegroundColor Cyan

# Ensure logged in
$state = (& $ts status --json | ConvertFrom-Json)
if (-not $state.Self -or -not $state.Self.Online) {
  Write-Host "Tailscale not online. Running tailscale up..." -ForegroundColor Yellow
  & $ts up
  $state = (& $ts status --json | ConvertFrom-Json)
}

# Verify local service
Write-Host "`n1) Checking local dashboard on 127.0.0.1:8765..." -ForegroundColor Cyan
try {
  $code = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "http://127.0.0.1:8765").StatusCode
  Write-Host "   Local dashboard OK (HTTP $code)" -ForegroundColor Green
} catch {
  throw "Dashboard not reachable on 127.0.0.1:8765. Make sure it's running in WSL."
}

# Reset and enable Tailscale Serve
Write-Host "`n2) Enabling Tailscale Serve for port 8765..." -ForegroundColor Cyan
& $ts serve reset | Out-Null
& $ts serve --bg 8765

# Show status
$status = & $ts serve status
$dns = ((& $ts status --json | ConvertFrom-Json).Self.DNSName).TrimEnd('.')

Write-Host "`n3) Tailscale Serve Status:" -ForegroundColor Cyan
Write-Host $status

Write-Host "`n4) Dashboard URLs:" -ForegroundColor Green
Write-Host "   https://$dns/" -ForegroundColor Green
Write-Host "   http://$dns/" -ForegroundColor Green
Write-Host "   http://127.0.0.1:8765/ (local fallback)" -ForegroundColor Gray

Write-Host "`n✓ Done! Dashboard is now accessible via Tailscale Serve." -ForegroundColor Green
Write-Host "Access from any device on your Tailnet without specifying the port.`n" -ForegroundColor Green
