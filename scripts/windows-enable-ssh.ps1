$ErrorActionPreference = "Stop"

Write-Host "=== OpenSSH Server Status ==="
Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*'

$cap = Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*'
if ($cap.State -ne "Installed") {
  Write-Host "`nInstalling OpenSSH Server..."
  Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
}

Write-Host "`n=== OpenSSH Server Status After Install ==="
Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*'

Write-Host "`nStarting sshd..."
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic

if (-not (Get-NetFirewallRule -Name sshd-22 -ErrorAction SilentlyContinue)) {
  Write-Host "Creating firewall rule for port 22..."
  New-NetFirewallRule -Name sshd-22 -DisplayName "OpenSSH Server (22)" -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 | Out-Null
} else {
  Write-Host "Firewall rule sshd-22 already exists."
}

Write-Host "`n=== sshd Service ==="
Get-Service sshd

Write-Host "`n=== Port 22 Listener ==="
Get-NetTCPConnection -State Listen | Where-Object LocalPort -eq 22

Write-Host "`nDone."
