# Conversation latency observer class boundary

`ConversationLatencyObserver` applies the Observer pattern. Voice objects emit
typed milestones without knowing how measurements are stored or displayed.
The observer uses one injected monotonic clock, derives durations when a trace
closes, and sends the immutable report to an injected sink.

```mermaid
classDiagram
  class ConversationLatencyObserverPort {
    <<interface>>
    +begin(context) TraceId
    +mark(traceId, milestone, detail) bool
    +finish(traceId, outcome) LatencyReport
    +discard(traceId, reason) bool
  }
  class ConversationLatencyObserver
  class MonotonicClockPort {
    <<interface>>
    +now() number
  }
  class TraceIdSourcePort {
    <<interface>>
    +next() TraceId
  }
  class LatencyReportSinkPort {
    <<interface>>
    +publish(report) void
  }
  class LatencyTraceContext {
    +SessionId sessionId
    +GenerationId generationId
    +AgentId agentId
    +InputMode inputMode
  }
  class LatencyMilestone {
    <<enumeration>>
    SPEECH_ENDED
    TRANSCRIPT_READY
    AGENT_REQUESTED
    FIRST_AGENT_DELTA
    FIRST_SENTENCE_QUEUED
    FIRST_TTS_REQUESTED
    FIRST_AUDIO_READY
    FIRST_AUDIO_PLAYING
  }
  class LatencyReport {
    +LatencyTraceContext context
    +LatencyOutcome outcome
    +MilestoneSampleList samples
    +DurationList durations
  }

  ConversationLatencyObserverPort <|.. ConversationLatencyObserver
  ConversationLatencyObserver --> MonotonicClockPort : timestamps milestones
  ConversationLatencyObserver --> TraceIdSourcePort : creates trace identity
  ConversationLatencyObserver --> LatencyReportSinkPort : publishes reports
  ConversationLatencyObserver --> LatencyTraceContext : owns active trace
  ConversationLatencyObserver --> LatencyMilestone : records first occurrence
  ConversationLatencyObserver --> LatencyReport : builds on finish
```
