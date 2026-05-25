---
name: scissari-hailey-pairing
description: Ensure Scissari and Hailey have the required Exa, executor, and Letta multi-agent communication tools; troubleshoot Scissari-to-Hailey hangs after Skill or send_message_to_agent_and_wait_for_reply; and capture the pinned-CLI/SDK continuation failure path when approval or tool-return metadata is lost.
---

# Scissari Hailey Pairing

Use this skill whenever Scissari, Hailey, or their agent-to-agent messaging/tool setup is involved.

## Agent IDs

- Scissari: `agent-5955b0c2-7922-4ffe-9e43-b116053b80fa`
- Hailey: `agent-2b4f760c-e22a-4b6a-9c8d-0ace7b9bac03`

## Required Tools

Both agents must have:

- `web_fetch_exa`
- `executor_run`
- `web_search_exa`
- `send_message_to_agent_async`
- `send_message_to_agent_and_wait_for_reply`

## First Step

Before relying on the pair, verify and repair their tool attachments:

```bash
python3 <SKILL_DIR>/scripts/ensure_pair_tools.py
```

Use `--dry-run` to inspect without attaching missing tools.

Use `--exact` when Scissari must match Hailey exactly and any stray legacy tools should be removed:

```bash
python3 <SKILL_DIR>/scripts/ensure_pair_tools.py --exact
```

Run this even if the tools were present earlier. Scissari's tool set has regressed before after manual changes, so treat verification as part of the workflow.

The ensure script reports both `missing_before` and `extra_before`. If Scissari shows only `fetch_webpage` and `web_search`, or shows those two in addition to the Exa/multi-agent tools, run the script with `--exact`.

## Skill Source Precedence

Letta Code loads project skills from `.skills/` before bundled skills from `src/skills/builtin/`. If behavior looks stale, inspect the project copy first:

```bash
sed -n '1,120p' /home/adamsl/letta-code/.skills/messaging-agents/SKILL.md
```

An old project-level `messaging-agents` skill can override the fixed bundled copy and tell Scissari to run a nested `letta -p` command. That nested CLI path is hang-prone and must not be used when the multi-agent tools are available.

## Local CLI Pinning

When debugging Scissari-to-Hailey failures, use the locally checked-out `letta-code` CLI/runtime rather than a global or stale SDK install.

This mattered in the May 2026 failure path because the local client was not reliably preserving the stream events needed for continuation. Pinning to the repo copy kept the execution path aligned with the patched `approval_request_message`, `stop_reason`, and tool-fallback handling.

If the tool call path looks suspicious, verify both:

- the CLI you launched is the repo-pinned one
- the server you are talking to is the real local API on port `8091`

## Messaging Rule

When Scissari sends a message to Hailey, Scissari must use:

```typescript
send_message_to_agent_and_wait_for_reply({
  other_agent_id: "agent-2b4f760c-e22a-4b6a-9c8d-0ace7b9bac03",
  message: "..."
})
```

Do not use `send_message_to_agent_async` for Scissari-to-Hailey requests unless the user explicitly asks for fire-and-forget delivery. Scissari must wait for Hailey's answer, read it, and incorporate it before continuing.

If `send_message_to_agent_and_wait_for_reply` is missing, stop and run the ensure script. If the tool still cannot be attached or called, report the failure instead of sending an async message.

## Known Continuation Failure

There is a confirmed May 2026 failure where Scissari could not reach Hailey even though tools were attached:

- The server streamed `approval_request_message` for `Skill(messaging-agents)` and then ended with `stop_reason: end_turn`, so the client did not execute the Skill.
- After that was patched, Scissari streamed `tool_call_message` for `send_message_to_agent_and_wait_for_reply` and again ended with `stop_reason: end_turn`, with no `tool_return_message`.
- The SDK/client layer dropped or lost `approval_request_message` and `stop_reason` in some paths, so continuation logic never saw the approval boundary or the final turn state.
- Some `tool_call_message` payloads arrived with tokenized or chunked `arguments`, so the fallback needed to reassemble the tool-call payload before dispatching it.
- `runs.messages.list` contained only `user_message` rows and `runs.steps.list` had `messages: []`.
- A narrow client fallback was added in `src/agent/multi-agent-tool-fallback.ts`, with call sites in `src/headless.ts` and `src/cli/App.tsx`.
- That fallback should stay in place as the guarded path for the local CLI and should continue to prefer the client path that preserves approval and tool-return metadata over a stale SDK stream.

If this comes back, use `$letta-run-message-troubleshooting` and read:

```text
/home/adamsl/.codex/skills/letta-run-message-troubleshooting/references/scissari-hailey-tool-continuation.md
```

Do not treat the issue as fixed just because the user sees a reply. The server-side persistence bug remains until source runs persist assistant/tool messages, not just user messages.

## Lettabot Fallback

If the direct client path regresses again, fall back to `lettabot` as the operational bridge and verify it against the real local API on `8091`.

Use the fallback to answer three questions:

- did the approval event arrive
- did the tool-call arguments survive intact
- did the run produce a `tool_return_message` before `stop_reason: end_turn`

## Known Tool-Wipe Root Cause

There is also a confirmed May 4, 2026 regression where Scissari's attached tools were rewritten back to the old two-tool base set:

- Observed live state: Scissari had only `fetch_webpage` and `web_search`, while Hailey still had the expected five-tool Exa/executor/multi-agent set.
- Root cause in `letta-code`: [src/cli/App.tsx](/home/adamsl/letta-code/src/cli/App.tsx) called `reconcileExistingAgentState()` on load, and the old implementation in [src/agent/reconcileExistingAgentState.ts](/home/adamsl/letta-code/src/agent/reconcileExistingAgentState.ts) force-set `tool_ids` to exactly `web_search` and `fetch_webpage`.
- That code path has been patched so existing agents no longer have their server-side tools rewritten during normal load/resume.

If this symptom returns, check:

- whether the local `letta-code` checkout includes the patched `reconcileExistingAgentState.ts`
- whether Scissari's live tool list shows only the two legacy defaults
- whether `ensure_pair_tools.py --exact` restores parity but a later app load wipes it again

## Tool Verification API Quirk (Letta 0.16.3)

`client.agents.retrieve(agentId).tools` always returns `[]` on Letta 0.16.3 even when tools are attached. **Do not use this to diagnose missing tools.** Use the dedicated endpoint instead:

```bash
curl -s http://100.80.49.10:8283/v1/agents/agent-5955b0c2-7922-4ffe-9e43-b116053b80fa/tools | python3 -m json.tool | grep '"name"'
```

Or run the ensure script with `--dry-run` — it uses `/v1/agents/{id}/tools` and reports the real list.

## "Machinating Forever" Hang Diagnosis (Fixed 2026-05-07)

**Symptom:** Scissari is stuck on the "machinating…" spinner for 8+ minutes in the Letta Code TUI after completing tool calls. The token counter ticks up slowly but no response appears.

**Root cause:** When Scissari's server turn ends with `stop_reason: end_turn` AND `serverToolCalls` contains a `send_message_to_agent_and_wait_for_reply` or `send_message_to_agent_async` call, the letta-code client-side fallback (`src/agent/multi-agent-tool-fallback.ts`) intercepts it and executes it locally. Before the fix there was no timeout: if the target agent (e.g. China, Hailey on a slow model) takes 8+ minutes to reply, the CLI freezes for the entire duration with the spinner still showing.

**Fix (applied 2026-05-07):** `AGENT_REPLY_TIMEOUT_MS = 90_000` via `Promise.race` in `sendMessageToAgentAndCollectReply`. Both the first attempt and the retry are now wrapped in try/catch. A timeout produces a clean `status: "error"` tool result back to Scissari so she can respond rather than the CLI hanging indefinitely.

**File:** `src/agent/multi-agent-tool-fallback.ts` — `sendMessageToAgentAndCollectReply` and `executeMultiAgentToolCall`.

**Verify the fix is present:**
```bash
grep -n "AGENT_REPLY_TIMEOUT_MS\|Promise.race" /home/adamsl/letta-code/src/agent/multi-agent-tool-fallback.ts
```

## LettaBot "Conversation Busy" 409 Bug (Fixed 2026-05-06)

**Symptom:** User sends Scissari a Telegram message; bot returns an error or stalls. LettaBot logs show `[Bot] CONFLICT detected - attempting orphaned approval recovery...` even though there is no orphaned approval — just a second Telegram message arriving while the first is still being processed.

**Root cause:** `isApprovalConflictError()` in `lettabot/src/core/bot.ts` matched ALL 409 responses by status code, including the "conversation is currently being processed" busy 409. Busy 409s were routed to approval recovery (wrong path), which failed, and the error was rethrown to the user.

**Fix location:** `lettabot/src/core/bot.ts`

- Added `isConversationBusyError()` — detects "is currently being processed" in both `error.message` and nested SDK `error.error.detail`.
- `isApprovalConflictError()` now returns `false` early when `isConversationBusyError()` is true.
- `runSession()` has a `trySend()` retry loop: up to 3 retries with 8s → 16s → 32s delays for busy 409s.

**Verify the fix is present:**

```bash
grep -n "isConversationBusyError\|Conversation busy" /home/adamsl/lettabot/src/core/bot.ts
```

If the function is missing, the fix has regressed — re-apply from the scissari-telegram-tool-loop-fix skill.

## Message Shape

Ask Hailey for a concrete answer, not just acknowledgement. Prefer:

```text
Hailey, please answer this request and include enough detail for Scissari to continue:

<request>
...
</request>
```

After Hailey replies, Scissari should summarize Hailey's answer to the user and say what action it changes or confirms.
