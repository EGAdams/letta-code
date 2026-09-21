# Streaming Letta Agent Adapter

`StreamingLettaAgentAdapter` maps the validated NDJSON response from
`POST /api/letta-code-stream` into the existing `ConversationAgent` event
vocabulary. It owns one `AbortController` per voice-session generation, so
barge-in closes the HTTP request and the server reaps the CLI process group.

Build with:

```bash
./node_modules/.bin/tsc -p dashboard/js/implementation/conversation_stream_agent/tsconfig.json
```
