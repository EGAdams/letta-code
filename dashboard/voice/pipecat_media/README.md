# Pipecat batch media adapter

This module adapts one complete dashboard recording to Pipecat 1.11.0. It
decodes the validated upload to 16 kHz mono signed PCM, reads Pipecat
transcription frames, and returns text through the existing
`TranscriptionStrategy`. `PcmTranscriber` has local Faster Whisper and Groq
implementations. The Groq Strategy wraps PCM in a valid in-memory WAV and
falls back to the local model when its hosted request fails.

`VoicePipeline` still owns cleanup and implements the Pydantic
`VoiceMediaPort` contract. Letta agent turns and speech playback stay in the
dashboard application layer.

Install the optional dependency with
`dashboard/.venv/bin/pip install -r dashboard/requirements-pipecat.txt`.
Set `PIPECAT_PILOT_AGENT_ID` in the dashboard service environment to one
existing Letta agent ID, then restart the service. When Toyota is selected,
the receptionist endpoint selects Pipecat for her home-screen recorder. For an
Agent Management Input Options page, set
`localStorage.setItem("voicePipecatPilotAgentId", "<same-agent-id>")` and
reload. The server rejects mismatched pilot headers and uses whisper.cpp for
all other uploads. Remove the localStorage key to stop the Agent Management
opt-in.

Set `PIPECAT_STT_PROVIDER=groq` and provide `GROQ_API_KEY` to use Pipecat's
Groq service. `PIPECAT_GROQ_MODEL` defaults to
`whisper-large-v3-turbo`. Set `PIPECAT_CLEANUP_MODE=direct` to return that
transcript without a second Letta cleanup request. The default values remain
`local` and `letta`. If Groq fails, the first local fallback request loads the
model selected by `PIPECAT_WHISPER_MODEL`, which defaults to `small.en`.

The live dashboard reads its protected key from
`~/.config/letta-code/dashboard-voice.env` through a user systemd drop-in.
Pipeline logs report separate transcription and cleanup durations.

On the live host on 2026-09-21, the first Groq request after a dashboard
restart took 12.8–13.6 seconds. The immediately following requests took
0.58–0.60 seconds, including decode and HTTP handling, while direct cleanup
took 0.0 milliseconds. Treat the first request as provider/client warm-up when
diagnosing latency; the fallback log explicitly reports if local Whisper ran.

This is a batch adapter. It does not provide streaming, server-side turn
detection, or Pipecat playback. Those need a separate contract.
