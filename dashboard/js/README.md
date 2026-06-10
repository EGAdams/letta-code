# Dashboard JS — GoF interface layer

`dashboard.html` was a 1300+ line monolith mixing CSS, markup, and ~850 lines of
JavaScript. This directory breaks the JavaScript into small, testable units
following the Gang of Four playbook.

## Layout

```
js/
  abstract/        Interfaces (abstract base classes). The contract + any
                   shared Template-Method logic. No DOM, no fetch — collaborators
                   are injected so everything is unit-testable.
  tests/           bun:test unit tests, one file per interface.
  implementation/  Concrete, DOM/fetch-wired subclasses. Populated AFTER the
                   interface tests are green (this layer is intentionally empty
                   for now).
```

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
| `tab-factory.interface.js`         | Factory Method           | agent/server `createElement` blocks |

## Design rule

Abstract classes never touch globals (`document`, `fetch`, `window`,
`MediaRecorder`). Those are passed in as ports/primitives. The concrete wiring
to real browser APIs belongs in `implementation/`. This keeps the contract and
its template logic fully exercised by `bun test` without a browser or DOM shim.
