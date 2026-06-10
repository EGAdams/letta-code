"""ResilientTransport — Proxy/Decorator over the raw SDK SubprocessTransport.

The F7 fix (bug b): on send() to a dead subprocess (pid=undefined / closed) it
lazily re-spawns ONCE and then sends, instead of letting the SDK throw
'Transport not connected'. Repeated spawn failures trip a CircuitBreaker
(reused from the executor scaffold) so a dead host doesn't cause an endless
respawn spin — ops gets a clean domain error instead.
"""
from __future__ import annotations

from typing import Optional

from ..breaker import CircuitBreaker
from ..interfaces import ICircuitBreaker
from ..models import FailureKind
from .interfaces import IResilientTransport, ISubprocessTransport


class TransportUnavailableError(RuntimeError):
    """Raised only after we have TRIED to re-spawn and could not.

    Deliberately NOT the raw 'Transport not connected' the SDK throws — the
    message explains that a respawn was attempted, so the heartbeat alert is
    actionable instead of cryptic.
    """


class ResilientTransport(IResilientTransport):
    def __init__(
        self,
        inner: ISubprocessTransport,
        breaker: Optional[ICircuitBreaker] = None,
    ):
        self._inner = inner
        self._breaker = breaker or CircuitBreaker(threshold=3)
        self.respawns = 0

    async def send(self, data: str) -> None:
        if self._inner.info.alive:
            self._inner.send(data)
            self._breaker.record_success()
            return

        # Dead transport (pid=undefined / closed): bring it back before sending.
        if not self._breaker.allow():
            raise TransportUnavailableError(
                "executor subprocess is down and the respawn circuit is open — "
                "alerting ops instead of spinning"
            )

        try:
            self._inner.spawn()
            self.respawns += 1
        except Exception as exc:  # spawn itself blew up
            self._breaker.record_failure(FailureKind.EXECUTOR_DOWN)
            raise TransportUnavailableError(f"re-spawn failed: {exc}") from exc

        if not self._inner.info.alive:
            self._breaker.record_failure(FailureKind.EXECUTOR_DOWN)
            raise TransportUnavailableError(
                "re-spawn did not produce a live subprocess"
            )

        self._inner.send(data)
        self._breaker.record_success()
