param(
  [Parameter(Mandatory=$true)][string]$RecoveryToken,
  [string]$InstallDir = "$env:ProgramData\SheliaRecovery",
  [string]$Python = "python"
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
$pythonCommand = Get-Command $Python -ErrorAction Stop
$pythonPath = $pythonCommand.Source
$source = Join-Path $PSScriptRoot 'service.py'
Copy-Item -Force $source (Join-Path $InstallDir 'service.py')
$tokenFile = Join-Path $InstallDir 'shelia-token.txt'
[System.IO.File]::WriteAllText($tokenFile, $RecoveryToken, (New-Object System.Text.UTF8Encoding($false)))
$acl = Get-Acl $tokenFile
$acl.SetAccessRuleProtection($true, $false)
$acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule('SYSTEM','Read','Allow')))
$acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule('Administrators','Read','Allow')))
Set-Acl -Path $tokenFile -AclObject $acl

$taskName = 'Shelia Rosemary46 Recovery Service'
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$InstallDir\service.py`"" -WorkingDirectory $InstallDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null

New-NetFirewallRule -DisplayName 'Shelia Rosemary46 Recovery (Tailscale)' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8795 -LocalAddress 100.106.176.58 -RemoteAddress 100.80.49.10 -Profile Any -ErrorAction SilentlyContinue | Out-Null
Write-Output "Installed $taskName. Start it with: Start-ScheduledTask -TaskName '$taskName'"
