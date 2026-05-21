# windows10-fix-ssh-auth.ps1
# Run in elevated PowerShell (Administrator) on Windows 10.

$ErrorActionPreference = 'Stop'

$u = "$env:USERDOMAIN\$env:USERNAME"
$sshDir = "$env:USERPROFILE\.ssh"
$auth = "$sshDir\authorized_keys"
$key = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJu4jIb5347YGP4FwD9xaFEERPdjBoNBUYJdiCzh3a5G adamsl@DESKTOP-2OBSQMC'

New-Item -ItemType Directory -Force $sshDir | Out-Null
Set-Content -Path $auth -Value $key -Encoding ascii

# OpenSSH-safe ACLs
icacls $sshDir /inheritance:r | Out-Null
icacls $sshDir /grant:r ("${u}:(OI)(CI)F") "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" | Out-Null
icacls $auth /inheritance:r | Out-Null
icacls $auth /grant:r ("${u}:F") "SYSTEM:F" "Administrators:F" | Out-Null

# Ensure pubkey auth is enabled
$cfg = "C:\ProgramData\ssh\sshd_config"
if (Test-Path $cfg) {
  $c = Get-Content $cfg -Raw
  if ($c -notmatch '(?m)^\s*PubkeyAuthentication\s+') {
    Add-Content $cfg "`nPubkeyAuthentication yes"
  }
  else {
    $c = $c -replace '(?m)^\s*#?\s*PubkeyAuthentication\s+.*$', 'PubkeyAuthentication yes'
    Set-Content $cfg $c
  }
}

Restart-Service sshd
Write-Host 'SSH key auth remediation complete.' -ForegroundColor Green
