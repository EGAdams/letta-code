# windows10-enable-ssh-key.ps1
# Run in PowerShell on Windows 10 as the target user.
# If Restart-Service fails, rerun from elevated PowerShell.

$ErrorActionPreference = 'Stop'

# Correct public key for THIS machine (~/.ssh/id_ed25519.pub)
$pubKey = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJu4jIb5347YGP4FwD9xaFEERPdjBoNBUYJdiCzh3a5G adamsl@DESKTOP-2OBSQMC'
$sshDir = Join-Path $env:USERPROFILE '.ssh'
$authFile = Join-Path $sshDir 'authorized_keys'

New-Item -ItemType Directory -Force -Path $sshDir | Out-Null
Set-Content -Path $authFile -Value $pubKey -Encoding Ascii -NoNewline
Add-Content -Path $authFile -Value "`r`n" -Encoding Ascii

$me = "$env:USERDOMAIN\$env:USERNAME"
icacls $sshDir /inheritance:r | Out-Null
icacls $sshDir /grant:r ("${me}:(OI)(CI)F") | Out-Null
icacls $authFile /inheritance:r | Out-Null
icacls $authFile /grant:r ("${me}:F") | Out-Null

$sshd = Get-Service -Name sshd -ErrorAction SilentlyContinue
if ($sshd) {
    try {
        Restart-Service sshd -ErrorAction Stop
        Write-Host 'sshd restarted.' -ForegroundColor Green
    } catch {
        Write-Warning 'Could not restart sshd (likely needs Admin). Run in elevated PowerShell: Restart-Service sshd'
    }
} else {
    Write-Warning 'sshd service not found. Install OpenSSH Server first.'
}

Write-Host "Done. authorized_keys written to: $authFile" -ForegroundColor Green
