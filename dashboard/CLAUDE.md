# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-page dashboard (`dashboard.html`, served by `server.py`) for monitoring and operating
Letta agents (roster in `LETTA_AGENTS` in `server.py` — currently Scissari, Frita, Hailey, Jeri,
the Mazda orchestrator + her minions, and the Suzuki orchestrator + her minions) plus Claude
Code — with browser **voice input** (push-to-talk → whisper.cpp → cleanup agent → send) and a
**Server Management** tab that health-checks and restarts the surrounding infrastructure. It
lives inside the `letta-code` repo but is a self-contained sub-project: a stdlib-only Python
backend and a vanilla JS/CSS frontend (no build step, no node_modules here).

## Commands

### Run the dashboard
```bash
./start.sh                 # frees port 8765, starts server.py (foreground; TUNNEL=1 for cloudflared)
# or directly:
python3 server.py          # PORT=9000 to override port; LETTA_BASE_URL to point at a different Letta server
```
Serves on **http://localhost:8765/**, binds `0.0.0.0`. `ReusableHTTPServer` is a
`ThreadingHTTPServer` — slow requests (whisper transcription ~5s) don't block the dashboard's
pollers. In production this also runs as a systemd `--user` service (`dashboard-server.service`)
that autostarts on boot — see "Boot autostart" below.

### Tests
```bash
# Python — server + voice pipeline
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # first time only
.venv/bin/python -m pytest tests/
.venv/bin/python -m pytest tests/test_server.py -k test_get_server_known_and_unknown  # single test

# JS — GoF interface/implementation layer (run with bun, NOT pytest/jest)
bun test js/tests
```
System Python is PEP-668 externally-managed; the **server itself needs only the stdlib** — the
venv exists solely to run pytest. `tests/conftest.py` adds the dashboard dir to `sys.path` so
`import voice` and `import server` work from test files, and has an autouse fixture that disables
the Trainer (see below) and redirects `recent_report.json` to a tmp path — any new test touching
`process_scanned_document`/`process_pdf_document` inherits this automatically.

### Phone / microphone access (HTTPS required)
`getUserMedia()` (mic capture) only works in a secure context (https or localhost). Plain
`http://<tailscale-ip>:8765` silently blocks the mic on Android. Front the server with a real
cert via Tailscale Serve:
```bash
tailscale serve --bg 8765   # one-time; persists across reboots (needs --operator=$USER once)
```
Then open `https://desktop-2obsqmc-24.tailb8fc54.ts.net/` on the phone — use the **hostname**,
not the IP, or the cert won't validate.

## Architecture

### `server.py` — the entire backend (stdlib `http.server`, no framework)
One file, one `DashboardHandler(SimpleHTTPRequestHandler)`. Two registries drive most of the app
and must stay in sync with the frontend / other repos when you add things:

- **`LETTA_AGENTS`** — `{'name', 'id'}` entries; `id: None` auto-discovers by name from the live
  Letta API (cached in `_letta_id_cache`). Adding an agent here makes it appear in the sidebar
  automatically. Keep in sync with `voice.config.KNOWN_AGENT_NAMES` (biases whisper transcription
  toward real agent names). `/api/agents` is cached server-side for 5 minutes
  (`AGENT_LIST_CACHE_TTL`); use `/api/agents?refresh=1` to bypass after editing the registry, and
  `/api/agents` must always return a bare array, never `{"agents": [...]}`.
- **`SERVERS`** (Server Management registry) — each entry describes one piece of infrastructure,
  monitored via one of: `log_file` (tailed locally), `health_url` (HTTP up/down), `tcp_check`
  `(host, port)` (non-HTTP servers like MCP proxies), or `check` (a custom body-aware probe fn in
  `HEALTH_CHECKS` — use when "HTTP 200" isn't enough and you must inspect the response). Remote
  hosts that can't be tailed locally are health-checked only. `/api/server-health` reports any
  server with a `health_url`, `tcp_check`, or `check`; log-only servers are inspected via
  `/api/server-logs` instead.
  - **`frita-executor`** uses a `check` (`frita_executor_health`) rather than a plain `health_url`
    because of a two-stack situation on the Win10 box: the Mazda minions reach an SDK-equipped
    executor via a **host bridge on `:8799`**, and the check goes red when that isn't SDK-ready,
    appending a `⚠ GHOST on :8797` warning if a stale no-SDK executor is shadowing it. Redeploy
    via the **"Start" button** (`deploy_frita_executor.sh` on the Win10 box).
  - **"Letta Server"** has a `log_file` despite running in Docker on the remote Win10 box
    (`100.80.49.10`): a background daemon (`_letta_remote_log_pull_loop`) SSHes there every 30s
    and appends new lines to a local cache that `tail_lines` reads like any other log. The pull
    script content-sniffs recent `*-json.log` files for Letta's logging signature rather than
    assuming the container named `letta-server` is the live one, because an untracked containerd
    task on that box can keep serving `:8283` after the named container's stdout goes silent.

Everything else proxies the live Letta API at `LETTA_BASE_URL` (default
`http://100.80.49.10:8283`, override via env) — `letta_get`/`letta_messages`/`letta_thoughts`/
`letta_toolcalls` map Letta's `reasoning_message`/`user_message`/`assistant_message`/
`tool_call_message`/`tool_return_message` stream into the dashboard's Thoughts/Messages/Tool
Calls tabs. Claude Code is wired differently — it has no Letta agent, so its messages/tool calls
come from local JSON files (`claude_messages.json`, `claude_toolcalls.json`) written via
`POST /api/claude-log` / `POST /api/claude-toollog` (a PostToolUse hook + the `dashboard-log`
skill write to these).

### Frontend — GoF layering
`dashboard.html` is pure markup (~328 lines); its only script is
`<script type="module" src="/js/dashboard-boot.js">`. Per the Gang of Four playbook in
`js/README.md`: CSS lives in `css/dashboard.css`; JS splits into `js/abstract/` (interfaces /
Template-Method skeletons — no DOM, no `fetch`, collaborators injected so they're unit-testable
in Node) and `js/implementation/` (concrete subclasses wiring those interfaces to real browser
APIs: `FetchHttpClient`, `DomConsoleView`, `ServerHealthMonitor`, `AgentStreamController`,
`DomTabFactory`, `MediaRecorderVoiceRecorder`, the detail renderers, the SSH/ROL/code-alert
controllers — see `js/implementation/README.md` for the full interface ↔ concrete-class ↔
GoF-pattern mapping). **`js/implementation/*` is the live code** — editing it changes runtime
behaviour. `js/dashboard-boot.js` is the entry point that constructs those classes, binds them to
the DOM, and holds page-specific navigation glue (sidebar tab transitions, the nested sub-nav
chains for plans → ROL Finance → Reports and agents → agent-detail, the `AM`/`SM`/`SSHM`/`RF`
facades, deep-linking) rather than forcing everything through `NavigationController`.

No build step — `server.py` serves `js/*` as-is, so editing + reloading the browser is the whole
loop. Verify in a real browser (Playwright against `http://localhost:8765/`; the only expected
console error is a `favicon.ico` 404), and run `bun test js/tests` after any change.
**Pre-commit gotcha:** husky/lint-staged runs `biome check --write` on staged `.js` files and an
unfixable lint **error aborts the commit** — most often `useIterableCallbackReturn`: write
`forEach(x => { x.remove(); })`, not `forEach(x => x.remove())`. Run
`bunx --bun @biomejs/biome@2.2.5 check --write js/<file>.js` before committing to catch these.

### Voice pipeline (`voice/`)
`browser MediaRecorder → POST /api/voice (raw audio body, X-Filename header) → whisper.cpp →
transcript-cleanup-agent → fills the message box → POST /api/test sends it`. GoF: Strategy
(transcription/cleanup swap), Adapter (`LettaClient`), Factory (`build_*`), Pipeline
(`VoicePipeline`), front-end State machine (recorder idle→recording→processing).

| File | Role |
|---|---|
| `voice/config.py` | paths/ids from env; bakes in lettabot's whisper defaults; `KNOWN_AGENT_NAMES` |
| `voice/transcription.py` | `WhisperCppTranscriber` (ffmpeg → 16k wav → `whisper-cli`) |
| `voice/cleanup.py` | `LettaAgentCleanup` — clears the cleanup agent's history each call; raw-text fallback |
| `voice/letta_client.py` | thin Letta HTTP adapter |
| `voice/pipeline.py` | `VoicePipeline.process` + `handle_voice_upload` (the `/api/voice` handler logic) |

It reuses lettabot's binaries rather than reinventing them — `whisper-cli` at
`~/whisper.cpp/build/bin/whisper-cli`, model `~/whisper.cpp/models/ggml-base.en.bin`, ffmpeg from
lettabot's bundled `imageio_ffmpeg`. All overridable via env (`WHISPER_CPP_BIN`,
`WHISPER_MODEL_PATH`, `FFMPEG_BIN`, `WHISPER_LANGUAGE`, `WHISPER_THREADS`, `WHISPER_PROMPT`).

Every successful `/api/voice` call appends `{date, raw, cleaned}` to `voice_transcripts.json`
(gitignored) — compare `raw` (what whisper heard) vs `cleaned` (what the cleanup agent produced)
to diagnose a mis-delivered agent name. Whisper's `base.en` model can mishear an agent name as a
common word too far off for the cleanup agent to rescue (e.g. "Mazda" → "Melissa"); the fix is
`config.WHISPER_PROMPT` biasing whisper up front with the real agent names (disable with
`WHISPER_PROMPT=""`).

Plan/design doc: `audio_input/audio_plan.html` (viewable in-dashboard under Project Plans →
Audio Input); original spec `audio_input/audio_input.md`.

### Agents-home voice/text router (`router/`)

The Agents tab's home view (`#agents-home` in `dashboard.html`) is no longer a static "Loaded N
agents…" message — it's a router (`AgentsRouterRenderer`,
`js/implementation/agents-router-renderer.js`): the user talks or types, and as soon as a **known
agent's name** is detected, the dashboard opens that agent's Input Options page and hands it only
the text *after* the name, without interrupting listening. Routable names are deliberately a
narrower list than `voice.config.KNOWN_AGENT_NAMES` — only the top-level roster (Frita, Scissari,
Hailey, Jeri, Mazda, Suzuki), defined in `router/config.py`'s `ROUTER_AGENT_NAMES`, not Mazda's/
Suzuki's sub-agents.

Two buttons, deliberately different tech, **both only on this page** (not on individual agents'
Input Options pages):
- **Start Recording** — the existing push-to-talk `MediaRecorderVoiceRecorder` → whisper.cpp flow
  (see Voice pipeline above), unchanged, just relabeled here.
- **Start Listening** — new: continuous browser-native `SpeechRecognition`
  (`js/implementation/browser-speech-recognition-listener.js`, `ListenerState` in
  `js/abstract/continuous-listener.interface.js`). Only *final* recognized chunks trigger
  detection; interim chunks are live-preview only. The listener is a **module-scope singleton in
  `dashboard-boot.js`** (not owned by the renderer, which is rebuilt fresh per-open like all other
  detail renderers) so listening survives navigation to the detected agent's page — only its
  callbacks get re-bound via `setCallbacks()` on each render.

Detection (`router/classify.py`, same Strategy shape as `voice/cleanup.py`'s `LettaAgentCleanup`)
is two-tier: `detect_known_agent()` first tries a deterministic exact-name match (zero network,
instant) before falling back to the `dashboard-agent-router` Letta agent
(`agent-b2993865-228f-47a2-b436-d35e3aff50f0`, model `chatgpt-plus-pro/gpt-5.4-mini`, **not** in
`LETTA_AGENTS` — stays out of the sidebar on purpose) for non-exact/implied references. **Fails
closed always**: any parse/network failure or ambiguous phrasing returns "no agent detected"
rather than guessing — a wrong guess would misroute a message, which is worse than not routing.
`POST /api/route-detect` `{text}` → `{ok, agent, remainder}`; `GET /api/router-agent` → `{ok,
agent_id}` (lets the frontend point the *existing* `/api/agent-model` dropdown at the router's own
classifier agent — `letta_id_for()` is a pure `agent-<uuid>` format check, not a `LETTA_AGENTS`
lookup, so no other backend changes were needed for that).

**openWakeWord was investigated and deliberately not used** (see `~/openWakeWord` if present) —
training custom per-agent-name wake-word models is real ML work (synthetic TTS data + a training
run per name) that was deferred. `ContinuousListener` is kept provider-agnostic specifically so a
future `ServerWakeWordListener` (streaming audio to a server-side `openwakeword.Model`) could be
swapped in later via `AgentsRouterRenderer`'s `listener` injection point with no renderer changes.

Tests: `tests/test_router_classify.py`, `js/tests/continuous-listener.test.js`,
`js/tests/browser-speech-recognition-listener.test.js`, `js/tests/agents-router-renderer.test.js`.

### Project Plans tab

The live dashboard source is the WSL repo at `/home/adamsl/letta-code`. `server.py` serves static
files from both `HERE` (`/home/adamsl/letta-code/dashboard`) and `REPO_ROOT`
(`/home/adamsl/letta-code`), so repo-root plan pages are valid dashboard URLs:

| Tab | File | Served URL |
|---|---|---|
| Self Evolving | `notes_plans_handoffs/agent_self_improvement/agent_self_improvement_plan.html` | `/notes_plans_handoffs/agent_self_improvement/agent_self_improvement_plan.html` |
| Mazda Dev Status | `notes_plans_handoffs/mazda_dev_status.html` | `/notes_plans_handoffs/mazda_dev_status.html` |
| Audio Input | `dashboard/audio_input/audio_plan.html` | `/audio_input/audio_plan.html` |

**`Mazda Dev Status` is the canonical current-direction doc** (Mazda is the orchestrator herself,
with minions that drive the Claude Agent SDK). `team_construction_plan.html` (repo root) describes
a discarded earlier design and is kept only as history, no longer linked from the Project Plans
tab. If deployment details are unclear, Frita knows the dashboard setup and can be messaged at
Letta agent id `agent-881a883f-edd0-4963-bf67-6ef178b8f018`.

After editing Project Plans, sanity-check with:
```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8765/notes_plans_handoffs/mazda_dev_status.html
.venv/bin/python -m pytest tests/
```

### ROL Finance Reports (Project Plans → ROL Finance → Reports)

Each report is a static `report.html` embedded in an iframe (built outside this repo under
`~/rol_finances/readable_documents/bank_statements/**/report.html`, served via the
`/rol_finances_reports/` URL prefix → `ROL_FINANCES_REPORTS_BASE`). The injector
`~/rol_finances/tools/python_tasks/verification_lib/restructure_verified_transactions.py`
rewrites the "Verified Transactions" table, stamping each `<tr>` with
`data-vendor-key/description/signed-amount/date` and appending a marker-delimited
(`<!-- rol-category-picker:start/end -->`) block holding the **Set Category dialog**. Re-running
the injector is idempotent and *replaces* that block, so JS/CSS changes there propagate:
`python3 restructure_verified_transactions.py $(find ~/rol_finances -name report.html)`.

The dialog calls these `server.py` endpoints — keep them in sync with the injector's JS:

| Endpoint | Purpose |
|---|---|
| `POST /api/recategorize-expense` | Sets a row's category in MySQL and rewrites the `cat-*` class on the `<tr>` on disk so the color survives refresh. |
| `POST /api/receipt-lookup` | "View Receipt" → `{ok, receipt_url}` (a `/rol_finances_receipts/` URL) or `{ok:false, error}`. |
| `POST /api/receipts-present` | Batch `{rows:[…]}` → `{present:[bool,…]}`, driving the red top-left receipt marker. |
| `GET /rol_finances_receipts/<rel>` | Serves a receipt file (path-traversal checked; image/pdf content-types). |

**Receipt resolution** (`_resolve_receipt_path`, FS index cached 300s): files are named
`<vendor>_MM_DD_YY_<dollars>_<cents>.<ext>` under `readable_documents/receipts/**`. Match order:
**(date, amount) parsed from the filename** → `receipt_url` exact path → stem-flex (any
extension) → basename anywhere — more reliable than the DB `expenses.receipt_url` string, which
often differs by extension or vendor spelling. Rows ↔ expenses join on `expense_date` +
`abs(amount)`, disambiguated by vendor_key prefix then exact description. Receipt files are
synced between this box and mom's machine rosemary46, so all receipts are present locally.

**Injector gotchas:** the head `CATEGORY_PICKER_CSS` is injected once and guarded, so it does
**not** refresh on re-run — put dialog CSS *changes* in the marker-block `<style>` instead (which
IS strip+reinjected). And `window.open(url, "_blank", "noopener,noreferrer")` returns **`null` by
spec** when `noopener` is set — don't treat a null return as "popup blocked".

**Deploy:** after editing `server.py`, `systemctl --user restart dashboard-server.service`. After
editing the injector, re-run it on all reports (command above). See the
`rol_finance_view_receipt_fix` project memory.

### Recent Report — the Reports tab's default view

Project Plans → ROL Finance → Reports opens on **Recent Report** (`GET /recent_report.html`),
not a fixed month: it always shows whatever document was most recently dispatched to Mazda, in
one of two modes chosen by `resolve_recent_report()` (newest of: an explicit report pointer, the
newest `report.html` mtime, and the last intake dispatch):

- **report mode** — the document has a real `report.html` (13 registered statement docs). Served
  with an injected `<base href>` so the report's own table + category picker work unchanged; the
  picker's POST is translated back to the real report URL by `_resolve_report_path_alias()`.
- **intake mode** — no `report.html` exists (the normal case for a **scanned** document, which
  stores straight to MySQL). `build_recent_intake_html()` renders a synthetic page live from the
  DB, listing every expense id Mazda's STEP 8/9 callback reported — both newly stored
  (`expense_ids`) and duplicate-matched-but-not-stored (`duplicate_expense_ids`) — as a clickable
  table with the same picker. Under the "dispatched" line it also shows **Document Type**,
  **Month Range**, **Associated PDF**, **Associated Receipt**, computed by reusing existing
  primitives (`_find_matching_report_row` + `_source_document_path` for the PDF,
  `_resolve_expense_receipt_path` for the receipt) rather than re-deriving linkage. `doc_kind`/
  `vendor` are seeded `unknown` by the text-extraction facade for scanned JPEGs (no extractable
  text) and overwritten once Mazda reports her own vision classification in STEP 8. Note the
  naming divergence: `mazda_intake.py` uses `doc_kind`/`vendor`, while
  `rol_finances/tools/classify_scan.py` (Mazda's vision classifier) uses `doc_type`/`merchant`;
  the merge functions accept either.

Bookkeeping lives in `dashboard/recent_report.json` (gitignored): `process_scanned_document`/
`process_pdf_document` write an intake record the moment they dispatch Mazda, and
`record_stored_expense` (the `/api/expense-stored` handler) folds in `expense_ids`/
`duplicate_expense_ids`/`parsed`/`stored` via `merge_recent_intake_event()`. **Mazda's callback
must fire even when `stored:0`** — a re-scan of an already-processed statement is a common,
correct outcome, but without the callback the page would show stale or empty data instead of
"here are the transactions this run touched."

Dispatch is server-side and deduped: `run_scanner()` spawns `process_scanned_document` itself the
instant a scan reports `ready` (so closing the browser tab right after a scan can't lose the
document); `_claim_scan_dispatch(key, image_path)` (keyed on scanner + path + mtime) prevents the
frontend's `/api/process-document` POST from double-dispatching the same image.

Tests: `tests/test_server.py` (recent-report pointer/resolve/html-building, intake-record + STEP
8 merge, dispatch-claim dedup, `_resolve_report_path_alias`) +
`js/tests/rol-finance-reports-controller.test.js`.

### Scanners — physical document scanners (Project Plans → ROL Finance → Scanners)

Two HP scanners attached to the live box: **Window** = HPI297BEA (HP OfficeJet 8120e),
**Freezer** = HP063E28 (HP DeskJet 4100, non-default, flaky). Driven by
`scanner_scripts/scan_device.ps1` (in this repo; deployed to
`~/planner/nonprofit_finance_db/receipt_scanning_tools/`), which selects the device **BY NAME**
(`-NameLike`), not "first device" — WIA enumeration order is unstable. Wrappers
`run_scan_window.sh` (→`scan.jpg`) / `run_scan_freezer.sh` (→`scan_freezer.jpg`). `SCANNERS`
registry + `_invoke_scanner()`/`classify_scan_result()` live in `server.py`. Output is JPEG
(quality 85, ~1MB) rather than a raw ~26MB WIA-transfer PNG.

| Endpoint | Purpose |
|---|---|
| `POST /api/scanner-scan` `{scanner}` | One-shot manual scan → `{status, ok, image_url\|error}` |
| `GET /api/scanner-status?scanner=` | Lightweight probe → same `{status}` |
| `GET /api/scanner-image?scanner=` | Serves the scanned JPEG |

`status` ∈ ready/busy/offline/error. Auto-poll is gated by `MONITORED_SCANNERS` (a `Set` in
`setupScanners` in `dashboard-boot.js`) — currently empty, so neither scanner auto-polls; both sit
idle until "Start Scan" is pressed (constant auto-polling was itself found to cause the Window
scanner reporting "busy" from shared WIA-service contention).

**Gotchas** (full detail in the `dashboard-scanner-wsl-interop` memory):
1. **WSL interop** — the systemd `--user` dashboard service has no `WSL_INTEROP`, so it can't
   launch Windows `powershell.exe` directly. `_wsl_interop_socket()` borrows a working
   `/run/WSL/<pid>_interop` from an interactive WSL session — at least one must stay alive.
2. **stisvc wedge** — a hung scan can leak the Windows `powershell.exe` and wedge the Windows
   Image Acquisition service, so every scan hangs at `New-Object WIA.DeviceManager`.
   `_reap_stale_scans()` runs before each scan + after timeout. Fully-wedged recovery: elevated
   SSH to the Windows host, find `stisvc`'s PID via `sc queryex stisvc`, `taskkill /f /pid <PID>`
   (it auto-restarts); a milder case just needs `net stop stisvc & net start stisvc`.
3. A "busy" state that won't clear on power-cycle is often an **open ink door/cover**, not a held
   handle. A real scan takes ≈33s (OfficeJet 300dpi), not 10s.

Deploy: scp `scanner_scripts/*` to the scan-tools dir; scp dashboard files;
`systemctl --user restart dashboard-server.service`. Tests: `tests/test_server.py -k scan` +
`classify_scan_result`.

### Scan → Mazda intake pipeline

When a scan finishes, `process_scanned_document` runs the deterministic text-extraction facade
inline, then dispatches Mazda fire-and-forget via `_notify_mazda_of_scan`. The instruction Mazda
gets is built by the pure function `build_mazda_scan_message()` (unit-tested with no network).
Three load-bearing details:

1. The facade (`mazda_intake.py`) returns `ok:true` but `doc_kind:unknown, confidence:0` for
   JPEG scans (no extractable text). `mazda_facade_identified()` therefore requires
   `doc_kind!=unknown AND confidence>0 AND action!=reject` — not just `ok`. On unknown, Mazda is
   routed to classify the image herself with `classify_scan.py` (Gemini vision) +
   `parse_and_categorize.py --json`.
2. Every `rol_finances` command Mazda runs needs `PYTHONPATH=/home/adamsl/rol_finances` +
   `/home/adamsl/rol_finances/.venv/bin/python3` (constants `MAZDA_RF_PYPATH`/`MAZDA_RF_VENV_PY`)
   — bare `python3 tools/...` dies with `ModuleNotFoundError`. These run via Mazda's
   `executor_run`, served by this same dev box (Letta reaches it at `10.0.0.7:8789`).
3. STEP 5 has Mazda record the trace as `IntakeVerificationEvidence` JSON under
   `task_name="document-intake"`, and STEP 6 judges every run (`judge_trace`), feeding the
   autonomous self-improvement loop. The judge (the intake rubric in
   `rol_finances/tools/self_improving_agent`) is served by this box's `mazda-tools-mcp.service`
   (`http://10.0.0.7:8791/sse`) — restart it after a rubric/tool change. The message and the
   evidence model share a field contract pinned by
   `test_scan_message_instructs_structured_intake_evidence`.

### Scan → Trainer (Mazda's watcher)

Every intake dispatch (scanner scan and PDF/reprocess) also spawns a **Trainer** — a Claude agent
built per-run with `/home/adamsl/claude-code-sdk-ts` that watches Mazda's transcript, verifies the
STEP 1–8 contract against successful tool returns (not her prose claims), coaches her via a
corrective Letta message on failure, and always writes a report to
`trainer/reports/<UTC ts>_<scanner>.md`. Wiring: `_notify_trainer_of_scan` (fire-and-forget
detached Popen — a broken Trainer never blocks intake). Files: `trainer/mazda_trainer_instructions.md`
(system instructions), `trainer/run_mazda_trainer.mjs` (bun runner; `--dry-run` verifies prompt
assembly for free). Logs: `/tmp/mazda_trainer_<ts>.log`. Env: `MAZDA_TRAINER_ENABLED=0` kill
switch, `TRAINER_MODEL` (default sonnet), `TRAINER_TIMEOUT_MS` (default 25 min). Non-obvious
invariants (details in the `mazda-trainer-ops` skill): the trainer session dies if it ends its
turn to "wait" (instructions mandate Bash `sleep` loops + report-before-finish); the `.mjs` strips
`ANTHROPIC_API_KEY`/`CLAUDECODE`/`CLAUDE_CODE_ENTRYPOINT` so an inherited API key can't outrank
the OAuth login; the dashboard service's PATH lacks bun/claude so the Popen prepends
`~/.bun/bin:~/.local/bin`. Tests: `tests/test_server.py -k trainer` — the pytest conftest fixture
disables the Trainer so test runs never spawn a real ~25-minute Claude session.

## Server health indicators, restart, and Model Stats

- **4-state server status** via `compute_server_status()`/`server_status_kind()`:
  `up`/`concern`(yellow)/`starting`/`down`. Both `/api/server-health` (sidebar) and
  `/api/server-logs` call the same function so they never disagree. `concern` = reachable but
  degraded, dependency-down, down-but-restartable, or recently-restarted.
- **Win10 node root-cause tile** — `SERVERS` key `win10-node` (TCP :22 probe). Dependent servers
  (`letta`, `logger-api`, `frita-executor`, `dashboard-proxy`) carry `depends_on: 'win10-node'`
  and surface `blocked_by: win10-node` when it's down, collapsing many reds into one cause. Its
  Restart button revives the WSL node by restarting `tailscaled` via the Windows host. If the node
  *flaps* (up then dies within a minute), the WSL VM itself is cycling — fix with a
  `wsl --compact`/reset on the Windows side, not repeated tailscaled restarts.
- **Restart-any-server** — `RESTART_HANDLERS`/`restart_server(key)` covers every server; every
  detail panel has an always-enabled Restart button (`POST /api/server-action` `action:restart`).
  Local units restart via `systemctl --user restart <unit>`; frita-executor first runs
  `ensure_win10_docker` (removes a stale `/var/run/docker.pid` and starts docker).
- **Model Stats tab** — `/api/model-stats?source=` (+ `-sources`). Sub-nav: this box and mom's
  (rosemary46, via SSH) × Claude/Codex/Antigravity CLI. Antigravity has no quota API for free
  accounts, so its daily-request window is derived from the `loadCodeAssist` tier cap vs today's
  local `streamGenerateContent` log count; an expired token needs a manual `agy` re-auth (no
  self-heal). Claude/Codex use the **live** usage APIs (`api.anthropic.com/api/oauth/usage`,
  `chatgpt.com/backend-api/wham/usage`) — not the local rollout/stats-cache files, which are
  stale. Extractors self-heal on 401 by refreshing the stored OAuth token; if a raw refresh from a
  headless box gets WAF-blocked (429), running the real `claude`/`codex` CLI once
  (`ssh <box> bash -lc 'claude -p "ok"'`) is the reliable manual fix.

After editing `server.py`: `systemctl --user restart dashboard-server.service` (then re-Start the
Executor — the restart kills it). Tests: `tests/test_server.py`; `bun test js/tests` for the JS
reducers/controllers.

## Boot autostart (systemd `--user` services)

The dashboard and its locally-hosted companion servers autostart on boot via systemd `--user`
units in `~/.config/systemd/user/` (this account has `Linger=yes`, so user services start at boot
without a login session):

| Unit | Runs | Port |
|---|---|---|
| `dashboard-server.service` | `python3 server.py` (stdout/stderr → `/tmp/dashboard_8765.log`; needs `PYTHONUNBUFFERED=1` so the Server Management "Dashboard Server" log tab has anything to tail in real time) | 8765 |
| `lettabot.service` | `~/lettabot/start_scissari_bot.sh` (Scissari Telegram bot; has its own internal restart-loop supervisor — systemd is outer defense) | API :8091 |
| `thought-bridge.service` | `~/a2a_communicating_agents/thought_bridge.py` via `~/ws-venv` | **8766** |
| `thought-bridge-monitor.service` | `~/a2a_communicating_agents/serve_monitor.py` | 8899 |
| `dashboard-browser.service` | `open-in-browser.sh` — polls `localhost:8765`, then `exec google-chrome --app=...` (needs `Type=simple`, since it execs into a long-running process, plus explicit `DISPLAY`/`WAYLAND_DISPLAY`/`XDG_RUNTIME_DIR` — systemd `--user` doesn't inherit the WSLg graphical session at boot) | — |

**Port 8765 is reserved for this dashboard** — the Thought Bridge originally hardcoded the same
port and was moved to **8766**. If you add another locally-run server to `SERVERS`, make sure its
port doesn't collide with 8765.

Genuinely-remote servers in `SERVERS` (Letta Server, Logger API) can't be autostarted from here
and are health-checked/log-pulled over SSH instead (see the `_letta_remote_log_pull_loop` note
above). **Logger API's "Start" button self-heals** a docker-compose v1.29.2 bug: it `docker rm`s
any `logger-api*` container stuck in `Created` state before running the normal start script.
**"Executor Server" runs locally** on this same machine (not remote Docker on Win10, despite an
old note claiming otherwise) — started via `~/server_tools/start_executor_server.sh`
(REST executor on `:8787` with `/health`, MCP front door on `:8789` via `mcp-proxy`, run in the
foreground forever, so it must be launched detached). `start_executor_server()` in `server.py`
launches it via `subprocess.Popen(..., start_new_session=True)` and tails output to
`/tmp/executor_startup.log`.

Verify everything is up:
```bash
systemctl --user is-active dashboard-server lettabot thought-bridge thought-bridge-monitor dashboard-browser
curl -s http://localhost:8765/api/server-health | python3 -m json.tool
```
