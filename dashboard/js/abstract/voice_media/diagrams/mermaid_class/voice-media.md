# Voice media class boundary

`VoiceMediaClient` and `HttpVoiceMediaClient` now form the TypeScript batch
media seam used by the recorder. The Python port and Whisper pipeline already
exist. The Pipecat adapter is planned on the Python side.

```mermaid
classDiagram
  class VoiceMediaClient {
    <<interface>>
    +transcribe(recording) Promise~VoiceTranscript~
  }
  class VoiceTranscript {
    <<interface>>
    +raw_transcript string
    +cleaned_text string
  }
  class VoiceRecorder {
    +start() Promise~boolean~
    +stop() Promise
  }
  class MediaRecorderVoiceRecorder
  class HttpVoiceMediaClient
  class VoiceMediaPort {
    <<interface>>
    +process(upload) VoiceTranscript
  }
  class VoicePipeline
  class PipecatMediaAdapter

  VoiceRecorder <|-- MediaRecorderVoiceRecorder
  VoiceMediaClient <|.. HttpVoiceMediaClient
  VoiceMediaClient --> VoiceTranscript : returns
  MediaRecorderVoiceRecorder --> VoiceMediaClient : injected
  HttpVoiceMediaClient ..> VoiceMediaPort : POST /api/voice
  VoiceMediaPort <|.. VoicePipeline
  VoiceMediaPort <|.. PipecatMediaAdapter
```
