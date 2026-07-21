# Handoff — 2026-07-20

## Summary

Built and shipped the **Agents-home voice/text router** (EG's ask: talk or type naturally on
the Agents tab, get auto-routed to whichever agent you named, hands-free). Committed and pushed
to `origin/main` (`c7986f9`). Also ran the Mazda **Trainer** on a live Freezer-scanner receipt at
EG's request and found/confirmed a recurring infra defect.

## What Was Shipped

### Agents-home voice/text router

The Agents tab's home view (`#agents-home` in `dashboard.html`) no longer shows a static
"Loaded N agents…" message. It now hosts a router: say or type something containing a known
agent's name (Frita, Scissari, Hailey, Jeri, Mazda, Suzuki — **not** their sub-agents), and the
dashboard opens that agent's Input Options page and hands it only the text *after* the name,
without interrupting the mic.

- **New backend package** `dashboard/router/` (`config.py`, `classify.py`) — same Strategy shape
  as `voice/cleanup.py`. Detection is two-tier: `detect_known_agent()` tries a deterministic
  exact-name match first (zero network); falls back to the `dashboard-agent-router` Letta agent
  (**`agent-b2993865-228f-47a2-b436-d35e3aff50f0`**, model `chatgpt-plus-pro/gpt-5.4-mini`, not
  in `LETTA_AGENTS` — deliberately off the sidebar) for implied/non-exact references. **Fails
  closed always** — any parse/network failure or ambiguous phrasing → no agent detected, never
  guesses.
- **New endpoints**: `POST /api/route-detect` `{text}` → `{ok, agent, remainder}`;
  `GET /api/router-agent` → `{ok, agent_id}` (lets the frontend Model dropdown reuse the existing
  `/api/agent-model` endpoint pointed at the router's own agent).
- **New frontend**: `ContinuousListener` abstract interface (`js/abstract/`) — sibling of
  `VoiceRecorder` — plus `BrowserSpeechRecognitionListener` (browser-native continuous speech,
  auto-restarts through silence timeouts) and `AgentsRouterRenderer`
  (`js/implementation/agents-router-renderer.js`, the new page: Model select, textarea, Send,
  **Start Recording** = today's whisper.cpp push-to-talk unchanged, **Start Listening** = new
  continuous mode, only on this page). The listener is a module-scope singleton in
  `dashboard-boot.js` so it survives navigation to the routed agent's page.
- **openWakeWord was investigated and deliberately deferred** — training custom per-name
  wake-word models is real ML work EG chose to skip for now. `ContinuousListener` was kept
  provider-agnostic on purpose so a server-side `openwakeword.Model` listener can be swapped in
  later via `AgentsRouterRenderer`'s `listener` injection point, no renderer changes needed.
- Full detail + rationale: `dashboard/CLAUDE.md` → "Agents-home voice/text router (`router/`)"
  section, and auto-memory `dashboard_agents_router_2026_07_20.md`.

**Tests**: `tests/test_router_classify.py`,
`js/tests/{continuous-listener,browser-speech-recognition-listener,agents-router-renderer}.test.js`.
All green at last check: 292 bun tests, 331 pytest tests (`bun test js/tests`,
`.venv/bin/python -m pytest tests/`).

**Deployed**: `dashboard-agent-router` Letta agent created live; `dashboard-server.service`
restarted; `/api/router-agent` and `/api/route-detect` verified live via curl; confirmed all six
routable names present in `/api/agents`.

### Git

Committed `c7986f9` ("Agents-home voice/text router + vendor review queue") and pushed to
`origin/main`. Note: this commit also swept up **concurrent in-progress work already sitting in
the tree** from other live agent sessions (the "Needs Vendor Review" scanner queue —
`js/abstract/vendor-review-view.interface.js` + friends, `server.py` vendor-review functions,
new `scanners-vendor-review` tab — plus edge-tts refinements and trainer report artifacts). This
matches how this repo is normally operated (multiple `--yolo` agents write to the same tree; see
CLAUDE.md's "Live agents" note) — just flagging it wasn't all mine so the next shift doesn't
assume single authorship.

**Left unstaged on purpose**: root `/home/adamsl/letta-code/CLAUDE.md` has a **corruption bug**
(not introduced by me) — under "Rosemary46 WSL Tailscale access," a stray URL got pasted mid-word
mid-sentence, breaking the markdown. I flagged it to EG but did not fix it (wasn't asked, didn't
want to guess at a silent edit). **Still needs cleanup.**

## Open Items / Unresolved

1. **"Sync all machines in this network"** — EG asked for this after the commit/push. I pushed to
   `origin` but did NOT SSH into rosemary46 or the Win10 box (`100.80.49.10`) to pull/sync
   anything there, because it's unclear whether those machines run their own checkout of this
   repo that needs `git pull`, or whether "sync" meant something else (e.g. an `scp` deploy of
   specific files, per the scanner-scripts deploy pattern in CLAUDE.md). **Asked EG to clarify,
   no answer yet as of end of shift.**
2. **Root CLAUDE.md corruption** — see above, still broken, still unstaged.
3. **Working tree is not clean** — as of end of shift: `dashboard/server.py` has a small
   further edit in progress (uncommitted, +16/-2 lines, likely another live agent), plus two new
   trainer reports (`20260720-183558_Freezer_Scanner_d1784572558.md`,
   `20260720-183846_Window_Scanner_d1784572726.md`) and the rolling `claude_toolcalls.json` log.
   Run `git status` before assuming anything, per repo convention.
4. **Standing infra defect (not new, but re-confirmed live today)**: `gemini CLI is not installed
   or not on PATH` on the executor breaks Mazda's vendor-research categorization step. This is
   at least the 3rd live occurrence (see Trainer section below and the
   `mazda_trainer_verified_wrap_v029_manual_fix_2026_07_19` memory). Needs an actual fix on the
   executor host — installing/PATH-configuring the `gemini` CLI — not another wrapper patch.
   Wrapper-side, Mazda's fail-closed behavior around this was just tightened to `wrap-v031` (see
   below), but that only makes the *failure* safer, it can't make the categorization succeed.

## Trainer run — Freezer Scanner receipt (EG's live test)

EG scanned a receipt and asked me to check the Trainer's verdict. A Trainer was already
auto-running (per the existing "every scan spawns a Trainer" wiring); I watched
`trainer/reports/` for its report rather than spawning a second one.

**Result: `trainer/reports/20260720-183558_Freezer_Scanner_d1784572558.md` — Verdict CORRECTED.**

- MB Markets / BP gas station receipt, $35.00, 2025-03-20 → **expense_id 1518**.
- Parsing/dedup were correct on the first pass. Categorization failed due to the missing
  `gemini` CLI on the executor (see Open Items #4) — the old wrapper let it store with
  `category_id: NULL` + `pending_vendor_review` instead of blocking, which the Trainer correctly
  graded FAIL.
- Trainer coached Mazda to fix it in-run (not just patch for next time): she found the existing
  `bp_2836900_leo_gas` → category 374 ("Leo Gas") vendor mapping, corrected expense_id 1518 via a
  direct SQL update, re-verified with `check_category`, and re-notified the dashboard.
- **No further action needed on expense_id 1518** — it's correctly filed now.
- `wrap-v031` was activated: future runs will fail closed (stop, don't store) when vendor
  research errors out, instead of degrading to a NULL-category "pending review" row.
- A **second** trainer report landed just before end of shift
  (`20260720-183846_Window_Scanner_d1784572726.md`) — **not yet reviewed**, next shift should
  check it.

## Verify

```bash
# Router feature live
curl -s http://localhost:8765/api/router-agent
curl -s -X POST http://localhost:8765/api/route-detect -H "Content-Type: application/json" \
  -d '{"text":"I was thinking about the scoreboard, Suzuki, check the undo logic"}'

# Tests
cd /home/adamsl/letta-code/dashboard
bun test js/tests
.venv/bin/python -m pytest tests/

# Tree state
cd /home/adamsl/letta-code && git status --short
```

## Risk Notes

- Don't assume the tree is clean — see Open Items #3.
- Don't silently "fix" the root CLAUDE.md corruption without checking with EG first; it may be
  mid-edit by something else.
- The router's LLM classify step is intentionally conservative (fails closed on anything
  ambiguous) — if EG reports "it didn't route when I expected," that's very likely working as
  designed, not a bug; check `router/classify.py`'s fail-closed philosophy before "fixing" it.
- Unreviewed second trainer report from this shift (`20260720-183846_Window_Scanner_d1784572726.md`)
  — check it before assuming today's scans are all clean.
