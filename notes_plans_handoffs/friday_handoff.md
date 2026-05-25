# Friday Handoff — 2026-05-08

## What We're Working On

Scissari (the Letta agent running as `@scissaribot` on Telegram via lettabot) was returning only internal
reasoning text ("I should search...", "**Preparing to search the web**...") instead of actual web search
results. We diagnosed, fixed, documented, and wrote integration tests for this bug.

---

## What We Accomplished Today

### 1. Root cause diagnosed (two compounding issues)

**Issue A — lettabot `bot.ts` sentAnyMessage bypass (FIXED)**
With `canEdit=true` (Telegram without TTS), lettabot live-streams pre-tool reasoning text immediately,
setting `sentAnyMessage=true`. When the tool produces no follow-up assistant message, the meta-only retry
check (`!sentAnyMessage`) is already `true`, so the bot silently gives up. User sees just the thought.

Fix applied in `/home/adamsl/lettabot/src/core/bot.ts`:
- Line ~1271: When transitioning `assistant→tool_call`, if accumulated text is meta-only, discard it and reset `sentAnyMessage=false`
- Line ~1344: Added `&& !isMetaOnlyResponse(streamText)` to live-stream guard

**Issue B — Letta 0.16.3 MCP streaming bug (OPEN, server-side)**
Raw SSE inspection confirmed: `web_search_exa` sends `tool_call_message` chunks then `end_turn` —
**no `tool_return_message` is ever emitted**. EXA_API_KEY is set on the server. This is a Letta server-side
bug, not a config issue.

### 2. Skills and memory updated

- Created/updated: `/home/adamsl/letta-code/src/skills/custom/scissari-web-search-fix/SKILL.md`
- Created/updated: `/home/adamsl/.claude/projects/-home-adamsl-letta-code/memory/project_scissari_web_search_thoughts_only.md`
- Updated: `MEMORY.md` index with Scissari web search, log viewer, and integration test entries

### 3. Integration test written

File: `/home/adamsl/letta-code/src/integration-tests/lettabot-meta-suppression.integration.test.ts`

Two tests:
- `LetabotMetaSuppression_SimpleQ_2026` — sends "What is 2 + 2?", verifies non-empty non-meta response
- `LetabotMetaSuppression_WebSearch_2026` — sends web search request, verifies meta-only reasoning NOT leaked

Run with:
```bash
LETTA_RUN_LETTABOT_TEST=1 bun test src/integration-tests/lettabot-meta-suppression.integration.test.ts --timeout 60000
```

Both tests currently **PASS** (2 pass, 0 fail, confirmed today).

Logger IDs added to `src/integration-tests/logger-helpers.ts`:
```
LetabotMetaSuppression_SimpleQ_2026
LetabotMetaSuppression_WebSearch_2026
```

Accordion sections added to `/home/adamsl/the-factory/public/index.html`.

### 4. LED trigger chain implemented

- Test ends with `await log("PASS: all ... assertions passed — test finished")`
- `normalizeLoggerMessage()` in the test ensures "finished" suffix is present → green LED
- `RemoteLogger.updatedLed()` matches "finished" substring → sets `background_color = "lightgreen"`
- Catch block emits `await log(\`ERROR: ${err.message}\`)` → red LED on failure

---

## What Still Needs to Be Done

### OPEN ISSUE: Accordion LED stays yellow despite tests passing

**Symptom:** Both tests pass (2/2) but `localhost:8080` accordion sections for
`LetabotMetaSuppression_SimpleQ_2026` and `LetabotMetaSuppression_WebSearch_2026` stay yellow.

**Likely causes to investigate (in order):**

1. **RemoteLogger not reaching Docker API** — Check if posts to `http://100.80.49.10:8284/...` are
   succeeding. The test catches logger errors but still continues. Run:
   ```bash
   curl -s "http://100.80.49.10:8284/libraries/local-php-api/object/select?object_view_id=LetabotMetaSuppression_SimpleQ_2026"
   ```
   If `null` → record not yet created (tests haven't run or logger failed).
   If empty or connection error → Docker API is down. See skill `manage-logger-api` to start it.

2. **Logger not initialized** — The test creates a `RemoteLogger` instance but if the initial `log()` call
   fails (network issue), `loggerReady` may stay false and all subsequent calls are silently skipped.
   Check: does `console.log` output appear during test run? That would confirm the logger wrapper fires
   even when the remote post fails.

3. **`normalizeLoggerMessage` not on the right `log()` wrapper** — There are TWO loggers in the test
   file (one for SimpleQ, one for WebSearch). Verify both have the same `normalizeLoggerMessage()` call.
   File: `/home/adamsl/letta-code/src/integration-tests/lettabot-meta-suppression.integration.test.ts`

4. **Browser cache** — Hard refresh with Ctrl+Shift+R on `localhost:8080`.

5. **Docker API CORS / rewrite config not injected** — After `docker compose up`, Apache rewrite config
   at `/home/adamsl/the-factory/api-routing.conf` must be re-injected into the container. See skill
   `logger-api-architecture`. Check: does `curl` to the API work, or does it 404?

### OPEN ISSUE: Letta 0.16.3 MCP streaming bug

Web searches via Scissari still won't return actual results even after the meta-only fix. The Exa MCP
tool fires but `tool_return_message` is never streamed back. Workaround options:
1. Route web searches through Hailey (separate agent with direct Exa access)
2. Upgrade Letta server to a version that properly streams MCP tool results
3. Implement client-side Exa search in the letta-code subprocess as a fallback

Diagnostic curl (check for `tool_return_message` absence):
```bash
curl -N -s "http://100.80.49.10:8283/v1/agents/agent-5955b0c2-7922-4ffe-9e43-b116053b80fa/messages/stream" \
  -H "Authorization: Bearer 6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Search for memfs"}],"stream_tokens":true}' \
  --max-time 30 | head -40
```

---

## Key File Locations

| What | Where |
|------|-------|
| lettabot core | `/home/adamsl/lettabot/src/core/bot.ts` |
| isMetaOnlyResponse() | `bot.ts` ~line 82 |
| sentAnyMessage bypass fix | `bot.ts` ~lines 1271 and 1344 |
| Integration test | `/home/adamsl/letta-code/src/integration-tests/lettabot-meta-suppression.integration.test.ts` |
| Logger helpers (IDs) | `/home/adamsl/letta-code/src/integration-tests/logger-helpers.ts` |
| Log viewer HTML | `/home/adamsl/the-factory/public/index.html` |
| Scissari web search skill | `/home/adamsl/letta-code/src/skills/custom/scissari-web-search-fix/SKILL.md` |
| Memory: web search bug | `/home/adamsl/.claude/projects/-home-adamsl-letta-code/memory/project_scissari_web_search_thoughts_only.md` |
| Memory: log viewer | `/home/adamsl/.claude/projects/-home-adamsl-letta-code/memory/reference_log_viewer_html.md` |

## Important Reminders

- Always use a **Haiku subagent** for file reads, writes, and bash command output — keeps main context clean
- The Docker Logger API at `100.80.49.10:8284` requires Apache rewrite config re-injection after fresh `docker compose up`
- Accordion sections in `index.html` are **hardcoded** — must add them manually when creating new logger IDs
- After editing `lettabot/src/core/bot.ts`, run `npm run build` in `/home/adamsl/lettabot` and restart the bot
- After editing `letta-code/src/`, run `bun run build` to rebuild `letta.js`
