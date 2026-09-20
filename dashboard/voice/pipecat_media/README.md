# Pipecat batch media adapter

This module adapts one complete dashboard recording to Pipecat 1.11.0's local
`WhisperSTTService`. It decodes the validated upload to 16 kHz mono signed PCM,
reads Pipecat transcription frames, and returns text through the existing
`TranscriptionStrategy`. `VoicePipeline` still owns cleanup and implements the
Pydantic `VoiceMediaPort` contract. Letta agent turns and speech playback stay
in the dashboard application layer.

Install the optional dependency with
`dashboard/.venv/bin/pip install -r dashboard/requirements-pipecat.txt`.
Set `PIPECAT_PILOT_AGENT_ID` in the dashboard service environment to one
existing Letta agent ID, then restart the service. In one browser, set
`localStorage.setItem("voicePipecatPilotAgentId", "<same-agent-id>")` and
reload. Only that agent's Input Options recorder sends Pipecat pilot headers.
The server rejects mismatched pilot headers and uses whisper.cpp for all other
uploads. Remove the localStorage key to stop opting in. The first Pipecat
request downloads the selected Faster Whisper model; `PIPECAT_WHISPER_MODEL`
defaults to `small.en` and can select a smaller pilot model.

This is a batch adapter. It does not provide streaming, server-side turn
detection, or Pipecat playback. Those need a separate contract.
