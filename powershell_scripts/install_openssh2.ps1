# install_openssh2.ps1 — direct GitHub download, no winget
# Run as Administrator in PowerShell

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$installDir = "C:\Program Files\OpenSSH"
$zipPath    = "$env:TEMP\OpenSSH.zip"
$url        = "https://github.com/PowerShell/Win32-OpenSSH/releases/download/v9.8.1.0p1-Beta/OpenSSH-Win64-v9.8.1.0p1-Beta.zip"

# ── 1. Download ──────────────────────────────────────────────────────────────
Write-Host "Downloading OpenSSH from GitHub..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing
Write-Host "Downloaded to $zipPath" -ForegroundColor Green

# ── 2. Extract ───────────────────────────────────────────────────────────────
Write-Host "Extracting..." -ForegroundColor Cyan
if (Test-Path $installDir) { Remove-Item $installDir -Recurse -Force }
Expand-Archive -Path $zipPath -DestinationPath "C:\Program Files\" -Force
$extracted = Get-ChildItem "C:\Program Files\" | Where-Object { $_.Name -like "OpenSSH*" } | Select-Object -First 1
Rename-Item $extracted.FullName $installDir
Write-Host "Installed to $installDir" -ForegroundColor Green

# ── 3. Install service ───────────────────────────────────────────────────────
Write-Host "Installing sshd service..." -ForegroundColor Cyan
& "$installDir\install-sshd.ps1"

# ── 4. Start and enable ──────────────────────────────────────────────────────
Write-Host "Starting sshd..." -ForegroundColor Cyan
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
Write-Host "sshd is running." -ForegroundColor Green

# ── 5. Firewall ──────────────────────────────────────────────────────────────
Write-Host "Opening port 22 in firewall..." -ForegroundColor Cyan
New-NetFirewallRule -Name "sshd" `
                    -DisplayName "OpenSSH Server (sshd)" `
                    -Enabled True `
                    -Direction Inbound `
                    -Protocol TCP `
                    -Action Allow `
                    -LocalPort 22 `
                    -ErrorAction SilentlyContinue
Write-Host "Firewall rule added." -ForegroundColor Green

# ── 6. Show connection info ───────────────────────────────────────────────────
$ip = (Get-NetIPAddress -AddressFamily IPv4 |
       Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.*' } |
       Select-Object -First 1).IPAddress
Write-Host ""
Write-Host "SSH server ready. Connect with:" -ForegroundColor Yellow
Write-Host "  ssh $env:USERNAME@$ip" -ForegroundColor Yellow
