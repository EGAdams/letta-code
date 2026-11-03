# Worker Activity integration

System Status > Worker Activity (directly below Printer) is read-only. It shows:

1. the **live Star Trek Bridge workflow SVG** (`js/abstract/bridge-workflow-render.js`),
   always drawn — with an explicit "Telemetry unavailable" notice when there is no ledger;
2. queued / running / completed / failed counts and the most recent failures with
   their error text;
3. the ledger table, and the `agent-bridge-worker` systemd/state-file heartbeat.

The sidebar **Worker legend** (below the nav tabs) shows one row per worker/agent
and its current task (open work first, else its latest).

## Data path (live on DESKTOP-2OBSQMC)

```
post office envelopes (agent_blocks/adws/adw_data/post_office/mailboxes)
  -> agent-bridge-activity-snapshot.timer (every 20 s)
     python -m agent_bridge_worker.activity_snapshot   (agent_blocks/lancedb_memory)
  -> ~/.cache/agent_bridge/worker_activity.json        (atomic write, 50 newest rows)
  -> dashboard-server.service.d/90-worker-activity.conf
     WORKER_ACTIVITY_SNAPSHOT=/home/adamsl/.cache/agent_bridge/worker_activity.json
  -> GET /api/worker-activity  (monitoring/worker_activity.py)
```

The snapshot must be a JSON array of objects. Each row may contain `id`,
`agent`, `operation`, `workspace`, `status`, `queue_age`, `run_duration`,
`attempts`, `last_update`, and `error`. The dashboard does not create or infer
rows, and it does not claim a worker is offline when the task ledger is absent.
A task still queued at the gateway (not yet in the post office) has no row.

## Polling

`js/boot/worker-activity.js` is the only reader of `/api/worker-activity`: one
`setTimeout` chain, 5 s while Worker Activity or Poll Settings is open, 20 s
otherwise, never two requests at once. Poll Settings subscribes to it for its
copy of the SVG (ids prefixed `abp-`; Worker Activity uses `worker-activity-`).
