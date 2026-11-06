# Message to ChatGPT

Activation update, 2026-11-06: the supervisor is active (PID 952892), and the
dashboard integration is live after its authorized restart (14778 to 978832).
Documentation PID 14906 was adopted without interruption by the independent
`agent-blocks-server.service` and survived that dashboard restart. See
`docs/agent-blocks-service.md` and `/tmp/adw-docs-separation/` for evidence.
The earlier repair-only statements below describe the pre-activation state.
Do not repeat the migration or restart services merely to verify this update.

Codex repaired the partial supervisor implementation left by failed task
`t_cb29dcb55654efa68f29fee9` on DESKTOP-2OBSQMC. The failure was Claude CLI's
configured 40-turn limit (41 turns reported), not a timeout. The original task
and its historical telemetry were preserved. Do not replay that write task.

Please read `/home/adamsl/letta-code/dashboard/docs/adw-supervisor.md` and inspect
the current diffs in both `/home/adamsl/letta-code` and `/home/adamsl/agent_blocks`.
There is unrelated WIP; do not reset, discard, commit, or overwrite it.

What is fixed: real worker timestamp/duration parsing, stalled-running-task
observations, stale/unknown data handling, direct read-only post-office visibility
without a live worker, bounded escalation state, honest model readiness, dashboard
alerts, Claude runtime diagnostics, trace run IDs/application closure, and checks
on settled partial writes. A validated service example and runbook are included.

Check:
1. Run the five focused Python files listed in the runbook and the Worker Activity
   JS tests. Codex got 62 Python and 26 JS passes. Verify the configured checker
   also passes in its actual read-only/no-network jail (61 pass, 1 integration
   check skipped there and passed on the host). The checker script is
   `dashboard/scripts/check_adw_supervisor.py`.
2. Run `monitoring.adw_supervisor --once` with its state path in `/tmp`. Confirm
   `source=local-post-office`, fresh heartbeat, correct task IDs, and explicit
   `coverage_complete=false`; remote-only queued tasks remain invisible.
3. Check the service activation status before claiming anything is deployed.
   No service was installed/restarted. Keep the user's no-restart/no-credential-
   change restriction unless they explicitly authorize activation. The reviewed
   unit is `dashboard/config/adw-supervisor.service`.
4. After authorized bridge/dashboard activation, submit ONE tiny read-only task.
   Poll that same ID until complete. Then use Star Trek Bridge agent
   `object-debugger`, workspace `object_trace`, operation `inspect`, exact prompt
   `task <new-task-id>`. Submit once and poll its inspection ID; retrieve full body
   and JSON. Confirm run/task/local IDs, runtime budget/subtype/child PID, phase
   status versus business outcome, and no abandoned worker-application object.
   Old historical rows will still lack the newly added fields.

What remains: a read-only gateway queue inventory/adapter; authenticated model
readiness checks; independent second-opinion execution and incident delivery;
The-factory integration; and live end-to-end validation. Keep dispatch independent
of the worker it diagnoses, behind our existing IAgentAdapter/IPhase interfaces,
with bounded, idempotent actions. Built-in model probes currently verify only local
configuration and correctly report runtime availability as unverified.

The broader JS suite also has three failures in untouched Notes tests (two
hands-free command tests and one deed-preview assertion). Handle those separately.
An extra polling suite stops on an existing mismatch between the shipped operator
schedule and a test that expects constructor defaults; preserve the operator
schedule and handle the test separately.

Continue with small, bounded tasks and explicit checks instead of one broad
supervisor rewrite. No fixes were committed or pushed.
