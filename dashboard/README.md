# Agent Dashboard

A single-page dashboard for monitoring/operating Letta agents, served by a small
stdlib HTTP server that proxies the Letta API. Includes **browser voice input**
(push-to-talk → whisper.cpp → cleanup agent → send to the chosen agent).

## Run it

```bash
cd /home/adamsl/letta-code/dashboard
./start.sh                 # frees port 8765, starts server.py in the background
# or: python3 server.py    # foreground; PORT=9000 to change port
```

- Serves on **http://localhost:8765/** (`dashboard.html`). Binds `0.0.0.0`.
- Server log (stdout/stderr): `/tmp/dashboard_8765.log` — written by the `dashboard-server`
  systemd `--user` unit (`StandardOutput=append:`/`StandardError=append:` +
  `PYTHONUNBUFFERED=1`, see `CLAUDE.md` "Boot autostart"), tailed by the dashboard's own
  "Server Management → Dashboard Server" tab. The old manual nohup pattern
  (`python3 server.py > /tmp/dashboard_8765.log 2>&1 &`) wrote the same path; if you ever run
  the server that way instead, add `python3 -u` or `PYTHONUNBUFFERED=1` or the lines will sit
  in Python's stdout buffer instead of appearing in the file.
- `ReusableHTTPServer` is a **ThreadingHTTPServer** — slow requests (whisper ~5s)
  don't block the dashboard's pollers.

### Phone / microphone access (HTTPS required)

`getUserMedia()` (mic) only works in a **secure context** (https or localhost).
Plain `http://<LAN-or-tailscale-IP>:8765` will **silently block the mic** on
Android. We front the server with a real Let's Encrypt cert via **Tailscale Serve**:

```bash
tailscale serve --bg 8765   # one-time; persists across reboots
# requires: sudo tailscale set --operator=$USER  (granted once, so no sudo after)
```

Open on the phone (must be on the tailnet, MagicDNS on):
**https://desktop-2obsqmc-24.tailb8fc54.ts.net/** — use the hostname, not the IP,
or the cert won't validate. Turn off with `tailscale serve --https=443 off`.

## Service locations

| Thing | Value |
|---|---|
| Dashboard server | `server.py`, port **8765** |
| Letta API | `LETTA_BASE_URL`, default `http://100.80.49.10:8283` (Tailscale) |
| Tailscale HTTPS (phone) | `https://desktop-2obsqmc-24.tailb8fc54.ts.net/` |
| This host on tailnet | `desktop-2obsqmc-24` / `100.72.158.63` |
| Android test device | `samsung-sm-s156v` / `100.111.161.7` |

## Endpoints (POST)

- `/api/test` — send a text message to an agent (`{agent, text}`); clears the
  agent's history first, returns assistant replies. Used by the **Send** button.
- `/api/voice` — **raw audio body** (not multipart), header `X-Filename`. Runs the
  voice pipeline and returns `{ok, raw_transcript, cleaned_text}`. Delivery to the
  agent is the client's job (it fills the box, then auto-/manually-sends via `/api/test`).
- `/api/claude-log`, `/api/claude-toollog` — Claude Code message/tool logs.

## Voice pipeline (`voice/`)

`browser MediaRecorder → /api/voice → whisper.cpp → transcript-cleanup-agent → fill box → /api/test`

GoF: **Strategy** (transcription, cleanup), **Adapter** (`LettaClient`),
**Factory** (`build_*`), **Pipeline** (`VoicePipeline`), front-end **State** machine.

| File | Role |
|---|---|
| `voice/config.py` | Paths + ids from env, with lettabot's whisper defaults baked in |
| `voice/transcription.py` | `WhisperCppTranscriber` (ffmpeg → 16k wav → `whisper-cli`) |
| `voice/cleanup.py` | `LettaAgentCleanup` (Friday→Frita); clears history each call; raw fallback |
| `voice/letta_client.py` | Thin Letta HTTP adapter |
| `voice/pipeline.py` | `VoicePipeline.process` + `handle_voice_upload` (the `/api/voice` logic) |

Reused from **lettabot** (don't reinvent): `whisper-cli` at
`~/whisper.cpp/build/bin/whisper-cli`, model `~/whisper.cpp/models/ggml-base.en.bin`,
ffmpeg from lettabot's bundled `imageio_ffmpeg` binary. All overridable via env
(`WHISPER_CPP_BIN`, `WHISPER_MODEL_PATH`, `FFMPEG_BIN`, `WHISPER_LANGUAGE`,
`WHISPER_THREADS`, `WHISPER_PROMPT`).

**Cleanup agent:** `transcript-cleanup-agent`, model `gemini-2.5-flash-lite`,
id `agent-250dc5e1-e8df-4497-89dc-2daed1725edb` (resolved by name in `build_cleanup`).
Known agent names live in `config.KNOWN_AGENT_NAMES` — keep in sync with
`LETTA_AGENTS` in `server.py`.

Mazda's stage agents are also dashboard agents:

- Mazda Router
- Mazda Parser
- Mazda Vendor Identity
- Mazda Receipt Linker
- Mazda Categorization

After adding or renaming dashboard agents, restart the user service:

```bash
systemctl --user restart dashboard-server
curl -s http://localhost:8765/api/agents?refresh=1
```

Agent list loading is cached in two places: `/api/agents` caches server-side for
5 minutes, and the browser reuses the loaded list when you leave Agent
Management and come back. A forced refresh is available with
`/api/agents?refresh=1`.

## Tests

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # first time
.venv/bin/python -m pytest tests/                                        # 21 tests
```

A venv is used because system Python is PEP-668 externally-managed. The **server
needs only the stdlib** — the venv is just for pytest.

## Debugging mishears

Every successful `/api/voice` appends `{date, raw, cleaned}` to
**`voice_transcripts.json`** (gitignored). To diagnose a wrong agent name, compare
`raw` (what whisper heard) vs `cleaned` (what the cleanup agent produced).

## Known problem & fix

**"Mazda" was delivered as "Melissa" (2026-06-07).** whisper's English `base.en`
model mis-heard the agent name "Mazda" as the common name "Melissa"; the cleanup
agent left it because Melissa↔Mazda is too phonetically far to look like a typo
(cleanup only rescues *near* mishears like Mazduh→Mazda, Friday→Frita).

**Fix:** bias whisper itself with an initial prompt of the agent names
(`config.WHISPER_PROMPT` → `whisper-cli --prompt "Agent names: …"`), so the right
name is transcribed up front. Disable with `WHISPER_PROMPT=""`. If a far mishear
ever recurs, next levers are a deterministic fuzzy name-match pass or a larger
whisper model (`small.en`).

## Plan / design doc

`audio_input/audio_plan.html` — full design doc, viewable in the dashboard under
**Project Plans → Audio Input**. Original spec: `audio_input/audio_input.md`.

Other Project Plans notes:

- The live dashboard is served from WSL at `/home/adamsl/letta-code` on the Windows 10 host.
- The phone-facing Tailscale HTTPS URL `https://desktop-2obsqmc-24.tailb8fc54.ts.net/` is served by
  the separate `DESKTOP-2OBSQMC` WSL box at `100.72.158.63`, which has its own
  `/home/adamsl/letta-code/dashboard` checkout. If that live URL looks stale, deploy the changed
  dashboard files to that machine too.
- Startup overlay behavior: during boot, the console should show the server and SSH connection names
  plus their live status checks, and the console area is intentionally taller so that output stays
  visible.
- Agent Management now uses the same startup-style loading overlay and log pacing when the Agents tab
  is opened.
- `server.py` serves static files from both `dashboard/` and the repo root.
- **Project Plans → Mazda Dev Status** (`/notes_plans_handoffs/mazda_dev_status.html`) is the
  canonical current-direction doc. The former **Mazda Orchestrator** tab was removed 2026-06-15;
  its doc `/team_construction_plan.html` is kept (with a SUPERSEDED banner) as design history only.
- **Project Plans → Verification Tracker** (`/notes_plans_handoffs/verification_tracker.html`) mirrors the January statement verification tracker markdown as a dashboard-readable HTML page.
- **Project Plans → Pipecat Voice** (`/notes_plans_handoffs/pipecat_letta_voice_plan.html`) records the proposed future integration that uses Pipecat for real-time voice/media while Letta remains the agent runtime and memory source of truth.
- The old Tool Fix plan was removed; `/agent_self_improvement/mazda_tool_fix_plan.html`
  should return 404.
- Frita can advise on dashboard deployment details at Letta agent id
  `agent-881a883f-edd0-4963-bf67-6ef178b8f018`.
