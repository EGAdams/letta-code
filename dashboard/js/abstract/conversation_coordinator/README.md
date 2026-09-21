# Conversation Coordinator

This module designs the browser-side Mediator for one conversational turn. It
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

The future Letta adapter will consume the CLI's existing
`--output-format stream-json --include-partial-messages` NDJSON output through
a streaming HTTP endpoint. That cross-process boundary will use Pydantic
request and stream-record models on the Python side. The browser adapter owns
conversion from cumulative or delta wire messages to non-duplicated
`assistant_text` deltas. The coordinator never parses Letta wire shapes.

The first implementation slice should be test driven. Its acceptance case is:

1. Toyota emits a partial answer containing one complete sentence.
2. That sentence enters the speech queue before the agent turn finishes.
3. Later sentences remain ordered.
4. An interruption cancels the agent and queued speech for that generation.
5. The browser abort reaches the server and reaps the CLI process group.
6. Any late event from the interrupted generation is discarded.

```bash
./node_modules/.bin/tsc -p dashboard/js/abstract/conversation_coordinator/tsconfig.json
```
