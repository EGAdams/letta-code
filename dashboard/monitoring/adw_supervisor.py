"""Independent read-only ADW supervisor. See docs/adw-supervisor.md.

Only this composition module selects concrete ledger/readiness adapters.
It writes bounded recommendations to its own state file; it never dispatches,
restarts, or mutates task records.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from monitoring import agent_bridge_poll, model_registry, worker_lanes, worker_supervisor
from monitoring.supervisor_contracts import ITaskLedgerReader
from monitoring.supervisor_sources import FileLedgerReader, GatewayAwareLedgerReader, PostOfficeLedgerReader
from monitoring.supervisor_policy import (MAX_EVENTS, Thresholds, TaskEscalationState,
                                         evaluate_task, tier_for_age)
from monitoring.task_timing import queue_age as _queue_age

DEFAULT_LEDGER = Path("~/.cache/agent_bridge/worker_activity.json").expanduser()
DEFAULT_STATE_PATH = Path("~/.cache/agent_bridge/adw_supervisor_state.json").expanduser()


def second_opinion_models() -> list[str]:
    return [entry["id"] for entry in model_registry.registry() if entry["available"]]


def read_ledger(path: Path) -> tuple[list[dict] | None, str | None, float | None]:
    found = FileLedgerReader(path).read(time.time())
    return ([row.model_dump() for row in found.tasks] if found.tasks is not None else None,
            found.error, found.updated_at)

def _load_state(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".adw-supervisor-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(payload, out, indent=2, allow_nan=False)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def _worker_lanes(now: float) -> list[dict] | None:
    """Each installed worker lane's own process and heartbeat, so a crash of either worker is recorded by the
    supervisor that runs outside both. `None` (not a made-up all-clear) when they cannot be observed."""
    try:
        return worker_lanes.lane_reports(now=now)
    except (OSError, TypeError, ValueError):
        return None


def _worker_diagnostic(tasks: list[dict] | None, now: float) -> dict | None:
    """Reuse of the existing, already-tested `worker_supervisor.diagnose`:
    process presence, heartbeat freshness, queue stagnation. Degrades to
    `None` (not a fabricated status) if the bridge poll files are absent --
    e.g. on a box that does not run the bridge worker at all."""
    try:
        worker = agent_bridge_poll.agent_bridge_poll_payload()
        service = agent_bridge_poll.ServiceState(**worker.get("service", {}))
    except (TypeError, ValueError):
        return None
    return worker_supervisor.diagnose(service=service, state=worker.get("state"), tasks=tasks, now=now)


DEFAULT_GATEWAY_URL = "https://bridge.americansjewelry.com/api/agent-bridge/v1"
DEFAULT_TOKEN_FILE = "~/.config/agent_bridge/worker_token"


def gateway_head(package: Path, url: str, token_file: Path) -> Callable[[], str | None]:
    """The one place that names the concrete gateway client: a read-only peek at the queue head."""
    def head() -> str | None:
        if str(package) not in sys.path:
            sys.path.insert(0, str(package))
        http = importlib.import_module("agent_bridge_worker.adapters.http_gateway")
        gateway = http.HttpTaskGateway(url, token_file.read_text(encoding="utf-8").strip(), timeout_seconds=10)
        return gateway.next()
    return head


def run_cycle(
    *, ledger_path: Path, state_path: Path, thresholds: Thresholds, now: float,
    reader: ITaskLedgerReader | None = None,
) -> dict:
    if ledger_path.resolve() == state_path.resolve():
        raise ValueError("state path must differ from the read-only ledger path")
    prior = _load_state(state_path)
    prior_tasks = prior.get("tasks") if isinstance(prior.get("tasks"), dict) else {}
    observation = (reader or FileLedgerReader(ledger_path)).read(now)
    tasks = [row.model_dump() for row in observation.tasks] if observation.tasks is not None else None
    states: dict[str, dict] = {}
    models = model_registry.registry()
    candidates = tuple(entry["id"] for entry in models if entry["available"])
    # Retain bounded last-known escalations during an outage, clearly marked
    # stale; do not count an unreadable source as progress or a fresh cycle.
    if observation.error or observation.stale:
        states = dict(list(prior_tasks.items())[-10000:])
    elif tasks is not None:
        for task in tasks:
            previous = TaskEscalationState.from_dict(prior_tasks.get(task["id"]))
            updated = evaluate_task(task, previous, thresholds, now, candidates)
            states[task["id"]] = updated.to_dict()
    unknown = [key for key, value in states.items() if value.get("observation_error")]
    alerts = [{"task_id": key, "tier": value.get("tier", "ok"),
               "observation_error": value.get("observation_error"),
               "recent_events": value.get("events", [])[-5:]}
              for key, value in states.items()
              if value.get("tier") != "ok" or value.get("observation_error")]
    snapshot = {
        "ok": tasks is not None and not observation.error and not observation.stale and not unknown,
        "source": observation.source, "generated_at": now, "heartbeat_at": now,
        "ledger_path": str(ledger_path), "ledger_updated_at": observation.updated_at,
        "ledger_error": observation.error, "ledger_stale": observation.stale,
        "coverage": observation.coverage, "coverage_complete": observation.coverage_complete,
        "coverage_reason": observation.coverage_reason,
        "thresholds": vars(thresholds), "tasks": states, "alerts": alerts,
        "unknown_task_ids": unknown,
        "worker_diagnostic": _worker_diagnostic(tasks if not observation.stale else None, now),
        "worker_lanes": _worker_lanes(now),
        # Waiting tasks as this supervisor saw them: the local ledger plus the gateway's queue head, so a task
        # queued only at the gateway is counted. A lower bound (the gateway shows only the head).
        "queued_count": sum(1 for task in (tasks or []) if task.get("status") in {"queued", "pending"}),
        "models": models,
    }
    _atomic_write(state_path, snapshot)
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--once", action="store_true", help="one observation; no daemon")
    args = parser.parse_args()
    ledger = Path(os.environ.get("WORKER_ACTIVITY_SNAPSHOT", str(DEFAULT_LEDGER))).expanduser()
    state = Path(os.environ.get("ADW_SUPERVISOR_STATE_PATH", str(DEFAULT_STATE_PATH))).expanduser()
    package = Path(os.environ.get("ADW_AGENT_BLOCKS_PACKAGE", "~/agent_blocks/lancedb_memory")).expanduser()
    reader = (FileLedgerReader(ledger) if os.environ.get("WORKER_ACTIVITY_SNAPSHOT")
              else PostOfficeLedgerReader(package))
    token_file = Path(os.environ.get("BRIDGE_WORKER_TOKEN_FILE", DEFAULT_TOKEN_FILE)).expanduser()
    if token_file.is_file() and not os.environ.get("ADW_SUPERVISOR_NO_GATEWAY"):
        reader = GatewayAwareLedgerReader(reader, gateway_head(
            package, os.environ.get("BRIDGE_GATEWAY_URL", DEFAULT_GATEWAY_URL), token_file))
    interval = float(os.environ.get("ADW_SUPERVISOR_POLL_SECONDS", "20"))
    if not 1 <= interval <= 3600:
        parser.error("poll interval must be between 1 and 3600 seconds")
    thresholds = Thresholds.from_env()
    while True:
        result = run_cycle(ledger_path=ledger, state_path=state, thresholds=thresholds,
                           now=time.time(), reader=reader)
        print(json.dumps({key: result[key] for key in ("ok", "source", "ledger_error", "coverage_reason")}), flush=True)
        if args.once:
            break
        time.sleep(interval)


if __name__ == "__main__":
    main()
