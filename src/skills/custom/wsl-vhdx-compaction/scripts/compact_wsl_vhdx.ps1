param(
  [Parameter(Mandatory=$true)]
  [string]$DistroName,

  [switch]$SkipSparseToggle
)

function Assert-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p  = New-Object Security.Principal.WindowsPrincipal($id)
  if (-not $p.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
    throw "Run this script in an elevated (Admin) PowerShell."
  }
}

function Get-Ext4VhdxPath([string]$Name) {
  $lxss = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss"
  foreach ($k in Get-ChildItem $lxss) {
    $p = Get-ItemProperty $k.PSPath
    if ($p.DistributionName -eq $Name) {
      return (Join-Path $p.BasePath "ext4.vhdx")
    }
  }
  throw "Could not find distro '$Name' in $lxss"
}

Assert-Admin

$vhdx = Get-Ext4VhdxPath $DistroName
if (-not (Test-Path $vhdx)) { throw "VHDX not found: $vhdx" }

Write-Host "[wsl] shutting down WSL..."
wsl.exe --shutdown

if (-not $SkipSparseToggle) {
  Write-Host "[wsl] set-sparse false..."
  wsl.exe --manage $DistroName --set-sparse false
}

Write-Host "[diskpart] compacting: $vhdx"
$dp = @"
select vdisk file="$vhdx"
attach vdisk readonly
compact vdisk
detach vdisk
exit
"@

$dpFile = Join-Path $env:TEMP "wsl_compact_diskpart.txt"
Set-Content -Path $dpFile -Value $dp -Encoding ASCII

diskpart /s $dpFile

if (-not $SkipSparseToggle) {
  Write-Host "[wsl] set-sparse true..."
  wsl.exe --manage $DistroName --set-sparse true
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "Sparse VHD re-enable failed; leaving sparse disabled."
  }
}

Write-Host "[done] Compaction complete."