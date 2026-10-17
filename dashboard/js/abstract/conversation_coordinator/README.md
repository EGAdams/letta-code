# Conversation Coordinator

This module contains the browser-side Mediator for one conversational turn. It
coordinates existing ports without depending on the DOM, `fetch`, Letta, or a
specific speech provider.

The coordinator accepts normalized `AgentEvent` objects from a
`ConversationAgentPort`, checks each event against the `VoiceSessionPort`
generation fence, exposes public assistant text to an observer, divides
speakable text into complete sentences, and sends those sentences to an
ordered `SpeechQueuePort`.

The design deliberately keeps five responsibilities separate:

- `ConversationCoordinatorPort` owns turn orchestration.
- `ConversationAgentPort` supplies normalized agent events.
- `SentenceSegmenterPort` is the Strategy for sentence boundaries.
- `SpeechQueuePort` prepares and plays speech in order.
- `ConversationCoordinatorObserver` reports text, status, and errors to a UI.

The `StreamingLettaAgentAdapter` consumes the CLI's existing
`--output-format stream-json --include-partial-messages` NDJSON output through
a streaming HTTP endpoint. The cross-process boundary uses Pydantic request and
stream-record models in `dashboard/letta_code/streaming.py`. The browser
adapter owns conversion from provider wire messages to `assistant_text`
deltas. The coordinator never parses Letta wire shapes.

The first implementation slice now provides this acceptance case:

1. Toyota emits a partial answer containing one complete sentence.
2. That sentence enters the speech queue before the agent turn finishes.
3. Later sentences remain ordered.
4. An interruption cancels the agent and queued speech for that generation.
5. The browser abort reaches the server and reaps the CLI process group.
6. Any late event from the interrupted generation is discarded.

Toyota's receptionist composition root selects the streaming adapter. Other
agent surfaces retain the batch adapter while this pilot is measured.

`InputOptionsRenderer` (`dashboard/js/implementation/detail-renderers.js`) is
what actually measures it: it opens a
[`ConversationLatencyObserver`](../conversation_latency_observer/README.md)
trace at speech-end (push-to-talk and continuous listening) or at Send
(typed), marks `AGENT_REQUESTED` right before `coordinator.start()`, and lets
the coordinator's own observer hooks (`onAssistantDelta`, `onSpeechQueued`,
`onTurnComplete`, `onError`) and `SequentialSpeechQueue`'s optional
`telemetry` callback mark the rest. This is the Phase 0 measurement the
voice-communication plan asked for before deciding anything further from
guesses.

```bash
./node_modules/.bin/tsc -p dashboard/js/abstract/conversation_coordinator/tsconfig.json
./node_modules/.bin/tsc -p dashboard/js/abstract/conversation_latency_observer/tsconfig.json
./node_modules/.bin/tsc -p dashboard/js/implementation/conversation_coordinator/tsconfig.json
./node_modules/.bin/tsc -p dashboard/js/implementation/conversation_stream_agent/tsconfig.json
bun test dashboard/js/abstract/conversation_coordinator/tests \
  dashboard/js/abstract/conversation_latency_observer/tests \
  dashboard/js/implementation/conversation_coordinator/tests \
  dashboard/js/implementation/conversation_stream_agent/tests \
  dashboard/js/tests
```
