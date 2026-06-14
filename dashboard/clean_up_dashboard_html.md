# Clean up `dashboard.html` — cut over to the `js/` library

**Audience:** the implementation team taking over the dashboard GoF refactor.
**Goal:** shrink `dashboard.html`'s inline `<script>` (currently **~1660 lines**, lines 351–2013 of a 2015-line file) down to a thin bootstrap that **imports** behaviour from `js/implementation/`, so the `js/` library is the source of truth — exactly the cutover the README has been deferring.

This document is the plan + spec. It does **not** change any code. Read it top to bottom before touching a file.

---

## 0. TL;DR of where we are

- `js/abstract/` holds 12 interfaces (Template-Method / Strategy / State / Observer / Factory skeletons, no DOM).
- `js/implementation/` holds 13 concrete classes + pure helpers, all unit-tested.
- **`bun test js/tests` → 118 pass / 0 fail today.** That is the baseline; never let it regress.
- **`dashboard.html` does NOT import any of it.** `grep` for `import`/`type="module"` in the file returns nothing. The inline `AM` / `SM` / `SSHM` / `RF` / `Speech` objects are the *live* code.
- The inline code has **drifted well past** what the library covers. Several live features have **no class at all** in `js/`. So this is not a pure "swap the imports" job — the library must first be **extended to match current behaviour**, then wired in.

**The cardinal rule: this is a behaviour-preserving refactor.** The dashboard is a live, autostarted systemd service (`dashboard-server.service`) that EG uses from a phone over Tailscale. Every tab must look and behave *identically* after the cutover. If you find a behaviour you think is a bug, leave it and flag it — do not "fix" it inside the refactor.

---

## 1. Guardrails — read before writing any code

1. **Match current runtime behaviour exactly**, including quirks. Specific quirks that are easy to drop:
   - `safeActivateView()` (line 391) toggles a **`fullbleed`** class on `#main-content` for iframe/console views (Scissari, plan frames, ROL reports). The library's `DomNavigationController.activateView()` does **not** do this. Preserve it.
   - The **Tests/chat tab** (`AM.renderTest`, line 1029) calls `setAgentTabStatus(id, 'active'|'idle'|'error')` around every send, speaks replies in the **agent's own voice** (`Speech.speak(spoken, self.current.name)`), and has a **"Copy to Clipboard"** button + an Auto/Review mode toggle that shows/hides Copy. The library's `ChatDetailRenderer` has **none of those three** behaviours and uses different button labels ("Speak Replies" vs "Speak"). Do not regress these.
   - Per-agent voices: `Speech.voiceFor(agentName)` assigns each agent a distinct cached voice from `AGENT_VOICE_PREFERENCES` (line 704). The library's `SpeechSynthesizer` only has a single shared voice. Preserve per-agent voices.
2. **Keep the cutover reviewable and phased.** Ship one section at a time (see §4). Each phase must leave the dashboard fully working and the test suite green. Do **not** do a single 1600-line big-bang replacement.
3. **The server serves static files as-is** (`server.py`, stdlib `http.server`, no build step). ES modules load natively in the browser — `dashboard.html` becomes `<script type="module" src="./js/dashboard-boot.js">` (or an inline `<script type="module">`). Verify the server sets a usable `Content-Type` for `.js` (it does for the existing `js/` tree; confirm with `curl -I http://localhost:8765/js/implementation/index.js`). **No bundler. No node_modules.**
4. **Every new/changed class gets a `bun test js/tests` test** following the existing pattern (`js/tests/_fake-dom.js` double, injected ports — never touch real `document`/`fetch`/`navigator` in `abstract/`). The repo convention: behaviour/policy lives in `abstract/` and is tested there; `implementation/` only binds primitives to browser globals.
5. **Remove dead code as part of this work** (see §2.4) — but in its own clearly-labelled commit, separate from behaviour moves.
6. **Manual browser verification is mandatory** (§5). Unit tests cannot catch a broken nav transition or a mis-mounted console.

---

## 2. Inventory — every inline block and its disposition

Legend: **REUSE** = class already exists and matches; **EXTEND** = class exists but is missing live behaviour; **NEW** = no class exists, build one; **GLUE** = stays inline in the boot file (page-specific wiring).

### 2.1 Top-of-script glue (lines 352–686)
| Inline | Disposition | Notes |
|---|---|---|
| `mainContent`, `navMain`…`navRolFinanceReports` element refs (352–362) | GLUE | Boot file looks these up and injects them into controllers. |
| `getWindows10BaseUrl` / `applyInstructionLinks` (370–384) | GLUE | Tiny, page-specific. Keep inline (or a `js/implementation/instruction-links.js` if you want it tested — optional). |
| `clearActive` / `safeActivateView` / `safeSetActive` / `setAgentDetailContent` (386–417) | EXTEND `DomNavigationController` | `safeActivateView` carries the **fullbleed** logic + fallback-to-`home`. Either add a `fullbleedSelector` option to the controller or keep a thin `safeActivateView` wrapper in the boot file that calls the controller then toggles `fullbleed`. **Recommended:** keep these four as boot-file helpers that delegate to the controller, because the sub-nav transition table here is far richer than `NavigationController.sections` models. |
| All nav `addEventListener` wiring + back-buttons (422–686) | GLUE | This is page wiring: which tab opens which manager. It stays in the boot file but should be **data-driven and compact** — see §3. Keep it calling `AM`/`SM`/`SSHM`/`RF` facades (now backed by the library) so it stays short. |

> The `NavigationController` State machine is a good fit for the *simple* sections (status, tools) but the **plans → rol-finance → rol-finance-reports** and **agents → agent-detail** chains have bespoke transitions. Don't force everything through `NavigationController.enterSection`; use it where it fits and keep explicit handlers for the nested chains.

### 2.2 Utilities & Speech (688–808)
| Inline | Disposition | Notes |
|---|---|---|
| `esc`, `sleep` (689–690) | REUSE `TextUtils` | `TextUtils.esc`, `TextUtils.sleep` (confirm `sleep` exists in `text-utils.js`; if not, add + test). |
| `Speech` object + `FEMALE_VOICE_RE`/`MALE_VOICE_RE`/`AGENT_VOICE_PREFERENCES` + `voiceFor` (700–808) | **EXTEND** | The library `SpeechSynthesizer` has a *single* voice; the live code has a **per-agent voice catalog**. Build the missing `AgentVoiceCatalog` (see §3.1). The inline comment at line 697 references `js/abstract/agent-voice-catalog.interface.js` — **that file does not exist yet; create it.** |

### 2.3 Agent Manager `AM` (810–1430)
| Inline method | Disposition | Maps to |
|---|---|---|
| `DETAIL_RENDERERS` map (812–820) | EXTEND | Rebuild as a registry of `DetailRenderer` strategies. **Drop the two dead entries** (`agent-detail-chat-interface` → `renderChatInterface`, which doesn't exist). |
| `fetchJSON` (835) | REUSE `FetchHttpClient` | `http.getJSON` / `http.postJSON`. |
| `stopPoll` (831) | REUSE `ActivePoller` | `poller.stop()`. |
| `showAgentsHome` / `loadAgentTabs` (845–908) | EXTEND | Tab creation → `DomTabFactory.buildAgentTab`. The **status-line messaging** (`file://` warning, "Loaded N agents (cached Ns ago)", `_tabsLoading` re-entrancy guard) is glue — wrap in a small `AgentTabsController` (NEW, §3.2) or keep as a thin boot helper that uses `DomTabFactory`. |
| `openAgent` / `renderDetail` (911–933) | EXTEND | Nav transition + `ActivePoller` + strategy dispatch. |
| `consoleShell` (935) | REUSE `DomConsoleView.mount` | |
| `formatStreamRow` (943) | REUSE `AgentStreamFormatter` | In `abstract/stream-formatter.interface.js`. |
| `renderStream` (959) | REUSE `StreamDetailRenderer` + `AgentStreamController` | |
| `renderAgentCard` (990) | **NEW** `AgentCardRenderer` | Fetches `/api/agent-card`, renders identity/system_message/role/responsibilities/tools/memory_summary. §3.3. |
| `renderLog` (1015) | **DELETE** | Dead code — defined, never referenced. |
| `renderTest` (1029, the chat/Tests tab) | **EXTEND `ChatDetailRenderer`** | Live version adds: `setAgentTabStatus` calls, per-agent voice, **Copy to Clipboard** button + `legacyCopy` fallback, Auto/Review toggle controlling Copy visibility. §3.4. |
| `renderInputOptions` (1235) | **NEW** `InputOptionsRenderer` | The "Input Options" tab — its own UI (textarea + Send + Start/Stop voice + Auto Send + Speak + Copy + status line). Shares the voice pipeline (`MediaRecorderVoiceRecorder`) and `/api/test` send, but the layout/labels differ from chat. §3.5. |
| `openById` (1416) | GLUE | Deep-link helper; stays in boot file, calls the agent facade. |

### 2.4 Confirmed dead code to delete
- `AM.renderLog` (1015–1027) — never referenced.
- `DETAIL_RENDERERS['agent-detail-chat-interface']` (816) — there is no `agent-detail-chat-interface` tab in the sidebar and no `AM.renderChatInterface` method. Dead.
- Duplicate `<section id="plans-mazda-orchestrator">` — **there are two** (lines 296–298 and 300–319). The second (with the inline status box + `#divide-conquer-frame`) is an unreachable duplicate id. Confirm which one is wanted and delete the other. (Markup, not script, but clean it up in the same pass.)
- The stray `<section id="scissari">` (247–249) iframe + its `SCISSARI_AGENT_NAME` const (822) — verify still used by any nav path before deleting; `safeActivateView('scissari')` has no caller in the current script. Flag for confirmation.

### 2.5 Server Manager `SM` (1432–1650)
| Inline | Disposition | Maps to |
|---|---|---|
| `fetchJSON` | REUSE `FetchHttpClient` | |
| `pollHealth` + `updateMainTabColor` + `updateServerTabColors` (1458–1500) | REUSE `ServerHealthMonitor` | Register two observers via `monitor.subscribe(...)`: one colours `#btn-server-mgmt` (use `HealthMonitor.overallStatus`), one colours the per-server tabs. |
| `showServersHome` / `loadServerTabs` (1502–1533) | EXTEND | `DomTabFactory.buildServerTab`; keep the 5s health interval. |
| `openServer` (1535–1645) | REUSE `ServerLogController` + `ServerActionController` + `classifyServerStatus` | The **log filter `#srv-filter`** is a view concern not in `ServerLogController`; add a small filter helper on the console view or keep filter wiring in a thin `ServerDetailView` (NEW-small, §3.6). The start-button labels map (`startLabels`, 1542) is glue/config. |
| Page-load health poll (1648–1650) | GLUE | `monitor.poll()` + `setInterval(..., 10000)` in boot. |

### 2.6 SSH Connections `SSHM` (1652–1838) — **mostly NEW**
Mirror of `SM` but against `/api/ssh-connection-*` with a different payload shape (`health.connections` not `health.servers`, status only `up`/`down`). No library classes exist.
| Inline | Disposition | Maps to |
|---|---|---|
| `pollHealth` + colorers (1677–1710) | REUSE `ServerHealthMonitor` w/ different endpoint **but** shape differs (`connections` key). Either generalise `HealthMonitor` (add a `collectionKey` so it reads `health.connections`) or add a `ConnectionHealthMonitor` subclass. §3.7. |
| `loadConnectionTabs` (1721–1741) | EXTEND `TabFactory` | Add `buildConnectionTab({key,name})` (sets `data-conn-key`/`data-conn-name`). |
| `openConnection` (1743–1833) | **NEW** `ConnectionLogController` (like `ServerLogController` but `/api/ssh-connection-logs`) + **NEW** `ConnectionTestController` (Command → `/api/ssh-connection-test`, GET). §3.7. |
| Page-load health poll (1836–1838) | GLUE | |

### 2.7 ROL Finance Reports `RF` (1840–1917) — **NEW**
| Inline | Disposition |
|---|---|
| `openReports` / `buildTabsAndViews` / `openReport` / `showOnlyVerifiedTransactions` (1846–1917) | **NEW** `RolFinanceReportsController`. Fetches `/api/rol-finance-reports`, injects one tab + one `<section><iframe class="plan-frame">` per report, and on iframe `load` reaches into the same-origin doc to hide every `<section>` except `#verified-transactions` (keeping the category picker). Document the same-origin assumption in the class. §3.8. |

### 2.8 Cross-cutting helpers (1919–2012)
| Inline | Disposition |
|---|---|
| `setAgentTabStatus` (1920) | **NEW small** `AgentTabStatus` helper (or method on the agent tabs controller). Used by chat + input-options + activity poll, so it must be a shared, injectable function. |
| `startActivityPoll` (1928) | **NEW** `AgentActivityPoller` — polls `/api/agent-activity`, calls `setAgentTabStatus`. §3.9. |
| `codeChangeAlert` (1942) | **NEW** `CodeChangeAlert` — polls `/api/code-status`, blinks `#btn-agents-home`, shows/hides `#code-change-modal`, restarts via `/api/server-action`. §3.10. |
| `deepLink` (2000) | GLUE | Stays in boot; reads `location.search`, calls the agent facade / RF. |

---

## 3. Library work to add (before wiring)

Build these in `js/abstract/` (interface + policy, tested) and `js/implementation/` (browser binding), following the existing split. Add each to `js/implementation/index.js`. Each bullet lists the **required public API** so the boot file can depend on it.

### 3.1 `AgentVoiceCatalog` (EXTEND speech) — Strategy/Registry
- `abstract/agent-voice-catalog.interface.js`: holds `FEMALE_VOICE_RE`, `MALE_VOICE_RE`, the `AGENT_VOICE_PREFERENCES` table, and `voiceFor(agentName, voices, sharedVoice)` selection policy (pure, testable against a fake voices array). Port the exact logic from lines 700–778.
- Extend `BrowserSpeechSynthesizer` (or add `AgentAwareSpeechSynthesizer`) with `speak(text, agentName)` that resolves+caches a per-agent voice via the catalog, falling back to the shared voice. Keep `cancel()`, `supported`, `bindVoiceChanges()` (also clear the per-agent cache on `onvoiceschanged`, per line 806).
- **API the boot needs:** `speech.speak(text, agentName?)`, `speech.cancel()`, `speech.supported`, `speech.bindVoiceChanges()`.

### 3.2 `AgentTabsController` (EXTEND) — wraps `DomTabFactory` + status messaging
- `loadInto(navAgentsEl)`: fetch `/api/agents` (cache + `agentsLoadedAt`), drop old `.agent-tab`s, append new ones via `DomTabFactory.buildAgentTab`, write the status line (incl. `file://` warning when `!served`, "Loaded N agents (cached Ns ago)"), honour the `_tabsLoading` re-entrancy guard.
- **API:** `tabs.showHome()`, `tabs.load()`, `tabs.agents` (cached list for deep-link lookup).

### 3.3 `AgentCardRenderer` (NEW) — `DetailRenderer`
- `render('agent-detail-agent-card', agentId)`: GET `/api/agent-card?agent=<id>`, render the exact HTML block from lines 1000–1009 (identity, agent_id, optional `system_message` in `<pre class="agent-system-message">`, role, responsibilities `<ul>`, tools `<ul>`, memory_summary). Error → `.msi-line err`.
- **API:** standard `DetailRenderer.render(target, agentId)`.

### 3.4 Extend `ChatDetailRenderer` to match live `renderTest`
Add, behind constructor options so existing tests stay valid:
- `onStatus(agentId, state)` callback fired `'active'` before send, `'idle'|'error'` after — boot passes `setAgentTabStatus`.
- per-agent voice: call `speech.speak(text, agentName)`.
- **Copy to Clipboard** button + `legacyCopy` fallback (lines 1192–1232) and the Auto/Review toggle that shows/hides Copy (1106–1118).
- Match the live button labels ("Speak", "🔊/🔈"), not the current library's "Speak Replies". (Confirm with EG if you'd rather keep the library labels — but default to preserving live behaviour.)
- Update `js/tests/detail-renderers.test.js` accordingly.

### 3.5 `InputOptionsRenderer` (NEW) — `DetailRenderer`
- Port `renderInputOptions` (1235–1413) verbatim in behaviour: textarea, Send (POST `/api/test`, `setAgentTabStatus`), Start/Stop voice via `MediaRecorderVoiceRecorder`, Auto Send toggle, Speak toggle (per-agent voice), Copy to Clipboard, status line. Reuse the same voice recorder + http + speech ports as chat.

### 3.6 `ServerDetailView` (NEW small, optional) — log filter wiring
- Owns `#srv-filter` input → hides `.msi-entry` rows not matching. Keeps `openServer`'s view glue out of the boot. Alternatively add a `filter(query)` method to `DomConsoleView`. Pick one; document it.

### 3.7 SSH classes (NEW)
- `ConnectionHealthMonitor` (or generalise `HealthMonitor` with a `collectionKey: 'connections'` option) → `/api/ssh-connection-health`, observers colour `#btn-ssh-connections` + per-conn tabs. Note SSH has only `up`/`down` (no `starting`).
- `TabFactory.buildConnectionTab({key,name})`.
- `ConnectionLogController extends PollingController` → `/api/ssh-connection-logs?conn=<key>`, same dedup-by-`seq` + status LED as `ServerLogController` (reuse `classifyServerStatus`; note CONNECTED vs UP label — see lines 1774–1782, may need a variant).
- `ConnectionTestController` (Command) → GET `/api/ssh-connection-test?conn=<key>`, returns `{ok,text}`; on click sets LED, re-polls health.

### 3.8 `RolFinanceReportsController` (NEW)
- `openReports()`, `buildTabsAndViews(reports)`, `openReport(key)`, `showOnlyVerifiedTransactions(iframe)` — port lines 1846–1917 exactly. Inject the nav (`#nav-rol-finance-reports`) and views container (`#rol-finance-reports-views`) and an `HttpClient`. Keep the same-origin iframe-reach + the missing-report red-tab placeholder.

### 3.9 `AgentActivityPoller` (NEW)
- Polls `/api/agent-activity` every 5s, calls an injected `setStatus(id, status)`. Trivial; test the poll loop with a fake http + fake timer.

### 3.10 `CodeChangeAlert` (NEW)
- Polls `/api/code-status` every 15s; blink `#btn-agents-home`, show/hide `#code-change-modal`, Yes → POST `/api/server-action {server:'dashboard',action:'restart'}`, No → remember dismissed signature. Port lines 1942–1995. Inject the element ids + http + timer.

---

## 4. Phased cutover plan (each phase ships independently, tests stay green)

Do them in this order — earliest phases are lowest-risk and unblock the rest.

> Before phase 1, decide the entry-point mechanics: change the `<script>` (line 351) to `<script type="module">` and create `js/dashboard-boot.js` that imports from `./implementation/index.js`. Move code into the boot file phase by phase; the boot file *is* the shrinking inline script. By the end, `dashboard.html`'s only script is `<script type="module" src="/js/dashboard-boot.js"></script>` (or a ~50-line inline module that just wires injected globals and calls `boot()`).

1. **Prep + dead-code removal.** Delete `renderLog`, the dead `DETAIL_RENDERERS` entry, the duplicate `plans-mazda-orchestrator` section (after confirming which to keep), and verify/flag the `scissari` section. Confirm `TextUtils.sleep` exists (add+test if not). Green tests. *(No behaviour change.)*
2. **HTTP + console + utils.** Replace inline `esc`/`sleep`/`fetchJSON`/`consoleShell` usages with `TextUtils` + `FetchHttpClient` + `DomConsoleView`. One shared `http` instance injected everywhere. Low risk, touches many call sites.
3. **Speech + agent voices** (§3.1). Swap `Speech` for the extended synthesizer. Verify TTS still picks per-agent voices in Chrome.
4. **Agent detail streams** (Thoughts/Messages/Tool Calls): swap to `StreamDetailRenderer`/`AgentStreamController` via `ActivePoller`. Verify dedup + "no X yet" placeholder + 3s polling + single-active-stream on tab switch.
5. **Agent Card** (§3.3) + **Chat/Tests** (§3.4) + **Input Options** (§3.5). These share the voice/http/speech ports. Verify mic on the **https Tailscale URL** (mic is blocked on plain http — see dashboard CLAUDE.md).
6. **Agent tabs + activity + tab status** (§3.2, §3.9, §2.8). Verify agent list loads/caches, tabs colour on activity, no double-load race (`_tabsLoading`).
7. **Server Management** (§2.5): health monitor + observers + log controller + action controller + filter. Verify LED colours on main tab + per-server tabs, log tail, filter, Start button.
8. **SSH Connections** (§2.6/§3.7): the new SSH classes. Verify tab colours, Test Connection, log tail.
9. **ROL Finance Reports** (§2.7/§3.8). Verify report tabs build, iframe loads, only Verified Transactions section shows, picker still works, missing reports show red.
10. **Code-change alert** (§3.10) + **deep-link** glue. Verify blinking Agents tab + modal + `?agent=`/`?view=rol-finance-reports` deep links.
11. **Final boot file cleanup.** Collapse the nav wiring (§2.1) to a compact, data-driven form. Confirm `dashboard.html` inline JS is gone (only the module entry remains).

---

## 5. Verification checklist (run after *every* phase)

**Automated:**
```bash
bun test js/tests                 # must stay 118+ pass / 0 fail (grows as you add tests)
.venv/bin/python -m pytest tests/ # server tests must stay green (no backend changes expected)
```

**Manual (browser — the only way to catch nav/mount regressions).** Load `http://localhost:8765/` and exercise, per phase touched:
- Sidebar: Home / Status / Instructions / Tool Management / Agent Management / Server Management / SSH Connections / Project Plans all open; every **Back** button returns to main+Home.
- Iframe/console views go **full-bleed** (Scissari, plan frames, ROL reports) — the `fullbleed` class still toggles.
- Agent → Thoughts/Messages/Tool Calls stream + dedupe + 3s refresh; switching agent stops the old stream.
- Agent → Agent Card renders system_message; Tests chat sends + speaks in the agent's voice + Copy works + Auto/Review toggles Copy; Input Options send/voice/auto-send/speak/copy.
- Server Management: main tab + per-server LED colours, log tail, filter, Start button.
- SSH Connections: tab colours, Test Connection, log tail.
- ROL Finance → Reports: tabs build, only Verified Transactions shows, category picker still saves, missing report = red tab.
- Mic test on the **https Tailscale hostname** (mic is silently blocked on plain http).
- Deep links: `/?agent=<id>&view=messages` and `/?view=rol-finance-reports`.
- Code-change alert: edit then revert a watched file, confirm Agents tab blinks + modal.

**Restart note:** if you restart the service to retest (`systemctl --user restart dashboard-server.service`), it **kills the Executor Server** (cgroup KillMode) — follow with the dashboard's "Start Executor Server" button. (See the dashboard CLAUDE.md / memory.)

---

## 6. Definition of done

- `dashboard.html` inline `<script>` reduced to a single `type="module"` entry (target: **< ~80 lines** of boot wiring, ideally an external `js/dashboard-boot.js`).
- Every live behaviour above preserved (verified manually).
- `bun test js/tests` green and **expanded** to cover the new classes (`AgentVoiceCatalog`, `AgentCardRenderer`, `InputOptionsRenderer`, SSH trio, `RolFinanceReportsController`, `AgentActivityPoller`, `CodeChangeAlert`, extended `ChatDetailRenderer`).
- `js/implementation/index.js` exports everything the boot file imports.
- Dead code removed in its own commit.
- `js/README.md` + `js/implementation/README.md` updated: remove the "not yet imported / intentionally separate cutover" caveats and document the new classes in the mapping tables. Update the dashboard `CLAUDE.md` section "Frontend — mid-refactor" to say the cutover is done.

---

## 7. Risks & rollback

- **Highest risk:** a nav transition or console mount that unit tests can't see. Mitigation: phase-by-phase + the manual checklist + keep `git` commits small so `git revert` of one phase is clean.
- **Same-origin iframe reach** (ROL reports, §3.8) only works because reports are served same-origin; if a report ever moves cross-origin the hide-sections step silently no-ops (current behaviour — preserve, don't throw).
- **ES module load failure** would blank the whole dashboard (vs. one broken tab). Test the module entry early (phase 1) with a trivial import before moving real code.
- Keep a `dashboard.html` backup of the pre-cutover file (there is already a `dashboard.html.bak-*` in the tree — make a fresh dated one at the start).

---

*Prepared from a full read of `dashboard.html` (2026-06-14) and every file in `js/abstract/`, `js/implementation/`, against the design rules in `js/README.md`. Test baseline at time of writing: `bun test js/tests` → 118 pass / 0 fail.*
