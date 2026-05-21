# install_openssh.ps1 — installs OpenSSH Server on Windows 10 without Windows Update
# Run as Administrator in PowerShell

$ErrorActionPreference = "Stop"

# ── 1. Try winget first (fastest) ───────────────────────────────────────────
Write-Host "Trying winget install..." -ForegroundColor Cyan
try {
    winget install --id Microsoft.OpenSSH.Beta -e --accept-source-agreements --accept-package-agreements
    Write-Host "winget install succeeded." -ForegroundColor Green
} catch {
    Write-Host "winget not available or failed, falling back to manual install..." -ForegroundColor Yellow

    # ── 2. Download OpenSSH portable from GitHub ────────────────────────────
    $release = "9.8.1.0p1-Beta"
    $zip     = "OpenSSH-Win64-v$release.zip"
    $url     = "https://github.com/PowerShell/Win32-OpenSSH/releases/download/v$release/$zip"
    $dest    = "$env:TEMP\$zip"
    $install = "C:\Program Files\OpenSSH"

    Write-Host "Downloading $url ..." -ForegroundColor Cyan
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing

    Write-Host "Extracting to $install ..." -ForegroundColor Cyan
    Expand-Archive -Path $dest -DestinationPath "C:\Program Files\" -Force
    Rename-Item "C:\Program Files\OpenSSH-Win64" $install -ErrorAction SilentlyContinue

    Write-Host "Running install script..." -ForegroundColor Cyan
    & "$install\install-sshd.ps1"
}

# ── 3. Start and enable the service ─────────────────────────────────────────
Write-Host "Starting sshd service..." -ForegroundColor Cyan
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic

# ── 4. Open firewall port 22 ─────────────────────────────────────────────────
Write-Host "Opening firewall port 22..." -ForegroundColor Cyan
New-NetFirewallRule -Name "sshd" `
                    -DisplayName "OpenSSH Server (sshd)" `
                    -Enabled True `
                    -Direction Inbound `
                    -Protocol TCP `
                    -Action Allow `
                    -LocalPort 22 `
                    -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Done! SSH server is running on port 22." -ForegroundColor Green
Write-Host "Connect with:  ssh $env:USERNAME@$(
    (Get-NetIPAddress -AddressFamily IPv4 |
     Where-Object { $_.IPAddress -like '10.*' -or $_.IPAddress -like '192.*' } |
     Select-Object -First 1).IPAddress
)" -ForegroundColor Yellow
