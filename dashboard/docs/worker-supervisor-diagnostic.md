# Worker Supervisor diagnostic

`GET /api/worker-activity` now includes `diagnostic`.  The dashboard calls a
worker **healthy** only when all available evidence agrees:

- the systemd-reported PID can be read locally and its exact `/proc/<pid>/cmdline`
  contains the expected bridge worker name;
- the worker state contains a fresh heartbeat (`heartbeat_at`,
  `last_check_at`, or `updated_at`); and
- queued work is not older than `WORKER_STAGNATION_SECONDS` (default 300s).

`offline` means the expected local process was not proven. `stalled` means the
process exists but its heartbeat is old or queued work has stopped advancing.
An absent task ledger is reported as unavailable; it is never treated as an
empty queue. The response includes evidence and an actionable next step.

## Current boundary and safe restart design

This workspace can inspect only the machine hosting the dashboard. It cannot
truthfully inspect a worker in another WSL instance when `/proc`, the worker's
state file, or a local systemd user bus is not mounted/reachable. The missing
capabilities are: an on-machine process probe, read-only access to the worker
heartbeat/ledger paths, and (only if separately authorized) a fixed service
manager adapter. No unrestricted SSH/WSL command or service restart is used.

The least-privilege adapter contract is:

```text
inspect(pid) -> { pid, present, command, reason }       # read-only
read_heartbeat() -> { timestamp, phase, attempts }      # read-only
read_tasks() -> [{ id, status, queue_age, attempts, ... }] # read-only
restart() -> result                                     # separate, explicit authorization
```

An authorized host may provide these operations through a narrowly scoped
local helper (for example, a systemd socket policy limited to
`agent-bridge-worker.service`). The dashboard must receive structured output,
not an arbitrary shell command. The existing restart endpoint remains token
protected and was not invoked or broadened by this change.
