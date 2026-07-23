# Holds Ubuntu-26.04 open so WSL never terminates the distro out from under the dashboard.
# WSL logs "InitEntryUtilityVm: Init has exited. Terminating distribution" when nothing is
# attached; every such teardown risks leaving the user@1000 cgroup wedged.
# Scheduled task: "ROL WSL26 Holder" (/sc onlogon). Loops forever; if the client ever returns,
# it reattaches immediately.
$ErrorActionPreference = 'SilentlyContinue'
while ($true) {
  & wsl.exe -d Ubuntu-26.04 -e sleep 3600 | Out-Null
  Start-Sleep -Milliseconds 500
}
