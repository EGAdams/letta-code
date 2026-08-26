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
./start.sh                          # frees port 8765, starts server.py (TUNNEL=1 for cloudflared)
python3 server.py                   # PORT= to override; LETTA_BASE_URL to point elsewhere
.venv/bin/python -m pytest tests/   # Python tests (venv is for pytest only; server is stdlib)
bun test js/tests                   # JS GoF interface/implementation layer
```

Serves `http://localhost:8765/`, binds `0.0.0.0`. `ReusableHTTPServer` is threaded so slow requests
(whisper ~5s) don't block pollers. Also runs as a systemd `--user` service
(`dashboard-server.service`) that autostarts on boot. `tests/conftest.py` puts the dashboard dir on
`sys.path` and has an autouse fixture that disables the Trainer and redirects `recent_report.json`
to a tmp path.

After editing `server.py`: `systemctl --user restart dashboard-server.service`, then re-Start the
Executor (the restart kills it).

### Known test failures

**None.** `.venv/bin/python -m pytest tests/` is green everywhere — anything
red is yours, on any box.

The counts differ by machine and that is expected: **2591 pass / 2 skip** on
the live box (DESKTOP-2OBSQMC), **2587 pass / 6 skip** on a dev box. The four
extra skips are the `requires_tesseract` tests in
`tests/test_document_annotation.py`, which drive the real OCR binary instead of
monkeypatching `image_to_data`. The live box has `tesseract` installed and runs
them; `which tesseract` tells you which case you are in. If you touch image
annotation, run that file on the live box — locally those four prove nothing.

This is a different suite from the root `CLAUDE.md`'s "~17 pre-existing
failures", which is `bun test src/tests` in letta-code. The two counts are
unrelated; don't reconcile them.

## Deploying — read this before you edit anything

**Editing files here doesn't necessarily change what users see.** The checkout you're editing is
often **not** the one serving the dashboard, and EG has no way to test a change that isn't live —
so every `dashboard/` change gets deployed, not just committed.

- **Live host:** `DESKTOP-2OBSQMC`, distro **`Ubuntu-26.04`** (codename `resolute`). SSH straight
  into WSL — no `wsl.exe` hop, user is `adamsl`:
  ```bash
  ssh adamsl@100.102.209.100 'cd ~/letta-code && git status'
  ssh adamsl@100.102.209.100 'grep VERSION_CODENAME /etc/os-release'   # must print: resolute
  ```
  Canonical machine list lives in the `sync-all` skill — trust it over this file. (An earlier
  `windows11-ssh-connect` skill is cited in older notes; it was never created.)
- **The live checkout carries real uncommitted WIP** from concurrent agents. Run `git status` there
  and diff the overlap before any pull/merge — never blind-`scp` whole files or `git pull` over it.
  For surgical edits, base64-pipe a script rather than inline quoting (nested shells mangle `$(...)`):
  ```bash
  B64=$(base64 -w0 script.sh); ssh adamsl@100.102.209.100 "echo $B64 | base64 -d > /tmp/s.sh && bash /tmp/s.sh"
  ```
- Preferred path once committed/pushed: `POST /api/server-action {"action":"deploy"}` (git-pulls +
  self-restarts, no SSH needed).

More history and failure modes: `docs/operations.md` § *Which machine is live*.

## Debugging strategy: rebuild the design, don't patch the symptom

Full doctrine: `~/tactical_debug_toolbox/gof_debug_tacticts.md`. Load it before any nontrivial fix.

- **Debug by rebuilding, not by patching.** A bug signals that some nearby design is tangled (mixed
  responsibilities, hidden coupling, a growing `if/elif` ladder, duplicated construction, a fat
  interface). Fix the defect *and* the weakness that let it happen.
- **Process:** reproduce → locate → immediate cause → inspect the surrounding design for those five
  smells → decide if a GoF pattern untangles it (Strategy, State, Command, Factory, Template Method,
  Chain of Responsibility) → build the interface if missing → fix through the improved structure →
  verify → delete now-obsolete patches/dead code.
- **Guardrails:** don't add a pattern that solves no real structural problem here, and don't
  redesign unrelated parts. This project already leans hard on program-to-interface/GoF (see
  `js/README.md` and Python's `IExpenseDocumentAnnotationService`-style ports) — extend that pattern
  rather than inventing a parallel one.

**File-size rule:** any file over 250 lines gets split into smaller modules, along real seams (data
shape / agreement / implementation), never at an arbitrary line count. Python: Pydantic models vs
ABC ports vs implementations. JS/TS: declared shapes and `interface`s in their own module,
implementations behind them — mirroring `js/`'s `abstract/`/`implementation/` split. TS types vanish
at runtime, so validate untrusted input (HTTP bodies, files, cross-process messages) with a runtime
schema. Don't convert working JS to TS as part of a fix — that's separate work.

## Architecture

### `server.py` + `http_app/` — the backend (stdlib `http.server`, no framework)

`server.py` is the **service layer**: every function and registry the dashboard exposes.
`http_app/` is the **HTTP layer** — `DashboardHandler` used to be a 1,380-line class inside
`server.py` and now lives here, split along its own seams:

| File | Seam |
|---|---|
| `http_app/models.py` | Pydantic shapes for everything crossing the process boundary (`ServerConfig`, `TerminalSessionRequest`, `TerminalResizeFrame`, `StaticAsset`, `ErrorResponse`, `BackgroundTask`) |
| `http_app/transport.py` | `HttpTransportMixin` — how bytes leave the socket. All responses funnel through `_write` |
| `http_app/get_routes.py` | `GetRoutesMixin.do_GET` — the read-side route ladder |
| `http_app/post_routes.py` | `PostRoutesMixin.do_POST` — the write-side route ladder |
| `http_app/terminal_ws.py` | `TerminalWebSocketMixin` — the RFC 6455 upgrade + pty bridge |
| `http_app/handler.py` | `DashboardHandler`, composed from those mixins |
| `http_app/runtime.py` | `ReusableHTTPServer` + `serve()`; boots the declared `BackgroundTask` threads |
| `http_app/static_files.py` | `resolve_static_asset` — fail-closed containment for the static fallthrough |
| `http_app/services.py` | `srv` — a PEP 562 module-`__getattr__` handle on `server` |

**Why `srv` and not `from server import ...`:** `server.py` imports `http_app` from its own tail,
so a module-scope `import server` in a route mixin is a cycle. `services.py` resolves each name at
*call* time, which also keeps `monkeypatch.setattr(server, ...)` and runtime rebinds visible to the
routes. Route bodies read `srv.build_agent_list()`, `srv.SCANNERS`, etc. Adding a route means adding
the service to `server.py` and calling it as `srv.<name>` — no import list to maintain.

The two ladders are still ~600 lines each; splitting them needs a route registry (Command /
Chain of Responsibility), not another file cut.

**Tests (`tests/test_http_app_*.py`, ~460 of them).** Written as the safety net for that registry
refactor, so they assert only what a browser observes — status, headers, body — never how dispatch
happens internally:

| File | Covers |
|---|---|
| `test_http_app_route_inventory.py` | every one of the 95 routes dispatches; unknown paths still 404; GET/POST do not leak into each other |
| `test_http_app_routes.py` | behavioural contracts (bare-array `/api/agents`, the `agent-claude` branches, malformed bodies, the model allowlist, threading) |
| `test_http_app_terminal_ws.py` | the RFC 6455 handshake and pty bridge, driven over a real socket against a real shell |
| `test_http_app_static_files.py` | path-traversal regressions (`GET /../../../../etc/passwd` used to return 200) |
| `test_http_app_transport.py`, `_models.py`, `_services.py` | the transport funnel, the Pydantic shapes, and the `srv` late-binding contract |

`tests/http_app_harness.py` holds the shared harness: a live `ReusableHTTPServer` on an ephemeral
port plus `ServiceRecorder`, which stubs every *function* on `server` (never the data registries) so
routes that restart systemd units or drive scanners stay inert. That stubbing only works because
`srv` is late-bound — if it ever becomes a snapshot, ~25 tests fail immediately.

Two registries in `server.py` drive most of the app:

- **`LETTA_AGENTS`** — `{'name','id'}`; `id: None` auto-discovers by name (cached 5 min via
  `AGENT_LIST_CACHE_TTL`, bypass with `?refresh=1`). Keep in sync with
  `voice.config.KNOWN_AGENT_NAMES`. `/api/agents` must return a bare array.
- **`SERVERS`** (Server Management) — each entry is monitored via `log_file`, `health_url`,
  `tcp_check`, or a custom `check` fn in `HEALTH_CHECKS` (when "HTTP 200" isn't enough).
  `frita-executor` uses a `check` because of a two-stack situation on the Win10 box (SDK executor
  bridged on `:8799`; warns `⚠ GHOST on :8797` if a stale no-SDK executor shadows it). "Letta
  Server" has a `log_file` despite running remotely — `_letta_remote_log_pull_loop` SSHes every 30s
  and content-sniffs `*-json.log` for Letta's signature (don't assume the named container is live).
  `browser-server` (ChatGPT Browser Server) is a Flask server on `:5001` driving a real
  Chrome window already logged into chatgpt.com via `undetected_chromedriver` — it backs the
  `relay_message_to_chatgpt` tool, so red means Chrome is down or logged out rather than a
  bad key. Start it from the Server Management tab; setup and API in
  `BROWSER_SERVER_INTEGRATION.md`, implementation in `browser_tools/browser_server.py`.

Everything else proxies the live Letta API (`LETTA_BASE_URL`, default `http://100.80.49.10:8283`).
Claude Code has no Letta agent — its messages/tool calls are local JSON
(`claude_messages.json`/`claude_toolcalls.json`) written via `/api/claude-log` /
`/api/claude-toollog`.

### Frontend — GoF layering

`dashboard.html` is markup only; its one script is `js/dashboard-boot.js`. Per `js/README.md`: CSS
in `css/dashboard.css`; `js/abstract/` = interfaces/Template-Method skeletons (no DOM/fetch,
injected collaborators, unit-testable in Node); `js/implementation/` = concrete subclasses wiring
those interfaces to real browser APIs — **this is the live code**; `js/boot/` = one module per
dashboard section (agent manager, model stats, server/SSH managers, scanners, nav bindings…), each
a `create*(deps)` factory. `dashboard-boot.js` is now only the ~150-line composition root: ports,
then sections, then nav bindings, in that order. No build step — edit + reload. Verify in a real
browser and run `bun test js/tests` after any change. When adding a section, add a module under
`js/boot/` and construct it in `dashboard-boot.js` — do not grow the boot file itself.

**Pre-commit gotcha:** biome errors abort the commit — `forEach(x => { x.remove(); })`, not `forEach(x => x.remove())`.

### Subsystem docs

Each of these is a real subsystem with its own invariants — read the doc before changing it.

| Doc | Covers |
|---|---|
| `docs/voice.md` | voice pipeline (`voice/`), Toyota's note + command channel, agents-home router (`router/`), Input Options "Send", phone/mic HTTPS setup |
| `docs/finance-intake.md` | ROL Finance reports, Recent Report, scanners + health LEDs, scan → Mazda intake, Trainer escalation, statement review, LLM fallback chains |
| `docs/operations.md` | Project Plans tab + Voice Communication workspace, server health/restart/Model Stats, boot autostart services |

Two cross-cutting rules worth stating here: **everything on the voice/note path fails closed** (a
malformed reply or dead connection means "keep waiting" / "unchanged", never a guess), and the
Voice Communication plan tab is a **living development guide** — open it before touching `voice/`.
