"""Read-only time adapter shared by queue health and escalation policies."""
from __future__ import annotations

import math
import re
from datetime import datetime


def epoch(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            stamp = float(value)
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:  # do not guess which machine's local timezone
                return None
            stamp = parsed.timestamp()
        return stamp if math.isfinite(stamp) else None
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def duration_seconds(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) and value >= 0 else None
    if not isinstance(value, str) or not re.fullmatch(r"(?:\d+(?:\.\d+)?[dhms]\s*)+", value):
        return None
    factors = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    return sum(float(n) * factors[unit] for n, unit in re.findall(r"(\d+(?:\.\d+)?)([dhms])", value))


def queue_age(task: dict, now: float) -> float | None:
    # Numeric age is the legacy contract. Real worker rows have an ISO time;
    # use that before their rounded display duration so age advances over time.
    value = task.get("queue_age")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return duration_seconds(value)
    stamp = epoch(task.get("queued_at"))
    if stamp is not None:
        return now - stamp if stamp <= now else None
    return duration_seconds(value)


def idle_age(task: dict, now: float) -> float | None:
    if task.get("status") in ("queued", "pending"):
        return queue_age(task, now)
    # A runtime heartbeat proves liveness, not useful progress. Worker rows'
    # last_update is the last recorded task event (including tool progress).
    stamp = epoch(task.get("last_progress_at") or task.get("last_update") or task.get("started_at"))
    return now - stamp if stamp is not None and stamp <= now else None
