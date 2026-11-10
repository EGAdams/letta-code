"""Read-only Worker Activity adapter.

The dashboard owns no StarTrekBridge/Codex task ledger.  This module reports
the bridge worker health source already owned by ``agent_bridge_poll`` and,
when explicitly configured, reads a local JSON snapshot supplied by the
worker.  Missing configuration is an honest unavailable state, not an empty
queue (which would hide stuck work).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from pydantic import ValidationError

from monitoring.supervisor_contracts import PublishedSupervisorState
from monitoring import agent_bridge_poll
from monitoring import model_registry
from monitoring import worker_restart
from monitoring import worker_lanes
from monitoring import worker_supervisor

DEFAULT_SNAPSHOT = Path(os.path.expanduser("~/.cache/agent_bridge/worker_activity.json"))
SNAPSHOT_STALE_SECONDS = 60
# Written every minute by agent_blocks' agent_bridge_worker.supervisor, which
# restarts a stopped or stalled worker (bounded). Shown as-is; never invented.
SUPERVISOR_HEALTH = Path(os.path.expanduser("~/.cache/agent_bridge/worker_health.json"))
# Written every poll cycle by the independent adw_supervisor process
# (monitoring/adw_supervisor.py), which runs outside this server and outside
# the bridge worker. Shown as-is; this module never runs its polling loop.
DEFAULT_ESCALATION_STATE = Path(os.path.expanduser("~/.cache/agent_bridge/adw_supervisor_state.json"))
ESCALATION_STALE_SECONDS = 120
# The gateway's own request supervision (agent_blocks' gateway/src/RequestWatch.php),
# read through gateway_alerts with the worker token and cached, so a 5 s page poll
# never becomes a 5 s gateway poll and a slow gateway never stalls this payload.
REQUESTS_CACHE_SECONDS = 30
_requests_cache: dict = {"at": 0.0, "value": None}


def _requests(now: float | None = None, source=None) -> dict:
    now = time.time() if now is None else now
    cached = _requests_cache["value"]
    if cached is not None and now - _requests_cache["at"] < REQUESTS_CACHE_SECONDS:
        return cached
    try:
        if source is None:
            import gateway_alerts
            source = gateway_alerts.from_environment()
        value = source.supervision()
    except Exception as exc:  # noqa: BLE001 -- this panel must never break Worker Activity
        value = {"available": False, "reason": f"request supervision could not be read: {type(exc).__name__}"}
    value = dict(value, fetched_at=now)
    _requests_cache.update(at=now, value=value)
    return value


def _supervisor() -> dict | None:
    try:
        value = json.loads(SUPERVISOR_HEALTH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(value, dict):
        return None
    keep = ("checked_at", "status", "reason", "action", "pid", "restarts_in_window", "max_restarts", "events")
    return {key: value.get(key) for key in keep}


def _escalation() -> dict:
    """The independent adw_supervisor process's own state file, read-only.
    Missing or stale is reported honestly -- never shown as "no escalations"."""
    configured = os.environ.get("ADW_SUPERVISOR_STATE_PATH")
    path = Path(configured).expanduser() if configured else DEFAULT_ESCALATION_STATE
    try:
        stat = path.stat()
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"available": False, "reason": "adw_supervisor has not written a state file; it may not be running."}
    except (OSError, ValueError) as exc:
        return {"available": False, "reason": f"adw_supervisor state file could not be read: {exc}"}
    if not isinstance(value, dict):
        return {"available": False, "reason": "adw_supervisor state file has an invalid shape."}
    try:
        value = PublishedSupervisorState.model_validate(value).model_dump()
    except ValidationError:
        return {"available": False, "reason": "adw_supervisor state file has invalid telemetry fields."}
    now = time.time()
    heartbeat = value.get("heartbeat_at") or value.get("generated_at")
    # A fresh file copy must not make an old supervisor heartbeat fresh.
    stamp = heartbeat if isinstance(heartbeat, (int, float)) and not isinstance(heartbeat, bool) else 0
    stale = now - min(stamp, stat.st_mtime) > ESCALATION_STALE_SECONDS or stamp > now + 5
    keep = ("generated_at", "heartbeat_at", "source", "ledger_error", "thresholds", "alerts", "worker_diagnostic", "worker_lanes", "queued_count", "models", "ok", "tasks", "coverage", "coverage_complete", "coverage_reason", "ledger_stale", "unknown_task_ids")
    out = {key: value.get(key) for key in keep}
    out["available"] = True
    out["stale"] = stale
    out["reason"] = "adw_supervisor's last heartbeat is older than expected." if stale else ""
    return out


def _snapshot() -> tuple[list[dict] | None, str | None, float | None, bool]:
    configured = os.environ.get("WORKER_ACTIVITY_SNAPSHOT")
    path = Path(configured).expanduser() if configured else DEFAULT_SNAPSHOT
    try:
        stat = path.stat()
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        source = "configured" if configured else "default"
        return None, f"The {source} worker task ledger is not present.", None, False
    except (OSError, ValueError) as exc:
        return None, f"The worker task ledger could not be read: {exc}", None, False
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        return None, "The worker task ledger has an invalid shape.", stat.st_mtime, False
    stale = time.time() - stat.st_mtime > SNAPSHOT_STALE_SECONDS
    return value, None, stat.st_mtime, stale


def payload() -> dict:
    tasks, error, snapshot_updated_at, snapshot_stale = _snapshot()
    if snapshot_stale and error is None:
        error = "The worker task ledger is stale; showing its last recorded events."
    worker = agent_bridge_poll.agent_bridge_poll_payload()
    service = worker.get("service", {})
    queue_depth = sum(1 for row in (tasks or []) if row.get("status") in {"queued", "pending"}) if tasks is not None else None
    service_model = agent_bridge_poll.ServiceState(**service)
    diagnosis = worker_supervisor.diagnose(
        service=service_model, state=worker.get("state"), tasks=tasks,
    )
    workers = worker_lanes.lane_reports()
    escalation = _escalation()
    seen = escalation.get("queued_count") if escalation.get("available") and not escalation.get("stale") else None
    if isinstance(seen, int) and not isinstance(seen, bool):
        queue_depth = max(queue_depth or 0, seen)   # never below what the local ledger shows
    return {
        "ok": True,
        "source": "configured-local-snapshot" if tasks is not None else "unavailable",
        "tasks": tasks or [],
        "tasks_available": tasks is not None,
        "tasks_error": error,
        "snapshot_updated_at": snapshot_updated_at,
        "snapshot_stale": snapshot_stale,
        # These are deliberately different signals: ledger queue depth is not
        # a count of processes. systemd owns the latter for this one worker.
        "queue_depth": queue_depth,
        "active_worker_count": sum(1 for lane in workers if lane.get("healthy")),
        "workers": workers,
        "diagnostic": diagnosis,
        "supervisor": _supervisor(),
        "escalation": escalation,
        "requests": _requests(),
        "provider_selection": model_registry.provider_selection_payload(),
        "worker": {
            "name": "agent-bridge-worker",
            "status": worker.get("polling", "unknown"),
            "reason": worker.get("reason", ""),
            "service": worker.get("service", {}),
            "state": worker.get("state"),
            "observed_at": worker.get("now"),
        },
        "restart": {
            "configured": worker_restart.configured(),
            "service": worker_restart.SERVICE,
        },
    }
