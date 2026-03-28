---
name: fixing-stream-errors
description: Diagnoses and fixes recurring stream/error-handling bugs in the letta-code source (App.tsx, turn-recovery-policy.ts, errorFormatter.ts). Use when the user reports a raw JSON error dump in the TUI, a provider error (ChatGPT/OpenAI/Anthropic) that isn't being retried, an approval-pending conflict that loops and then errors out, or any ⚠ error that surfaces repeatedly from agent streaming.
---

# Fixing Stream Errors

## Key Files

| File | Role |
|------|------|
| `src/agent/turn-recovery-policy.ts` | Retry/recovery classifiers — add new retryable patterns here |
| `src/cli/App.tsx` | TUI stream loop, approval recovery, error display (~line 5490+) |
| `src/cli/helpers/errorFormatter.ts` | User-facing error text, retry status messages |
| `src/agent/approval-recovery.ts` | `fetchRunErrorDetail` — extracts detail from nested run metadata |

## Recurring Error Classes

### 1. Provider error not being retried (shows raw error instead of silently retrying)

**Symptom:** User sees `⚠ ChatGPT request failed ...` or similar provider error text.

**Root cause:** The error's detail string doesn't match any entry in `RETRYABLE_PROVIDER_DETAIL_PATTERNS` in `turn-recovery-policy.ts`.

**Fix:**
1. Identify the new detail string fragment (e.g. `"ChatGPT request failed"`).
2. Add it to `RETRYABLE_PROVIDER_DETAIL_PATTERNS` in `src/agent/turn-recovery-policy.ts`.
3. Add a matching entry in `getRetryStatusMessage` in `src/cli/helpers/errorFormatter.ts` so the retry shows a friendly status line.
4. Run `bun test src/tests/turn-recovery-policy.test.ts src/tests/cli/errorFormatter.test.ts`.

### 2. Raw JSON dump `⚠ { "error": { "error": { ... } } }`

**Symptom:** Error is printed as indented JSON rather than a readable message.

**Root cause:** The run metadata has a doubly-nested shape:
```
run.metadata.error = { error: { detail: "...", message: "..." }, run_id: "..." }
```
The error display code in App.tsx around line 5950 casts `run.metadata.error` as
`{ type?, message?, detail? }` and misses the nested `.error.detail`. When
`serverErrorDetail` is null, `errorObject` is passed to `formatErrorDetails` which
falls back to `JSON.stringify`.

**Fix:**
- Extend the cast to include `error?: { type?, message?, detail? }`.
- Set `serverErrorDetail` to `errorData.error?.detail ?? errorData.error?.message` as additional fallbacks.
- When `serverErrorDetail` is non-null, call `formatErrorDetails(serverErrorDetail, agentId)` instead of `formatErrorDetails(errorObject, agentId)`.

### 3. Approval-pending conflict loops until retries exhausted, then errors

**Symptom:**
```
⚠ CONFLICT: Cannot send a new message: The agent is waiting for approval on a tool call.
⚠ Something went wrong? Use /feedback to report issues.
```

**Root cause:** The `approvalPendingDetected` recovery block auto-denies pending approvals and retries. If the agent just creates a new approval request on each retry, all 3 attempts are consumed and the error falls through to the display path.

**Fix:** In App.tsx in the `approvalPendingDetected` block (search for `"Check for approval pending error"`):
1. Fetch pending approvals first.
2. **If approvals found**: surface the approval dialog (set `setPendingApprovals`, preserve the user's in-flight message via `setRestoredInput`, `setStreaming(false)`, `return`). Same pattern as the `invalidIdsDetected` block above it.
3. **If no approvals found** (stale state): auto-deny and retry within the budget (current fallback behavior).

## Run Metadata Structure (Letta 0.16.3)

`fetchRunErrorDetail` in `src/agent/approval-recovery.ts` correctly handles both flat and doubly-nested shapes:
- Flat: `metaError.detail` or `metaError.message`
- Nested: `metaError.error.detail` or `metaError.error.message`

The error display in App.tsx re-fetches the run independently and has historically used the wrong cast. Always use `fetchRunErrorDetail` when you only need the detail string.

## Testing

```bash
bun test src/tests/turn-recovery-policy.test.ts
bun test src/tests/cli/errorFormatter.test.ts
bun test src/tests/cli/zaiErrors.test.ts
```

See `references/error-shapes.md` for documented run metadata structures and stream chunk shapes.
