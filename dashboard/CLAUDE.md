# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-page dashboard (`dashboard.html`, served by `server.py`) for monitoring and operating
Letta agents — Letta-backed agents (Scissari, Frita, Hailey, Cesare, Jeri, Mazda) plus Claude
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
pollers.

In production this also runs as a systemd `--user` service (`dashboard-server.service`) that
autostarts on boot — see "Boot autostart" below.

### Tests
```bash
# Python — server + voice pipeline (32 tests)
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # first time only
.venv/bin/python -m pytest tests/
.venv/bin/python -m pytest tests/test_server.py -k test_get_server_known_and_unknown  # single test

# JS — GoF interface/implementation layer (118 tests; run with bun, NOT pytest/jest)
bun test js/tests
```
System Python is PEP-668 externally-managed; the **server itself needs only the stdlib** — the
venv exists solely to run pytest. `tests/conftest.py` adds the dashboard dir to `sys.path` so
`import voice` and `import server` work from test files.

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
One file, one `DashboardHandler(SimpleHTTPRequestHandler)`. It is the single source of truth for
two registries that you must keep in sync with the frontend / other repos when adding things:

- **`LETTA_AGENTS`** (top of file) — `{'name', 'id'}` entries; `id: None` auto-discovers by name
  from the live Letta API (cached in `_letta_id_cache`). Adding an agent here makes it appear in
  the sidebar automatically. Keep this in sync with `voice.config.KNOWN_AGENT_NAMES` (used to
  bias whisper transcription toward real agent names).
  - Mazda's stage agents are explicitly listed here with stable IDs: Mazda Router, Mazda Parser,
    Mazda Vendor Identity, Mazda Receipt Linker, and Mazda Categorization. After adding agents,
    restart `dashboard-server.service` and verify with `curl -s http://localhost:8765/api/agents`.
  - `/api/agents` is cached server-side for 5 minutes (`AGENT_LIST_CACHE_TTL`) and the browser
    reuses the loaded list while navigating away/back to Agent Management. Use
    `/api/agents?refresh=1` after changing `LETTA_AGENTS` if you need to bypass the cache.
- **`SERVERS`** (Server Management registry, ~line 61) — each entry describes one piece of
  infrastructure the dashboard monitors via one of: `log_file` (tailed locally), `health_url`
  (HTTP pinged for up/down), `tcp_check` `(host, port)` (TCP connect test for non-HTTP servers like
  MCP proxies), or `check` (name of a custom body-aware probe fn in the `HEALTH_CHECKS` registry —
  use when "HTTP 200" isn't enough and you must inspect the response). Remote Docker hosts that
  can't be tailed locally are normally health-checked only — an unreachable health check *is* the
  "something is wrong" signal. `/api/server-health` reports any server with a `health_url`,
  `tcp_check`, or `check`; log-only servers (e.g. `lettabot`) are inspected via `/api/server-logs`
  instead. (`server_health` dispatches to `HEALTH_CHECKS[cfg['check']]` when `check` is set.)
  - **`frita-executor` uses a `check` (`frita_executor_health`)**, not a plain `health_url`, because
    of the two-stack mess on the Win10 box (the live Letta fleet runs in an untracked containerd
    "ghost" stack; see `frita_executor_ghost_container_2026_06_15` + `live_letta_db_topology`
    memories). The Mazda minions' `run_claude_code_sdk` reaches an SDK-equipped executor via the
    **host bridge on `:8799`** (the executor's cheap `GET /claude_sdk_status` reports
    sdk/claude/creds presence + container hostname — no Claude call). The check goes **down/red**
    when `:8799` isn't SDK-ready ("minions broken"), and appends a `⚠ GHOST on :8797` warning when a
    stale no-SDK executor is shadowing. Redeploy the good executor via the **"Start" button**
    (`deploy_frita_executor.sh` on `100.80.49.10`, which mounts the SDK + `rol_finances` + a
    `frita-claude-home` seeded with mom's token, and publishes `:8799`).
  - **Exception — "Letta Server"**: it *does* have a `log_file` despite running in Docker on the
    remote Win10 box (`100.80.49.10`). A background daemon thread (`_letta_remote_log_pull_loop`,
    started in `__main__`) SSHes there every 30s (key auth + passwordless sudo, both already set
    up for `adamsl`), runs `~/server_tools/pull_letta_server_logs.sh <since-ts>` (deployed to that
    box), and appends new lines to a local cache `/tmp/letta_server_remote.log` that `tail_lines`
    reads like any other log. The remote script self-heals around the box's recurring
    orphan-container problem (see `reference_letta_server_docker_architecture` memory — a NEW
    orphan ID `bcb52ddd…` was found active 2026-06-08, different from the `56e4d74c…` one
    documented 2026-06-01): instead of assuming the container named `letta-server` is the live
    one (it often isn't — its stdout goes silent ~10min after each restart while an *untracked*
    containerd task keeps serving `:8283`), it content-sniffs recent `*-json.log` files for
    Letta's `"Letta.<module> - LEVEL - ..."` signature and tails whichever one is actually live.

Everything else proxies the live Letta API at `LETTA_BASE_URL` (default
`http://100.80.49.10:8283`, override via env) — `letta_get`/`letta_messages`/`letta_thoughts`/
`letta_toolcalls` map Letta's `reasoning_message` / `user_message` / `assistant_message` /
`tool_call_message` / `tool_return_message` stream into the dashboard's Thoughts / Messages /
Tool Calls tabs. Claude Code is wired differently — it has no Letta agent, so its messages/tool
calls come from local JSON files (`claude_messages.json`, `claude_toolcalls.json`) written via
`POST /api/claude-log` / `POST /api/claude-toollog` (a PostToolUse hook + the `dashboard-log`
skill write to these). `/api/agents` must always return a bare array, never `{"agents": [...]}`.

### Frontend — GoF refactor (cutover complete)
`dashboard.html` was a ~2000-line monolith (markup + CSS + ~1660 lines of inline JS). It has
been broken up following the Gang of Four playbook documented in `js/README.md`:

- **CSS** is fully extracted to `css/dashboard.css`.
- **JS** is split into `js/abstract/` (interfaces / Template-Method skeletons — no DOM, no
  `fetch`, collaborators injected so they're unit-testable in Node) and
  `js/implementation/` (concrete subclasses that wire those interfaces to real browser APIs:
  `FetchHttpClient`, `DomConsoleView`, `ServerHealthMonitor`, `AgentStreamController`,
  `DomTabFactory`, `MediaRecorderVoiceRecorder`, the detail renderers, the SSH/ROL/code-alert
  controllers, etc — see the table in `js/implementation/README.md` for the full interface ↔
  concrete-class ↔ GoF-pattern mapping).

**The cutover is done.** `dashboard.html` is now pure markup (~328 lines); its only script is
`<script type="module" src="/js/dashboard-boot.js">`. `js/dashboard-boot.js` is the thin entry
point that constructs the classes above and binds them to the DOM, plus the page-specific
navigation glue (sidebar tab transitions, `safeActivateView`'s `fullbleed` toggle, the
`AM`/`SM`/`SSHM`/`RF` facades, deep-linking). **`js/implementation/*` is the live code now** —
editing it changes runtime behaviour. The nested sub-nav chains (plans → ROL Finance → Reports,
agents → agent-detail) are kept as explicit handlers in the boot file rather than forced through
`NavigationController`. Run `bun test js/tests` (160 green) after any change.

No build step — `server.py` serves these files as-is, so editing `js/*` + reloading the browser
is the whole loop. Verify in a real browser (Playwright MCP against `http://localhost:8765/`;
the only expected console error is a `favicon.ico` 404). **Pre-commit gotcha:** husky/lint-staged
runs `biome check --write` on staged `.js` files and an unfixable lint **error aborts the commit**
(reverting your changes) — most often `useIterableCallbackReturn`: write
`forEach(x => { x.remove(); })`, not `forEach(x => x.remove())`. biome also reformats the whole
file to 2-space indent. Run `bunx --bun @biomejs/biome@2.2.5 check --write js/<file>.js` before
committing to catch these.

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

It **reuses lettabot's binaries rather than reinventing them** — `whisper-cli` at
`~/whisper.cpp/build/bin/whisper-cli`, model `~/whisper.cpp/models/ggml-base.en.bin`, ffmpeg
from lettabot's bundled `imageio_ffmpeg`. All overridable via env (`WHISPER_CPP_BIN`,
`WHISPER_MODEL_PATH`, `FFMPEG_BIN`, `WHISPER_LANGUAGE`, `WHISPER_THREADS`, `WHISPER_PROMPT`).

Every successful `/api/voice` call appends `{date, raw, cleaned}` to `voice_transcripts.json`
(gitignored) — compare `raw` (what whisper heard) vs `cleaned` (what the cleanup agent produced)
to diagnose a mis-delivered agent name. Known failure mode: whisper's `base.en` model can mishear
an agent name as a common word that's phonetically *too far* for the cleanup agent to rescue
(e.g. "Mazda" → "Melissa"); the fix is `config.WHISPER_PROMPT` biasing whisper up front with the
real agent names (disable with `WHISPER_PROMPT=""`).

Plan/design doc: `audio_input/audio_plan.html` (viewable in-dashboard under Project Plans →
Audio Input); original spec `audio_input/audio_input.md`.

### Project Plans tab deployment notes

The live Windows 10 dashboard source is the WSL repo at `/home/adamsl/letta-code`. Do not look
for the live dashboard under `/var/www/html`; `/mnt/c/Users/NewUser/Desktop/agent_dashboard`
has existed as a Windows Desktop folder but is not the served dashboard app.

`server.py` serves static files from both:

- `HERE = /home/adamsl/letta-code/dashboard`
- `REPO_ROOT = /home/adamsl/letta-code`

So repo-root plan pages are valid dashboard URLs. Current important Project Plans pages:

| Tab | File | Served URL |
|---|---|---|
| Self Evolving | `/home/adamsl/letta-code/notes_plans_handoffs/agent_self_improvement/agent_self_improvement_plan.html` | `/notes_plans_handoffs/agent_self_improvement/agent_self_improvement_plan.html` |
| Mazda Dev Status | `/home/adamsl/letta-code/notes_plans_handoffs/mazda_dev_status.html` | `/notes_plans_handoffs/mazda_dev_status.html` |
| Audio Input | `/home/adamsl/letta-code/dashboard/audio_input/audio_plan.html` | `/audio_input/audio_plan.html` |

The old `Tool Fix` tab/document was replaced by `Mazda Orchestrator`; keep
`/home/adamsl/letta-code/agent_self_improvement/mazda_tool_fix_plan.html` deleted. The
**`Mazda Orchestrator` tab was removed 2026-06-15** — its doc (`team_construction_plan.html`)
described the discarded "Mazda gets direct finance tools" design and is now kept (with a
SUPERSEDED banner) as design history only, no longer in the Project Plans tab. The `Self Evolving`
plan doc is also partly superseded — **`Mazda Dev Status` is the canonical current-direction doc**
(Mazda is the orchestrator herself, with minions that drive the Claude Agent SDK; see
[[mazda_orchestration_pivot]] memory). If deployment details are unclear, Frita knows the
dashboard setup and can be messaged at Letta agent id `agent-881a883f-edd0-4963-bf67-6ef178b8f018`.

After editing Project Plans:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8765/team_construction_plan.html
curl -s http://localhost:8765/ | rg 'Mazda Orchestrator|team_construction_plan|Tool Fix|mazda_tool_fix'
.venv/bin/python -m pytest tests/
```

### ROL Finance Reports — recategorize + receipts (Project Plans → ROL Finance → Reports)

Each report is a static `report.html` embedded in an iframe (built outside this repo under
`~/rol_finances/readable_documents/bank_statements/**/report.html`, served by `server.py` via the
`/rol_finances_reports/` URL prefix → `ROL_FINANCES_REPORTS_BASE`). The injector
`~/rol_finances/tools/python_tasks/verification_lib/restructure_verified_transactions.py`
rewrites the "Verified Transactions" table: it drops/reorders columns, stamps each `<tr>` with
`data-vendor-key/description/signed-amount/date`, and appends a marker-delimited
(`<!-- rol-category-picker:start/end -->`) block holding the **Set Category dialog** (`#rol-category-picker`).
Re-running the injector is idempotent and *replaces* that block, so JS/CSS changes there propagate:
`python3 restructure_verified_transactions.py $(find ~/rol_finances -name report.html)`.

The dialog (same-origin in the iframe) calls these `server.py` endpoints — keep them in sync with
the injector's JS:

| Endpoint | Purpose |
|---|---|
| `POST /api/recategorize-expense` | Set a row's category; writes `expenses.category_id` (MySQL via rol_finances `app.db.get_connection`) **and** rewrites the `cat-*` class on the `<tr>` on disk so the color survives refresh. |
| `POST /api/receipt-lookup` | "View Receipt" button → returns `{ok, receipt_url}` (a `/rol_finances_receipts/` URL the dialog `window.open()`s) or `{ok:false, error}`. |
| `POST /api/receipts-present` | Batch: `{rows:[…]}` → `{present:[bool,…]}`. Drives the **red top-left corner marker** (`tr.has-receipt td:first-child::before`) on rows that have a receipt on file. |
| `GET /rol_finances_receipts/<rel>` | Serves a receipt file from `~/rol_finances/readable_documents/` (path-traversal checked; image/pdf content-types). |

**Receipt resolution** (`_resolve_receipt_path`, FS index cached 300s): receipt files are named
`<vendor>_MM_DD_YY_<dollars>_<cents>.<ext>` under `readable_documents/receipts/**`. Match order:
**(date, amount) parsed from the filename** → `receipt_url` exact path → stem-flex (any extension)
→ basename anywhere. The `(date, amount)` key is far more reliable than the DB `expenses.receipt_url`
string (which often differs by extension or vendor spelling). Rows ↔ expenses join on
`expense_date` + abs(amount), disambiguated by vendor_key prefix then exact description.

**Receipt files are synced** between this Win11 box and **mom's machine, rosemary46 (Tailscale
`100.72.34.38`)** — identical trees, so all receipts are present locally; no cross-machine fetch.
**Known data gap:** ~45 expenses have a `receipt_url` in the DB whose file isn't findable under any
name — those rows get no marker and View Receipt reports "Receipt recorded but file not found".

**Deploy:** all of the above (the endpoints in `server.py`, the dialog+marker in the injector) currently
live on the **live Win11 box only and are uncommitted** — this repo's checked-in `report.html` files
still use the older `alert('Vendor Key')` injector. After editing `server.py`:
`systemctl --user restart dashboard-server.service`. After editing the injector: re-run it on all
reports (command above). See the `rol_finance_view_receipt_fix` project memory.

**Injector gotchas:** the head `CATEGORY_PICKER_CSS` is injected once and guarded
(`if "ROL category picker" not in html`), so it does **not** refresh on re-run — put dialog CSS
*changes* in the marker-block `<style>` (which IS strip+reinjected; body overrides head by source
order). And `window.open(url, "_blank", "noopener,noreferrer")` returns **`null` by spec** when
`noopener` is set, so don't treat a null return as "popup blocked" (it caused a false red error
even though the receipt opened).

### Scanners — physical document scanners (Project Plans → ROL Finance → Scanners)

Two HP scanners attached to the live Win11 box: **Window** = HPI297BEA (HP OfficeJet 8120e),
**Freezer** = HP063E28 (HP DeskJet 4100, non-default, flaky). Driven by
`scanner_scripts/scan_device.ps1` (in this repo; **deployed to**
`~/planner/nonprofit_finance_db/receipt_scanning_tools/`) which selects the device **BY NAME**
(`-NameLike`), NOT "first device" — WIA enumeration order is unstable (the busy Freezer often
enumerates first). Wrappers `run_scan_window.sh` (→`scan.jpg`) / `run_scan_freezer.sh`
(→`scan_freezer.jpg`). `SCANNERS` registry + `_invoke_scanner()`/`classify_scan_result()` live in
`server.py`.

**Output is JPEG (not PNG).** A raw 300dpi WIA transfer to PNG is **~26MB** and loads painfully
slow in the browser. `scan_device.ps1` transfers to a temp BMP then re-encodes to **JPEG quality
85** (`-JpegQuality 85`) → **~1MB** (~24× smaller); `SCANNERS[*]['output']` = `scan.jpg`/
`scan_freezer.jpg`. If scanned images "take forever to load" again, verify the **live** box's
`scan_device.ps1`/`server.py` actually have the jpg version (`grep JpegQuality`) — this fix sat
undeployed for weeks while the live box kept emitting 26MB PNGs.

| Endpoint | Purpose |
|---|---|
| `POST /api/scanner-scan` `{scanner}` | One-shot manual scan → `{status, ok, image_url\|error}` |
| `GET /api/scanner-status?scanner=` | Lightweight probe (Freezer's poll) → same `{status}` |
| `GET /api/scanner-image?scanner=` | Serves the scanned JPEG (`image/jpeg`) |

`status` ∈ ready/busy/offline/error. Frontend (`dashboard-boot.js` `setupScanners`): Start Scan +
Show Image + dismissable image preview. **Auto-poll is gated by `MONITORED_SCANNERS` (a `Set` near
the top of `setupScanners`).** As of 2026-06-25 it is **empty** — neither scanner auto-polls; both
sit **idle until "Start Scan"** is pressed (the user did not want the Freezer scanning on its own).
The old behavior (Freezer in the set → immediate check then every 15s; `busy`/`offline` → red
blinking "Restart the Scanner Please" `.scan-busy`/`.scanner-blink`; `ready` → green + image, stop)
still triggers for any key listed in `MONITORED_SCANNERS`, and the `startMonitor()` calls in the
sub-nav are harmless no-ops when the set doesn't list that scanner. **Constant Freezer auto-polling
was itself a cause of the Window scanner reporting "busy"** — each probe is a real WIA call, and
pile-ups wedge the shared stisvc (see gotcha 2). Tests: `tests/test_server.py -k scan` +
`classify_scan_result`.

**Three gotchas that wasted hours (all in [[dashboard-scanner-wsl-interop]] memory):**
1. **WSL interop** — the systemd `--user` dashboard service has no `WSL_INTEROP`, so it can't
   launch Windows `powershell.exe` ("Invalid argument"). `_wsl_interop_socket()` borrows a working
   `/run/WSL/<pid>_interop` (the init `1/2_interop` does NOT relay). Needs ≥1 interactive WSL
   session alive.
2. **stisvc wedge** — a hung scan leaks the Windows `powershell.exe` (Python kills only the bash
   wrapper); pile-ups wedge the Windows Image Acquisition service so EVERY scan hangs at
   `New-Object WIA.DeviceManager`. `_reap_stale_scans()` (`reap_scans.ps1`) runs under `_SCAN_LOCK`
   before each scan + after timeout. Recover a fully-wedged stisvc (StopPending, won't stop):
   elevated `ssh NewUser@100.118.122.75` → `sc queryex stisvc` PID → `taskkill /f /pid <PID>`
   (auto-restarts). **Milder case (2026-06-25):** the device reported "busy" with stisvc still
   RUNNING and *no* leaked powershell — just contention from the Freezer's 15s auto-poll. A plain
   `ssh NewUser@100.118.122.75 'net stop stisvc & net start stisvc'` cleared the stuck device
   state and the Window scan succeeded. (Root cause was the auto-poll itself — now disabled.)
3. **"busy" power-cycle won't clear** = often an **open ink door/cover** (HP reports WIA busy) or
   driver/connectivity, not a held handle. Real scan ≈ 33s (OfficeJet 300dpi), not 10s.

Deploy: scp `scanner_scripts/*` → the scan-tools dir; scp dashboard files; `systemctl --user
restart dashboard-server.service`.

### Scan → Mazda intake pipeline (the message Mazda receives) — 2026-06-28

When a scan finishes, `process_scanned_document` runs the deterministic facade inline, then
dispatches Mazda fire-and-forget via `_notify_mazda_of_scan`. The instruction Mazda gets is
built by the **pure** function `build_mazda_scan_message(scan_image_path, scanner_name,
facade_result)` (and predicate `mazda_facade_identified()`) — pure so they're unit-tested in
`tests/test_server.py` (no network). Three things this encodes, each a fix for a live failure:

1. **The text-extraction facade (`mazda_intake.py`) returns `ok:true` but `doc_kind:unknown,
   confidence:0` for JPEG scans** (no extractable text). `mazda_facade_identified` therefore
   requires `doc_kind!=unknown AND confidence>0 AND action!=reject` — NOT just `ok`. On unknown
   it routes Mazda to classify the image herself with `classify_scan.py` (Gemini **vision**) +
   `parse_and_categorize.py --json`.
2. **Every rol_finances command uses `PYTHONPATH=/home/adamsl/rol_finances` +
   `/home/adamsl/rol_finances/.venv/bin/python3`** (constants `MAZDA_RF_PYPATH`/`MAZDA_RF_VENV_PY`).
   Bare `python3 tools/...` dies with `ModuleNotFoundError: No module named 'tools'`. These run via
   Mazda's `executor_run`, which is served by **this same dev box** (Letta sees it at
   `10.0.0.7:8789` — `10.0.0.7` is this machine's *Windows-host* LAN IP forwarded to WSL — so the
   hardcoded venv path resolves here).
3. **STEP 5 makes Mazda record the trace as `IntakeVerificationEvidence` JSON** under
   `task_name="document-intake"`, and **STEP 6 judges every run** (`judge_trace`). The verdict feeds
   the autonomous self-improvement loop. The judge that reads this is the **intake rubric** in
   `rol_finances/tools/self_improving_agent` (routed by task_name) — it is served by **Win10's**
   `mazda-tools-mcp.service` (`172.17.0.1:8791`), a *different machine* from the dashboard/executor,
   so deploying a rubric change means SSH to `100.80.49.10`. The message and that model share a
   field contract; `test_scan_message_instructs_structured_intake_evidence` pins it so the two
   repos can't drift. Full pipeline + topology: the `mazda-intake-tests-and-verdict-rubric-gap-2026-06-28`
   memory.

## Server health indicators, Restart-all & Model Stats (2026-06-22)

Three things were added to `server.py` + the frontend (see memories
`dashboard-server-restart-and-concern-2026-06-22`, `dashboard-model-stats-2026-06-22`,
`win10-node-offline-letta-recovery-2026-06-22`):

- **4-state server status** via `compute_server_status()` / `server_status_kind(cfg, health)` —
  `up`/`concern`(yellow)/`starting`/`down`. **Both** `/api/server-health` (sidebar tab) and
  `/api/server-logs`→`server_log_rows` (detail panel) call `server_status_kind` so they never
  disagree. Yellow `concern` = reachable-but-degraded (health `concern` flag, e.g. frita ghost),
  dependency-down, down-but-restartable, or recently-restarted. `/api/server-health` also emits
  per-server `restartable`, `down_for_seconds`, `stale`, `blocked_by`, `failure_class`,
  `container_status`. CSS: `.tab.server-concern` (amber), `.tab.server-stale` (blink).
- **Win10 node root-cause tile** — SERVERS key `win10-node` (`win10_node_health`, TCP :22 probe).
  `letta`/`logger-api`/`frita-executor`/`dashboard-proxy` carry `depends_on: 'win10-node'` and read
  `blocked_by: win10-node` when it's unhealthy (collapses many reds into one cause). Its **Restart**
  button revives the WSL node by restarting `tailscaled` via the **Windows host**
  (`restart_win10_node` → `ssh NewUser@100.69.80.89 'wsl.exe -d Ubuntu-24.04 -u root -- bash -lc
  "systemctl restart tailscaled"'`). NOTE: if the node *flaps* (up then dies in ~1min), the WSL VM
  itself is cycling → fix is a `wsl --compact`/reset on the Windows side, not repeated tailscaled
  restarts. `classify_failure()` gives accurate labels (404/auth/rate_limit/timeout) instead of the
  old "rate-limited"-for-everything.
- **Restart-any-server** — `RESTART_HANDLERS`/`restart_server(key)` covers ALL servers; every detail
  panel has an always-enabled **Restart** button (`/api/server-action` `action:restart`). Local =
  `systemctl --user restart <unit>` (lettabot/thought-bridge/mazda-tools-mcp); executor/mcp-proxy =
  `start_executor_server`; remote = SSH/redeploy; frita-executor first runs `ensure_win10_docker`
  (rm stale `/var/run/docker.pid` + start docker — the recurring `:8799`-down cause).
- **Model Stats tab** — `/api/model-stats?source=` (+ `-sources`), `MODEL_STAT_SOURCES`,
  `model_stats(key)`. Sub-nav: R46/W11 × Claude/Codex + Gemini (W11=this box local, R46=mom's via
  SSH). **LIVE usage APIs** (the local rollout/stats-cache files are stale/bogus — do NOT use them):
  Codex `GET https://chatgpt.com/backend-api/wham/usage` (token `~/.codex/auth.json`); Claude
  `GET https://api.anthropic.com/api/oauth/usage` (token `~/.claude/.credentials.json`
  `claudeAiOauth.accessToken`). Shows 5h + weekly used%, reset, model; **red at 100%** with reset.
  Extractors SELF-HEAL on 401/expiry (refresh: Claude `platform.claude.com/v1/oauth/token`
  client `9d1c250a-…`; Codex `auth.openai.com/oauth/token` client `app_EMoamEEZ…`). **Headless WAF
  gotcha**: raw refresh from a headless box can 429 — the real `claude`/`codex` CLI refresh passes
  the WAF, so `ssh <box> bash -lc 'claude -p "ok"'` is the reliable manual fix. Extractors run via
  `_run_extractor` (local `python3 -` / SSH `python3 -` with source on STDIN, NOT `-c`).

Tests: `tests/test_server.py` (64) for all of the above; `bun test js/tests` for the JS reducers/
controllers. After editing `server.py`: `systemctl --user restart dashboard-server.service` (then
re-Start the Executor — the restart kills it).

## Boot autostart (systemd `--user` services)

The dashboard and its two locally-hosted companion servers autostart on machine boot via
systemd `--user` units in `~/.config/systemd/user/` (this account has `Linger=yes`, so user
services start at boot without a login session):

| Unit | Runs | Port |
|---|---|---|
| `dashboard-server.service` | `python3 server.py` (stdout/stderr → `/tmp/dashboard_8765.log` via `StandardOutput=append:`/`StandardError=append:` + `Environment=PYTHONUNBUFFERED=1` — required so the `SERVERS` registry's `log_file` for the "Dashboard Server" tab has something to tail in real time; `print()`-based `log_message` would otherwise sit in Python's stdout buffer) | 8765 |
| `lettabot.service` | `~/lettabot/start_scissari_bot.sh` (Scissari Telegram bot; has its own internal restart-loop supervisor — systemd is outer defense) | API :8091 |
| `thought-bridge.service` | `~/a2a_communicating_agents/thought_bridge.py` via `~/ws-venv` | **8766** |
| `thought-bridge-monitor.service` | `~/a2a_communicating_agents/serve_monitor.py` | 8899 |
| `dashboard-browser.service` | `open-in-browser.sh` — polls `localhost:8765`, then `exec google-chrome --app=...` (needs `Type=simple`, not `oneshot`, since it execs into a long-running process; needs explicit `DISPLAY`/`WAYLAND_DISPLAY`/`XDG_RUNTIME_DIR` env — systemd `--user` doesn't inherit the WSLg graphical session at boot) | — |

**Port 8765 is reserved for this dashboard** — the Thought Bridge originally hardcoded the same
port and was moved to **8766** (in `thought_bridge.py`, `start_thought_bridge.sh`,
`monitor_thoughts_plan.html`, plus `THOUGHT_BRIDGE_URL=ws://localhost:8766` in
`~/lettabot/.env`). If you add another locally-run server to `SERVERS`, make sure its port
doesn't collide with 8765.

The genuinely-remote servers in `SERVERS` (Letta Server, Logger API — on other hosts/Docker)
can't be autostarted from here. Logger API is health-checked only; Letta Server is also
log-pulled over SSH (see the `_letta_remote_log_pull_loop` note above) since the box is
reachable via passwordless key-based SSH + sudo.

**Logger API "Start" button is self-healing**: `start_logger_api()` runs
`build_logger_api_start_command()`, which `docker rm`s any `logger-api*` container stuck in
`Created` state on the Win10 box *before* running `~/server_tools/start_logger_api.sh`
(`docker-compose up -d` + Apache rewrite reinject). This works around a docker-compose v1.29.2
bug (`KeyError: 'ContainerConfig'`) that otherwise makes `docker-compose up` fail forever once a
container gets stuck in `Created` — see `dashboard_logger_api_containerconfig_2026_06_10` memory
and `tests/test_server.py -k logger_api`.

**"Executor Server" is NOT remote** — despite an old `SERVERS` note claiming "remote Docker on
win10", it actually runs **locally on this same machine** (DESKTOP-2OBSQMC), started by the
`start_executor_server` alias in `~/.bashrc` → `~/server_tools/start_executor_server.sh`
(REST executor on `:8787` with `/health`, MCP front door on `:8789` via `mcp-proxy`, which the
script runs in the foreground forever — so it must be launched detached, never awaited).
`start_executor_server()` in `server.py` (fixed 2026-06-08, was previously SSHing to the
*wrong* remote host `100.69.80.89` and always failing with exit 1) now launches the script
directly via `subprocess.Popen(..., start_new_session=True)`, tails its combined output to
`/tmp/executor_startup.log`, and `health_url` correctly points at `http://127.0.0.1:8787/health`.
See [[project-dashboard-executor-server-local]] for the full debugging story.

Verify everything is up:
```bash
systemctl --user is-active dashboard-server lettabot thought-bridge thought-bridge-monitor dashboard-browser
curl -s http://localhost:8765/api/server-health | python3 -m json.tool
```
