# Chat Test Agent

`src/` contains the typed adapter for Chat's existing `/api/test` endpoint.
This endpoint resets agent messages for each send; Input Options instead uses
`/api/letta-code-message` and resumes a conversation. The adapter validates
the response at runtime and maps its reply types to `ConversationAgent` events.
Only `assistant_text` can pass the shared `SpokenOutputPolicy` gate.

Build the browser ES module after changing TypeScript:

```bash
./node_modules/.bin/tsc -p dashboard/js/implementation/chat_test_agent/tsconfig.json
```

`dist/` is checked in because the dashboard loads ES modules directly. The
compatibility entry is `../test-chat-agent-adapter.js`.
Run the module contract and boundary tests with
`bun test dashboard/js/implementation/chat_test_agent/tests`.
