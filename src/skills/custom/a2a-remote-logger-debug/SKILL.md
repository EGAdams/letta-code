---
name: a2a-remote-logger-debug
description: Debug and fix permanent remote logger disabling in a2a_communicating_agents Python agents (orchestrator_agent, coder_agent, etc.). Use when an agent's remote logger appears stuck at old timestamps despite the agent process running normally, or when logs show "[agent-name] Remote logger disabled:" in the agent's local log file.
---

# A2A Communicating Agents - Remote Logger Permanent Disable Bug

## Problem

Each agent in `/home/adamsl/planner/a2a_communicating_agents/` (orchestrator_agent, coder_agent, etc.) posts status updates to the remote logger API at `http://100.80.49.10:8284/libraries/local-php-api`. 

**The bug:** After any exception from the remote logger (such as `HTTP 422 Unprocessable Entity` or `timed out`), the global `_REMOTE_LOGGER_ENABLED` flag was permanently set to `False`. Once disabled, the agent would never post ANY future status updates — indefinitely — even though the agent process continued running normally.

**Observable symptom:** The log viewer at `localhost:8080` shows the logger stuck at an old timestamp (e.g., "44+ hours in the past") while the agent process is alive and logging to its local file.

## Root Cause

In each agent's `main.py`, the `log_update()` function had this pattern:

```python
_REMOTE_LOGGER_ENABLED = False  # Global flag

def log_update(msg: str):
    global _REMOTE_LOGGER_ENABLED
    if not _REMOTE_LOGGER_ENABLED:
        return
    
    try:
        # POST to remote logger
        response = requests.post(logger_api_url, ...)
        if response.status_code != 200:
            _REMOTE_LOGGER_ENABLED = False  # ← PERMANENT disable on any error
            log(f"[{agent_name}] Remote logger disabled: {response.status_code}")
            return
    except Exception as e:
        _REMOTE_LOGGER_ENABLED = False  # ← PERMANENT disable on any exception
        log(f"[{agent_name}] Remote logger disabled: {e}")
        return
```

Once `_REMOTE_LOGGER_ENABLED = False`, it was never reset, and the agent would silently skip all remote logger calls for the remainder of the process lifetime.

## The Fix

Replace the permanent-disable flag with a **60-second retry backoff**:

```python
import time

_REMOTE_LOGGER_RETRY_AFTER = 0.0  # time.monotonic() + seconds, or 0.0

def log_update(msg: str):
    global _REMOTE_LOGGER_RETRY_AFTER
    
    # Check if backoff period has expired
    now = time.monotonic()
    if now < _REMOTE_LOGGER_RETRY_AFTER:
        return  # Still in backoff; skip this call
    
    try:
        # POST to remote logger
        response = requests.post(logger_api_url, ...)
        if response.status_code != 200:
            _REMOTE_LOGGER_RETRY_AFTER = now + 60.0  # Backoff 60 seconds
            log(f"[{agent_name}] Remote logger HTTP {response.status_code}, retry in 60s")
            return
        # SUCCESS: reset backoff timer so next call goes through immediately
        _REMOTE_LOGGER_RETRY_AFTER = 0.0
    except Exception as e:
        _REMOTE_LOGGER_RETRY_AFTER = now + 60.0  # Backoff 60 seconds
        log(f"[{agent_name}] Remote logger error: {e}, retry in 60s")
        return
```

**Key changes:**
1. Replace `_REMOTE_LOGGER_ENABLED` (boolean) with `_REMOTE_LOGGER_RETRY_AFTER` (float timestamp).
2. On exception or HTTP error, set `_REMOTE_LOGGER_RETRY_AFTER = time.monotonic() + 60.0`.
3. On success, reset `_REMOTE_LOGGER_RETRY_AFTER = 0.0` so the next call goes through immediately.
4. At the start of `log_update()`, check if `now < _REMOTE_LOGGER_RETRY_AFTER` before attempting the POST.

## Affected Files

Located in `/home/adamsl/planner/a2a_communicating_agents/`:

- `orchestrator_agent/main.py`
- `coder_agent/main.py`
- (and any other agent `main.py` with the same `_REMOTE_LOGGER_ENABLED` pattern)

## Diagnosis Checklist

### 1. Check agent local log for the disable marker

```bash
tail -f /home/adamsl/planner/a2a_communicating_agents/orchestrator_agent/logs/agent.log
```

Look for lines like:
```
[orchestrator] Remote logger disabled: HTTP 422
[orchestrator] Remote logger disabled: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
```

If present, the flag is stuck `False`.

### 2. Verify the viewer timestamp is stale

Open `localhost:8080` and check the corresponding agent's accordion (e.g., `Orchestrator_2026`):
- Note the **last log timestamp** (e.g., "2026-05-18 12:34:56")
- Compare with current time. If >1 hour old and the agent process is running, the flag is likely stuck.

### 3. Confirm agent process is alive

```bash
ps aux | grep orchestrator_agent
# or
ps aux | grep coder_agent
```

If the process is still running, but the logger is stuck, the bug is confirmed.

## Verification After Fix

1. **Apply the 60-second retry backoff fix** to the agent's `main.py`.

2. **Restart the agent process:**
   ```bash
   # Kill the existing process
   pkill -f orchestrator_agent
   pkill -f coder_agent
   
   # Restart (exact command depends on your setup)
   ```

3. **Wait up to 60 seconds** for the first retry attempt.

4. **Check the viewer:**
   - Refresh `localhost:8080`
   - The accordion should now show a recent timestamp (within the last minute)
   - New log entries should appear as the agent runs

5. **Tail the local log** to confirm no more "Remote logger disabled" messages:
   ```bash
   tail -f /home/adamsl/planner/a2a_communicating_agents/orchestrator_agent/logs/agent.log
   ```

   Expected output: No "disabled" messages; normal progress logs instead.

## Why 60 seconds?

- **Too short** (e.g., 5 seconds): Can hammer an unstable API and exhaust retries faster.
- **Too long** (e.g., 5 minutes): Operator has to wait too long between noticing failure and recovery.
- **60 seconds** strikes a balance: enough breathing room for transient failures (TCP backoff, server restart), short enough for human awareness.

If the remote logger API has sustained outages, adjust:
```python
_REMOTE_LOGGER_RETRY_AFTER = now + 120.0  # 2 minutes for very unstable API
```

## Integration with Remote Logger API Health

The remote logger API at `http://100.80.49.10:8284/libraries/local-php-api` occasionally returns:
- **HTTP 422 Unprocessable Entity** — malformed request or entity
- **HTTP 500 Internal Server Error** — server-side database or file system issue
- **Connection timeouts** — network issues or server overload

These are **transient failures** — they may resolve within seconds or minutes. The 60-second backoff gives the API time to recover.

If failures persist beyond 60 seconds, investigate the API:

```bash
# Check Docker container status
docker ps -a | grep logger

# View API container logs
docker logs logger-api-php

# Manual API health check
curl -i http://100.80.49.10:8284/libraries/local-php-api/health
```

## Summary

| Before Fix | After Fix |
|---|---|
| One HTTP 422 error → logger permanently disabled → agent silent forever | One HTTP 422 error → 60-second backoff → agent retries → (if API recovers) logger resumes |
| Operator must restart agent process to recover | No restart needed; automatic recovery after 60 seconds |
| Log viewer stuck at old timestamp (confusing, silent failure) | Log viewer updates within 60s of API recovery (transparent retry) |

## Reference

- Skill: `remote-logger-implementation` — general RemoteLogger documentation and API details
- Skill: `managing-logger-api` — how to troubleshoot the PHP API itself (Docker, disk space, etc.)
- Letta Code issue tracker — search for "remote logger" for any concurrent refactoring

## Related Python Agents

The a2a_communicating_agents system includes:
- `orchestrator_agent` — main orchestrator
- `coder_agent` — code generation and execution
- (and potentially others in `/home/adamsl/planner/a2a_communicating_agents/`)

All follow the same pattern. **Apply the fix to every agent that has `_REMOTE_LOGGER_ENABLED`.**

## Additional Pitfall: clear_logs() Resets LED After PASS Trigger

In a2a agent systems, `clear_logs()` (and `flush_logs()`) in `remote_logger.py` explicitly reset the monitor LED to the default yellow state. This causes a common LED color bug:

**The problem:**
```python
log_update("PASS: coder ready — subscribed and waiting for tasks finished")
# LED turns green ✓

try:
    self.logger.clear_logs("ready.")  # ← BAD: resets LED to yellow
except Exception:
    pass
# LED turns yellow ✗ (overwrites the PASS signal)
```

**The rule:**
- **Never** call `self.logger.clear_logs()` or `self.logger.flush_logs()` after a PASS/green trigger
- These methods always reset `self.monitor_led` to default yellow and post that state to the API
- If you need to clear the log terminal, do so before calling the PASS trigger
- Or wrap the clear in a try-except that **logs a new PASS message after clearing** to restore green

**Correct pattern:**
```python
# Option 1: clear before the PASS trigger
self.logger.clear_logs("ready.")
log_update("PASS: coder ready — subscribed and waiting")

# Option 2: if clear is needed after PASS, re-trigger green
log_update("PASS: coder ready — subscribed and waiting")
try:
    self.logger.clear_logs("ready.")
    log_update("PASS: ready")  # ← Re-trigger green after clear
except Exception:
    pass
```

## Key File Locations for Quick Diagnosis

When debugging LED color issues, remote logger failures, or multi-agent state problems in `/home/adamsl/planner/a2a_communicating_agents/`:

| What | Path |
|------|------|
| **Agent Source Code** | |
| Orchestrator agent main | `/home/adamsl/planner/a2a_communicating_agents/orchestrator_agent/main.py` |
| Coder agent main | `/home/adamsl/planner/a2a_communicating_agents/coder_agent/main.py` |
| **Shared Modules** | |
| Remote logger (LED logic, clear_logs bug) | `/home/adamsl/planner/a2a_communicating_agents/orchestrator_agent/remote_logger.py` |
| **Local Logs** | |
| Orchestrator log file | `/home/adamsl/planner/logs/orchestrator.log` |
| Coder agent log file | `/home/adamsl/planner/a2a_communicating_agents/logs/coder_agent.log` |
| **Process Control** | |
| Stop orchestrator | `bash /home/adamsl/planner/a2a_communicating_agents/stop_orchestrator.sh` |
| Start orchestrator | `bash /home/adamsl/planner/a2a_communicating_agents/start_orchestrator.sh` |
| Stop coder agent | `bash /home/adamsl/planner/a2a_communicating_agents/stop_coder_agent.sh` |
| Start coder agent | `bash /home/adamsl/planner/a2a_communicating_agents/start_coder_agent.sh` |
| **Web Viewer & API** | |
| Web viewer | `http://localhost:8080` (check accordion timestamps and LED colors) |
| Logger API query | `curl -s "http://100.80.49.10:8284/libraries/local-php-api/object/select?object_view_id=<ID>"` |

**Typical debug flow:**
1. Check web viewer at `http://localhost:8080` — note accordion timestamps and LED colors
2. Tail local log: `tail -f /home/adamsl/planner/logs/orchestrator.log`
3. Look for "Remote logger disabled" or "PASS" followed by yellow LED
4. If PASS was logged but LED is yellow, check for `clear_logs()` or `flush_logs()` immediately after
5. If logger is stuck at old timestamp, verify process is running: `ps aux | grep orchestrator_agent`
6. If stuck, check for permanent disable marker in log, then apply the 60-second retry backoff fix
