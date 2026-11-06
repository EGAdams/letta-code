"""Append-only activity log for the Notes Bridge interface.

One JSON object per line in ``NOTES_ACTIVITY_LOG`` (default
``~/.cache/agent_bridge/notes_activity.jsonl``). The Bridge worker's
``agent_bridge_worker.adapters.notes_activity_log`` writes the same shape, and
``agent_bridge_worker.activity_snapshot`` turns both into Worker Activity rows.

A line names what happened, never what a note says: event, filename,
revisions, the authenticated client name, the Bridge task id when the caller
sent one, and a short reason. Logging must never break a request, so every
failure here is swallowed.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

SOURCE = "dashboard"


def log_path() -> Path:
    return Path(os.environ.get("NOTES_ACTIVITY_LOG")
                or Path.home() / ".cache" / "agent_bridge" / "notes_activity.jsonl")


def record(event: str, *, task_id: str = "", filename: str = "", revision: str = "",
           expected_revision: str = "", actor: str = "", detail: str = "") -> None:
    entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "source": SOURCE, "event": event}
    for key, value in (("task_id", task_id), ("filename", filename), ("revision", revision),
                       ("expected_revision", expected_revision), ("actor", actor),
                       ("detail", detail[:240])):
        if value:
            entry[key] = value
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except OSError:
        pass
