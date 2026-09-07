"""What one Claude Code SDK run cost, and the rate that follows from many.

The executor's activity feed is a rolling buffer of *events*: it says what a
run is doing right now and, on the final status event, how many tokens it
spent. It never says "how fast are we burning tokens" -- nothing there
outlives the buffer. These models are the shape the dashboard keeps instead:
one immutable sample per finished run, and the windowed rate derived from
them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List, Optional

from pydantic import Field

from contracts import StrictModel


#: Rate windows shown on Server Management, shortest first. A single run can
#: easily spend 50k tokens, so a one-minute window is spiky by nature -- the
#: longer windows are what a human reads as "the rate".
RATE_WINDOWS: tuple = (
    (60, 'last minute'),
    (300, 'last 5 min'),
    (3600, 'last hour'),
    (86400, 'last 24h'),
)

#: Samples older than this are dropped on write. The longest window is 24h;
#: a little slack keeps that window honest across a restart.
SAMPLE_RETENTION_SECONDS = 30 * 3600


class RunUsageSample(StrictModel):
    """One finished run's token spend, keyed by the run that spent it.

    ``run_id`` is the identity: the same run is re-observed on every poll
    (its final status event stays in the buffer for hundreds of events), and
    counting it twice would double the rate. Cache reads are counted in
    ``total_tokens`` because they are tokens the model processed -- they are
    reported separately as well, since they are the cheap ones and a rate that
    hides the split invites the wrong conclusion.
    """

    run_id: str
    model: str = 'unknown'
    ended_at: float
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0

    @property
    def cache_tokens(self) -> int:
        return self.cache_creation_tokens + self.cache_read_tokens

    @property
    def total_tokens(self) -> int:
        return (self.input_tokens + self.output_tokens
                + self.cache_creation_tokens + self.cache_read_tokens)


class RateWindow(StrictModel):
    """Tokens spent inside one trailing window, and the per-minute rate.

    ``complete`` is False while the dashboard has been watching for less than
    the window: 40k tokens seen over four minutes is not an hourly rate, and
    saying so is the difference between a reading and a guess.
    """

    seconds: int
    label: str
    runs: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_tokens: int = 0
    total_tokens: int = 0
    tokens_per_minute: float = 0.0
    complete: bool = True


class CurrentRunUsage(StrictModel):
    """The in-flight (or most recent) run, so a live burn is visible at once."""

    run_id: str
    status: str = 'unknown'
    model: str = 'unknown'
    total_tokens: int = 0


class TokenRatePayload(StrictModel):
    """GET /api/claude-sdk-token-rate.

    Fails soft rather than closed: an unreachable executor costs the *live*
    run but not the history already on disk, so the windows still answer.
    """

    ok: bool = True
    error: Optional[str] = None
    observed_since: Optional[float] = None
    sample_count: int = 0
    current_run: Optional[CurrentRunUsage] = None
    windows: List[RateWindow] = Field(default_factory=list)


class IRunUsageStore(ABC):
    """Where finished-run samples outlive both the buffer and the process."""

    @abstractmethod
    def record(self, sample: RunUsageSample) -> bool:
        """Store `sample` unless its run_id is already known.

        Returns whether it was new. Idempotency lives here, not in the caller:
        every poll re-reads the same final status event.
        """

    @abstractmethod
    def samples(self) -> List[RunUsageSample]:
        """Every retained sample, oldest first."""


def usage_from_payload(run_id: str, model: str, ended_at: float,
                       usage) -> Optional[RunUsageSample]:
    """Build a sample from the executor's raw ``usage`` dict, or None.

    The executor mirrors the Anthropic usage block verbatim and has added
    fields to it before (``server_tool_use``, ``cache_creation``), so this
    picks the four counters it needs by name instead of validating the whole
    shape -- an unknown sibling field must not cost us the measurement.
    """
    if not isinstance(usage, dict) or not run_id:
        return None

    def count(key: str) -> int:
        value = usage.get(key, 0)
        return value if isinstance(value, int) and value >= 0 else 0

    sample = RunUsageSample(
        run_id=str(run_id),
        model=str(model or 'unknown'),
        ended_at=float(ended_at),
        input_tokens=count('input_tokens'),
        output_tokens=count('output_tokens'),
        cache_creation_tokens=count('cache_creation_input_tokens'),
        cache_read_tokens=count('cache_read_input_tokens'),
    )
    return sample if sample.total_tokens else None


def prune(samples: Iterable[RunUsageSample], now: float) -> List[RunUsageSample]:
    """Drop samples past retention, oldest first. Pure, so the store is dumb."""
    cutoff = now - SAMPLE_RETENTION_SECONDS
    return sorted((s for s in samples if s.ended_at >= cutoff),
                  key=lambda s: s.ended_at)
