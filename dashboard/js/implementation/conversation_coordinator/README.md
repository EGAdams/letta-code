# Conversation Coordinator Adapters

`SequentialSpeechQueue` is the concrete ordered playback adapter for the typed
`SpeechQueuePort`. It starts the first sentence as soon as the coordinator
emits it, waits for each playback token before starting the next sentence, and
registers the active queue with `VoiceSession` so navigation or barge-in can
cancel it.

Build with:

```bash
./node_modules/.bin/tsc -p dashboard/js/implementation/conversation_coordinator/tsconfig.json
```
