# Keeps the ROL Finance dashboard alive on DESKTOP-2OBSQMC.
# Ubuntu-26.04 is the ONLY distro allowed to serve the dashboard (24.04's unit is masked to /dev/null).
#
# Root cause this guards against: nothing held Ubuntu-26.04 open, so WSL terminated the whole
# distro when the last command exited. That dirty teardown left foreign-PID cgroups behind, and
# the next start of user@1000.service failed with EBUSY -> every user service (dashboard-server,
# lettabot, thought-bridge, mazda-*) stayed dead. Holding one long-lived process in the distro
# stops the termination, and therefore stops the wedge.
#
# Scheduled task: "ROL Dashboard Keepalive", every 2 minutes.
$ErrorActionPreference = 'SilentlyContinue'
$log = "$env:USERPROFILE\keep-dashboard-up.log"
function Log($m) { "$(Get-Date -f 'yyyy-MM-dd HH:mm:ss') $m" | Out-File -Append -Encoding utf8 $log }

function WslOut($cmd) {
  $o = & wsl.exe -d Ubuntu-26.04 -e bash -lc $cmd 2>$null
  return (($o -join "`n") -replace "`0", "").Trim()
}

# 1. A long-lived holder process must exist inside the distro, or WSL shuts the distro down.
#    Owned by the "ROL WSL26 Holder" scheduled task. Check the TASK state on the Windows side --
#    probing for the process through `wsl.exe -e bash -lc "...^sleep 3600$..."` misreports, because
#    the regex anchors do not survive the nested quoting.
$holderTask = (& schtasks.exe /query /tn "ROL WSL26 Holder" /fo list 2>$null | Select-String '^Status:').ToString()
if ($holderTask -notmatch 'Running') {
  Log "holder task not running ($holderTask) -> starting ROL WSL26 Holder"
  & schtasks.exe /run /tn "ROL WSL26 Holder" | Out-Null
  Start-Sleep -Seconds 8
}

# 2. systemd --user session must be healthy (the cgroup-v2 EBUSY wedge).
$user1000 = WslOut 'systemctl is-active user@1000.service'
if ($user1000 -ne 'active') {
  Log "user@1000.service=$user1000 -> running fix-user-session.sh (detached)"
  # systemd-run, not `setsid nohup`: the recovery must outlive the WSL session it was launched from.
  WslOut 'sudo -n systemctl reset-failed fix-user-session.service 2>/dev/null; sudo -n systemd-run --unit=fix-user-session --collect /home/adamsl/bin/fix-user-session.sh' | Out-Null
  Start-Sleep -Seconds 25
}

# 3. Dashboard itself must answer. Two strikes before acting, so blips don't trigger a restart.
$code = WslOut "curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://localhost:8765/"
if ($code -ne '200') {
  Start-Sleep -Seconds 10
  $code = WslOut "curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://localhost:8765/"
}
if ($code -ne '200') {
  Log "dashboard http=$code -> restarting dashboard-server.service"
  WslOut 'systemctl --user restart dashboard-server.service' | Out-Null
  Start-Sleep -Seconds 8
  Log ("after restart http=" + (WslOut "curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://localhost:8765/"))
}
