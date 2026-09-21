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

`MediaRecorder → POST /api/voice → selected STT Strategy → selected cleanup Strategy → fills message box → /api/test`.
GoF: Strategy (transcription/cleanup swap), Adapter (`LettaClient`), Factory (`build_*`), Pipeline
(`VoicePipeline`), State (recorder idle→recording→processing).

| File | Role |
|---|---|
| `voice/config.py` | paths/ids from env; bakes in lettabot's whisper defaults; `KNOWN_AGENT_NAMES` |
| `voice/transcription.py` | `WhisperCppTranscriber` (ffmpeg → 16k wav → `whisper-cli`) |
| `voice/cleanup.py` | `LettaAgentCleanup` and `PassThroughCleanup` Strategies |
| `voice/letta_client.py` | thin Letta HTTP adapter |
| `voice/pipeline.py` | `VoicePipeline.process` + `handle_voice_upload` (the `/api/voice` handler logic) |
| `voice/media/` | Pydantic `AudioUpload` / `VoiceTranscript` models and the `VoiceMediaPort` batch-media protocol |
| `voice/pipecat_media/` | Pipecat 1.11.0 batch adapters for local Faster Whisper and Groq |

`POST /api/voice` receives the recorded audio bytes as its body, with
`X-Filename` describing the actual MediaRecorder format (`voice.webm`,
`voice.mp4`, `voice.ogg`, etc.). The route returns HTTP 200 JSON:
`{ok:true, raw_transcript:string, cleaned_text:string}` or
`{ok:false, error:string}`. Empty audio preserves the existing
`empty audio upload` error. `AudioUpload` rejects unsafe filenames and
unsupported extensions before the transcriber runs; `VoiceTranscript`
validates the successful result before it reaches the browser. The current
`VoicePipeline` implements `VoiceMediaPort` with a complete recording as one
request. The TypeScript browser port lives in `js/abstract/voice_media/`.
The recorder delegates completed recordings to its injected
`VoiceMediaClient`; the default HTTP adapter in `js/implementation/voice_media/`
derives the filename from the blob MIME type, checks HTTP status and response
data at runtime, and returns only the transcript fields to capture.

For the one-agent Pipecat pilot, install `requirements-pipecat.txt`, set
`PIPECAT_PILOT_AGENT_ID` in the dashboard service environment, and restart.
When that ID is Toyota, `/api/receptionist-agent` selects Pipecat for Toyota's
home-screen recorder automatically. Agent Management remains browser-local:
set `localStorage.voicePipecatPilotAgentId` to the same ID and reload that
agent's Input Options page. Pilot uploads carry the agent ID and Pipecat
headers. The route rejects a mismatched ID; all unmarked uploads continue
through whisper.cpp. `PIPECAT_STT_PROVIDER` selects `local` or `groq`. Groq
defaults to `whisper-large-v3-turbo`, receives English plus the known-agent
prompt, and falls back to the local model if its request fails.
`PIPECAT_CLEANUP_MODE` selects `letta` or `direct`. Direct mode removes the
second network/model call and returns the STT result in both transcript fields.
The live Toyota pilot uses Groq plus direct cleanup; other voice paths retain
their existing behavior. Separate stage timings appear in the dashboard log.
See `voice/pipecat_media/README.md`.

Microphone capture follows idle → recording → processing → idle. The stream's
tracks are released when capture stops and when recorder construction, start,
or stop fails. The existing speech output is separate: `POST /api/tts` returns
MP3 audio to `EdgeTtsSpeechSynthesizer`, whose playback token is cancellable
through the voice session. Its tests cover non-audio responses, blocked
playback, cancellation during fetch/playback, and audio-end completion.

Toyota has two distinct microphone buttons. **Start** records an audio upload
and uses the Pipecat/Groq path above. **Start Listening** uses Chrome's native
continuous speech recognition, so it does not call Groq or `/api/voice`.
Final Start Listening text goes through `/api/receptionist-intent`. That route
now uses `DeterministicReceptionistIntentStrategy` by default: an explicit
`Toyota`, `Hey Toyota`, or similar wake phrase is stripped locally and the
remaining request is sent to Toyota. This removes the former cleanup-agent
round trip and its 15-second browser timeout. Set
`RECEPTIONIST_INTENT_MODE=letta` only if model-based intent detection is
deliberately required.

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

## Input Options "Send" → batch or streaming Letta Code

`InputOptionsRenderer` now sends through the injected `ConversationAgent`
port. The dashboard composition roots select `LettaAgentAdapter`, which owns
the 1800-second client timeout and per-agent conversation resume. The renderer
shows a working row immediately and replaces it with the answer or error. For
resumed conversations, the Python runner checks the persisted Letta answer if
the headless CLI stays open after a completed run; it waits for outstanding
tool returns before stopping that process. The renderer uses a per-agent
`VoiceSession` for turn ids across renderer rebuilds and asks
`SpokenOutputPolicy` before speaking assistant text. The agent adapter is also
retained per agent, so cancelling an older turn cannot overwrite the newer
conversation id. Interrupted, closed, or superseded turns cannot put a late
reply in the transcript or speaker. Leaving Input Options through the agent
tabs interrupts the pending turn. Speech already playing is
cancelled through the session's per-utterance playback handle. A speaking
turn stays active until audio ends. A new Send, leaving Input Options,
starting push-to-talk, or a new recognized utterance interrupts current
playback; Toyota's continuous listener also interrupts a pending reply when
new speech arrives. Automatic microphone echo detection is not part of this
contract, so a recognized echo can count as a new utterance.
The typed session source and its ports live in
`js/abstract/voice_session/src/`; its module-local `tsconfig.json` compiles
browser-loadable JS into `dist/`. See that module's README for the build command.

Toyota's receptionist selects `StreamingLettaAgentAdapter` and
`POST /api/letta-code-stream`. The endpoint starts Letta Code with
`stream-json` plus partial messages and writes validated NDJSON records as
they arrive. `ConversationCoordinator` publishes each assistant delta to the
UI, uses `DeterministicSentenceSegmenter` to release complete sentences, and
sends them through `SequentialSpeechQueue`. Toyota can therefore start saying
the first sentence while later text is still being generated. A browser abort
closes the response and reaps the CLI process group. Other Input Options pages
remain on the batch adapter during this pilot.

The Chat tab also uses a per-agent `VoiceSession` and `SpokenOutputPolicy`.
Its typed `TestChatAgentAdapter` keeps the existing `/api/test` behavior,
which resets agent messages on each send, and maps only assistant replies to
speech. Reasoning, tool, and error rows remain visible but silent. Navigation,
another Send, push-to-talk, or turning Speak off interrupts active playback.
The Agents-home router only classifies and hands text to Input Options; it
does not send an agent turn or synthesize a reply, so it has no speech policy.

The batch endpoint shells out to this checkout's `letta` CLI headlessly
(`--output-format json --memfs-startup skip --permission-mode acceptEdits`).
Two invariants (both from a 2026-07-22 failure where Mazda's
correct answer looked like "no answer"):

1. Server budget is 1770s but `FetchHttpClient`'s default abort is 30s — the
   `LettaAgentAdapter` passes a 1800s timeout for this endpoint.
2. Headless mode auto-denies gated tools with nobody to approve them, so `--permission-mode
   acceptEdits` is required (not `--yolo`/`bypassPermissions` — `acceptEdits` already auto-allows
   Write/Edit/MultiEdit/Bash without handing blanket access to a `0.0.0.0`-bound endpoint).

**Debugging tip:** "agent gave no answer" has twice been a dashboard rendering bug, not an agent
failure — check `GET /api/messages?agent=<id>` before concluding the agent misbehaved.
