# Handoff - 2026-05-06

## Summary

Primary issue this shift: Telegram LettaBot runs frequently ended with streamed tool-call fragments and no final assistant delivery, even when Scissari invoked `send_message_to_agent_and_wait_for_reply`.

All issues have been identified and fixed. The Scissari→Hailey relay is confirmed working via two live API tests.

## What Was Changed (complete list)

### 1) LettaBot (`/home/adamsl/lettabot/src/core/bot.ts`)

Four separate fixes:

**Fix 1 — Conversation-busy 409 vs. orphaned-approval 409:**
- Added `isConversationBusyError()` — detects "is currently being processed" in both `error.message` and nested SDK `error.error.detail`.
- `isApprovalConflictError()` now returns `false` early when `isConversationBusyError()` is true.
- Added `trySend()` retry loop in `runSession()` with exponential backoff (8s → 16s → 32s, max 3 retries) for busy 409s.

**Fix 2 — Tool loop false positive on argument fragments:**
- Added `seenToolCallIds` Set populated with each unique `toolCallId`.
- Loop detector checks `seenToolCallIds.size >= maxToolCalls` (distinct calls, not stream events).
- Lowered default `maxToolCalls` from 100 → 30.

**Fix 3 — Meta-only responses reaching users:**
- Added `isMetaOnlyResponse()` classification.
- `processMessage`: meta-only result with no tool calls now retries once, then suppresses to trigger no-response fallback.
- `sendToAgent`: meta-only result suppressed to empty string.

**Fix 4 — Subprocess CWD so skills are discovered:**
- Session `cwd` now uses `dirname(LETTA_CLI_PATH)` = `/home/adamsl/letta-code` instead of the lettabot working directory.
- Without this, the subprocess searched for `.skills/` in `/home/adamsl/lettabot` which has none.

### 2) letta-code (`/home/adamsl/letta-code/src/headless.ts`)

**Critical fix — Multi-agent tool fallback added to bidirectional mode:**

Root cause: The letta-code subprocess runs in bidirectional mode (`--input-format stream-json`) when spawned by the SDK session. The multi-agent tool fallback — which executes `send_message_to_agent_and_wait_for_reply` client-side when the server ends with `stop_reason: end_turn` without executing it — existed only in `runHeadlessMode` (one-shot), NOT in `runBidirectionalMode`.

Effect: Scissari's tool call fired, the server ended with `stop_reason: end_turn`, the subprocess broke out immediately (no tool_return), Scissari had nothing to reply from → empty result.

Fix: Added the same multi-agent fallback block from one-shot mode into `runBidirectionalMode`'s inner loop, right before `if (stopReason === "end_turn") { break; }`. The fallback executes the pending tool calls, feeds the result back as a user message, and continues the loop so Scissari generates a real reply.

**Rebuild required:** `bun run build` in `/home/adamsl/letta-code`. The `letta.js` at 2026-05-06 18:xx reflects all changes.

### 3) Skills updated

- `/home/adamsl/letta-code/.skills/scissari-telegram-tool-loop-fix/SKILL.md` — Added three "Known Bug" sections (tool loop false positive, conversation busy 409, bidirectional mode fallback missing).
- `/home/adamsl/letta-code/.skills/scissari-hailey-pairing/SKILL.md` — Added "Conversation Busy 409 Bug" section.
- `/home/adamsl/letta-code/src/skills/custom/scissari-hailey-pairing/SKILL.md` — Same section added.

## Current Status

**Working.** Two live API tests confirmed Scissari→Hailey relay returns real Hailey content:

```
Ask Hailey what 2 plus 2 is → "Hailey's exact reply was:\n\n`4`"
Ask Hailey for today's date  → "She said exactly:\n\n\"Today's date is **May 6, 2026**.\""
```

Bot is running at localhost:8091 with `LETTA_CLI_PATH=/home/adamsl/letta-code/letta.js`.

## Debug logging still present in `sendToAgent`

`bot.ts` still has `[sendToAgent] type=...` and `[sendToAgent] final response length=...` log lines added during debugging. These are harmless but should be removed once Telegram path is confirmed stable.

## Bot restart procedure

```bash
kill $(lsof -tiTCP:8091 -sTCP:LISTEN 2>/dev/null) 2>/dev/null
sleep 2
cd /home/adamsl/lettabot
LETTA_CLI_PATH=/home/adamsl/letta-code/letta.js node dist/main.js >> lettabot.log 2>&1 &
sleep 5
curl http://localhost:8091/health
```

## Verify relay works

```bash
curl -s -X POST http://localhost:8091/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: c108de0747838761ec5dd2126769b901518c9c71df09420ecdd240f7f096f070" \
  -d '{"message":"Ask Hailey what 2 plus 2 is and tell me her exact answer."}' \
  --max-time 120
```

Expected: `{"success":true,"response":"Hailey's exact reply was:\n\n\`4\`",...}`

## Risk Notes

- Telegram runtime is separate from letta-code CLI path; fixes in one do not automatically fix the other.
- Tool-call argument chunking behavior remains inconsistent (cumulative vs. append deltas). Parser must stay tolerant.
- Meta/thought phrasing is non-deterministic; response classifier should remain prefix-pattern based and easy to extend.
- Debug logging in `sendToAgent` should be cleaned up once Telegram path is confirmed stable.
