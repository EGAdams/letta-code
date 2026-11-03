# Worker Activity integration

The System Status > Worker Activity section is read-only. It always reports
the existing `agent-bridge-worker` systemd/state-file health source. Task rows
are shown only when `WORKER_ACTIVITY_SNAPSHOT` points at a local JSON file
maintained by the worker integration.

The snapshot must be a JSON array of objects. Each row may contain `id`,
`agent`, `operation`, `workspace`, `status`, `queue_age`, `run_duration`,
`attempts`, `last_update`, and `error`. The dashboard does not create or infer
rows, and it does not claim a worker is offline when the task ledger is absent.

Deployment still needs the Star Trek Bridge/Codex worker to publish that
snapshot and set `WORKER_ACTIVITY_SNAPSHOT` in the dashboard service
environment. Until then the page intentionally says task activity is
unavailable while keeping verified bridge-worker health visible.
