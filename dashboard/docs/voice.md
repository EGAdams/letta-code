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

## Toyota's note + voice command channel (home screen)

Two boxes, two conversations. The **top** box is Toyota's note document — a `ReadOnlyNoteSurface`
(white on black, `readOnly` not `disabled` so notes stay selectable), fed by the existing
`ReceptionistTranscriptController` streaming path. The **bottom** box (`#note-command-box`) is
where you speak instructions *about* that note ("put a period at the end", "save this as meeting
notes").

The chain, each link replaceable:

```
ContinuousListener → TranscriptBuffer → CompletenessDetector → CommandInterpreter → NoteDocument
```

- **Completeness is judged from the accumulated text, never from a silence timer** — that is the
  whole point. "Put a" comes back incomplete and the channel waits however long you pause; "Put a
  period at the end" comes back complete and runs. `POST /api/note-command-complete`.
- **Applying** a command is a separate call (`POST /api/note-command-apply`) that runs once per
  finished instruction and returns a discriminated outcome: `edit` (whole revised note), `save`
  (Toyota names the file if you didn't), or `none`.
- **Everything fails closed.** A malformed reply, a 401, a dead connection → "keep waiting" / "note
  unchanged". An `edit` carrying empty text is treated as malformed, never as "blank the note"
  (checked in both `note_interpreter.py` and `note-command-contracts.js`).

| Layer | Files |
|---|---|
| Data shapes (Pydantic) | `voice/note_models.py` |
| Ports (ABCs) | `voice/note_ports.py` |
| Strategies | `voice/note_completeness.py`, `voice/note_interpreter.py`, `voice/note_repository.py` |
| Application policy | `voice/note_service.py` |
| Composition root | `voice/note_factory.py` |
| Browser contracts | `js/abstract/note-document.interface.js`, `note-command-contracts.js`, `transcript-buffer.js` |
| Browser policy | `js/abstract/voice-command-channel.js` (no DOM in it) |
| Browser wiring | `js/implementation/{textarea-note-surfaces,transcript-synced-note,http-note-command-services,note-command-panel}.js` |

Non-obvious bits:

- `TranscriptSyncedNote` (Decorator) exists because the note has **two writers** — the dictation
  buffer and the command channel. Without the resync, "put a period at the end" appears to work and
  is then silently undone by the next dictated sentence.
- `InputOptionsRenderer` takes an injected `surfaceFactory`; the default is the editable message box
  every agent page has always had. Send clears an *editable* surface only — clearing a read-only
  note would delete the user's document.
- Both boxes own **separate** `BrowserSpeechRecognitionListener`s and separate Start/Stop buttons.
  Running two native recognizers at once is unreliable in Chrome; use one at a time.
- The worker agent defaults to `transcript-cleanup-agent` (short strict-JSON calls, history cleared
  each time). Override with `NOTE_COMMAND_AGENT_ID` / `NOTE_COMMAND_AGENT_NAME`; `NOTES_DIR`
  (default `~/notes`) is where "save this" writes.

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
