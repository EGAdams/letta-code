# windows10-fix-logviewer-firewall.ps1
# Run in elevated PowerShell (Administrator) on Windows 10.

$ErrorActionPreference = 'Stop'

function Assert-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p = New-Object Security.Principal.WindowsPrincipal($id)
  if (-not $p.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
    throw 'Run this script in elevated PowerShell (Administrator).'
  }
}

Assert-Admin

$port = 3030

Write-Host "Removing old Dashboard Tailnet rules..." -ForegroundColor Cyan
Get-NetFirewallRule -DisplayName "Dashboard Tailnet 3030*" -ErrorAction SilentlyContinue |
  Remove-NetFirewallRule -ErrorAction SilentlyContinue

Write-Host "Creating IPv4 Tailnet rule..." -ForegroundColor Cyan
New-NetFirewallRule -DisplayName "Dashboard Tailnet 3030 IPv4" `
  -Direction Inbound -Protocol TCP -LocalPort $port `
  -RemoteAddress "100.64.0.0/10" -Action Allow -Profile Any | Out-Null

Write-Host "Creating IPv6 Tailnet rule..." -ForegroundColor Cyan
New-NetFirewallRule -DisplayName "Dashboard Tailnet 3030 IPv6" `
  -Direction Inbound -Protocol TCP -LocalPort $port `
  -RemoteAddress "fd7a:115c:a1e0::/48" -Action Allow -Profile Any | Out-Null

Write-Host "\nRules now:" -ForegroundColor Green
Get-NetFirewallRule -DisplayName "Dashboard Tailnet 3030*" |
  Get-NetFirewallAddressFilter |
  Select-Object Name,RemoteAddress | Format-Table -Auto

Write-Host "\nLocal endpoint test:" -ForegroundColor Green
Test-NetConnection 127.0.0.1 -Port $port |
  Select-Object ComputerName,RemotePort,TcpTestSucceeded | Format-Table -Auto

$tsExe = "$env:ProgramFiles\Tailscale\tailscale.exe"
if (-not (Test-Path $tsExe)) { $tsExe = "$env:ProgramFiles(x86)\Tailscale\tailscale.exe" }

if (Test-Path $tsExe) {
  $dns = $null
  $ip4 = $null
  try { $dns = ((& $tsExe status --json | ConvertFrom-Json).Self.DNSName).TrimEnd('.') } catch {}
  try { $ip4 = (& $tsExe ip -4 | Select-Object -First 1).Trim() } catch {}

  Write-Host "\nURL candidates:" -ForegroundColor Green
  if ($dns) { Write-Host "http://$dns`:$port" }
  if ($ip4) { Write-Host "http://$ip4`:$port" }
}

Write-Host "\nDone." -ForegroundColor Green
