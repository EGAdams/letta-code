---
name: scissari-web-search-fix
description: Diagnose and fix Scissari returning only reasoning thoughts instead of web search results via Telegram/lettabot
---

# Scissari Web Search: Thoughts Only (No Results)

## Problem
When asking Scissari to search the web via Telegram, she returns only her internal
thoughts/reasoning ("I should search...", "**Preparing to search the web**...") but
never outputs actual search results. The search tool fires but no results reach the user.

## Root cause (fully diagnosed 2026-05-07, updated 2026-05-11)

Three compounding issues:

### Issue 1 — lettabot `bot.ts`: meta-only bypass via `sentAnyMessage`

With `canEdit=true` on Telegram (no TTS), lettabot live-streams the pre-tool reasoning
text to the user immediately. This sets `sentAnyMessage=true`. Then when the tool call
completes with no follow-up assistant message, the meta-only retry check:

```ts
if (!hasDeliverableResponse && !sentAnyMessage && ...)
```

…sees `sentAnyMessage=true` and silently gives up. The user is left with just the thought.

**Fix applied** in `/home/adamsl/lettabot/src/core/bot.ts`:
1. **Line ~1271** (type-change finalization): When transitioning `assistant→tool_call`,
   if accumulated text is meta-only, discard it and reset `sentAnyMessage=false`.
2. **Line ~1344** (live streaming): Added `&& !isMetaOnlyResponse(streamText)` to prevent
   meta-only text from ever being live-streamed to Telegram.

### Issue 2 — Letta 0.16.3: MCP `web_search_exa` never streams `tool_return_message`

Confirmed by raw SSE stream inspection. The Letta 0.16.3 server sends:
```
tool_call_message (30+ empty chunks) → stop_reason: end_turn → [DONE]
```
**No `tool_return_message` is ever emitted.** The MCP Exa tool (`external_mcp`,
server ID `mcp_server-ef79bf36-03a6-4237-bb58-de8299ce9bf1`) executes on the
Letta server but the result is never streamed back to the client. The Letta
subprocess (letta-code) then falls back to the last reasoning text as the result.

Key facts:
- EXA_API_KEY (`40ffa2db-b7d6-43b1-bf1d-4af651594a79`) IS present in both local env AND the Letta server container
- Tool IS registered correctly: `tool-ddc2587d-be5d-4f09-bc9e-49de956b3399` (`web_search_exa`) and `tool-2ce4d194-4a0b-4b57-9a47-85df76a29861` (`web_fetch_exa`)
- This is a **Letta 0.16.3 server-side streaming bug** — the MCP tool executes but the result never reaches the stream

### Issue 3 — stale `/home/adamsl/letta-code/letta.js` after source fix

Telegram uses `lettabot`, and `lettabot/start_scissari_bot.sh` pins the SDK to the
local compiled CLI bundle:

```bash
LETTA_CLI_PATH=/home/adamsl/letta-code/letta.js
```

Editing `src/headless.ts` is not enough for Telegram. If `letta.js` still contains
the old fallback:

```bash
rg -n "lastReasoning\\?\\.text|selectUserVisibleResultText" /home/adamsl/letta-code/letta.js
```

then rebuild and restart:

```bash
cd /home/adamsl/letta-code
bun run build

cd /home/adamsl/lettabot
kill "$(lsof -tiTCP:8091 -sTCP:LISTEN)" 2>/dev/null || true
nohup ./start_scissari_bot.sh >> lettabot.log 2>&1 &
```

After the 2026-05-11 fix, `letta.js` should contain `selectUserVisibleResultText`
and should not contain a final-result fallback from `lastReasoning?.text`.
`/new` in Telegram does **not** reload the bot process or rebuild the CLI bundle.

### Issue 4 — ChatGPT relay tool returns empty via Telegram tool workflow

Observed 2026-05-11 when Scissari was asked over Telegram to use
`relay_message_to_chatgpt` for an Iran conflict update. Telegram returned:

```text
(The agent started a tool workflow but did not return the final reply. ...)
```

Live `/home/adamsl/lettabot/lettabot.log` showed:

```text
type=tool_call toolName=relay_message_to_chatgpt
type=result success=true result=""
Attempting multi-agent fallback for relay_message_to_chatgpt ...
Empty response after tool workflow; requesting one continuation turn...
Stream:continuation type=tool_call toolName=relay_message_to_chatgpt
Stream:continuation type=result success=true result=""
Agent had tool activity but no assistant message - returning visible fallback
```

Continuation alone was insufficient because Scissari simply called the same relay
tool again. The streamed relay args were also malformed/tokenized, for example:

```text
{"message:How ...","browser_server_url":,"executor_url":,...}
```

Fix applied in `/home/adamsl/lettabot`:

- `/home/adamsl/lettabot/src/core/bot.ts` tries a relay-specific fallback before generic continuation/fallback handling.
- `/home/adamsl/lettabot/src/core/chatgpt-relay-fallback.ts` reconstructs malformed streamed relay args, imports `/home/adamsl/letta-code/browser_tools/letta_chatgpt_relay_tool.py`, executes it locally, and returns the ChatGPT response text.
- `/home/adamsl/lettabot/src/core/bot-tool-continuation.integration.test.ts` covers both the generic continuation case and the malformed relay-args case.

## Diagnostic steps

### Fast check — lettabot logs
```bash
tail -260 /home/adamsl/lettabot/lettabot.log | grep -E "type=|final response|suppressing|tool workflow|ChatGPT relay fallback|relay_message_to_chatgpt|Stream:continuation"
```
Look for:
- `suppressing meta-only response (len=N)` → meta-only bypass issue (fixed)
- `type=tool_call` followed directly by `type=result` (no `type=tool_result` in between) → Letta 0.16.3 MCP streaming bug
- `result` equal to a thought like "I should..." → check for stale `letta.js` and restart `lettabot`
- `relay_message_to_chatgpt` followed by empty `result` and no `ChatGPT relay fallback` log → stale `/home/adamsl/lettabot/dist`
- `ChatGPT relay fallback produced no response` with malformed args → check `parseChatGptRelayArgs()` in `chatgpt-relay-fallback.ts`

### Check whether Telegram is using stale code
```bash
rg -n "lastReasoning\\?\\.text|selectUserVisibleResultText" /home/adamsl/letta-code/letta.js
lsof -iTCP:8091 -sTCP:LISTEN -Pn
ps -ef | rg "node dist/main.js|node /home/adamsl/letta-code/letta.js"
```

Expected after rebuild/restart:
- `letta.js` contains `selectUserVisibleResultText`
- no final-result fallback from `lastReasoning?.text`
- `node dist/main.js` is listening on `127.0.0.1:8091`
- its child process is `node /home/adamsl/letta-code/letta.js ...`

Check that the live Telegram path is using rebuilt lettabot code:

```bash
rg -n "ChatGPT relay fallback|parseChatGptRelayArgs|executeChatGptRelayFallback" /home/adamsl/lettabot/dist/core -S
```

Expected after the relay fallback fix:
- `/home/adamsl/lettabot/dist/core/bot.js` imports `executeChatGptRelayFallback`
- `/home/adamsl/lettabot/dist/core/chatgpt-relay-fallback.js` exists

### Verify tool execution via raw SSE
```bash
curl -N -s "http://100.80.49.10:8283/v1/agents/agent-5955b0c2-7922-4ffe-9e43-b116053b80fa/messages/stream" \
  -H "Authorization: Bearer 6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Search for memfs"}],"stream_tokens":true}' \
  --max-time 30 | head -40
```
If you see `tool_call` chunks but no `tool_return_message` → Letta MCP streaming bug confirmed.

### Verify meta-only suppression (lettabot API)
```bash
API_KEY="c108de0747838761ec5dd2126769b901518c9c71df09420ecdd240f7f096f070"
curl -s -X POST http://127.0.0.1:8091/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"message": "Search the web for what memfs is"}'
```
Response must NOT start with "I should...", "I need to...", or "**Preparing to search".
For the known Exa MCP streaming bug, an empty response is acceptable; it means
thoughts were suppressed and no tool result arrived. A non-empty thought response
means the suppression/fallback path is broken or stale.

### Check `isMetaOnlyResponse` patterns
File: `/home/adamsl/lettabot/src/core/bot.ts` (lines ~82–108)

If the response slips through despite being reasoning text, add the new pattern to `metaPrefixes`.

## Fix locations

| File | What to change |
|------|---------------|
| `/home/adamsl/lettabot/src/core/bot.ts` ~line 1271 | Discard meta-only pre-tool text, reset `sentAnyMessage=false` |
| `/home/adamsl/lettabot/src/core/bot.ts` ~line 1344 | Add `&& !isMetaOnlyResponse(streamText)` to live-stream guard |
| `/home/adamsl/lettabot/src/core/bot.ts` ~line 82 | `isMetaOnlyResponse` pattern list — add any new patterns seen |
| `/home/adamsl/lettabot/src/core/chatgpt-relay-fallback.ts` | Repair tokenized `relay_message_to_chatgpt` args and run the Python relay tool locally |
| `/home/adamsl/lettabot/src/core/bot-tool-continuation.integration.test.ts` | Regression tests for empty tool workflow, continuation, and ChatGPT relay fallback |
| `/home/adamsl/letta-code/src/headless.ts` result selection | Never use `reasoning_message` as final user-visible result |
| `/home/adamsl/letta-code/letta.js` | Rebuild with `bun run build`; this is what Telegram uses |

## Known remaining issue

The Letta 0.16.3 MCP `tool_return_message` streaming bug means web searches may still
silently fail even after the meta-only and `headless.ts` result-selection fixes.
The desired failure mode is an empty/fallback response, not raw reasoning text.
This is a Letta server-side issue.

Workaround options (not yet implemented):
1. Have Scissari route web searches through Hailey or a subagent that has direct Exa access
2. Upgrade the Letta server to a version that properly streams MCP tool results
3. Implement client-side Exa search in the letta-code subprocess as a fallback

## Related skills
- `scissari-telegram-routing`
- `scissari-hailey-pairing`
- `operating-letta-across-machines`

## Integration test
`/home/adamsl/letta-code/src/integration-tests/lettabot-meta-suppression.integration.test.ts`
Run with: `LETTA_RUN_LETTABOT_TEST=1 bun test src/integration-tests/lettabot-meta-suppression.integration.test.ts`

For the lettabot-side relay regression:

```bash
cd /home/adamsl/lettabot
npm run test:run -- src/core/bot-multi-agent-fallback.test.ts src/core/sdk-session-contract.test.ts src/core/bot-tool-continuation.integration.test.ts
npm run build
```
