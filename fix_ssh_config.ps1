# fix_ssh_config.ps1 — uncomment PubkeyAuthentication and fix admin authorized_keys
# Run as Administrator in PowerShell

$key    = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJu4jIb5347YGP4FwD9xaFEERPdjBoNBUYJdiCzh3a5G adamsl@DESKTOP-2OBSQMC"
$config = "C:\ProgramData\ssh\sshd_config"

# ── 1. Uncomment PubkeyAuthentication yes ────────────────────────────────────
Write-Host "Enabling PubkeyAuthentication in sshd_config..." -ForegroundColor Cyan
$content = Get-Content $config -Raw
$content = $content -replace '#PubkeyAuthentication yes', 'PubkeyAuthentication yes'
Set-Content -Path $config -Value $content -Encoding UTF8
Write-Host "Done." -ForegroundColor Green

# ── 2. Write key to administrators_authorized_keys ───────────────────────────
Write-Host "Writing administrators_authorized_keys..." -ForegroundColor Cyan
$adminKeys = "C:\ProgramData\ssh\administrators_authorized_keys"
Set-Content -Path $adminKeys -Value $key -Encoding UTF8

# Permissions must be exactly SYSTEM + Administrators only (no inheritance)
icacls $adminKeys /inheritance:r /grant "SYSTEM:F" /grant "Administrators:F"
Write-Host "Done." -ForegroundColor Green

# ── 3. Restart sshd ──────────────────────────────────────────────────────────
Write-Host "Restarting sshd..." -ForegroundColor Cyan
Restart-Service sshd
Write-Host "sshd restarted." -ForegroundColor Green

# ── 4. Confirm config ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Current sshd_config relevant lines ===" -ForegroundColor Yellow
Get-Content $config | Select-String "AuthorizedKeys|PubkeyAuth|Match Group"
