# Operations: Project Plans, server health, boot autostart

Detail for the ops surfaces of the dashboard. Summarized in `../CLAUDE.md`.

## Project Plans tab

The live dashboard source is the `letta-code` repo at `/home/adamsl/letta-code` **on the live box**
(see "Which machine is live" in `../CLAUDE.md` — that is not necessarily this machine). `server.py`
serves static files from both `HERE` (`/home/adamsl/letta-code/dashboard`) and `REPO_ROOT`
(`/home/adamsl/letta-code`), so repo-root plan pages are valid dashboard URLs:

| Tab | File | Served URL |
|---|---|---|
| Self Evolving | `notes_plans_handoffs/agent_self_improvement/agent_self_improvement_plan.html` | `/notes_plans_handoffs/agent_self_improvement/agent_self_improvement_plan.html` |
| Codebase Rewrite | `notes_plans_handoffs/codebase_rewrite.html` | `/notes_plans_handoffs/codebase_rewrite.html` |
| Mazda Dev Status | `notes_plans_handoffs/mazda_dev_status.html` | `/notes_plans_handoffs/mazda_dev_status.html` |
| Audio Input | `dashboard/audio_input/audio_plan.html` | `/audio_input/audio_plan.html` |
| Voice Communication | `dashboard/voice_communication_plan.html` + `js/plans/` modules | `/voice_communication_plan.html` |

**`Mazda Dev Status` is the canonical current-direction doc** (Mazda is the orchestrator herself,
with minions that drive the Claude Agent SDK). `team_construction_plan.html` (repo root) describes a
discarded earlier design and is kept only as history, no longer linked from the Project Plans tab.
If deployment details are unclear, Frita knows the dashboard setup and can be messaged at Letta
agent id `agent-881a883f-edd0-4963-bf67-6ef178b8f018`.

After editing Project Plans, sanity-check with:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8765/notes_plans_handoffs/mazda_dev_status.html
.venv/bin/python -m pytest tests/
```

### Voice Communication is an interface *workspace*, not a document

It is the one Project Plans tab that is a data-driven SPA, and it is the **living development
guide** — open it before changing anything in `voice/` or the voice JS.
`voice_communication_plan.html` is a ~19-line content-only shell; the tabs live in the dashboard's
own `#nav-voice-communication` sub-nav (built from the same specs that render each page, so tabs
cannot drift from content), and all content lives in modules:

| Module | Role |
|---|---|
| `js/plans/interface-spec.js` | The `InterfaceSpec` contract + runtime validator + `Status` vocabulary |
| `js/plans/mermaid-view.js` | Mermaid render + mermaid.live-style pan/zoom, used by every diagram |
| `js/plans/interface-page.js` | Renders one spec into its 7 fixed sections |
| `js/plans/interface-workspace.js` | Nav + hash routing shell |
| `js/plans/voice-communication/*.js` | This project's specs + composition root |
| `css/plan-workspace.css` | Shared styling |

**Adding an interface = adding one spec object**, never markup. The four `js/plans/*.js` modules are
project-agnostic and a test asserts they never mention Letta/Toyota/whisper/VoiceSession, so a
second project workspace can reuse them. `validateSpecs()` throws on a malformed spec rather than
rendering a blank tab.

Mermaid gotchas that cost real time here (see also the `mermaid-pan-zoom-dashboard-plans` skill):

- **`Note` is a reserved word in `sequenceDiagram`** — a participant named `Note` fails to parse.
- One failed diagram injects a **global** error element into `document.body` that survives tab
  switches, so a single broken diagram makes every later tab look broken too. Validate sources with
  `mermaid.parse()` rather than eyeballing.
- **Never top-level-`await` visibility in the boot module** — the tab's iframe is hidden, so the
  `load` event never fires. `MermaidView.render()` awaits layout internally instead.
- `svg-pan-zoom` measures at construction, before layout settles; the deferred
  `requestAnimationFrame` re-`fit()`/`center()` in `_attachPanZoom` is why diagrams are centred
  rather than shoved right.

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

## Boot autostart (systemd `--user` services)

`~/.config/systemd/user/` (account has `Linger=yes`, so these start at boot without a login):

| Unit | Runs | Port |
|---|---|---|
| `dashboard-server.service` | `python3 server.py` (needs `PYTHONUNBUFFERED=1` for live log tailing) | 8765 |
| `lettabot.service` | Scissari Telegram bot (has its own restart loop; systemd is outer defense) | 8091 |
| `thought-bridge.service` | `~/a2a_communicating_agents/thought_bridge.py` | **8766** (moved off 8765) |
| `thought-bridge-monitor.service` | `~/a2a_communicating_agents/serve_monitor.py` | 8899 |
| `dashboard-browser.service` | polls `localhost:8765` then execs `google-chrome --app=...` (`Type=simple`, explicit `DISPLAY`/`WAYLAND_DISPLAY`/`XDG_RUNTIME_DIR`) | — |

Port 8765 is reserved for this dashboard — don't collide a new local server with it. Remote servers
(Letta Server, Logger API) are health-checked/log-pulled over SSH instead of autostarted. "Executor
Server" runs locally via `~/server_tools/start_executor_server.sh` (REST `:8787`, MCP front door
`:8789`), launched detached (`start_new_session=True`) with output tailed to
`/tmp/executor_startup.log`.

```bash
systemctl --user is-active dashboard-server lettabot thought-bridge thought-bridge-monitor dashboard-browser
curl -s http://localhost:8765/api/server-health | python3 -m json.tool
```

## Which machine is live — extra history

- **`DESKTOP-SHDBATI`** (Letta server box) has no `dashboard-server.service` — its `:8765` is
  `dashboard-proxy.service` forwarding to the live box, so a local `curl` succeeding there proves
  nothing about your edits being deployed.
- `NewUser` is the *Windows* account and only applied to the old `ssh → wsl.exe -d …` route. That
  route died on 2026-08-05 when `Ubuntu-24.04` was unregistered and Ubuntu-26.04 got its own
  `openssh-server` + `tailscale`. Using the stale `NewUser@` form fails with `Permission denied
  (publickey,password)`, which looks like a broken key but is just a bad user.
- **`Address already in use` on :8765 during restart** — historically the `Ubuntu-24.04` stub also
  ran its own `dashboard-server.service` and won the port race. That distro is gone as of
  2026-08-05, so if this recurs, find the real owner with `ss -tlnp` and check it matches the unit's
  `MainPID` rather than assuming the old cause.
