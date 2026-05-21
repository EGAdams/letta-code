# windows10-public-internet-url-logviewer-v3.ps1
# Creates a public Internet URL for local log viewer (default localhost:8080)
# using Cloudflare Quick Tunnel (no domain needed).
# Run in PowerShell (Admin recommended).

param(
  [int]$LocalPort = 8080
)

$ErrorActionPreference = 'Stop'

function Ensure-Cloudflared {
  $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
  if ($cmd -and (Test-Path $cmd.Source)) { return $cmd.Source }

  $common = @(
    "$env:ProgramFiles\cloudflared\cloudflared.exe",
    "$env:ProgramFiles(x86)\cloudflared\cloudflared.exe",
    "$env:LocalAppData\cloudflared\cloudflared.exe"
  )
  foreach ($p in $common) { if (Test-Path $p) { return $p } }

  try {
    Write-Host "Installing cloudflared via winget..." -ForegroundColor Yellow
    winget install --id Cloudflare.cloudflared --source winget -e | Out-Null
  } catch {
    Write-Warning "winget install failed: $($_.Exception.Message)"
  }

  $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
  if ($cmd -and (Test-Path $cmd.Source)) { return $cmd.Source }
  foreach ($p in $common) { if (Test-Path $p) { return $p } }

  $targetDir = "$env:LocalAppData\cloudflared"
  New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
  $targetExe = Join-Path $targetDir 'cloudflared.exe'
  $url = 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe'
  Write-Host "Downloading cloudflared directly..." -ForegroundColor Yellow
  Invoke-WebRequest -Uri $url -OutFile $targetExe -UseBasicParsing
  if (-not (Test-Path $targetExe)) { throw 'cloudflared download failed.' }
  return $targetExe
}

function Ensure-FirewallOutbound([string]$exePath) {
  New-NetFirewallRule -DisplayName 'cloudflared outbound tcp 443' `
    -Direction Outbound -Program $exePath -Protocol TCP -RemotePort 443 -Action Allow -Profile Any -ErrorAction SilentlyContinue | Out-Null
  New-NetFirewallRule -DisplayName 'cloudflared outbound udp 7844' `
    -Direction Outbound -Program $exePath -Protocol UDP -RemotePort 7844 -Action Allow -Profile Any -ErrorAction SilentlyContinue | Out-Null
}

# Verify local app
try {
  $status = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 6 "http://localhost:$LocalPort").StatusCode
  Write-Host "Local log viewer OK on http://localhost:$LocalPort (HTTP $status)" -ForegroundColor Green
} catch {
  throw "Local app not reachable on http://localhost:$LocalPort. Start it first."
}

$cloudflared = Ensure-Cloudflared
Write-Host "Using cloudflared: $cloudflared" -ForegroundColor Cyan

try {
  Ensure-FirewallOutbound -exePath $cloudflared
  Write-Host "Firewall outbound rules ensured for cloudflared." -ForegroundColor Green
} catch {
  Write-Warning "Could not add firewall rules (try running as Admin): $($_.Exception.Message)"
}

$stdoutLog = Join-Path $env:TEMP "cloudflared-logviewer-$LocalPort.out.log"
$stderrLog = Join-Path $env:TEMP "cloudflared-logviewer-$LocalPort.err.log"
if (Test-Path $stdoutLog) { Remove-Item $stdoutLog -Force }
if (Test-Path $stderrLog) { Remove-Item $stderrLog -Force }

Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$proc = Start-Process -FilePath $cloudflared `
  -ArgumentList @('tunnel','--url',"http://localhost:$LocalPort",'--no-autoupdate') `
  -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog `
  -PassThru

Write-Host "Started cloudflared (PID $($proc.Id)). Waiting for public URL..." -ForegroundColor Cyan

$url = $null
for ($i = 0; $i -lt 100; $i++) {
  Start-Sleep -Milliseconds 400
  $out = ''
  if (Test-Path $stdoutLog) { $out += (Get-Content $stdoutLog -Raw -ErrorAction SilentlyContinue) }
  if (Test-Path $stderrLog) { $out += "`n" + (Get-Content $stderrLog -Raw -ErrorAction SilentlyContinue) }
  if ($out -match 'https://[-a-z0-9]+\.trycloudflare\.com') {
    $url = $matches[0]
    break
  }
}

if (-not $url) {
  Write-Warning "Could not detect URL yet. Follow logs:"
  Write-Host "Get-Content '$stdoutLog' -Wait"
  Write-Host "Get-Content '$stderrLog' -Wait"
  Write-Host "Tunnel PID: $($proc.Id)"
  exit 1
}

Write-Host "`nPUBLIC INTERNET URL:" -ForegroundColor Green
Write-Host $url -ForegroundColor Green
Write-Host "`nStop tunnel later with:" -ForegroundColor Yellow
Write-Host "Stop-Process -Id $($proc.Id)"
