# Live ADW Sequence Debugger

A sequence diagram above the Terminal tab's stream that follows one ADW run as
it executes. Each column is one backend phase instance. Clicking either of its
boxes filters the terminal to that instance's recorded and incoming events.

## The route one event takes

```
adw_debug_pilot.py  phase object            agent_blocks/adws/debug_pilot/
  -> MonitoredPhase / PhaseProbe            emit( kind, phase_id, ... )
  -> SssfDebugEvents                        Tracer.event( EventRecord )
  -> sssf.db  events table (rowid = cursor) agent_blocks/adws/adw_data/sssf.db
  -> SqliteAdwEventRepository (read-only)   dashboard/adw_debugger/
  -> event_adapter.adapt -> DebugEvent
  -> GET /api/adw-debugger/feed[?after=N]   http_app/get_routes.py
  -> PollingEventSource (500 ms)            dashboard/adw_debugger_ui/src/
  -> project() reducer -> DebuggerController -> DebuggerPanel / SequenceDiagram / LogPane
```

The browser never opens SQLite. The dashboard had no reader for `sssf.db`
before this; the Terminal tab's own stream reads `/api/worker-activity` and is
left exactly as it was.

## Rules that hold everywhere

- **Identity.** A phase instance is `<adw_id>:<step key>`, fixed at construction.
  SSSF's `phase_id` is attached by the `bound` event. Display names and column
  positions identify nothing. An ADW that is not instrumented falls back to its
  `phase_id`.
- **Order.** The events table's rowid is the cursor. Wall-clock time is shown,
  never sorted on.
- **Outcomes.** Only `phase_end` sets pass or fail. Cleanup is evidence. A late
  event never reopens a finished phase.
- **No invention.** A killed run reads `interrupted`; its open phase is orange
  and says no cleanup was recorded. Nothing writes a cleanup or an outcome on a
  phase's behalf.
- **Text.** Recorded text is shown whole and only ever as text (Vue
  interpolation; no `v-html`). SSSF does no secret redaction today, so none is
  claimed here.
- **Display state is not data.** Clear stores a per-run cursor in
  `localStorage`. No database row is touched.

## Settings

`dashboard/config/adw_debugger.json`, read on every request, env wins:

| Key | Env | Default |
|---|---|---|
| `stall_timeout_seconds` | `ADW_DEBUGGER_STALL_SECONDS` | `120` |
| `adw_names` | `ADW_DEBUGGER_ADWS` (comma separated) | `["adw_debug_pilot", "adw_interface_scala_file_scan"]` |
| `db_path` | `ADW_DEBUGGER_DB` | `~/agent_blocks/adws/adw_data/sssf.db` |
| `bootstrap_runs` | | `5` |

Adding an ADW to the debugger is one name in `adw_names`. To get waiting
columns, purposes and cleanup evidence the pilot wraps its steps in `MonitoredPhase`.
Scala wraps her existing IPhase objects in `adw_modules.monitored_phase.MonitoredSssfPhase`;
this preserves their handles, params and results. Its cleanup event means only
that the monitor scope closed, not that business resources were disposed.
The normal freezer/window scan path stages a document and `scala-scanner.service`
starts the monitored seven-phase filing ADW. No scan or filing is simulated.

## Which columns are on screen

`src/domain/columns.ts` and `src/domain/view.ts`. Column 0 is the ADW runner
(`@runner`, named after the ADW); after it, every phase of the run in start
order, finished ones included, so a finished run reads top to bottom as its
whole story. The UI is Vue components only, no Mermaid: `ParticipantBox`,
`Lifeline`, `ActivationBar`, `MessageArrow` and `TimeAxis` under
`src/ui/sequence/`, laid out after heichong/vue-sequence-diagram (MIT).

Arrows come from three sources. The projector draws the run's lifecycle
itself, because an ADW like Scala's records no tool calls or messages: runner
-> phase (solid, the phase name) when a phase starts, a self-call for each
non-empty `progress` message, and phase -> runner (dashed, `status · 1.2s`
plus any error) when it ends. Recorded tool calls and messages are drawn as
before, only when both ends are on screen. An activation bar runs from a
phase's first row to its return; it stays open (pulsing) while the phase has
no outcome. The left axis is time since the run's first event.

## Patterns used

### Adapter (GoF)
- **Problem.** Three shapes that must not leak into each other: the pilot's
  events, SSSF's event rows, and what the browser draws.
- **Files.** `adws/debug_pilot/events.py` (`IDebugEvents` -> `Tracer.event`);
  `dashboard/adw_debugger/event_adapter.py` (row -> `DebugEvent`);
  `src/infra/browser.ts` (`DomLegacyTerminal` implements `ILegacyTerminal`).
- **Example.** `adapt(raw, machine)` maps `phase_end {"status": "success"}` to
  `kind='phase_end', status='pass'`.
- **Trade-off.** One more hop per event. Reuse it for any other trace store.

### Decorator (GoF)
- **Problem.** Every phase must announce construction, purpose and cleanup, and
  cleanup must be certain, without each step writing that itself.
- **Files.** `adws/debug_pilot/monitored_phase.py` wraps an `IPilotStep`.
- **Example.** `act()` runs `self._step.perform( probe )` inside `try/finally`
  and reports `cleanup` from the `finally`.
- **Trade-off.** The step cannot see its own SSSF handle; it gets a probe
  instead. Reuse it to instrument any other interface-style ADW.

### Strategy (GoF)
- **Problem.** "Which run do we follow", "is this stalled" and "what goes wrong
  in this test run" are policies that will change independently of the code
  that asks.
- **Files.** `IRunSelectionPolicy` -> `src/domain/run-selection.ts`;
  `IStallPolicy` -> `src/domain/stall-policy.ts`;
  `IFaultInjector` -> `adws/debug_pilot/faults.py` (`NoFaults`, `PlannedFaults`).
- **Example.** `stall.evaluate(phase, now, timeoutMs)` returns
  `{ reason: 'no progress for 121s (timeout 120s)' }` or `null`.
- **Trade-off.** Small classes with one method each. A scheduler-aware
  selection policy would be a second `IRunSelectionPolicy`, not an edit.

### Observer (GoF)
- **Problem.** The feed and the controller both publish to listeners that come
  and go with the page.
- **Files.** `IAdwEventSource.subscribe` -> `src/infra/polling-event-source.ts`;
  `DebuggerController.subscribe` -> `src/controller.ts`.
- **Example.** `const off = source.subscribe({ onPage, onConnection })`; `off()`
  on dispose.
- **Trade-off.** Listeners must unsubscribe; `dispose()` does and a test checks it.

### Reducer (not GoF; from Elm/Redux)
- **Problem.** Duplicate, delayed and replayed events must always produce the
  same state.
- **Files.** `src/domain/projector.ts` (`project(state, page) -> state`), with
  `src/domain/view.ts` as the selector that adds time.
- **Example.** Feeding the same page twice returns the same object.
- **Trade-off.** Clones state for every page that carries something new. This
  is a reducer over a log, not an event-sourced system: the database, not this
  state, is the record.

### Ports and Adapters, with constructor injection (not GoF)
- **Problem.** Rules should be testable without a browser, a clock, or SQLite.
- **Files.** Interfaces: `src/contracts.ts`, `dashboard/adw_debugger/ports.py`,
  `adws/debug_pilot/interfaces.py`. Composition roots: `src/main.ts`,
  `adw_debugger/feed.py::payload`, `adws/adw_debug_pilot.py::build_application`.
- **Example.** Tests build `DebuggerController` with `FakeClock`, `FakeTimer`,
  `ManualSource` and `MemoryClearStore`.
- **Trade-off.** More files than a single script; every one is under 250 lines.

## Limits

- **No parallel phases.** One SSSF `Run` executes phases one at a time (one
  sqlite connection, one console lane), so overlapping phases inside a run
  cannot be produced or tested. Overlapping *runs* are tested.
- **Polling, not push.** The feed is polled every 500 ms while the tab is in
  view and every 5 s otherwise, so an event can be up to that old when shown.
- **Pins are per page load.** Reloading shows the active run, or the latest
  finished one.
- **The diagram is a port, not Mermaid.** `SequenceDiagram.vue` is a Vue 3 /
  TypeScript port of `vue-sequence-diagram` (MIT), which draws with elements.

## Checks

```bash
cd dashboard/adw_debugger_ui
npm install
npm test            # 49 unit tests, fake clock and fixtures
npm run build       # type-check, then writes ../js/adw-debugger/
E2E_BASE=http://localhost:8765/ E2E_TERMINAL_TAB='[data-target="terminal"]' npm run e2e
cd .. && .venv/bin/python -m pytest tests/test_adw_debugger_feed.py
cd ~/agent_blocks/adws && uv run --quiet --with pydantic --with pytest --with pyyaml \
    --with rich --with python-dotenv pytest -q debug_pilot/tests
```

`e2e/dev_server.py` serves the bundle and the real feed on their own, for
running the browser scenarios without the rest of the dashboard.
