# Read-only scanner-workflow health probe. One PowerShell launch reports every
# Windows-side failure point the dashboard's scanner LEDs surface, as compact
# JSON on the last line:
#   {"stisvc":"Running","stale_scans":0,"driver_present":true,
#    "driver_status":"OK","wia":"present"}
#
# It NEVER transfers a scan (that's scan_device.ps1). The only WIA COM call is a
# device *enumeration*, and it is wrapped in a timed Start-Job so a wedged
# Windows Image Acquisition service (the exact fault we're trying to detect)
# cannot hang the probe — it reports "timeout" instead. Everything else
# (Get-Service / Get-PnpDevice / Get-CimInstance) is safe even when stisvc is wedged.
param(
    [string]$NameLike = "",       # WIA device Name substring (e.g. HP063E28)
    [string]$FriendlyLike = "",   # PnP Image-class FriendlyName substring (model)
    [switch]$SkipWia              # set while a real scan holds the device
)
$ErrorActionPreference = "Continue"
$r = [ordered]@{}

# Windows Image Acquisition service — the "wedge" everyone power-cycles for.
try {
    $r.stisvc = [string](Get-Service -Name stisvc -ErrorAction Stop).Status
} catch { $r.stisvc = "unknown" }

# HP Print and Scan Doctor leaves an auto-start service behind.  It can hold one
# HP scanner open while WIA enumeration still succeeds, which makes every older
# LED green even though an actual scan fails with "device is busy".
try {
    $r.hp_scan_doctor = [string](
        Get-Service -Name HPPrintScanDoctorService -ErrorAction Stop
    ).Status
} catch { $r.hp_scan_doctor = "absent" }

# Leaked scan_device.ps1 processes — a leading indicator of an impending wedge.
try {
    $r.stale_scans = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
        Where-Object { $_.CommandLine -like '*scan_device.ps1*' }).Count
} catch { $r.stale_scans = -1 }

# Driver / PnP imaging-device health — answers "do we need to reinstall the driver".
try {
    $pnp = @(Get-PnpDevice -Class Image -ErrorAction Stop |
        Where-Object { $_.FriendlyName -like ("*" + $FriendlyLike + "*") })
    if ($pnp.Count -gt 0) {
        $r.driver_present = $true
        $r.driver_status = [string]$pnp[0].Status   # OK / Error / Unknown / Degraded
    } else {
        $r.driver_present = $false
        $r.driver_status = "absent"
    }
} catch { $r.driver_present = $null; $r.driver_status = "unknown" }

# WIA enumeration by name, followed by a non-transfer Connect() probe.  Merely
# seeing the device is not enough: HP Print and Scan Doctor can leave it present
# but exclusively held. Guarded by a timed job so a wedged stisvc reports
# "timeout" rather than hanging us.
if ($SkipWia) {
    $r.wia = "skipped"
    $r.wia_connect = "skipped"
} elseif ($r.stisvc -ne "Running") {
    $r.wia = "service-down"
    $r.wia_connect = "service-down"
} else {
    $job = Start-Job -ScriptBlock {
        param($n)
        try {
            $wia = New-Object -ComObject WIA.DeviceManager
            $infos = @($wia.DeviceInfos | Where-Object { $_.Type -eq 1 })
            if ($n -ne "") {
                $infos = @($infos | Where-Object {
                    $nm = $null
                    try { $nm = $_.Properties.Item("Name").Value } catch {}
                    $nm -like ("*" + $n + "*")
                })
            }
            if ($infos.Count -eq 0) {
                [pscustomobject]@{ wia = "absent"; connect = "not-tested" }
            } else {
                try {
                    $device = $infos[0].Connect()
                    if ($null -ne $device) {
                        [pscustomobject]@{ wia = "present"; connect = "ready" }
                    } else {
                        [pscustomobject]@{ wia = "present"; connect = "error" }
                    }
                } catch {
                    $connect = if ($_.Exception.Message -match "busy") {
                        "busy"
                    } else {
                        "error"
                    }
                    [pscustomobject]@{ wia = "present"; connect = $connect }
                }
            }
        } catch {
            $state = if ($_.Exception.Message -match "busy") { "busy" } else { "error" }
            [pscustomobject]@{ wia = $state; connect = $state }
        }
    } -ArgumentList $NameLike
    if (Wait-Job $job -Timeout 8) {
        $probe = Receive-Job $job
        $r.wia = [string]$probe.wia
        $r.wia_connect = [string]$probe.connect
    } else {
        $r.wia = "timeout"
        $r.wia_connect = "timeout"
        Stop-Job $job -ErrorAction SilentlyContinue
    }
    Remove-Job $job -Force -ErrorAction SilentlyContinue
}

$r | ConvertTo-Json -Compress
