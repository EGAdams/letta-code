# One recording through the voice media boundary

The browser client extraction and Pipecat branch are planned. The current
`MediaRecorderVoiceRecorder` already handles the capture, upload, and response
validation steps. The server currently selects `VoicePipeline`.

```mermaid
sequenceDiagram
  participant User
  participant Recorder as MediaRecorderVoiceRecorder
  participant Client as VoiceMediaClient (planned)
  participant API as /api/voice
  participant Media as VoiceMediaPort adapter
  participant UI

  User->>Recorder: Start recording
  Recorder->>Recorder: Acquire microphone and capture audio
  User->>Recorder: Stop recording
  Recorder->>Recorder: Release microphone tracks
  Recorder->>Client: transcribe(recording)
  Client->>Client: Derive filename from MIME type
  Client->>API: POST audio with X-Filename
  API->>API: Validate AudioUpload
  alt Valid upload
    API->>Media: process(upload)
    alt Current Whisper pipeline
      Media->>Media: Transcribe and clean text
    else Planned Pipecat adapter
      Media->>Media: Produce batch transcript
    end
    Media-->>API: VoiceTranscript
    API-->>Client: ok, raw_transcript, cleaned_text
    Client->>Client: Validate response
    Client-->>Recorder: VoiceTranscript
    Recorder-->>UI: Cleaned text
  else Invalid upload or media failure
    API-->>Client: ok false, error
    Client-->>Recorder: Error
    Recorder-->>UI: Show error
  end
```
