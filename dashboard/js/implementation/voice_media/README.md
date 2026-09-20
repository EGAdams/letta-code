# Voice media HTTP adapter

`src/voice-media-contract.ts` validates the browser's `/api/voice` response and
derives the upload filename from MediaRecorder's actual MIME type.
`src/http-voice-media-client.ts` implements the abstract `VoiceMediaClient`
port by posting one complete recording to `/api/voice`. It validates the wire
reply and gives capture only the transcript fields. The Python counterpart is
`dashboard/voice/media/`, which owns the Pydantic upload and transcript shapes
plus the `VoiceMediaPort` protocol.

Build checked-in browser JavaScript after building the abstract contract:

```bash
./node_modules/.bin/tsc -p dashboard/js/abstract/voice_media/tsconfig.json
./node_modules/.bin/tsc -p dashboard/js/implementation/voice_media/tsconfig.json
```
