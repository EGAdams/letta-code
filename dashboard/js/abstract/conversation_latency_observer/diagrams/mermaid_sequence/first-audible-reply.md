# Measuring the first audible reply

The observer receives milestones from existing objects. It does not start an
agent request, synthesize speech, play audio, or update the UI. This keeps
instrumentation separate from conversation behavior.

```mermaid
sequenceDiagram
  actor User
  participant Capture as Voice capture
  participant Media as VoiceMediaClient
  participant Coordinator as ConversationCoordinator
  participant Agent as ConversationAgent
  participant Queue as SpeechQueue
  participant TTS as Speech adapter
  participant Observer as ConversationLatencyObserver
  participant Sink as LatencyReportSink

  User->>Capture: finishes speaking
  Capture->>Observer: mark speech ended
  Capture->>Media: finalize transcript
  Media-->>Capture: final transcript
  Capture->>Observer: mark transcript ready
  Capture->>Coordinator: start turn
  Coordinator->>Observer: mark agent requested
  Coordinator->>Agent: submit turn
  Agent-->>Coordinator: first assistant text delta
  Coordinator->>Observer: mark first agent delta
  Coordinator->>Queue: enqueue first complete sentence
  Coordinator->>Observer: mark first sentence queued
  Queue->>Observer: mark first TTS requested
  Queue->>TTS: prepare first sentence
  TTS-->>Queue: audio ready
  Queue->>Observer: mark first audio ready
  Queue-->>User: begin playback
  Queue->>Observer: mark first audio playing
  Coordinator->>Observer: finish completed
  Observer->>Sink: publish latency report
```

