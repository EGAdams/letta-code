# Pipecat media adapter

This Python module is the next voice implementation. It will adapt Pipecat's
media events to `voice.media.ports.VoiceMediaPort` for one dashboard user and
one existing Letta agent. The current `VoicePipeline` remains the other
implementation of that port.

`src/` is reserved for the adapter, `tests/` for its contract and failure
tests, and `diagrams/` for class, flow, and sequence diagrams. The Python
implementation uses the Pydantic models in `voice/media/`; it does not need a
TypeScript configuration. Verify and pin Pipecat's current API before adding
source code or tests that depend on it. Streaming media will need a separate
port because `VoiceMediaPort` currently accepts one complete recording.
