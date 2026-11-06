"""Read-only diagnostics for the local agent bridge worker.

This module deliberately has no restart capability.  ``systemctl`` describes a
unit; it does not prove that the expected worker process is alive, nor that it
is making progress.  The supervisor combines three independent observations:
the service PID, its exact local ``/proc`` command line, and worker telemetry.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from monitoring import agent_bridge_poll
from monitoring.task_timing import queue_age


DEFAULT_STAGNATION_SECONDS = 300.0


@dataclass(frozen=True)
class ProcessObservation:
    pid: int
    present: bool
    command: str = ""
    reason: str = ""


class ProcessProbe(Protocol):
    def inspect(self, pid: int) -> ProcessObservation: ...


class ProcWorkerProbe:
    """Proves the configured systemd PID is a bridge worker, locally."""

    def inspect(self, pid: int) -> ProcessObservation:
        if not pid:
            return ProcessObservation(0, False, reason="systemd did not report a worker PID")
        try:
            command = " ".join(
                part.decode("utf-8", errors="replace")
                for part in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
                if part
            )
        except OSError as exc:
            return ProcessObservation(pid, False, reason=f"cannot inspect local PID {pid}: {exc}")
        if not command:
            return ProcessObservation(pid, False, reason=f"local PID {pid} has no command line")
        # The unit runs `adws/adw_bridge_worker.py --watch`; the package is agent_bridge_worker.
        if not any(name in command for name in ("adw_bridge_worker", "agent-bridge-worker", "agent_bridge_worker")):
            return ProcessObservation(pid, False, command,
                                      "systemd PID is not the expected bridge worker")
        return ProcessObservation(pid, True, command, "expected bridge worker process is present")


def _epoch(value) -> float | None:
    try:
        return float(value) if isinstance(value, (int, float)) else datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        ).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def _freshness(state: dict | None, now: float) -> tuple[bool, str, float | None]:
    if not state:
        return False, "worker has not written a heartbeat", None
    # poll_state.json (agent_bridge_worker/watch.py) writes checked_at and, while
    # waiting, next_check_at. A wait can legitimately be long (error backoff up to
    # 15 min), and a drain of several tasks writes nothing until it ends, so a
    # fixed age limit on checked_at would call a healthy worker stalled.
    due = _epoch(state.get("next_check_at")) if state.get("phase") == "waiting" else None
    if due is not None:
        grace = float(os.environ.get("WORKER_WAIT_GRACE_SECONDS", "180"))
        late = now - due
        return late <= grace, (f"next check due in {-late:.0f}s" if late <= 0
                               else f"next check {late:.0f}s overdue (grace {grace:.0f}s)"), max(0.0, late)
    value = state.get("heartbeat_at") or state.get("checked_at") or state.get("last_check_at") or state.get("updated_at")
    if not value:
        return False, "worker state has no heartbeat timestamp", None
    try:
        stamp = float(value) if isinstance(value, (int, float)) else datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        ).timestamp()
    except (TypeError, ValueError, OverflowError):
        return False, "worker heartbeat timestamp is invalid", None
    age = max(0.0, now - stamp)
    limit = float(os.environ.get("WORKER_WORKING_MAX_AGE_SECONDS", "1500") if state.get("phase") == "working"
                  else os.environ.get("WORKER_HEARTBEAT_MAX_AGE_SECONDS", "120"))
    return age <= limit, f"heartbeat age is {age:.0f}s (limit {limit:.0f}s)", age


def _queue_diagnostic(tasks: list[dict], now: float) -> tuple[bool, str]:
    queued = [task for task in tasks if task.get("status") in {"queued", "pending"}]
    if not queued:
        return False, "no queued work"
    threshold = float(os.environ.get("WORKER_STAGNATION_SECONDS", DEFAULT_STAGNATION_SECONDS))
    ages = [queue_age(task, now) for task in queued]
    stale = [age for age in ages if age is not None and age >= threshold]
    if stale:
        return True, f"{len(stale)} queued task(s) have waited at least {threshold:.0f}s"
    if any(age is None for age in ages):
        return False, "queued task age unavailable; queue health unknown"
    return False, f"{len(queued)} queued task(s), none older than {threshold:.0f}s"


def diagnose(*, service: agent_bridge_poll.ServiceState, state: dict | None,
             tasks: list[dict] | None, probe: ProcessProbe | None = None,
             now: float | None = None) -> dict:
    """Return a conservative, actionable diagnosis; never infer success."""
    now = time.time() if now is None else now
    process = (probe or ProcWorkerProbe()).inspect(service.pid)
    heartbeat_ok, heartbeat_reason, heartbeat_age = _freshness(state, now)
    stagnant, queue_reason = _queue_diagnostic(tasks or [], now) if tasks is not None else (False, "task ledger unavailable")
    reasons = [process.reason, heartbeat_reason, queue_reason]
    if not process.present:
        status = "offline"
        action = "Inspect the local worker unit and process; do not assume systemd active means work is running."
    elif not heartbeat_ok:
        status = "stalled"
        action = "Inspect worker logs and heartbeat writer; restart only through the authorized worker adapter."
    elif stagnant:
        status = "stalled"
        action = "Inspect queue ownership and worker logs; queued work has not advanced."
    elif tasks is None or "unknown" in queue_reason:
        status = "unknown"
        action = "Task queue telemetry is incomplete; inspect the ledger before declaring queue health."
    else:
        status = "healthy"
        action = "No action indicated by local process, heartbeat, and queue observations."
    attempts = sum(
        int(task.get("attempts", 0))
        for task in (tasks or [])
        if isinstance(task.get("attempts", 0), (int, float))
    )
    return {
        "status": status,
        "action": action,
        "reasons": reasons,
        "process": {"pid": process.pid, "present": process.present, "command": process.command},
        "heartbeat": {"fresh": heartbeat_ok, "age_seconds": heartbeat_age},
        "queue": {"available": tasks is not None, "stagnant": stagnant,
                   "attempts": attempts, "reason": queue_reason},
    }
