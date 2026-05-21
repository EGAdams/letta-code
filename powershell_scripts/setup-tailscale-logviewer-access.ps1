# setup-tailscale-logviewer-access.ps1
# Purpose: Ensure Tailscale + firewall are configured so log viewer is reachable over Tailnet.
# Run in elevated PowerShell (Administrator) on Windows 10.

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
if (-not $ts) {
  Write-Host "Installing Tailscale from winget source..." -ForegroundColor Yellow
  winget install --id Tailscale.Tailscale --source winget -e
  $ts = Find-TailscaleExe
}
if (-not $ts) { throw "Tailscale not found after install attempt." }

# Ensure service is running
Set-Service -Name Tailscale -StartupType Automatic -ErrorAction SilentlyContinue
Start-Service -Name Tailscale -ErrorAction SilentlyContinue

# Ensure outbound rules for Tailscale binaries
$tsDir = Split-Path $ts -Parent
$bins = @("tailscale.exe","tailscale-ipn.exe","tailscaled.exe") | ForEach-Object { Join-Path $tsDir $_ }
foreach ($bin in $bins) {
  if (Test-Path $bin) {
    New-NetFirewallRule -DisplayName "Allow $([IO.Path]::GetFileName($bin)) Inbound"  -Direction Inbound  -Program $bin -Action Allow -Profile Any -ErrorAction SilentlyContinue | Out-Null
    New-NetFirewallRule -DisplayName "Allow $([IO.Path]::GetFileName($bin)) Outbound" -Direction Outbound -Program $bin -Action Allow -Profile Any -ErrorAction SilentlyContinue | Out-Null
  }
}

# Allow common log viewer ports from Tailnet only
$ports = @(3000,3030,8080)
foreach ($p in $ports) {
  New-NetFirewallRule -DisplayName "Log Viewer Tailnet TCP $p" `
    -Direction Inbound -Protocol TCP -LocalPort $p `
    -RemoteAddress "100.64.0.0/10,fd7a:115c:a1e0::/48" -Action Allow -Profile Any -ErrorAction SilentlyContinue | Out-Null
}

# Print status + URLs
$status = & $ts status --json | ConvertFrom-Json
$dns = $status.Self.DNSName.TrimEnd('.')
$ip4 = (& $ts ip -4 | Select-Object -First 1).Trim()

Write-Host "`nTailscale device:" -ForegroundColor Cyan
Write-Host "DNS: $dns"
Write-Host "IP4: $ip4"

Write-Host "`nLog viewer URL candidates:" -ForegroundColor Green
foreach ($p in $ports) {
  if ($dns) { Write-Host ("http://{0}:{1}" -f $dns, $p) }
  if ($ip4) { Write-Host ("http://{0}:{1}" -f $ip4, $p) }
}

Write-Host "`nDone." -ForegroundColor Green
