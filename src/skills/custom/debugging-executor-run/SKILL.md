---
name: debugging-executor-run
description: "Diagnoses executor_run failures — covers both (A) letta-code client not recognizing the tool (shows 'Cancelled' or 'Tool not found'), and (B) the executor server itself failing (timeouts, allowlist blocks, 500/408 errors). Use when executor_run calls produce no output, return errors, or get cancelled without running."
---

# Debugging Executor Run

## Quick Triage: Permission Mode First

**Before diving into executor_run specifics:** If the agent seems stuck waiting for approval on EVERY tool call (not just executor_run), the issue is likely a missing `permissionMode` in `~/.letta/settings.json`, not executor_run itself. See the "Agent permission modes" memory entry.

## Two distinct failure modes

### Mode A — tool shows "⎿  Cancelled" or stream interrupted

**Symptom:** `executor_run` (or any Letta tool) shows `⎿  Cancelled` in the letta-code display.

**How to distinguish the cause:**
- `executor_run` is a **server-side** tool (comes through as `tool_call_message`, NOT `approval_request_message`)
- The "Cancelled" display happens when the **stream is interrupted mid-execution** — e.g. the user types a new message while the server is still running the tool
- This is a display artefact; the server may have completed the tool call successfully or errored separately

**What actually happened (2026-05-12 investigation):**
Scissari's `executor_run` calls showed "Cancelled" because the user typed "Please continue"
while the server was still processing the tool. The stream was interrupted, letta-code marked
the in-flight `tool_call_message` as cancelled in the UI. The REAL failure was the executor
server returning `HTTP 400: Command not in allowlist` (see Mode B below).

**Client-side executor_run implementation (2026-05-12, now in source):**
A client-side implementation was added to `src/tools/toolDefinitions.ts` as a fallback. Since
`executor_run` normally comes through as `tool_call_message` (server-side), this fallback
is NOT triggered in normal use. It would only activate if executor_run somehow appeared in
an `approval_request_message` (e.g., in a future Letta version that routes it client-side).
The fallback is harmless. Don't remove it; it may be useful if the executor server is broken.

**General pattern — adding a client-side fallback for any Letta tool:**
If you need letta-code to handle a tool locally when the server can't execute it:
1. `src/tools/schemas/YourTool.json` — JSON schema
2. `src/tools/impl/YourTool.ts` — implementation function
3. `src/tools/toolDefinitions.ts` — register in `toolDefinitions` object
4. `src/tools/manager.ts` — add to `TOOL_PERMISSIONS`; if shell-like, add to `STREAMING_SHELL_TOOLS`
5. `src/cli/helpers/toolNameMapping.ts` — if shell-like, add to `isShellTool()` and `getDisplayToolName()`

---

### Mode B — executor server itself is failing (original content)

**Quick Triage**

1. Capture the exact failure mode (`500`, `408`, allowlist rejection, or connection error).
2. Record timestamp, request context, and the attempted command.
3. Classify the issue before changing configuration or restarting services.

**Log Discovery (use the script)**

```bash
python scripts/find_executor_logs.py
```

Open the newest candidate logs first, then inspect around the failure timestamp:

```bash
tail -n 200 <log_path>
```

**Executor service location:** `10.0.0.7:8789` (reachable from WSL as of 2026-05-12; returns 404 at `/` which is normal — actual endpoints are `/execute` etc.)

**Known allowlist block (2026-03-15):** `/home/adamsl/letta-code/scripts/run-local-in-dir.sh` was blocked.
`run-local-in-dir.sh` runs the letta binary from a target directory. Add it to `EXECUTOR_ALLOW_CMDS`.

**Common Failures**

- Allowlist blocks from `EXECUTOR_ALLOW_CMDS` → HTTP 400, `detail: "Command not in allowlist: <path>"`
- `500` errors caused by watchfiles reload loops.
- `408` timeouts from broad searches or long-running commands.
- MCP connection failure to `10.0.0.7:8789`.
- Executor server process not running.

**Safe Restart Steps**

1. Retry once with a narrower command.
2. Apply minimal fixes (allowlist or reload settings) only if needed.
3. Restart the executor safely with your local service command:

```bash
<restart_command>
```

4. Wait for healthy startup logs before sending new `executor_run` calls.

**Verification**

1. Re-run the failing `executor_run` request.
2. Confirm the response succeeds without `500`/`408`.
3. Confirm logs no longer show the original failure signature.

---

### Mode C — tool_call_message streams but end_turn fires before tool_return_message

**Symptom:** Scissari calls `executor_run`, the stream shows:
```
[drainStream] stopReason="end_turn" approvals=0 approvalRequestEndedTurn=false
● Executor(ls)
────────────────────────────────────────────────────────────────────────────────
> 
```
No tool result shown. No follow-up from Scissari. Prompt returns immediately.

**Root cause:** Letta 0.16.3 streams `tool_call_message` for `executor_run`, then sends `stop_reason: end_turn` **without a `tool_return_message`** (verified by reading the chunk log at `~/.letta/logs/chunk-logs/<agent-id>/<session>.jsonl`). The server expects the client to execute the tool and send results back.

**Where the fix lives (implemented 2026-05-15):**
`src/agent/multi-agent-tool-fallback.ts` — the `CLIENT_SIDE_FALLBACK_TOOLS` set:
```typescript
const CLIENT_SIDE_FALLBACK_TOOLS = new Set(["executor_run"]);
```

When `collectPendingMultiAgentToolCalls()` sees a pending `executor_run` in `buffers.serverToolCalls` at `end_turn`, it now collects it. `executePendingMultiAgentToolCalls()` dispatches to `executeClientSideTool()` which runs it via the local `executor_run` implementation in `src/tools/impl/Bash.ts`.

Both App.tsx (interactive) and headless.ts automatically benefit from this fix — they both call `collectPendingMultiAgentToolCalls` after `end_turn`.

**To diagnose in future:** Check the chunk log for the most recent session:
```bash
ls -lt ~/.letta/logs/chunk-logs/<agent-id>/
cat <newest>.jsonl | python3 -c "
import sys, json
for l in sys.stdin:
    c = json.loads(l)
    print(c.get('message_type'), c.get('stop_reason',''))
"
```
If you see `tool_call_message` immediately followed by `stop_reason: end_turn` with NO `tool_return_message`, Mode C is the issue.

**Adding more tools to CLIENT_SIDE_FALLBACK_TOOLS:**
If a new Letta server-side tool exhibits Mode C behavior, add its name to `CLIENT_SIDE_FALLBACK_TOOLS` and add a dispatch branch in `executeClientSideTool()` in `multi-agent-tool-fallback.ts`.
