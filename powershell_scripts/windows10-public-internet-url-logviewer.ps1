# windows10-public-internet-url-logviewer.ps1
# Creates a public Internet URL for the local log viewer (default: http://localhost:8080)
# using a Cloudflare Quick Tunnel (no domain required).
# Run in PowerShell on Windows 10.

param(
  [int]$LocalPort = 8080
)

$ErrorActionPreference = 'Stop'

function Ensure-Cloudflared {
  $candidates = @(
    "$env:ProgramFiles\cloudflared\cloudflared.exe",
    "$env:ProgramFiles (x86)\cloudflared\cloudflared.exe",
    "$env:USERPROFILE\AppData\Local\Microsoft\WinGet\Packages\Cloudflare.cloudflared_*\cloudflared.exe"
  )

  $exe = Get-Command cloudflared -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue
  if ($exe -and (Test-Path $exe)) { return $exe }

  foreach ($c in $candidates) {
    if (Test-Path $c) { return $c }
  }

  Write-Host "Installing cloudflared via winget..." -ForegroundColor Yellow
  winget install --id Cloudflare.cloudflared --source winget -e | Out-Null

  $exe = Get-Command cloudflared -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue
  if ($exe -and (Test-Path $exe)) { return $exe }

  # common post-winget location fallback
  $fallback = "$env:ProgramFiles\cloudflared\cloudflared.exe"
  if (Test-Path $fallback) { return $fallback }

  throw "cloudflared not found after install."
}

# Verify local app reachable first
try {
  $status = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "http://localhost:$LocalPort").StatusCode
  Write-Host "Local log viewer OK on http://localhost:$LocalPort (HTTP $status)" -ForegroundColor Green
}
catch {
  throw "Local app not reachable on http://localhost:$LocalPort. Start it first."
}

$cloudflared = Ensure-Cloudflared
Write-Host "Using cloudflared: $cloudflared" -ForegroundColor Cyan

$logFile = Join-Path $env:TEMP "cloudflared-logviewer-$LocalPort.log"
if (Test-Path $logFile) { Remove-Item $logFile -Force }

# Start tunnel in background
$proc = Start-Process -FilePath $cloudflared `
  -ArgumentList @('tunnel','--url',"http://localhost:$LocalPort",'--no-autoupdate') `
  -RedirectStandardOutput $logFile -RedirectStandardError $logFile `
  -PassThru

Write-Host "Started cloudflared (PID $($proc.Id)). Waiting for public URL..." -ForegroundColor Cyan

$url = $null
for ($i = 0; $i -lt 40; $i++) {
  Start-Sleep -Milliseconds 500
  if (Test-Path $logFile) {
    $content = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
    if ($content -match 'https://[-a-z0-9]+\.trycloudflare\.com') {
      $url = $matches[0]
      break
    }
  }
}

if (-not $url) {
  Write-Warning "Could not detect URL yet. Check log: $logFile"
  Write-Host "Tunnel process PID: $($proc.Id)"
  Write-Host "Try: Get-Content '$logFile' -Wait"
  exit 1
}

Write-Host "`nPUBLIC INTERNET URL:" -ForegroundColor Green
Write-Host $url -ForegroundColor Green

Write-Host "`nTo stop tunnel later:" -ForegroundColor Yellow
Write-Host "Stop-Process -Id $($proc.Id)"
Write-Host "or: Get-Process cloudflared | Stop-Process"
