# Handoff — Voice note/command channel + Voice Communication workspace (2026-08-13)

Written on **DESKTOP-SHDBATI**, updated after merging with the live box's parallel work.

**Where the truth lives:** this file is a snapshot. The living guide is
**Project Plans → Voice Communication** on the dashboard — 13 tabs, each with the same eight
sections (Responsibility → Contract → Implementations → Dependencies → Development status → Tests →
Gotchas → Next work). Read the tab before changing the thing it documents; update the tab in the
same commit that changes it. That guide, not this file, is what keeps us from drifting again.

## 1. Read this first: the symlink gap is CLOSED

An earlier revision of this handoff told you to hand-copy the plan HTML because
`dashboard/voice_communication_plan.html` was a **symlink** into `~/talking_agent_parts/` (a repo
with no remote), so it never travelled with a push. **That is fixed.** Both
`voice_communication_plan.html` and `voice_communication_plan_v1.html` are now ordinary versioned
files under `dashboard/`. A plain `git pull` gets you the whole guide — no manual step, and
`~/talking_agent_parts/` is no longer on the serving path at all.

`test_project_plans.py` enforces the new arrangement (`VOICE_COMMUNICATION_PLAN.is_file()`), so it
cannot silently regress to a symlink.

## 2. What shipped

### Feature A — Toyota's note + voice command channel (home screen)

Top box is now a **read-only note document** (white on black); the second box is a **command
channel** where you speak instructions about that note.

The defining behaviour: **command completeness is judged from the accumulated text, never a silence
timer.** "Put a" waits indefinitely; "Put a period at the end" executes. Verified live.

| Layer | Files |
|---|---|
| Pydantic models | `dashboard/voice/note_models.py` |
| ABC ports | `dashboard/voice/note_ports.py` |
| Strategies | `voice/note_completeness.py`, `note_interpreter.py`, `note_repository.py` |
| Application policy | `voice/note_service.py` |
| Composition root | `voice/note_factory.py` |
| Browser contracts | `js/abstract/{note-document.interface,note-command-contracts,transcript-buffer,voice-command-channel}.js` |
| Browser wiring | `js/implementation/{textarea-note-surfaces,transcript-synced-note,http-note-command-services,note-command-panel}.js` |
| Endpoints | `POST /api/note-command-complete`, `POST /api/note-command-apply` |

Two non-obvious bits:

- **`TranscriptSyncedNote` (Decorator)** exists because the note has *two writers* — the dictation
  buffer and the command channel. Without the resync, "put a period at the end" appears to work and
  is then silently undone by the next dictated sentence.
- **`InputOptionsRenderer` takes an injected `surfaceFactory`.** Default is the editable message box
  every agent page has always had. Send clears an *editable* surface only — clearing a read-only
  note would delete the user's document.

### Feature B — Project Plans → Voice Communication is now an interface workspace

13 tabs, data-driven. **Adding an interface = one new file under
`js/plans/voice-communication/specs/` + one import line in `index.js`.** Never markup.

The four modules in `js/plans/` (`interface-spec`, `mermaid-view`, `interface-page`,
`interface-workspace`) are project-agnostic; a test asserts they never mention
Letta/Toyota/whisper/VoiceSession, so a second project workspace can reuse them.

**The finding that shaped it:** `~/talking_agent_parts/` contains *only* the plan document.
`VoiceSession`, `ConversationCoordinator`, `IConversationAgent`, `LettaAgentAdapter`,
`PipelineFactory`, `SpokenOutputPolicy` — **zero lines written**. Meanwhile a different, working
voice system grew inside `dashboard/` with narrower, differently-named seams. The workspace
documents both and marks the plan's objects honestly as Planned.

Mermaid gotchas that cost real time (also recorded in `dashboard/CLAUDE.md`):

- **`Note` is a reserved word in `sequenceDiagram`** — a participant named `Note` fails to parse.
- One failed diagram injects a **global** error element into `document.body` that survives tab
  switches, so a single broken diagram makes every later tab look broken. Validate with
  `mermaid.parse()`, don't eyeball.
- **Never top-level-`await` visibility in the boot module** — the tab's iframe is hidden, so `load`
  never fires. `MermaidView.render()` awaits layout internally instead.
- `svg-pan-zoom` measures at construction, before layout settles; the deferred
  `requestAnimationFrame` re-`fit()`/`center()` is why diagrams are centred.

## 3. Live-system changes already made (not in git)

`transcript-cleanup-agent` (`agent-250dc5e1-e8df-4497-89dc-2daed1725edb`) was repointed:

```
lc-gemini/gemini-2.5-flash-lite  →  chatgpt-plus-pro/gpt-5.6-luna
```

`lc-gemini` now returns **401 UNAUTHENTICATED**, which was silently killing voice cleanup, the
receptionist intent policy, and the note-command channel — all three default to that agent and were
failing closed. Mechanism: `PATCH /v1/agents/{id}` with body `{"model": "<handle>"}`.

Why Luna: OpenAI cut it ~80% on 2026-07-30 to **$0.20/M in, $1.20/M out**, vs `gpt-5.4-mini` at
**$0.75/$4.50** — the "mini" model is no longer the cheap one. A 10-prompt benchmark scored
10/10 for `5.4-mini`, `luna`, and `luna + reasoning_effort=high` at 4.5s / 4.1s / 3.9s avg, i.e.
indistinguishable. Luna chosen on cost + headroom, not measured superiority.

**`reasoning_effort` is a trap:** top-level PATCH is silently ignored, partial `llm_config` PATCH
returns 422, only a full `llm_config` replace works — and it **resets to null on any
`PATCH {"model": ...}`**, which is exactly what the dashboard model dropdown sends. Left unset.

Note these agents are on the **Codex OAuth subscription**
(`model_endpoint: https://chatgpt.com/backend-api/codex/responses`), not the metered API, so list
prices are a capability proxy, not a bill.

## 4. Test state

```bash
cd dashboard
bun test js/tests                              # 469 pass, 2 skip, 0 fail
.venv/bin/python -m pytest tests/              # 832 pass, 13 fail (ALL pre-existing)
```

The 13 failures are all in `tests/test_server.py` and are scanner/intake related — they predate
this work. Confirm with `git stash && pytest tests/test_server.py && git stash pop` if in doubt.

Browser-verified with Playwright: all 13 tabs, 21 diagrams, every one a real SVG with pan/zoom
attached, zero syntax errors, wheel zoom 1.000 → 1.263, reset works, page scroll outside diagrams
unaffected.

## 5. Branch note

`feat/category-taxonomy` was **0 ahead / 44 behind** `reconcile/category-taxonomy-x-intake-duplicate-rows`
and was fast-forwarded to it before any work started. The receptionist streaming code EG asked to
preserve did not exist on the old tip (`transcript-merge.js` was missing, its tests were 0/3).

## 6. Next work

1. **Latency, not model choice, is the bottleneck.** Every finalized speech fragment costs a 3–6s
   round-trip to the completeness detector. Add a cheap local pre-filter that skips the LLM for
   obviously-incomplete fragments.
2. **Microphone arbitration.** Three `BrowserSpeechRecognitionListener`s now exist (router,
   receptionist, note-command) and nothing arbitrates. The home screen renders two on one page;
   two active native recognizers are unreliable in Chrome. Untested.
3. **`VoiceSession`** — the smallest object owning one conversation's identity, state, and current
   generation. Everything else on the workspace's roadmap is blocked behind it.
4. **`IConversationAgent`** — extract from the direct `/api/letta-code-message` calls in
   `detail-renderers.js`, with the existing Letta path as its first adapter. Write the
   characterization test first.
5. `lc-gemini` is still dead for anything else on it (the rol_finances categorizer's tier 1 will be
   falling through to its Codex fallback).
6. **Deploy.** SSH to the live box works — `ssh adamsl@100.102.209.100` (user is `adamsl`, NOT
   `NewUser`, and there is no `wsl.exe` hop; the earlier `Permission denied (publickey,password)`
   was purely the wrong username). The live checkout still carried ~390 lines of uncommitted WIP
   at merge time, so `git status` there and diff the overlap before pulling.
7. **Commit WIP promptly.** This merge existed only because two agents built a note-taking UI in
   `detail-renderers.js` within 30 minutes of each other with neither side committing. See
   Design Protocol → Gotchas.
