# Independent documentation service

On DESKTOP-2OBSQMC, `agent-blocks-server.service` owns the Agent Blocks
documentation server on port 8931. The reviewed unit is
`config/agent-blocks-server.service`; install it in `~/.config/systemd/user/`.
It reuses `spa_documentation/start.sh 8931`, including its existing build step,
working directory and Python selection. It has no dashboard dependency.

Dashboard startup and the Server Management action call
`servers.agent_blocks.AgentBlocksServer`, which checks HTTP health and requests
`systemctl --user start --no-block agent-blocks-server.service` when needed.
It never launches the documentation process itself. A new process session alone
does not separate systemd control groups.

On 2026-11-06, live PID 14906 and its shell parent 14800 were adopted into the
independent unit without restarting the server or rebinding its socket.
The temporary adoption configuration was removed afterward; normal future
starts use the permanent startup script. The unit uses `ExitType=cgroup` to track
the adopted shell and server together, including their exit during this first
service lifetime. Both staging and production retained an open HTTP connection
across adoption. Production retained another connection
across the authorized dashboard restart (14778 to 978832).
No Chrome connection was present at adoption; no Chrome process was stopped.

The previous independent unit had been repeatedly failing with address-in-use
because the dashboard owned the port. Its backup and migration evidence are in
`/tmp/adw-docs-separation/`. Those PID-specific scripts are historical evidence,
not reusable startup commands. Staging services have been removed.

Verify ownership with `systemctl --user show agent-blocks-server.service
-p MainPID -p ControlGroup`, `cat /proc/<pid>/cgroup`, and HTTP on port 8931.
Do not restart a documentation server while Chrome has an active connection
without accounting for that interruption. Do not change dashboard KillMode.

The dashboard now publishes the independent ADW supervisor's escalation state.
Worker Activity explicitly discloses incomplete gateway coverage and unverified
model readiness. The supervisor and bridge worker were not restarted.
