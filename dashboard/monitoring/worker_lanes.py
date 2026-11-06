"""Both bridge workers, observed one by one, read-only.

agent_blocks runs two worker processes (see `agent_bridge_worker/lanes.py`): the
`general` worker takes everything, and the `express` worker takes everything
except coding writes so a diagnostic never waits behind one. This module looks
at each through the checks that already existed for the single worker --
`agent_bridge_poll` (systemd + poll-state file) and `worker_supervisor.diagnose`
(process, heartbeat, queue) -- and reads each lane's own supervisor health file.

A lane whose unit was never installed is reported as "not installed", not as a
failure; an installed lane that is down is a failure, whichever lane it is.
"""
from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from monitoring import agent_bridge_poll, worker_supervisor

CACHE = Path(os.path.expanduser("~/.cache/agent_bridge"))
HEALTH_KEEP = ("checked_at", "status", "reason", "action", "pid", "restarts_in_window", "max_restarts", "events")


class LaneRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    service: str
    state_path: Path
    health_path: Path


LANES = (
    LaneRef(name="general", description="takes every task, including coding writes (one at a time, in order)",
            service="agent-bridge-worker.service",
            state_path=CACHE / "poll_state.json", health_path=CACHE / "worker_health.json"),
    LaneRef(name="express", description="never takes coding writes: diagnostics, Machine Ops and Notes run here",
            service="agent-bridge-worker-express.service",
            state_path=CACHE / "poll_state_express.json", health_path=CACHE / "worker_health_express.json"),
)


def _health(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return {key: value.get(key) for key in HEALTH_KEEP} if isinstance(value, dict) else None


def lane_report(lane: LaneRef, now: float,
                poll: Callable[..., dict] | None = None) -> dict:
    page = (poll or agent_bridge_poll.agent_bridge_poll_payload)(lane.service, lane.state_path)
    service = page.get("service", {})
    base = {"lane": lane.name, "description": lane.description, "service": lane.service,
            "supervisor": _health(lane.health_path)}
    if service.get("loaded") == "not-found":
        return {**base, "installed": False, "healthy": None, "status": "not installed",
                "reason": f"{lane.service} is not installed on this machine."}
    # A lane is judged on its own process and heartbeat. Queue age is a property of the whole queue, not of this
    # lane (a coding write waiting behind another is expected while `express` is idle), so it is judged elsewhere.
    diagnostic = worker_supervisor.diagnose(
        service=agent_bridge_poll.ServiceState(**service), state=page.get("state"), tasks=[], now=now)
    return {**base, "installed": True,
            "healthy": bool(diagnostic["process"]["present"] and diagnostic["heartbeat"]["fresh"]),
            "status": diagnostic.get("status", "unknown"), "reason": page.get("reason", ""),
            "polling": page.get("polling"), "service_state": service, "state": page.get("state"),
            "diagnostic": diagnostic}


def lane_reports(now: float | None = None,
                 poll: Callable[..., dict] | None = None) -> list[dict]:
    now = time.time() if now is None else now
    return [lane_report(lane, now, poll) for lane in LANES]
