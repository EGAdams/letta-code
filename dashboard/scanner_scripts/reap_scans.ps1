# Reaper: kill any lingering scan_device.ps1 Windows powershell processes.
#
# When the dashboard's scan subprocess times out, Python kills the bash wrapper
# but NOT the Windows powershell.exe it launched via WSL interop (it's a separate
# Windows process). A blocked WIA call in such a leaked process keeps the scanner
# "busy" and, if they accumulate, wedges the whole Windows Image Acquisition
# service (stisvc). The dashboard runs this reaper under its scan lock right
# BEFORE each scan, so any scan_device.ps1 still alive is a leak and safe to kill.
#
# Only targets scan_device.ps1 (the dashboard's own script) — never the user's
# manual scan_image.ps1. Uses no WIA calls, so it stays fast even if stisvc is
# wedged.
$procs = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
  Where-Object { $_.CommandLine -like '*scan_device.ps1*' }
$n = 0
foreach ($p in $procs) {
  try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop; $n++ } catch {}
}
Write-Output ("reaped=" + $n)
