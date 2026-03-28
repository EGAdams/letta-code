# fix_ssh_auth.ps1 — fix Windows OpenSSH authorized_keys for both admin and regular users
# Run as Administrator in PowerShell

$key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJu4jIb5347YGP4FwD9xaFEERPdjBoNBUYJdiCzh3a5G adamsl@DESKTOP-2OBSQMC"

# ── 1. Administrator-level authorized_keys (used when NewUser is in Administrators group) ──
Write-Host "Writing administrators_authorized_keys..." -ForegroundColor Cyan
$adminKeys = "C:\ProgramData\ssh\administrators_authorized_keys"
Set-Content -Path $adminKeys -Value $key -Encoding UTF8
icacls $adminKeys /inheritance:r /grant "SYSTEM:F" /grant "Administrators:F"
Write-Host "Done." -ForegroundColor Green

# ── 2. Per-user authorized_keys (used when NewUser is a standard user) ──────────────────
Write-Host "Writing per-user authorized_keys..." -ForegroundColor Cyan
$sshDir  = "C:\Users\NewUser\.ssh"
$userKeys = "$sshDir\authorized_keys"
New-Item -ItemType Directory -Force -Path $sshDir | Out-Null
Set-Content -Path $userKeys -Value $key -Encoding UTF8
icacls $userKeys /inheritance:r /grant "NewUser:F" /grant "SYSTEM:F"
Write-Host "Done." -ForegroundColor Green

# ── 3. Show relevant sshd_config lines for diagnosis ─────────────────────────────────────
Write-Host ""
Write-Host "=== Relevant sshd_config lines ===" -ForegroundColor Yellow
$config = "C:\ProgramData\ssh\sshd_config"
Get-Content $config | Select-String "AuthorizedKeys|PubkeyAuth|Match Group"

# ── 4. Restart sshd to pick up any changes ───────────────────────────────────────────────
Write-Host ""
Write-Host "Restarting sshd..." -ForegroundColor Cyan
Restart-Service sshd
Write-Host "sshd restarted." -ForegroundColor Green
