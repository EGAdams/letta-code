---
name: debugging-executor-run
description: "Diagnoses executor_run failures (timeouts, allowlist blocks, server errors), guides log inspection, and safe executor restarts. Use when executor_run returns 500/408, allowlist errors, MCP connection failures, or other executor issues."
---

# Debugging Executor Run

## Quick Triage

1. Capture the exact failure mode (`500`, `408`, allowlist rejection, or connection error).
2. Record timestamp, request context, and the attempted command.
3. Classify the issue before changing configuration or restarting services.

## Log Discovery (use the script)

1. Run:

```bash
python scripts/find_executor_logs.py
```

2. Open the newest candidate logs first.
3. Inspect lines around the failure timestamp, for example:

```bash
tail -n 200 <log_path>
```

## Common Failures

- Allowlist blocks from `EXECUTOR_ALLOW_CMDS`.
- `500` errors caused by watchfiles reload loops.
- `408` timeouts from broad searches or long-running commands.
- MCP connection failure to `10.0.0.7:8789`.
- Executor server process not running.

## Safe Restart Steps

1. Retry once with a narrower command.
2. Apply minimal fixes (allowlist or reload settings) only if needed.
3. Restart the executor safely with your local service command:

```bash
<restart_command>
```

4. Wait for healthy startup logs before sending new `executor_run` calls.

## Verification

1. Re-run the failing `executor_run` request.
2. Confirm the response succeeds without `500`/`408`.
3. Confirm logs no longer show the original failure signature.
