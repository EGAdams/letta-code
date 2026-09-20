# Voice media wire contract

`src/voice-media-contract.ts` validates the browser's `/api/voice` response and
derives the upload filename from MediaRecorder's actual MIME type. The Python
counterpart is `dashboard/voice/media/`, which owns the Pydantic upload and
transcript shapes plus the `VoiceMediaPort` protocol.

Build checked-in browser JavaScript with:

```bash
./node_modules/.bin/tsc -p dashboard/js/implementation/voice_media/tsconfig.json
```
