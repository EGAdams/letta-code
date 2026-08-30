# Voice, notes, and the agent router

Detail for `voice/`, `router/`, and the voice-related JS. Summarized in `../CLAUDE.md`.

## Phone / microphone access (HTTPS required)

`getUserMedia()` (mic capture) only works in a secure context (https or localhost). Plain
`http://<tailscale-ip>:8765` silently blocks the mic on Android. Front the server with a real
cert via Tailscale Serve:

```bash
tailscale serve --bg 8765   # one-time; persists across reboots (needs --operator=$USER once)
```

Then open `https://desktop-2obsqmc.tailb8fc54.ts.net/` on the phone — use the **hostname**, not
the IP, or the cert won't validate. This is `desktop-2obsqmc` (the primary Linux node), **not**
`desktop-2obsqmc-24` (the WSL node — goes offline when its distro terminates; check
`tailscale status` if unsure which one is currently up).

## Voice pipeline (`voice/`)

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
to diagnose a mis-delivered agent name. Whisper's `small.en` model can still mishear an agent name
as a common word too far off for the cleanup agent to rescue; the fix is `config.WHISPER_PROMPT`
biasing whisper up front with the real agent names (disable with `WHISPER_PROMPT=""`).

Plan/design doc: `audio_input/audio_plan.html` (viewable in-dashboard under Project Plans → Audio
Input); original spec `audio_input/audio_input.md`.

## Toyota's box (home screen)

One box now, not two. It used to be a read-only note document (`ReadOnlyNoteSurface`) paired with a
second spoken "command channel" box (`#note-command-box`) that edited it via instructions like "put
a period at the end." That command channel is gone as of 2026-08-28 — the box is now an ordinary
editable message box (`EditableDarkNoteSurface`, same white-on-black look) fed by dictation or
typing, cleared on **Send** or **Save Note** exactly like any other agent's Input Options page.
`InputOptionsRenderer` still takes an injected `surfaceFactory` (the default elsewhere is the plain
`EditableTextareaSurface` every agent page has always had) — Toyota just injects the dark-styled
editable one instead of a read-only one now.

`POST /api/note-save` is the "Save Note" endpoint: no LLM interpretation, just writes the current
box text straight to `NOTES_DIR` (default `~/notes`) via `voice/note_repository.py`'s
`FilesystemNoteRepository`, and the button clears the box on success.

The old command-channel machinery (`voice/note_service.py`, `note_ports.py`, `note_interpreter.py`,
`note_completeness.py`, the `/api/note-command-*` routes, and the browser-side
`js/abstract/voice-command-channel.js` + `js/implementation/note-command-panel.js`) is still in the
tree and still tested, but nothing wires it up anymore — it's unused, not deleted, in case a future
feature wants a spoken-edit channel again. Its `NoteRepository` port is what `/api/note-save` reuses
directly.

Non-obvious bits:

- `TranscriptSyncedNote` (Decorator) still wraps the surface so `ReceptionistTranscriptController`
  dictation and `note.setText("")` (on Send/Save) stay in sync — no command channel needed for that.
- Send clears an *editable* surface only; that check is what made Toyota's box need to become
  editable rather than special-cased in the send handler.

## Agents-home voice/text router (`router/`)

`#agents-home` routes free speech/text to the right agent's Input Options page once a **known agent
name** is detected, forwarding only the text after the name, without stopping listening. Routable
names = top-level roster only (`router/config.py`'s `ROUTER_AGENT_NAMES`), not sub-agents. Two
buttons: **Start Recording** (push-to-talk whisper flow) and **Start Listening** (continuous browser
`SpeechRecognition`, `ListenerState` in `js/abstract/continuous-listener.interface.js` — a
module-scope singleton in `dashboard-boot.js` so it survives navigation).

Detection (`router/classify.py`) is two-tier: exact-name match first, then the
`dashboard-agent-router` Letta agent for implied references — **fails closed always** (any
ambiguity/error → "no agent detected", never a guess). `openWakeWord` was evaluated and deliberately
deferred (real ML training work); `ContinuousListener` stays provider-agnostic so a future
wake-word listener can be swapped in later.

## Input Options "Send" → `/api/letta-code-message`

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
