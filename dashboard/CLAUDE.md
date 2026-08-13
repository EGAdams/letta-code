# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

A single-page dashboard (`dashboard.html` served by `server.py`) for monitoring/operating Letta
agents (roster in `LETTA_AGENTS` in `server.py`) plus Claude Code — browser **voice input**
(push-to-talk → whisper.cpp → cleanup agent → send) and a **Server Management** tab that
health-checks/restarts surrounding infrastructure. Lives inside `letta-code` but is self-contained:
stdlib-only Python backend, vanilla JS/CSS frontend, no build step, no node_modules.

## Commands

```bash
./start.sh                 # frees port 8765, starts server.py (TUNNEL=1 for cloudflared)
python3 server.py          # PORT= to override; LETTA_BASE_URL to point elsewhere
```
Serves `http://localhost:8765/`, binds `0.0.0.0`. **Editing files here doesn't necessarily change
what users see** — read "Which machine is live" before deploying/restarting. `ReusableHTTPServer`
is threaded so slow requests (whisper ~5s) don't block pollers. Also runs as a systemd `--user`
service (`dashboard-server.service`) that autostarts on boot.

```bash
# Tests
.venv/bin/python -m pytest tests/            # Python (venv is for pytest only; server is stdlib)
bun test js/tests                             # JS GoF interface/implementation layer
```
`tests/conftest.py` puts the dashboard dir on `sys.path` and has an autouse fixture that disables
the Trainer and redirects `recent_report.json` to a tmp path.

### Phone / microphone access (HTTPS required)
`getUserMedia()` (mic capture) only works in a secure context (https or localhost). Plain
`http://<tailscale-ip>:8765` silently blocks the mic on Android. Front the server with a real
cert via Tailscale Serve:
```bash
tailscale serve --bg 8765   # one-time; persists across reboots (needs --operator=$USER once)
```
Then open `https://desktop-2obsqmc.tailb8fc54.ts.net/` on the phone — use the **hostname**,
not the IP, or the cert won't validate. Note: this is `desktop-2obsqmc` (the primary Linux
node), **not** `desktop-2obsqmc-24` (the WSL node — goes offline when its distro terminates;
check `tailscale status` if unsure which one is currently up).

## Debugging strategy: rebuild the design, don't patch the symptom

Full doctrine: `~/tactical_debug_toolbox/gof_debug_tacticts.md`. Load it before any nontrivial
fix. Core points, condensed:

- **Debug by rebuilding, not by patching.** A bug is a signal that some nearby design is tangled
  (mixed responsibilities, hidden coupling, a growing `if/elif` ladder, duplicated construction, a
  fat interface). Fix the defect *and* the weakness that let it happen — don't stack another patch
  on old patches.
- **Process:** reproduce → locate → find immediate cause → inspect surrounding design for the five
  smells above → decide if a GoF pattern untangles it (Strategy for interchangeable behavior, State
  for mode-dependent behavior, Command for actions, Factory/Abstract Factory for construction,
  Template Method for shared-process-with-varying-steps, Chain of Responsibility for multiple
  handlers) → build the interface if it doesn't exist → fix through the improved structure →
  verify old bug is gone and nothing else broke → delete now-obsolete patches/dead code.
- **Guardrails:** don't add a pattern that doesn't solve a real structural problem here, and don't
  redesign unrelated parts of the system. Every new interface must earn its keep (replaceability,
  testability, clarity) — this project already leans hard on program-to-interface/GoF (see
  `js/README.md`'s abstract/implementation split and Python's `IExpenseDocumentAnnotationService`-
  style ports); extend that pattern rather than inventing a parallel one.

**File-size rule:** any file over 250 lines gets split into smaller modules — prefer more small
modules over one long file. In Python, split along Pydantic models (data/validation) vs Interfaces
(ABC ports) vs implementations, mirroring the JS `abstract/`/`implementation/` split already used
in `js/`.

## Architecture

### `server.py` — the whole backend (stdlib `http.server`, no framework)

One `DashboardHandler(SimpleHTTPRequestHandler)`. Two registries drive most of the app:

- **`LETTA_AGENTS`** — `{'name','id'}`; `id: None` auto-discovers by name (cached 5 min via
  `AGENT_LIST_CACHE_TTL`, bypass with `?refresh=1`). Keep in sync with
  `voice.config.KNOWN_AGENT_NAMES`. `/api/agents` must return a bare array.
- **`SERVERS`** (Server Management) — each entry is monitored via `log_file`, `health_url`,
  `tcp_check`, or a custom `check` fn in `HEALTH_CHECKS` (when "HTTP 200" isn't enough).
  - `frita-executor` uses a `check` because of a two-stack situation on the Win10 box (SDK
    executor bridged on `:8799`; warns `⚠ GHOST on :8797` if a stale no-SDK executor shadows it).
  - "Letta Server" has a `log_file` despite running remotely — `_letta_remote_log_pull_loop` SSHes
    every 30s and content-sniffs `*-json.log` for Letta's signature (don't assume the named
    container is the live one).

Everything else proxies the live Letta API (`LETTA_BASE_URL`, default `http://100.80.49.10:8283`).
Claude Code has no Letta agent — its messages/tool calls are local JSON
(`claude_messages.json`/`claude_toolcalls.json`) written via `/api/claude-log` /
`/api/claude-toollog`.

### Frontend — GoF layering

`dashboard.html` is markup only; its one script is `js/dashboard-boot.js`. Per `js/README.md`: CSS
in `css/dashboard.css`; `js/abstract/` = interfaces/Template-Method skeletons (no DOM/fetch,
injected collaborators, unit-testable in Node); `js/implementation/` = concrete subclasses wiring
those interfaces to real browser APIs — **this is the live code**. `dashboard-boot.js` constructs
those classes and holds page-specific nav glue. No build step — edit + reload. Verify in a real
browser and run `bun test js/tests` after any change. **Pre-commit gotcha:** biome errors abort the
commit — `forEach(x => { x.remove(); })`, not `forEach(x => x.remove())`.

### Voice pipeline (`voice/`)

`MediaRecorder → POST /api/voice → whisper.cpp → cleanup agent → fills message box → /api/test`.
GoF: Strategy (transcription/cleanup swap), Adapter (`LettaClient`), Factory (`build_*`), Pipeline
(`VoicePipeline`), State (recorder idle→recording→processing).

| File | Role |
|---|---|
| `voice/config.py` | paths/ids from env; bakes in lettabot's whisper defaults; `KNOWN_AGENT_NAMES` |
| `voice/transcription.py` | `WhisperCppTranscriber` (ffmpeg → 16k wav → `whisper-cli`) |
| `voice/cleanup.py` | `LettaAgentCleanup` — clears the cleanup agent's history each call; raw-text fallback |
| `voice/letta_client.py` | thin Letta HTTP adapter |
| `voice/pipeline.py` | `VoicePipeline.process` + `handle_voice_upload` (the `/api/voice` handler logic) |

It reuses lettabot's binaries rather than reinventing them — `whisper-cli` at
`~/whisper.cpp/build/bin/whisper-cli`, model `~/whisper.cpp/models/ggml-small.en.bin` (upgraded
2026-08-08 from `base.en` for better accuracy on agent names; adds a bit of latency per
transcription, acceptable given transcription already runs ~5s). ffmpeg from lettabot's bundled
`imageio_ffmpeg`. All overridable via env (`WHISPER_CPP_BIN`, `WHISPER_MODEL_PATH`, `FFMPEG_BIN`,
`WHISPER_LANGUAGE`, `WHISPER_THREADS`, `WHISPER_PROMPT`).

Every successful `/api/voice` call appends `{date, raw, cleaned}` to `voice_transcripts.json`
(gitignored) — compare `raw` (what whisper heard) vs `cleaned` (what the cleanup agent produced)
to diagnose a mis-delivered agent name. Whisper's `small.en` model still can mishear an agent name
as a common word too far off for the cleanup agent to rescue; the fix is
`config.WHISPER_PROMPT` biasing whisper up front with the real agent names (disable with
`WHISPER_PROMPT=""`).

Plan/design doc: `audio_input/audio_plan.html` (viewable in-dashboard under Project Plans →
Audio Input); original spec `audio_input/audio_input.md`.

### Agents-home voice/text router (`router/`)

`#agents-home` routes free speech/text to the right agent's Input Options page once a **known
agent name** is detected, forwarding only the text after the name, without stopping listening.
Routable names = top-level roster only (`router/config.py`'s `ROUTER_AGENT_NAMES`), not
sub-agents. Two buttons: **Start Recording** (push-to-talk whisper flow) and **Start Listening**
(continuous browser `SpeechRecognition`, `ListenerState` in `js/abstract/continuous-listener.
interface.js` — a module-scope singleton in `dashboard-boot.js` so it survives navigation).
Detection (`router/classify.py`) is two-tier: exact-name match first, then the
`dashboard-agent-router` Letta agent for implied references — **fails closed always** (any
ambiguity/error → "no agent detected", never a guess). `openWakeWord` was evaluated and
deliberately deferred (real ML training work); `ContinuousListener` stays provider-agnostic so a
future wake-word listener can be swapped in later.

### Input Options "Send" → `/api/letta-code-message`

Shells out to this checkout's `letta` CLI headlessly (`--output-format json --memfs-startup skip
--permission-mode acceptEdits`). Two invariants (both from a 2026-07-22 failure where Mazda's
correct answer looked like "no answer"):

1. Server budget is 900s but `FetchHttpClient`'s default abort is 30s — callers of long-running
   endpoints must pass `{timeout: 930000}` explicitly rather than raising the global default.
2. Headless mode auto-denies gated tools with nobody to approve them, so `--permission-mode
   acceptEdits` is required (not `--yolo`/`bypassPermissions` — `acceptEdits` already auto-allows
   Write/Edit/MultiEdit/Bash without handing blanket access to a `0.0.0.0`-bound endpoint).

**Debugging tip:** "agent gave no answer" has twice been a dashboard rendering bug, not an agent
failure — check `GET /api/messages?agent=<id>` before concluding the agent misbehaved.

### Project Plans tab

The live dashboard source is the `letta-code` repo at `/home/adamsl/letta-code` **on the live box**
(see "Which machine is live" below — that is not necessarily this machine). `server.py` serves static
files from both `HERE` (`/home/adamsl/letta-code/dashboard`) and `REPO_ROOT`
(`/home/adamsl/letta-code`), so repo-root plan pages are valid dashboard URLs:

| Tab | File | Served URL |
|---|---|---|
| Self Evolving | `notes_plans_handoffs/agent_self_improvement/agent_self_improvement_plan.html` | `/notes_plans_handoffs/agent_self_improvement/agent_self_improvement_plan.html` |
| Codebase Rewrite | `notes_plans_handoffs/codebase_rewrite.html` | `/notes_plans_handoffs/codebase_rewrite.html` |
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

Each report is a static `report.html` built by `~/rol_finances`, with a category-picker block
injected/re-injected idempotently by `restructure_verified_transactions.py`. Endpoints:
`recategorize-expense`, `receipt-lookup`, `receipts-present`, `rol_finances_receipts/<rel>`.
Receipt matching prefers (date, amount) parsed from filename over the DB's `receipt_url` string.
**Injector gotcha:** head CSS is injected once and not refreshed on re-run; put dialog CSS changes
in the marker-block `<style>` instead. `window.open(..., "noopener")` returns `null` by spec — not
proof of a popup blocker.

Supporting-document opens (`document_annotation.py`) are non-destructive — annotate a cached copy,
never the original. `IExpenseDocumentAnnotationService` is the port; PDF/OCR-image/Excel are
strategies wired in `build_document_annotation_service()`. A match needs date+amount,
description+amount, or a check number, else no box is drawn. On EG's handwritten scans, OCR often
misreads the amount column, so `_line_score` accepts date+payee as a lower-priority tiebreaker that
can't outrank a real amount match; `_same_row` compares vertical overlap so a row never ties (and
cancels) against itself.

### Recent Report (Reports tab default view)

`GET /recent_report.html` shows whichever document was most recently dispatched to Mazda
(`resolve_recent_report()`), in **report mode** (real `report.html` exists) or **intake mode**
(scanned doc stored straight to MySQL, page rendered live from DB by
`build_recent_intake_html()`). Bookkeeping in `dashboard/recent_report.json` (gitignored), folded
by `merge_recent_intake_event()` / `_fold_event_into_intake`. Mazda's STEP 8 callback must fire even
when `stored:0` (a correct re-scan of an already-processed statement) so the page shows real state
instead of stale/empty data. `duplicate_expense_ids` applies to receipts/invoices too, not just
statements — a duplicate-only event with no ids falls back to resolving them from the DB by
`(expense_date, amount)`, bailing if >3 rows share that pair.

Dispatch is server-side and deduped: `run_scanner()` spawns intake processing itself the instant a
scan reports ready; `_claim_scan_dispatch()` prevents double-dispatch from the frontend's own POST.

### Scanners — physical document scanners (Project Plans → ROL Finance → Scanners)

Two HP scanners attached to the live box: **Window** = HPI297BEA (HP OfficeJet 8120e),
**Freezer** = HP063E28 (HP DeskJet 4100). Since 2026-07-24 they are driven directly from WSL
through native `sane-airscan`/eSCL — **not Windows WIA**:

- Window: `airscan:e0:Window Scanner` → `https://10.0.0.26/eSCL`
- Freezer: `airscan:e1:Freezer Scanner` → `http://10.0.0.243/eSCL`

WSL multicast discovery is unreliable, so the addresses are static in
`scanner_scripts/airscan.conf` (installed at `/etc/sane.d/airscan.conf`). The shared
`scanner_scripts/scan_airscan.sh` performs a 300-dpi flatbed JPEG scan with an 85-second timeout
and preserves the existing `SCANNER_BUSY` / `SCANNER_OFFLINE` / `Saved:` output contract.
`run_scan_window.sh` writes `window_scan.jpg`; `run_scan_freezer.sh` writes `scan_freezer.jpg`.
All three scripts are deployed to `~/planner/nonprofit_finance_db/receipt_scanning_tools/`.
`SCANNERS` + `_invoke_scanner()`/`classify_scan_result()` live in `server.py`.

| Endpoint | Purpose |
|---|---|
| `POST /api/scanner-scan` `{scanner}` | One-shot manual scan → `{status, ok, image_url\|error}` |
| `GET /api/scanner-status?scanner=` | Legacy endpoint that performs a real scan; do NOT use as a health probe |
| `GET /api/scanner-image?scanner=` | Serves the scanned JPEG |
| `GET /api/scanner-diagnostics?scanner=` | Read-only health LEDs (see below) → `{overall, checks:[{id,label,state,detail}]}` |

**Scanner Health LEDs** — `scanner_diagnostics()` first calls `_airscan_ready()`, a read-only
capability query (`scanimage -d <device> --help`; never transfers a scan). A ready direct backend
renders the actual live chain: **Scanner Backend → Scanner Service → Driver Health → Scanner
Online → Scanner Access → No Stuck Scans**. Stale Windows WIA/WSD state must not turn these LEDs
red. The Freezer also keeps its direct LEDM hardware check at
`http://10.0.0.243/DevMgmt/ProductStatusDyn.xml`: door/jam/offline are red; paper/ink are
printing-only yellow warnings and never block scanning.

`scanner_diag.ps1`, WIA, stisvc, and WSL interop remain a legacy fallback only when AirScan is
unavailable. Front end: `ScannerDiagnosticsController`
(`js/implementation/scanner-diagnostics-controller.js`); server-side
`build_scanner_diagnostics()` owns the mapping.

`status` ∈ ready/busy/offline/error. Auto-poll is gated by `MONITORED_SCANNERS` (a `Set` in
`setupScanners` in `dashboard-boot.js`) — currently empty, so neither scanner auto-polls; both sit
idle until "Start Scan" is pressed (constant auto-polling was itself found to cause the Window
scanner reporting "busy" from shared WIA-service contention).

**Root cause/history:** on 2026-07-24 both scanners' own eSCL interfaces reported `Idle` while
Windows retained their WSD Image records as `Present:false, Problem:45`. Even elevated
`fdPHost`/`upnphost`/`stisvc` restarts plus `pnputil /scan-devices` did not reconnect them. This
explained the recurring busy/offline/power-cycle class of failures. Earlier HP Scan Doctor,
open-cover, leaked-process, and missing-interop incidents were real but are no longer on the live
scan path. Full current runbook: memory `dashboard_scanner_airscan_wia_bypass_2026_07_24`;
`dashboard_scanner_wsl_interop` is legacy history.

Install/deploy/verify:

```bash
sudo apt-get install -y sane-airscan sane-utils
sudo install -m 0644 scanner_scripts/airscan.conf /etc/sane.d/airscan.conf
install -m 0755 scanner_scripts/{scan_airscan,run_scan_window,run_scan_freezer}.sh \
  ~/planner/nonprofit_finance_db/receipt_scanning_tools/
scanimage -L
systemctl --user restart dashboard-server.service
# Restart Executor after every dashboard restart:
curl -sS -H 'Content-Type: application/json' \
  -d '{"server":"executor","action":"start"}' http://localhost:8765/api/server-action
curl -sS 'http://localhost:8765/api/scanner-diagnostics?scanner=window'
curl -sS 'http://localhost:8765/api/scanner-diagnostics?scanner=freezer'
.venv/bin/python -m pytest tests/ -q
```

Both scanners completed direct 300-dpi test scans on 2026-07-24 (Window ≈22s, Freezer ≈19s).
Browser blinking-red state can be stale after repair; hard-refresh with `Ctrl+Shift+R`.

### Scan → Mazda intake pipeline

`process_scanned_document` runs a deterministic text-extraction facade inline, then dispatches
Mazda fire-and-forget (`_notify_mazda_of_scan`, message built by pure `build_mazda_scan_message()`).

1. The facade returns `ok:true, doc_kind:unknown, confidence:0` for JPEG scans (no extractable
   text) — `mazda_facade_identified()` requires `doc_kind!=unknown AND confidence>0 AND
   action!=reject`, not just `ok`. On unknown, Mazda classifies the image herself via vision.
2. Every `rol_finances` command Mazda runs needs `PYTHONPATH=/home/adamsl/rol_finances` +
   its venv python — bare `python3 tools/...` dies with `ModuleNotFoundError`.
3. STEP 5 records `IntakeVerificationEvidence` under `task_name="document-intake"`; STEP 6 has the
   self-improvement judge score the trace (served by `mazda-tools-mcp.service` — restart after a
   rubric/tool change).

### Scan → Trainer (Mazda's watcher)

Every intake dispatch also spawns a Trainer — a Claude agent (via `~/claude-code-sdk-ts`) that
watches Mazda's transcript, verifies the STEP 1–8 contract against actual tool returns (not her
prose), coaches her via a corrective Letta message on failure, and always writes a report
(`trainer/reports/<ts>_<scanner>.md`). Fire-and-forget detached Popen — a broken Trainer never
blocks intake. `MAZDA_TRAINER_ENABLED=0` kill switch. Non-obvious: the Trainer session dies if it
ends its turn to "wait" (must Bash `sleep`-loop + report before finishing); the SDK's
`.withTimeout()` is a no-op in `@instantlyeasy/claude-code-sdk-ts@0.3.3` — only `.withSignal()`
reaches the child process, so `trainer/claude-attempt.ts` supplies its own AbortSignal + hard
deadline. A 0-byte trainer log means "still running" (bun block-buffers stdout to a file), not
"never started" — check `systemctl --user list-units 'mazda-trainer-*'`.

**Wrapper defect vs. application defect (2026-08-01).** Before coaching, the Trainer now
classifies the failure: a *wrapper defect* (Mazda's instructions/tools/memory — coach her,
unchanged) or an *application defect* (a real bug in this repo's or `rol_finances`' code —
she cannot fix it by retrying). Application defects get a structured `## Escalation` block
in the report (`repo_path`, `bug_description`, `metadata`) instead of a buried sentence. The
Trainer still never executes anything under `rol_finances` and never invokes Suzuki itself —
a human (or a future report-grepping dispatcher) turns that block into Suzuki's
`BugHuntRequest`. Full contract, routing rule, and exact Suzuki invocation:
`notes_plans_handoffs/mazda_suzuki_escalation_contract.md`.

### Statement review dialog (Scanner screen)

A statement `store_statement_transactions.py` refuses is quarantined to `_needs_review/` with a
JSON sidecar; `statement_review.py` + `StatementReviewDialog` poll `/api/statement-reviews` every
15s and let EG resolve it via `/api/statement-review-resolve`. Two item kinds, both fail-closed:
**workbook** (unresolved last-4 digits — add a row to the known-accounts spreadsheet; a still-
failing resolve deliberately leaves the sidecar so the dialog reappears) and **amounts** (unreadable
rows — one prefilled input per row; a blank entry is an error, never a silent skip). The sidecar is
a self-contained retry packet, so resolving replays the store without re-scanning.

### Categorizer LLM fallback chain + provider health

`rol_finances/tools/categorizer/categorizer_main.py` (STEP 3) tries `gemini` → `chatgpt-oauth`
(EG's Codex OAuth, then mom's, synced by `codex-moms-token-sync.timer`) → `anthropic`. Every call
logs through `IProviderHealthRecorder` to `~/.mazda/provider_health.json`. Dashboard tile: Server
Management → "LLM Provider Fallbacks (Categorizer)" (yellow = fallback fired in 24h, red = every
tier's last attempt failed). **Not yet covered** by this pattern: `parsing_router/` and
`e_two_e_processing/row_sources/{_pdf_utils,llm_pdf_parser}.py` — port the same pattern there if a
failure traces to either.

### Statement Codex CLI vision fallback

`parse_statement_scan.py` / `apply_statement_annotations.py` try Gemini → OpenAI Codex CLI → legacy
ChatGPT-OAuth → standalone OpenAI. The Codex leg (`codex_cli_vision.py`) renders PDF pages to PNG
via `pdftoppm` before attaching — never send a raw PDF to the ChatGPT `input_image` backend, it's
rejected. Uses the existing Codex OAuth subscription, never `OPENAI_API_KEY`.

## Server health, restart, Model Stats

- 4-state status (`compute_server_status()`): `up`/`concern`/`starting`/`down`, shared by both
  `/api/server-health` and `/api/server-logs` so they never disagree.
- `win10-node` (TCP :22 probe) is the root-cause tile for dependents (`depends_on:'win10-node'`) —
  collapses many reds into one cause. If it *flaps* (up then dies within a minute), the WSL VM
  itself is cycling — fix with `wsl --compact`/reset on Windows, not repeated tailscaled restarts.
- Every server has an always-enabled Restart button (`POST /api/server-action`,
  `RESTART_HANDLERS`/`restart_server(key)`).
- **Mass yellow across many unrelated tiles at once** (same `down_for_seconds`/`failure_class:
  "refused"`) = the live box's `user@1000.service` cgroup wedge, not several independent bugs:
  ```bash
  echo 1 | sudo tee /sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/cgroup.kill
  sudo systemctl reset-failed user@1000.service && sudo systemctl start user@1000.service
  ```
  Can re-wedge within ~60s of the fix — re-check after ~90s before declaring it fixed.
- Model Stats (`/api/model-stats`) uses the **live** usage APIs, not local rollout/stats-cache files
  (which are stale). Antigravity has no quota API for free accounts, so its window is derived from
  the tier cap vs local log count; an expired token needs manual `agy` re-auth (no self-heal).

After editing `server.py`: `systemctl --user restart dashboard-server.service`, then re-Start the
Executor (the restart kills it).

## Which machine is live (read before deploying or restarting)

The checkout you're editing is often **not** the one serving the dashboard.

- **Live host:** `DESKTOP-2OBSQMC`, distro **`Ubuntu-26.04`** specifically. That box runs two WSL
  distros sharing one network namespace; the older `Ubuntu-24.04` is a stub that still owns
  `tailscaled`/`sshd`, so a bare SSH can land in the *wrong* distro even though `hostname` matches.
  Always name the distro explicitly: `ssh NewUser@<ip> 'wsl.exe -d Ubuntu-26.04 -e bash -lc "<cmd>"'`.
- **`DESKTOP-SHDBATI`** (Letta server box) has no `dashboard-server.service` — its `:8765` is
  `dashboard-proxy.service` forwarding to the live box, so a local `curl` succeeding there proves
  nothing about your edits being deployed.
- **Verification must go through a base64-piped script, not inline quoting** — the nested
  `ssh → wsl.exe → bash -lc` hop mangles inline `$(...)` substitutions and can report a genuinely
  `enabled`/`active` unit as `not-found`. Write the script locally, then:
  ```bash
  B64=$(base64 -w0 script.sh)
  ssh NewUser@<ip> "wsl.exe -d Ubuntu-26.04 -e bash -lc \"echo $B64 | base64 -d > /tmp/s.sh && bash /tmp/s.sh\""
  ```
  Same pattern for edits — the live checkout is diverged from this repo; verify each anchor string
  is unique, back it up, then string-replace. Never blind-`scp` whole files or `git pull` over it.
- **`Address already in use` on :8765 during restart** = the `Ubuntu-24.04` stub also runs (and
  wins the port race for) its own `dashboard-server.service`. Fix: stop+disable that unit in
  `Ubuntu-24.04` (never shut the distro down — it owns tailscaled/sshd), then restart the real one
  in `Ubuntu-26.04`. Verify the real unit's `MainPID` matches `ss -tlnp`'s owner of :8765.

## Boot autostart (systemd `--user` services)

`~/.config/systemd/user/` (account has `Linger=yes`, so these start at boot without a login):

| Unit | Runs | Port |
|---|---|---|
| `dashboard-server.service` | `python3 server.py` (needs `PYTHONUNBUFFERED=1` for live log tailing) | 8765 |
| `lettabot.service` | Scissari Telegram bot (has its own restart loop; systemd is outer defense) | 8091 |
| `thought-bridge.service` | `~/a2a_communicating_agents/thought_bridge.py` | **8766** (moved off 8765) |
| `thought-bridge-monitor.service` | `~/a2a_communicating_agents/serve_monitor.py` | 8899 |
| `dashboard-browser.service` | polls `localhost:8765` then execs `google-chrome --app=...` (`Type=simple`, explicit `DISPLAY`/`WAYLAND_DISPLAY`/`XDG_RUNTIME_DIR`) | — |

Port 8765 is reserved for this dashboard — don't collide a new local server with it. Remote
servers (Letta Server, Logger API) are health-checked/log-pulled over SSH instead of autostarted.
"Executor Server" runs locally via `~/server_tools/start_executor_server.sh` (REST `:8787`, MCP
front door `:8789`), launched detached (`start_new_session=True`) with output tailed to
`/tmp/executor_startup.log`.

```bash
systemctl --user is-active dashboard-server lettabot thought-bridge thought-bridge-monitor dashboard-browser
curl -s http://localhost:8765/api/server-health | python3 -m json.tool
```
