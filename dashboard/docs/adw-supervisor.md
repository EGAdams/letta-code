# Independent ADW supervisor

The supervisor is repaired and locally verified, but its user service is not
installed or started. No dashboard/bridge service was restarted. The failed task
`t_cb29dcb55654efa68f29fee9` remains a historical failure; do not replay it.

## What is implemented

- `monitoring/adw_supervisor.py`: standalone composition root and atomic state
  publisher. It runs outside the dashboard and bridge worker.
- `supervisor_contracts.py`: validated Pydantic observations and the small
  `ITaskLedgerReader` interface.
- `supervisor_sources.py`: interchangeable read-only adapters. By default the
  supervisor rebuilds observations directly from durable post-office envelopes
  and events using the existing `activity_snapshot` row builder. It does not
  require a live worker or a worker-produced JSON file. An explicitly configured
  `WORKER_ACTIVITY_SNAPSHOT` selects the file adapter instead.
- `task_timing.py`: common ISO timestamp and duration adapter, also used by the
  worker health diagnostic. ISO times require a timezone; numeric ages and
  worker display durations such as `2h 01m` are supported.
- `supervisor_policy.py`: pure escalation State policy, with readiness candidates
  injected by the composition root. Defaults: warn 120s, recommend 300s,
  diagnose 600s, incident 1800s. For running/claimed work the signal is time since
  recorded progress, not time spent waiting before execution. These are
  recommendations; absence of recorded progress is not proof of a dead model.
- Two subsequent cycles without a status, attempt, or recorded-progress change
  produce one switch-tactic recommendation. Repeated identical observation times
  do not count as new cycles. Events are bounded to 200 per task, and the direct
  source is capped at 10,000 rows with explicit truncation error.
- Missing, invalid, stale (60s), duplicate-ID, and unknown-age observations do not
  claim healthy task telemetry. Stale/unreadable cycles preserve last-known
  escalations without advancing them. State publication uses a private temporary
  file, atomic replacement, and mode 0600. State and source paths must differ.
- `/api/worker-activity` exposes escalation state; the Worker Activity page renders
  per-task alerts, stale-source warnings, and incomplete coverage. New module
  assets are served from this checkout; backend imports require a later restart.
- Model registry entries declare capabilities, write rights, cost tier and
  strategy. Configuration is validated. Built-in CLI/file-existence probes report
  **configured, runtime unverified**, never authenticated availability. Opus and
  Astra remain unverified/unavailable. There is no fabricated provider selection.

The supervisor makes no model calls, delivers no external notifications, changes
no credentials, restarts no worker, and never claims/retries task records.

## Visibility limit

Local post-office records only cover tasks already handed off locally. Tasks
still queued only at the remote gateway, or refused before handoff, are invisible.
Every snapshot therefore includes `coverage_complete: false` and the reason.
`ok: true` means the available local observations were read and evaluated;
**it does not mean the entire remote queue is healthy**.

A full solution needs a separately authenticated, read-only gateway queue reader.
Do not use `/worker/tasks/next` for observation: the worker path can perform lease
maintenance. Do not reuse a privileged worker credential for a new monitor API.

## Run one observation

From `/home/adamsl/letta-code/dashboard`, using the existing shared environment:

```bash
ADW_SUPERVISOR_STATE_PATH=/tmp/adw-supervisor-check.json \
  /home/adamsl/agent_blocks/lancedb_memory/.venv/bin/python -B \
  -m monitoring.adw_supervisor --once
```

The command reads actual local records and writes only its named state file.
Default daemon output is `~/.cache/agent_bridge/adw_supervisor_state.json`.
`ADW_AGENT_BLOCKS_PACKAGE` overrides `~/agent_blocks/lancedb_memory`.
`ADW_SUPERVISOR_POLL_SECONDS` defaults to 20 (valid range 1–3600).
`ADW_SUPERVISOR_{WARN,RECOMMEND,DIAGNOSE,INCIDENT}_SECONDS` override thresholds;
they must be finite, positive and strictly increasing. Avoid multiple writers
sharing one state path; use the one user unit.

An optional `WORKER_ACTIVITY_SNAPSHOT=/path/to/list.json` selects the file source.
That source must contain worker-style objects with unique `id`, `status`, and
non-negative integer `attempts` when supplied. Its mtime is its freshness signal.
A running row needs a trustworthy `last_progress_at`, `last_update`, or
`started_at`; heartbeat-only data must not masquerade as useful progress.

## Activate later

A reviewed example is at `config/adw-supervisor.service`; `systemd-analyze --user
verify` passes. It has bounded service restart attempts and filesystem restrictions.
The unit is intentionally not installed, enabled, or started in this repair.
When service changes are authorized, create the state directory, install this
unit into `~/.config/systemd/user/`, reload user units, and enable/start
`adw-supervisor.service`. Backend changes also need a controlled dashboard
restart. Bridge telemetry imports need a controlled bridge-worker restart after
confirming there is no active write task. The dashboard restart can stop its
Executor; account for that before activation. Do not change credentials.

Verify the new state heartbeat advances, the HTTP payload matches the state,
and the actual Worker Activity page displays it. The isolated browser fixture
already verifies rendering and escaping, not live service activation.

## Claude failure and telemetry repair

The original Sonnet CLI call reached its configured 40-turn limit (runtime
reported 41 turns, 510.9s, exit 1, `error_max_turns`). `no answer` meant no final
result text. Seven intact files survived. Orchestration still completed all 11
phases and published a failed result; phase success never proved code correctness.

Future Claude results/audit events include configured maximum turns, effective
timeout, subtype, error source, child/process-group PID, model, and local/Bridge
IDs. The post-office adapter carries a small allowlist into `AgentOutcome.details`,
so `TracingAgent` can expose it to Object Debugger. ADW traces now receive run IDs
(falling back to the ADW ID while preserving an outer request run ID), identify
orchestration status explicitly, and close the worker-application trace when its
run ends. Existing historical rows are unchanged. These process IDs describe the
execution; they do not prove a process with a reused PID belongs to that run.

Configured checks now also run after a settled failed execution, while cancelled,
resumed, or unsettled writes remain excluded. Failed checks do not promote partial
code to success. `letta_code` now has a **focused supervisor** check command in
`agent_bridge_worker/workspaces.json`; it is not a full workspace test suite.

## Validation and remaining work

Repair validation on 2026-11-06:

- Supervisor/source/registry/activity/worker diagnostic: 62 pytest checks pass.
- The configured checker also passes in the actual read-only, no-network jail:
  61 passed, 1 skipped. The skip is the real producer integration outside that
  workspace; it passes on the host. `scripts/check_adw_supervisor.py` excludes the
  unrelated intake/server conftest so it needs no foreign finance checkout.
- Worker Activity controller/rendering/escalation: 26 Bun tests pass.
- Claude CLI: 18; post office: 24; scoped write access: 17; Object Trace: 21;
  tracing adapters: 5. Bridge worker, activity snapshot, and Object Debugger
  standalone suites pass.
- A read-only live observation found 387 local tasks, no current escalations,
  no unknown task ages, and no runtime-verified models. Output stayed in `/tmp`
  with mode 0600. This is an observation at that time, not a permanent health claim.
- Browser fixture confirms task rows, stale warnings, incomplete coverage,
  configured/unverified providers, and HTML escaping.
- Full dashboard Bun run: 2949 pass, 2 skip, 3 failures in untouched Notes tests
  (`hands-free-notes-controller.test.js` twice; `notes-page.test.js` deed preview).
  Eight pre-existing Worker Activity test failures were reproduced in an isolated
  copy; the fake DOM/old label assertions were repaired, along with a real terminal
  issue where dashboard observations hid a worker's last recorded error.

Still pending:

1. Authorized live activation/restarts and end-to-end Object Debugger verification
   on a new tiny task. Poll one task ID, never duplicate a write. Verify configured
   budget/subtype/PID/IDs and closed lifecycle objects. The original failed task
   cannot resume its non-persisted Claude conversation, and its journal prevents
   rerunning the same write ID.
2. A read-only gateway queue inventory with bounded retention/pagination, freshness
   and explicit scope; then an adapter behind `ITaskLedgerReader`. This requires
   remote API/security review and deployment, which this repair did not perform.
3. Authenticated runtime readiness probes, independent second-opinion dispatch and
   incident delivery. Current implementation records recommendations only. Reuse
   `IAgentAdapter` and existing `IPhase` ADW machinery at the composition boundary;
   do not send diagnosis through the same potentially stalled worker queue. Keep
   any future dispatch bounded/idempotent and preserve subscription authentication.
4. The-factory integration, stronger child-process identity/spans, and a separate
   fix for the three Notes test failures.

An additional polling suite stops at its existing shipped-settings/defaults
assertion: the shipped configuration is 60s idle / 10s burst with 08:00–23:00
active hours, while the test expects constructor defaults (30s / 5s / all day).
Neither the operator schedule nor that test was changed. A route inventory filter
selected no worker-specific tests; it adds no route validation claim.

No commits, pushes, service restarts, remote deployment, or credential changes
were performed as part of this repair. Unrelated working-tree changes remain.
