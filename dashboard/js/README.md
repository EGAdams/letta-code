# Dashboard JS — GoF interface layer

`dashboard.html` was a 1300+ line monolith mixing CSS, markup, and ~850 lines of
JavaScript. This directory breaks the JavaScript into small, testable units
following the Gang of Four playbook.

**The cutover is complete.** `dashboard.html` is now pure markup; its only script
is `<script type="module" src="/js/dashboard-boot.js">`. `dashboard-boot.js` is a
~150-line composition root: it constructs the shared ports, builds one module
per dashboard section from `boot/`, and hands them to the nav bindings. All
behaviour lives in the unit-tested classes below.

## Layout

```
js/
  abstract/        Interfaces (abstract base classes). The contract + any
                   shared Template-Method logic. No DOM, no fetch — collaborators
                   are injected so everything is unit-testable.
  tests/           bun:test unit tests, one file per interface/class.
  implementation/  Concrete, DOM/fetch-wired subclasses (the live code).
  boot/            One module per dashboard section. Each exports a
                   `create*(deps)` factory that takes its collaborators
                   (`http`, `nav`, `viewNav`, …) and returns that section's
                   facade — no module reaches for a global of its own.
  dashboard-boot.js  The composition root: builds the ports, the sections, the
                   nav bindings, in that order. Nothing else.
```

### `boot/` — the section modules

| Module | Owns |
|---|---|
| `nav-elements.js` | the one place every `nav-*` element is looked up |
| `gates.js` | the two startup overlays, from `abstract/startup-gate.js` |
| `view-navigator.js` | `activateView` / `setActive` / `returnTo*` — the choke point every tab switch runs through, and where the statement-review modal is told to re-check its visibility |
| `agent-manager.js` | the `AM` facade: roster, per-agent detail fanout, deep-link `openById` |
| `agent-detail-renderers.js` | the Strategy table behind `AM.renderDetail()` |
| `agent-tab-status.js` | activity + structural-health colouring of agent tabs |
| `scanner-agent-views.js` | Mazda's Thoughts + the archive-verification terminal on scanner report tabs |
| `model-stats.js`, `pc-monitor.js` | the `MS` / `PCM` facades (card HTML lives in `abstract/`) |
| `server-manager.js`, `ssh-manager.js` | the `SM` / `SSHM` facades; they share `log-panel.js` |
| `rol-finance.js` | the `RF` controller + its on-screen-only status poll |
| `receptionist.js` | Toyota's note box and its voice command channel |
| `startup-checks.js` | the four boot-time preload tasks, each failing closed |
| `deep-link.js` | `?agent=` / `?view=` entry points |
| `bindings/` | every sidebar listener, one file per nav area |
| `scanners/` | the scanner dialogs: `scanner-dialog.js` (workflow), `scanner-progress-panel.js` (bar + label), `scanner-image-viewer.js` (zoom/pan modal), `scanner-status-monitor.js` (observation-only recovery poll), `printer-repair-panel.js`, and `index.js` (statement review, vendor review, Process PDF) |

Run the tests:

```bash
bun test js/tests
```

## Interface → GoF pattern → origin in dashboard.html

| Interface (`abstract/`)            | GoF pattern              | Replaces in the old file |
|------------------------------------|--------------------------|--------------------------|
| `not-implemented.js`               | (contract primitive)     | — |
| `text-utils.js`                    | pure helpers             | `esc()`, `sleep()`, `Speech.clean()` |
| `http-client.interface.js`         | Adapter + Template Method| duplicated `AM.fetchJSON` / `SM.fetchJSON` |
| `polling-controller.interface.js`  | Template Method          | `setInterval` poll loops |
| `console-view.interface.js`        | Builder / Composite      | `consoleShell()` + `seen` dedup |
| `stream-formatter.interface.js`    | Strategy                 | `formatStreamRow()` |
| `speech-synthesizer.interface.js`  | Facade                   | the `Speech` object |
| `voice-recorder.interface.js`      | State                    | mic capture idle→recording→processing |
| `detail-renderer.interface.js`     | Strategy + Context       | `DETAIL_RENDERERS` map |
| `health-monitor.interface.js`      | Observer                 | `SM.pollHealth` + tab colorers |
| `navigation-controller.interface.js`| State                   | nav panel show/hide + view switching |
| `tab-factory.interface.js`         | Factory Method           | agent/server/connection `createElement` blocks |
| `agent-voice-catalog.interface.js` | Strategy / Registry      | per-agent `voiceFor()` + `AGENT_VOICE_PREFERENCES` |
| `startup-gate.js`                  | Template Method          | the two 135-line copy-pasted `startupGate` / `agentGate` IIFEs |
| `model-stats-render.js`            | pure renderer            | `renderModelStats()` / `renderRateOfChange()` |
| `pc-metrics-render.js`             | pure renderer            | `renderPcMetrics()` |

Concrete classes that have no separate `abstract/` interface live directly in
`implementation/` (they are pure DOM/fetch glue over the interfaces above):
`AgentCardRenderer`, `InputOptionsRenderer` (Strategies, in `detail-renderers.js`),
`AgentActivityPoller`, `ConnectionLogController`/`ConnectionTestController`
(in `connection-controllers.js`), `RolFinanceReportsController`, and
`CodeChangeAlert`.

## Design rule

Abstract classes never touch globals (`document`, `fetch`, `window`,
`MediaRecorder`). Those are passed in as ports/primitives. The concrete wiring
to real browser APIs belongs in `implementation/`. This keeps the contract and
its template logic fully exercised by `bun test` without a browser or DOM shim.
