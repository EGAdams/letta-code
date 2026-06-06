"""Recovery strategies (Strategy + Template Method + Factory).

BaseRecoveryStrategy.recover() is the fixed skeleton; subclasses fill _decide().
Non-retryable classifications short-circuit to ABORT before _decide() runs.
"""
from __future__ import annotations

from typing import Dict

from .interfaces import IRecoveryStrategy, IRecoveryStrategyFactory
from .models import (
    ExecutorCommand,
    FailureClassification,
    RecoveryOutcome,
    RecoveryAction,
    FailureKind,
)


class BaseRecoveryStrategy(IRecoveryStrategy):
    """Template Method: recover() is fixed; subclasses implement _decide()."""

    async def recover(
        self, cmd: ExecutorCommand, classification: FailureClassification
    ) -> RecoveryOutcome:
        if not classification.retryable:
            # Honor the classifier's recommended terminal action (ABORT or CIRCUIT_OPEN).
            action = (
                classification.recommended_action
                if classification.recommended_action
                in (RecoveryAction.ABORT, RecoveryAction.CIRCUIT_OPEN)
                else RecoveryAction.ABORT
            )
            return RecoveryOutcome(action=action, reason=classification.evidence)
        return self._decide(cmd, classification)  # subclass hook

    def _decide(
        self, cmd: ExecutorCommand, c: FailureClassification
    ) -> RecoveryOutcome:
        raise NotImplementedError


class AllowlistAbortStrategy(BaseRecoveryStrategy):       # F1
    handles = FailureKind.ALLOWLIST_BLOCKED

    def _decide(self, cmd, c) -> RecoveryOutcome:  # pragma: no cover - non-retryable
        return RecoveryOutcome(action=RecoveryAction.ABORT, reason=c.evidence)


class BackoffRetryStrategy(BaseRecoveryStrategy):         # F2
    handles = FailureKind.SERVER_RELOAD_500

    def _decide(self, cmd, c) -> RecoveryOutcome:
        return RecoveryOutcome(
            action=RecoveryAction.RETRY,
            backoff_ms=1500,
            reason="executor reloading — backing off before one retry",
        )


class NarrowCommandStrategy(BaseRecoveryStrategy):        # F3
    handles = FailureKind.REQUEST_TIMEOUT

    def _decide(self, cmd, c) -> RecoveryOutcome:
        # A real narrowing would tighten globs / add a tighter timeout; here we
        # halve the timeout so a verbatim re-run is impossible (defeats the spin).
        narrowed = cmd.model_copy(update={"timeout_s": max(5.0, cmd.timeout_s / 2)})
        return RecoveryOutcome(
            action=RecoveryAction.NARROW,
            next_command=narrowed,
            reason="timeout — retrying once with a tightened command/timeout",
        )


class ClientSideFallbackStrategy(BaseRecoveryStrategy):   # F5
    handles = FailureKind.END_TURN_NO_RETURN

    def _decide(self, cmd, c) -> RecoveryOutcome:
        return RecoveryOutcome(
            action=RecoveryAction.FALLBACK,
            next_command=cmd,
            reason="server omitted tool_return — execute client-side",
        )


class CircuitOpenStrategy(BaseRecoveryStrategy):          # F4
    handles = FailureKind.EXECUTOR_DOWN

    def _decide(self, cmd, c) -> RecoveryOutcome:  # pragma: no cover - non-retryable
        return RecoveryOutcome(action=RecoveryAction.CIRCUIT_OPEN, reason=c.evidence)


class PeerToolRuleAbortStrategy(BaseRecoveryStrategy):    # F6
    handles = FailureKind.PEER_TOOL_RULE_HANG

    def _decide(self, cmd, c) -> RecoveryOutcome:  # pragma: no cover - non-retryable
        return RecoveryOutcome(action=RecoveryAction.ABORT, reason=c.evidence)


class AbortStrategy(BaseRecoveryStrategy):
    """Default for FailureKind.UNKNOWN — always abort."""

    handles = FailureKind.UNKNOWN

    def _decide(self, cmd, c) -> RecoveryOutcome:  # pragma: no cover - non-retryable
        return RecoveryOutcome(action=RecoveryAction.ABORT, reason=c.evidence)


class StrategyFactory(IRecoveryStrategyFactory):
    """Factory Method — map a FailureKind to its Strategy."""

    def __init__(self) -> None:
        strategies: list[BaseRecoveryStrategy] = [
            AllowlistAbortStrategy(),
            BackoffRetryStrategy(),
            NarrowCommandStrategy(),
            ClientSideFallbackStrategy(),
            CircuitOpenStrategy(),
            PeerToolRuleAbortStrategy(),
            AbortStrategy(),
        ]
        self._registry: Dict[FailureKind, IRecoveryStrategy] = {
            s.handles: s for s in strategies
        }

    def for_kind(self, kind: FailureKind) -> IRecoveryStrategy:
        return self._registry.get(kind, self._registry[FailureKind.UNKNOWN])
