"""ExecutorRunService (Facade).

The ONLY entry point Scissari's turn loop calls. Orchestrates:

    breaker.allow() -> client.run() -> classifier.classify()
      -> factory.for_kind().recover() -> guard.register() -> alert_sink.emit()

All collaborators are injected (Dependency Injection) so the facade can be
unit-tested with fakes. On any unrecoverable path it emits a StallReport that
finally carries a concrete reason and raises StalledError.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from .interfaces import (
    IExecutorRunService,
    IExecutorClient,
    IFailureClassifierChain,
    IRecoveryStrategyFactory,
    ILoopGuard,
    ICircuitBreaker,
    IAlertSink,
    IConversationSnapshotStore,
)
from .classifiers import build_default_chain
from .strategies import StrategyFactory
from .guard import LoopGuard
from .breaker import CircuitBreaker
from .models import (
    ExecutorCommand,
    ExecutorResponse,
    ExecutorFailureError,
    FailureClassification,
    FailureKind,
    RecoveryAction,
    RecoveryOutcome,
    StallReport,
    TurnState,
    GuardVerdict,
)


class StalledError(RuntimeError):
    """Raised when the turn cannot complete. Carries the StallReport."""

    def __init__(self, report: StallReport):
        self.report = report
        super().__init__(report.message)


# Hard ceiling so a logic bug can never reproduce the original infinite spin.
_ABSOLUTE_MAX_ATTEMPTS = 6


class ExecutorRunService(IExecutorRunService):
    def __init__(
        self,
        client: IExecutorClient,
        alert_sink: IAlertSink,
        classifier: Optional[IFailureClassifierChain] = None,
        factory: Optional[IRecoveryStrategyFactory] = None,
        guard: Optional[ILoopGuard] = None,
        breaker: Optional[ICircuitBreaker] = None,
        snapshot_store: Optional[IConversationSnapshotStore] = None,
        sleep=asyncio.sleep,
    ):
        self._client = client
        self._alert_sink = alert_sink
        self._classifier = classifier or build_default_chain()
        self._factory = factory or StrategyFactory()
        self._guard = guard or LoopGuard(snapshot_store=snapshot_store)
        self._breaker = breaker or CircuitBreaker()
        self._snapshots = snapshot_store
        self._sleep = sleep

    async def _stall(
        self,
        agent_id: str,
        classification: Optional[FailureClassification],
        verdict: Optional[GuardVerdict],
        note: str,
    ) -> "StalledError":
        report = StallReport(
            agent_id=agent_id,
            classification=classification,
            calls_used=verdict.calls_used if verdict else 0,
            final_state=verdict.state if verdict else TurnState.TRIPPED,
            snapshot_id=verdict.snapshot_id if verdict else None,
            # The fix: a concrete, classified reason — never "no error captured".
            message=(
                f"executor_run could not complete: {note}"
                + (f" — {classification.evidence}" if classification else "")
            ),
        )
        await self._alert_sink.emit(report)
        return StalledError(report)

    async def execute(self, cmd: ExecutorCommand, agent_id: str) -> ExecutorResponse:
        current = cmd

        for _ in range(_ABSOLUTE_MAX_ATTEMPTS):
            # Circuit breaker: don't even touch a service we believe is dead.
            if not self._breaker.allow():
                classification = FailureClassification(
                    kind=FailureKind.EXECUTOR_DOWN,
                    retryable=False,
                    recommended_action=RecoveryAction.CIRCUIT_OPEN,
                    evidence="circuit open — executor presumed down",
                    classifier_name="circuit_breaker",
                )
                verdict = self._guard.register(
                    current,
                    RecoveryOutcome(
                        action=RecoveryAction.CIRCUIT_OPEN,
                        kind=classification.kind,
                        reason="circuit open",
                    ),
                )
                raise await self._stall(
                    agent_id, classification, verdict, "circuit open"
                )

            try:
                response = await self._client.run(current)
            except ExecutorFailureError as exc:
                classification = self._classifier.classify(exc.failure)
                self._breaker.record_failure(classification.kind)

                strategy = self._factory.for_kind(classification.kind)
                outcome = await strategy.recover(current, classification)
                outcome.kind = classification.kind  # tag for guard budget + reporting

                verdict = self._guard.register(current, outcome)

                # Terminal action or guard tripped -> stop and alert with a reason.
                if (
                    outcome.action in (RecoveryAction.ABORT, RecoveryAction.CIRCUIT_OPEN)
                    or not verdict.should_continue
                ):
                    raise await self._stall(
                        agent_id, classification, verdict, outcome.action.value
                    )

                # Retry-ish: honor backoff, advance the command, loop again.
                if outcome.backoff_ms:
                    await self._sleep(outcome.backoff_ms / 1000)
                current = outcome.next_command or current
                continue
            else:
                self._breaker.record_success()
                return response

        # Defensive: absolute attempt ceiling reached (should be unreachable).
        raise await self._stall(
            agent_id, None, None, "attempt ceiling reached"
        )
