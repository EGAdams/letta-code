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
