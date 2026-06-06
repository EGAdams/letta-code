"""Circuit breaker — stops the 14x spin on a dead executor.

Counts CONSECUTIVE open-worthy failures (EXECUTOR_DOWN by default). After
`threshold` of them the circuit opens and allow() returns False, so the service
aborts fast. A single success resets the count; after `reset_after_s` the
breaker half-opens to allow a probe.
"""
from __future__ import annotations

import time
from typing import Optional

from .interfaces import ICircuitBreaker
from .models import FailureKind


# Failure kinds that indicate the executor service itself is unhealthy.
OPEN_WORTHY: frozenset[FailureKind] = frozenset(
    {FailureKind.EXECUTOR_DOWN, FailureKind.SERVER_RELOAD_500}
)


class CircuitBreaker(ICircuitBreaker):
    def __init__(self, threshold: int = 2, reset_after_s: float = 30.0):
        self._threshold = threshold
        self._reset_after_s = reset_after_s
        self._consecutive = 0
        self._opened_at: Optional[float] = None

    def _now(self) -> float:
        return time.monotonic()

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        # Half-open after the cooldown: allow a single probe.
        if self._now() - self._opened_at >= self._reset_after_s:
            self._opened_at = None
            self._consecutive = 0
            return True
        return False

    def record_success(self) -> None:
        self._consecutive = 0
        self._opened_at = None

    def record_failure(self, kind: FailureKind) -> None:
        if kind not in OPEN_WORTHY:
            # Non-infra failures don't latch the breaker.
            self._consecutive = 0
            return
        self._consecutive += 1
        if self._consecutive >= self._threshold:
            self._opened_at = self._now()
