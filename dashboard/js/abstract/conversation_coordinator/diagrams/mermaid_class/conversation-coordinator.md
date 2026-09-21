# Conversation coordinator class boundary

`ConversationCoordinator` is a Mediator. It owns orchestration while each
injected port retains one focused responsibility. Concrete HTTP, Letta, DOM,
and audio classes stay outside this module.

```mermaid
classDiagram
  class ConversationCoordinatorPort {
    <<interface>>
    +start(turn, options) Promise~ConversationTurnOutcome~
    +interrupt() GenerationId
    +close() void
  }
  class ConversationCoordinator
  class ConversationAgentPort {
    <<interface>>
    +submit(turn, generationId) AsyncIterable~AgentEvent~
    +cancel(generationId) void
  }
  class VoiceSessionPort {
    <<interface>>
    +beginTurn() GenerationId
    +accepts(generationId) bool
    +beginSpeaking(generationId) bool
    +interrupt() GenerationId
    +completeTurn(generationId) bool
    +close() void
  }
  class SpokenOutputPolicyPort {
    <<interface>>
    +admit(event) SpeechVerdict
  }
  class SentenceSegmenterPort {
    <<interface>>
    +push(delta) StringList
    +flush() string
    +reset() void
  }
  class SpeechQueuePort {
    <<interface>>
    +enqueue(segment, agentName) void
    +finish(generationId) Promise~void~
    +cancel(generationId) void
  }
  class ConversationCoordinatorObserver {
    <<interface>>
    +onAssistantDelta(generationId, text) void
    +onSpeechQueued(segment) void
    +onTurnComplete(outcome) void
    +onError(generationId, error) void
  }

  ConversationCoordinatorPort <|.. ConversationCoordinator
  ConversationCoordinator --> ConversationAgentPort : consumes events
  ConversationCoordinator --> VoiceSessionPort : checks generation
  ConversationCoordinator --> SpokenOutputPolicyPort : gates speech
  ConversationCoordinator --> SentenceSegmenterPort : finds boundaries
  ConversationCoordinator --> SpeechQueuePort : orders playback
  ConversationCoordinator --> ConversationCoordinatorObserver : reports progress
```
