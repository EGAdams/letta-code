# Worker Activity integration

System Status > Worker Activity (directly below Printer) is read-only. It shows:

1. the **top-five-jobs view** (`js/abstract/worker-activity-rows-render.js`): five
   compact rows of the same four stations as the shared bridge workflow SVG
   (`js/abstract/bridge-workflow-render.js`, still used as-is by Poll Settings), one
   row per real task chosen by `js/abstract/worker-activity-priority.js`'s
   deterministic ranking — failed/stalled first, then running by most recent
   activity, then queued by age, then recent results filling any slots left over.
   A slot with no real task to show says so explicitly rather than duplicating a
   placeholder; with no task ledger at all the view adds one explicit
   "unavailable" banner above the (then-empty) five rows instead of guessing;
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
`attempts`, `last_update`, and `error`. For live terminal detail, a row may
also contain `events`, `event_log`, or `progress_events`, each an array of
objects with `timestamp` (or `time`/`at`) and `message` (or `detail`,
`description`, `action`, or `text`), or strings. These are rendered as
**worker event** entries. The producer should append events rather than
overwrite them and retain at least the most recent 50 rows/events.

Optional lifecycle timestamps `queued_at`, `started_at`, `completed_at`,
`finished_at`, and `failed_at` are shown as worker-supplied phase markers.
Missing timestamps are not filled in by the dashboard. If a feed has no
event arrays or lifecycle timestamps, the page says detailed step logs are
unavailable; it does not infer agent or model activity.

The dashboard does not create or infer task rows or agent actions. It adds
clearly labelled **dashboard observation** entries only when polling observes a
new task or a changed status. Those entries mean “the UI saw this state”; they
do not claim that an agent called a tool, opened a file, or completed a hidden
step. Every displayed line includes a timestamp and task/agent identity when
available. If the ledger is absent, the page shows the exact missing-feed
diagnostic instead of inventing activity.
A task still queued at the gateway (not yet in the post office) has no row.

## Polling

`js/boot/worker-activity.js` is the only reader of `/api/worker-activity`: one
`setTimeout` chain, 5 s while Worker Activity or Poll Settings is open, 20 s
otherwise, never two requests at once. Poll Settings subscribes to it for its
copy of the SVG (ids prefixed `abp-`; Worker Activity uses `worker-activity-`).

The `escalation` field in that same payload comes from a separate,
independent process — see `docs/adw-supervisor.md` for the supervisor that
produces it, its state file, and its (not yet activated) user service.
