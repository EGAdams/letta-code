# Wiring the fix into lettabot (Win11)

> **STATUS UPDATE 2026-06-06 (late): F7 IS ALREADY LIVE.** lettabot on Win11 got a
> *native* in-`src/core/bot.ts` F7 fix (commits `2ae0d25` + `101834f` on branch
> `diag/executor-run-trace`), `dist` rebuilt 13:29, bot restarted 13:31. The
> standalone scaffold below was **not** the thing that shipped — the bot uses its
> own primitives (`isTransportDeadError`, `inFlightToolCalls`, tool-call-aware
> `resetStreamInactivityTimer`, respawn branch in `runSession`). The original
> `Transport not connected` / 300s stall is fixed. The remaining live stall is a
> *different* mode — `tool_response_lost` (45 toolCalls / 1 result) — not F7.
> Keep the rest of this file only as a reference for the F1–F6 executor layer,
> which is still NOT ported.

Both layers are **built and green** in this repo (`pytest -q` → 29 passed). The
F7 layer is now superseded by the native lettabot fix (see status note above);
the F1–F6 executor layer remains a port target. lettabot runs on Win11
(`100.72.158.63:/home/adamsl/lettabot`), which is not mounted in this WSL. This
file is the adoption checklist.

```
Layer   What it fixes                         Reference (tested)               Port target
-----   -----------------------------------   ------------------------------   --------------------------------
F1–F6   executor_run classify-not-spin (14x)  scissari_executor/*.py           lettabot executor call site
F7      session/transport stall (today's)     scissari_executor/session/*.py   port-typescript/sessionSupervisor.ts
```

---

## F7 — session/transport (do this first; it's what's biting now)

lettabot is Node/TypeScript, so the F7 port lives in
`port-typescript/sessionSupervisor.ts` (a 1:1 mirror of the Python reference;
same behaviour the 13 F7 pytest cases pin down).

### Change sites in `dist/core/bot.js` (source: `src/core/bot.ts`)

1. **`Stream inactivity timeout after 300000ms — closing session`** — this single
   blind timer is bug (a). Replace it with `SessionSupervisor`:
   - On each `[Stream] type=...` event, call `supervisor.feedEvent(kind)`
     (map `reasoning|text|tool_call|tool_return|end_turn` → `StreamEventKind`).
   - Replace the fixed 300 000 ms timer with a periodic `await supervisor.tick()`.
     While a tool call is in flight, `tick()` returns `shouldClose:false` until the
     **tool-call deadline** (900 s default), not the 300 s idle window.
   - Only `closeSession()` when `tick()` returns `shouldClose:true`, and log
     `verdict.reason` + `verdict.detail` (no more "took too long" with no reason).

2. **`trySend` / `runSession`** — wrap the SDK transport in `ResilientTransport`
   and send through it. `ResilientTransport.send()` re-spawns a dead subprocess
   once instead of throwing `Transport not connected`.

### Change site in `dist/cron/heartbeat.js` (source: `src/cron/heartbeat.ts`)

3. **`runHeartbeat` → `sendToAgent` → `Session.send`** is where today's
   `Transport not connected (closed=true, pid=undefined, stdin=false)` is thrown
   (bug b). Route the heartbeat send through `supervisor.send(...)` so a closed
   session is transparently re-spawned. If `ResilientTransport` throws
   `TransportUnavailableError`, the respawn circuit is open — alert ops via the
   existing Telegram + `~/.letta/scissari-alerts.jsonl` sinks instead of crashing.

### Adapter you must supply

`ISubprocessTransport` (in the `.ts` file) needs a thin adapter around the real
`@letta-ai/letta-code-sdk` `SubprocessTransport`:
- `pid` / `closed` ← read from the SDK transport state.
- `spawn()` ← whatever lettabot already does to (re)start a session subprocess.
- `write(data)` ← the SDK `transport.write(...)`.

---

## F1–F6 — executor_run recovery (the original scaffold)

Replace the live `count < 14` loop + `"No specific tool error captured"` alert
with a single call into the facade. Two adoption options:

- **Python executor host:** copy `scissari_executor/` into the executor tree and
  call `await ExecutorRunService(...).execute(cmd, agent_id)`.
- **Node lettabot host:** port `models/classifiers/strategies/guard/breaker/
  service` the same way the F7 layer was ported, OR expose the Python service
  behind a tiny local endpoint the bot calls.

On `StalledError`, send `err.report.message` to Telegram — it now names the
failure kind (F1–F6) and the evidence, instead of the old "no error" lie.

## Verify after porting

- Re-run `pytest -q` here whenever you change the Python reference (29 must stay green).
- In lettabot, confirm: a >5-min `executor_run` no longer trips "took too long";
  and a heartbeat after an idle close re-spawns instead of `Transport not connected`.
