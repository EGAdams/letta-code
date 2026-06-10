# implementation/ — concrete subclasses (implemented)

Each abstract interface in `js/abstract/` now has a concrete subclass here that
binds its abstract *primitive operations* to a real browser API. The
Template-Method skeletons and shared policy still live in `js/abstract/`; these
classes only fill in the primitives. Every one has a matching test in
`js/tests/` (run `bun test js/tests` — 111 green).

| Concrete class              | Extends                | Wires to | File |
|-----------------------------|------------------------|----------|------|
| `FetchHttpClient`           | `HttpClient`           | `window.fetch` | `fetch-http-client.js` |
| `DomConsoleView`            | `ConsoleView`          | a `.msi-console` element (+ `mount()` helper) | `dom-console-view.js` |
| `BrowserSpeechSynthesizer`  | `SpeechSynthesizer`    | `window.speechSynthesis` + `SpeechSynthesisUtterance` | `browser-speech-synthesizer.js` |
| `MediaRecorderVoiceRecorder`| `VoiceRecorder`        | `navigator.mediaDevices` + `MediaRecorder` + `/api/voice` | `media-recorder-voice-recorder.js` |
| `DomTabFactory`             | `TabFactory`           | `document.createElement('button')` | `dom-tab-factory.js` |
| `DomNavigationController`   | `NavigationController` | the nav panels + `.view` sections | `dom-navigation-controller.js` |
| `ServerHealthMonitor`       | `HealthMonitor`        | `/api/server-health` (via an `HttpClient`) | `server-health-monitor.js` |
| `AgentStreamController`     | `PollingController`    | `/api/thoughts\|messages\|toolcalls` → `ConsoleView` | `agent-stream-controller.js` |
| `ServerLogController`       | `PollingController`    | `/api/server-logs` → `ConsoleView` | `server-log-controller.js` |
| `ServerActionController`    | — (Command)            | `POST /api/server-action` (via an `HttpClient`) | `server-action-controller.js` |
| `StreamDetailRenderer`      | `DetailRenderer`       | mounts a console + `AgentStreamController` | `detail-renderers.js` |
| `ChatDetailRenderer`        | `DetailRenderer`       | chat UI + voice recorder + speech + `/api/test` | `detail-renderers.js` |

Supporting pieces:

- `ActivePoller` (`active-poller.js`) — reproduces the old single-`pollTimer`
  guarantee: `run(controller)` stops the previously-active stream before
  starting a new one.
- `classifyServerStatus` / `composeSpokenText` / `renderReplyRows` /
  `buildServerActionRequest` — pure helpers extracted from the original inline
  JS so they are tested directly.
- `index.js` — barrel re-export of everything above.

Every browser dependency (`fetch`, `document`, `navigator`, `MediaRecorder`,
`localStorage`, the speech engine, the polling scheduler) is injected through the
constructor and defaults to the real global, so the classes run unchanged in the
browser and are unit-testable with the lightweight DOM double in
`js/tests/_fake-dom.js`.

## Remaining wiring (not done here)

These classes are not yet imported by `dashboard.html` — its inline `<script>`
is still the live code. The final swap (replace the inline AM/SM objects with
imports from `./js/implementation/index.js`) is intentionally a separate step so
the behavior-preserving refactor can be reviewed before the cutover.
