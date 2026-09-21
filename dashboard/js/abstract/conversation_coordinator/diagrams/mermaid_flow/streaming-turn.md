# Streaming conversation flow

The adapter normalizes the wire stream before the coordinator sees it. The
coordinator renders assistant text immediately and sends only complete,
current sentences to speech.

```mermaid
flowchart TD
  A[Final user transcript] --> B[VoiceSession begins generation]
  B --> C[ConversationAgent submits turn]
  C --> D[Read next normalized AgentEvent]
  D --> E{Current generation?}
  E -->|no| F[Discard late event]
  E -->|yes| G[Notify UI observer]
  G --> H{Assistant text?}
  H -->|no| I{Terminal event?}
  H -->|yes| J[Apply SpokenOutputPolicy]
  J --> K{Speakable and current?}
  K -->|no| D
  K -->|yes| L[Append visible text]
  L --> M[SentenceSegmenter receives delta]
  M --> N{Complete sentence ready?}
  N -->|yes| O[Queue sentence by sequence]
  O --> P[Begin speaking on first sentence]
  P --> D
  N -->|no| D
  I -->|no| D
  I -->|yes| Q[Flush final phrase]
  Q --> R[Finish queued playback]
  R --> S[Complete generation]
```
