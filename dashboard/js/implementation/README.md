# implementation/ — concrete subclasses (implemented)

Each abstract interface in `js/abstract/` has a concrete subclass here that
binds its abstract *primitive operations* to a real browser API. The
Template-Method skeletons and shared policy still live in `js/abstract/`; these
classes only fill in the primitives. Every one has a matching test in
`js/tests/` (run `bun test js/tests` — 160 green).

**These classes are the live code.** `dashboard.html` loads
`/js/dashboard-boot.js`, which imports everything below from `./index.js` and
binds it to the page. (The cutover is done — there is no inline `<script>` left.)

| Concrete class              | Extends                | Wires to | File |
|-----------------------------|------------------------|----------|------|
| `FetchHttpClient`           | `HttpClient`           | `window.fetch` | `fetch-http-client.js` |
| `DomConsoleView`            | `ConsoleView`          | a `.msi-console` element (+ `mount()` helper) | `dom-console-view.js` |
| `BrowserSpeechSynthesizer`  | `SpeechSynthesizer`    | `window.speechSynthesis` + `SpeechSynthesisUtterance` + `AgentVoiceCatalog` | `browser-speech-synthesizer.js` |
| `MediaRecorderVoiceRecorder`| `VoiceRecorder`        | `navigator.mediaDevices` + `MediaRecorder` + `/api/voice` | `media-recorder-voice-recorder.js` |
| `DomTabFactory`             | `TabFactory`           | `document.createElement('button')` (agent/server/connection tabs) | `dom-tab-factory.js` |
| `DomNavigationController`   | `NavigationController` | the nav panels + `.view` sections | `dom-navigation-controller.js` |
| `ServerHealthMonitor`       | `HealthMonitor`        | `/api/server-health` (also reused for `/api/ssh-connection-health`) | `server-health-monitor.js` |
| `AgentStreamController`     | `PollingController`    | `/api/thoughts\|messages\|toolcalls` → `ConsoleView` | `agent-stream-controller.js` |
| `AgentActivityPoller`       | `PollingController`    | `/api/agent-activity` → sidebar tab colours | `agent-activity-poller.js` |
| `ServerLogController`       | `PollingController`    | `/api/server-logs` → `ConsoleView` | `server-log-controller.js` |
| `ConnectionLogController`   | `PollingController`    | `/api/ssh-connection-logs` → `ConsoleView` | `connection-controllers.js` |
| `ServerActionController`    | — (Command)            | `POST /api/server-action` | `server-action-controller.js` |
| `ConnectionTestController`  | — (Command)            | `GET /api/ssh-connection-test` | `connection-controllers.js` |
| `StreamDetailRenderer`      | `DetailRenderer`       | mounts a console + `AgentStreamController` | `detail-renderers.js` |
| `AgentCardRenderer`         | `DetailRenderer`       | `/api/agent-card` → identity/system-message/lists | `detail-renderers.js` |
| `ChatDetailRenderer`        | `DetailRenderer`       | chat UI + voice + per-agent speech + `/api/test` | `detail-renderers.js` |
| `InputOptionsRenderer`      | `DetailRenderer`       | Input Options UI (textarea/voice/auto-send) + `/api/test` | `detail-renderers.js` |
| `RolFinanceReportsController`| — (controller)        | `/api/rol-finance-reports` → report tabs + same-origin iframe reach | `rol-finance-reports-controller.js` |
| `CodeChangeAlert`           | — (controller)         | `/api/code-status` → blink tab + restart modal | `code-change-alert.js` |

Supporting pieces:

- `ActivePoller` (`active-poller.js`) — reproduces the old single-`pollTimer`
  guarantee: `run(controller)` stops the previously-active stream before
  starting a new one.
- `classifyServerStatus` / `classifyConnectionStatus` / `composeSpokenText` /
  `renderReplyRows` / `buildServerActionRequest` — pure helpers extracted from
  the original inline JS so they are tested directly.
- `index.js` — barrel re-export of everything above.

Every browser dependency (`fetch`, `document`, `navigator`, `MediaRecorder`,
`localStorage`, the speech engine, the polling scheduler) is injected through the
constructor and defaults to the real global, so the classes run unchanged in the
browser and are unit-testable with the lightweight DOM double in
`js/tests/_fake-dom.js`.

## Page wiring

`js/dashboard-boot.js` is the entry point. It constructs the shared ports
(`FetchHttpClient`, `ActivePoller`, `DomTabFactory`, `BrowserSpeechSynthesizer`),
the detail-renderer strategies and the `SM`/`SSHM`/`RF`/alert instances, and
keeps the page-specific navigation glue (sidebar tab show/hide transitions,
`safeActivateView`'s `fullbleed` toggle, deep-linking). The nested sub-nav chains
(plans → ROL Finance → Reports, agents → agent-detail) stay as explicit handlers
rather than being forced through `NavigationController`.
