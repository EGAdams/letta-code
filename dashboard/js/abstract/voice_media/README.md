# Voice Media

`src/voice-media-client.ts` defines the provider neutral batch
`VoiceMediaClient` port and `VoiceTranscript` shape. It sits beside
`voice_session/` in `js/abstract/`. The browser recorder receives this port;
the HTTP adapter lives in `js/implementation/voice_media/`.

`tsconfig.json` compiles `src/` to checked-in `dist/`; `tsconfig.tests.json`
checks the TypeScript port agreement. The Pipecat adapter belongs on the Python
side of the media port in `dashboard/voice/media/ports.py`.

```bash
./node_modules/.bin/tsc -p dashboard/js/abstract/voice_media/tsconfig.json
./node_modules/.bin/tsc -p dashboard/js/abstract/voice_media/tsconfig.tests.json
bun test dashboard/js/abstract/voice_media/tests
```
