"""Ports / interfaces — program to THESE, inject implementations.

Every abstract method is a stub raising NotImplementedError.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from .models import (
    ExecutorCommand,
    ExecutorResponse,
    ExecutorFailure,
    FailureClassification,
    RecoveryOutcome,
    GuardVerdict,
    StallReport,
    FailureKind,
)


class IExecutorClient(ABC):
    """Adapter over the HTTP executor service (uvicorn @ 127.0.0.1:8787)."""

    @abstractmethod
    async def run(self, cmd: ExecutorCommand) -> ExecutorResponse:
        """Return ExecutorResponse on success; raise ExecutorFailureError otherwise. STUB."""
        raise NotImplementedError


class IFailureClassifier(ABC):
    """One link in the Chain of Responsibility. Returns None to defer to the next link."""

    name: str = "abstract"

    @abstractmethod
    def classify(self, failure: ExecutorFailure) -> Optional[FailureClassification]:
        raise NotImplementedError


class IFailureClassifierChain(ABC):
    @abstractmethod
    def classify(self, failure: ExecutorFailure) -> FailureClassification:
        """First matching link wins; falls back to FailureKind.UNKNOWN. STUB."""
        raise NotImplementedError


class IRecoveryStrategy(ABC):
    """Strategy — decides what to do about one classified failure."""

    handles: FailureKind

    @abstractmethod
    async def recover(
        self, cmd: ExecutorCommand, classification: FailureClassification
    ) -> RecoveryOutcome:
        raise NotImplementedError


class IRecoveryStrategyFactory(ABC):
    @abstractmethod
    def for_kind(self, kind: FailureKind) -> IRecoveryStrategy:
        """Map a FailureKind to its Strategy. STUB."""
        raise NotImplementedError


class ICircuitBreaker(ABC):
    @abstractmethod
    def allow(self) -> bool:
        """False when the circuit is open (executor presumed dead). STUB."""
        raise NotImplementedError

    @abstractmethod
    def record_success(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def record_failure(self, kind: FailureKind) -> None:
        raise NotImplementedError


class ILoopGuard(ABC):
    """State machine that replaces the blind `count < 14` counter."""

    @abstractmethod
    def register(self, cmd: ExecutorCommand, outcome: RecoveryOutcome) -> GuardVerdict:
        """Advance the state machine; enforce per-kind budgets & repetition. STUB."""
        raise NotImplementedError

    @abstractmethod
    def reset(self) -> None:
        raise NotImplementedError


class IConversationSnapshotStore(ABC):
    """Memento store — snapshot before any TRIPPED reset."""

    @abstractmethod
    def capture(self, agent_id: str, transcript: Sequence[dict]) -> str:
        """Persist a snapshot, return its id. STUB."""
        raise NotImplementedError

    @abstractmethod
    def restore(self, snapshot_id: str) -> Sequence[dict]:
        raise NotImplementedError


class IAlertSink(ABC):
    """Observer — Telegram, scissari-alerts.jsonl, dashboard LED all implement this."""

    @abstractmethod
    async def emit(self, report: StallReport) -> None:
        raise NotImplementedError


class IExecutorRunService(ABC):
    """Facade — the ONLY thing Scissari's turn loop calls."""

    @abstractmethod
    async def execute(self, cmd: ExecutorCommand, agent_id: str) -> ExecutorResponse:
        """Orchestrate breaker -> client -> classify -> strategy -> guard -> alert. STUB."""
        raise NotImplementedError
