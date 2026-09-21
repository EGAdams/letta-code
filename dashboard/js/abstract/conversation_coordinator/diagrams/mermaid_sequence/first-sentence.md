# First sentence starts before the turn finishes

The key latency improvement is that Toyota can begin speaking after the first
complete sentence. Later text generation, TTS preparation, and playback can
overlap while the queue preserves sentence order.

```mermaid
sequenceDiagram
  actor User
  participant UI as Conversation observer
  participant Coordinator as ConversationCoordinator
  participant Session as VoiceSession
  participant Agent as StreamingConversationAgent
  participant Segmenter as SentenceSegmenter
  participant Queue as SpeechQueue
  participant TTS as Speech adapter

  User->>Coordinator: start user turn with speech enabled
  Coordinator->>Session: beginTurn
  Session-->>Coordinator: generation id
  Coordinator->>Agent: submit turn and generation id
  Agent-->>Coordinator: assistant text delta: The next step is ready.
  Coordinator->>Session: accepts generation id
  Session-->>Coordinator: true
  Coordinator-->>UI: assistant text delta
  Coordinator->>Segmenter: push text delta
  Segmenter-->>Coordinator: first complete sentence
  Coordinator->>Session: beginSpeaking generation id
  Coordinator->>Queue: enqueue sentence 1
  Queue->>TTS: prepare sentence 1
  Agent-->>Coordinator: assistant text delta: I will explain it now.
  Coordinator->>Queue: enqueue sentence 2
  Queue->>TTS: prepare sentence 2
  TTS-->>Queue: sentence 1 ready
  Queue->>TTS: play sentence 1
  Agent-->>Coordinator: terminal
  Coordinator->>Queue: finish generation
  Queue->>TTS: play sentence 2
  Queue-->>Coordinator: playback drained
  Coordinator->>Session: completeTurn generation id
```
