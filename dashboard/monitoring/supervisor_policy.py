"""Pure escalation State policy: no I/O or model discovery."""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field, replace
from typing import Literal

from monitoring.task_timing import idle_age

Tier = Literal["ok", "warn", "recommend", "diagnose", "incident"]
TIER_ORDER: tuple[Tier, ...] = ("ok", "warn", "recommend", "diagnose", "incident")
MAX_EVENTS = 200

RECOMMENDATION_TEXT: dict[Tier, str] = {
    "warn": "No recorded task progress past the warn threshold. No action taken; continue observing.",
    "recommend": (
        "No recorded task progress past the recommend threshold. RECOMMENDATION: a human or the "
        "owning agent should inspect this task. This supervisor will not "
        "restart the worker or resubmit the task."
    ),
    "diagnose": (
        "No recorded task progress past the diagnose threshold. Independent diagnosis "
        "recommended; see this event's 'second_opinion_models' for which "
        "models have verified runtime availability to review it. "
        "This supervisor does not invoke any model itself."
    ),
    "incident": (
        "No recorded task progress past the incident threshold. INCIDENT: notify a human. "
        "This supervisor still will not act on the bridge or the worker."
    ),
}

NO_PROGRESS_MESSAGE = (
    "Two consecutive cycles with no status or attempt change while escalated. "
    "RECOMMENDATION: switch tactic (a different model or manual review) "
    "rather than waiting again."
)


@dataclass(frozen=True)
class Thresholds:
    """2/5/10/30 minute defaults, each overridable so tests can use a fake
    clock without waiting, and so an operator can retune without editing
    code."""

    warn_seconds: float = 120.0
    recommend_seconds: float = 300.0
    diagnose_seconds: float = 600.0
    incident_seconds: float = 1800.0

    def __post_init__(self) -> None:
        values = (self.warn_seconds, self.recommend_seconds, self.diagnose_seconds, self.incident_seconds)
        if not all(math.isfinite(value) and value > 0 for value in values) or any(
            left >= right for left, right in zip(values, values[1:])
        ):
            raise ValueError("escalation thresholds must be finite, positive, and strictly increasing")

    @classmethod
    def from_env(cls) -> "Thresholds":
        def _get(name: str, default: float) -> float:
            try:
                return float(os.environ.get(name, default))
            except (TypeError, ValueError):
                return default

        return cls(
            warn_seconds=_get("ADW_SUPERVISOR_WARN_SECONDS", 120.0),
            recommend_seconds=_get("ADW_SUPERVISOR_RECOMMEND_SECONDS", 300.0),
            diagnose_seconds=_get("ADW_SUPERVISOR_DIAGNOSE_SECONDS", 600.0),
            incident_seconds=_get("ADW_SUPERVISOR_INCIDENT_SECONDS", 1800.0),
        )


def _tier_rank(tier: Tier) -> int:
    return TIER_ORDER.index(tier)


def tier_for_age(age: float, thresholds: Thresholds) -> Tier:
    """Pure: which escalation tier a queue age falls into."""
    if age >= thresholds.incident_seconds:
        return "incident"
    if age >= thresholds.diagnose_seconds:
        return "diagnose"
    if age >= thresholds.recommend_seconds:
        return "recommend"
    if age >= thresholds.warn_seconds:
        return "warn"
    return "ok"


@dataclass
class TaskEscalationState:
    tier: Tier = "ok"
    highest_tier: Tier = "ok"
    last_status: str | None = None
    last_attempts: float | None = None
    no_progress_cycles: int = 0
    observation_error: str | None = None
    last_progress: str | None = None
    last_observed_at: float | None = None
    events: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "tier": self.tier,
            "highest_tier": self.highest_tier,
            "last_status": self.last_status,
            "last_attempts": self.last_attempts,
            "no_progress_cycles": self.no_progress_cycles,
            "observation_error": self.observation_error,
            "last_progress": self.last_progress,
            "last_observed_at": self.last_observed_at,
            "events": self.events[-MAX_EVENTS:],
        }

    @classmethod
    def from_dict(cls, raw: dict | None) -> "TaskEscalationState":
        if not isinstance(raw, dict):
            return cls()
        tier = raw.get("tier")
        highest = raw.get("highest_tier")
        count = raw.get("no_progress_cycles", 0)
        count = min(2, max(0, int(count))) if isinstance(count, (int, float)) and math.isfinite(count) else 0
        events = raw.get("events")
        return cls(
            tier=tier if tier in TIER_ORDER else "ok",
            highest_tier=highest if highest in TIER_ORDER else "ok",
            last_status=raw.get("last_status"),
            last_attempts=raw.get("last_attempts"),
            no_progress_cycles=count,
            observation_error=raw.get("observation_error"),
            last_progress=raw.get("last_progress"),
            last_observed_at=raw.get("last_observed_at") if isinstance(raw.get("last_observed_at"), (int, float)) else None,
            events=[e for e in events if isinstance(e, dict)][-MAX_EVENTS:] if isinstance(events, list) else [],
        )


def evaluate_task(
    task: dict, prior: TaskEscalationState, thresholds: Thresholds, now: float,
    candidates: tuple[str, ...] = (),
) -> TaskEscalationState:
    """One task, one poll cycle. Pure given `now`, so a fake clock makes this
    deterministic in tests. Idempotent: an event is appended only on the
    transition into a new highest tier, or on the second consecutive
    no-progress cycle while already escalated -- re-running identical inputs
    never duplicates an event."""
    status = task.get("status")
    attempts = task.get("attempts") if isinstance(task.get("attempts"), (int, float)) else None
    age = idle_age(task, now)
    progress = str(task.get("last_progress_at") or task.get("last_update") or task.get("current") or "")

    if status not in ("queued", "pending", "running", "claimed", "succeeded", "failed", "cancelled", "timed_out", "completed"):
        return replace(prior, observation_error="Task status is unknown or unsupported.")
    if status not in ("queued", "pending", "running", "claimed"):
        return TaskEscalationState(last_status=status, last_attempts=attempts)
    if age is None:
        return replace(prior, last_status=status, last_attempts=attempts,
                       observation_error="No valid queue/progress timestamp; task health is unknown.")
    if prior.last_observed_at is not None and now <= prior.last_observed_at:
        return prior  # replaying the same observation is not another cycle

    tier = tier_for_age(age, thresholds)
    task_id = task.get("id")
    events = list(prior.events)
    escalated = _tier_rank(tier) > _tier_rank(prior.highest_tier)
    if escalated:
        event = {
            "at": now, "tier": tier, "task_id": task_id, "age_seconds": age,
            "message": RECOMMENDATION_TEXT[tier],
        }
        event["signal"] = "queue-age" if status in ("queued", "pending") else "progress-age"
        if _tier_rank(tier) >= _tier_rank("diagnose"):
            event["second_opinion_models"] = list(candidates)
        events.append(event)
    highest_tier = tier if escalated else prior.highest_tier

    # Stagnation within the *current* tier only: a tier change is itself the
    # signal a RECOMMENDATION event already recorded above, not "no progress".
    if (tier != "ok" and tier == prior.tier
            and status == prior.last_status and attempts == prior.last_attempts
            and progress == prior.last_progress):
        no_progress = prior.no_progress_cycles + 1
    else:
        no_progress = 0
    if no_progress == 2 and prior.no_progress_cycles < 2:
        events.append({
            "at": now, "tier": tier, "task_id": task_id, "age_seconds": age,
            "message": NO_PROGRESS_MESSAGE,
        })

    return TaskEscalationState(
        tier=tier, highest_tier=highest_tier, last_status=status, last_attempts=attempts,
        no_progress_cycles=min(no_progress, 2), last_progress=progress,
        last_observed_at=now, events=events[-MAX_EVENTS:],
    )
