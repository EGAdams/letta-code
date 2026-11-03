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
from pathlib import Path

from monitoring import agent_bridge_poll


def _snapshot() -> tuple[list[dict] | None, str | None]:
    configured = os.environ.get("WORKER_ACTIVITY_SNAPSHOT")
    if not configured:
        return None, "No task ledger is configured for this dashboard."
    try:
        value = json.loads(Path(configured).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "The configured worker task ledger is not present."
    except (OSError, ValueError) as exc:
        return None, f"The configured worker task ledger could not be read: {exc}"
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        return None, "The configured worker task ledger has an invalid shape."
    return value, None


def payload() -> dict:
    tasks, error = _snapshot()
    worker = agent_bridge_poll.agent_bridge_poll_payload()
    return {
        "ok": True,
        "source": "configured-local-snapshot" if tasks is not None else "unavailable",
        "tasks": tasks or [],
        "tasks_available": tasks is not None,
        "tasks_error": error,
        "worker": {
            "name": "agent-bridge-worker",
            "status": worker.get("polling", "unknown"),
            "reason": worker.get("reason", ""),
            "service": worker.get("service", {}),
            "state": worker.get("state"),
            "observed_at": worker.get("now"),
        },
    }
