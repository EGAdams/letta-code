# Holds Ubuntu-26.04 open so WSL never terminates the distro out from under the dashboard.
# WSL logs "InitEntryUtilityVm: Init has exited. Terminating distribution" when nothing is
# attached; every such teardown risks leaving the user@1000 cgroup wedged.
#
# This is NOT a poll. `sleep infinity` blocks forever, so steady state is one idle process and
# zero window activity. The loop body only runs again if the client actually died -- which is
# the event worth reacting to -- and then it blocks again. (It used to be `sleep 3600`, which
# re-attached every hour and flashed a console window each time.)
#
# Launched by task "ROL WSL26 Holder" (/sc onlogon) via hold-ubuntu2604-hidden.vbs, which starts
# it with no console window. Do not point the task at powershell.exe directly: a console process
# started by an interactive task flashes a visible window every time it launches.
$ErrorActionPreference = 'SilentlyContinue'
while ($true) {
  & wsl.exe -d Ubuntu-26.04 -e sleep infinity | Out-Null
  Start-Sleep -Seconds 5
}
