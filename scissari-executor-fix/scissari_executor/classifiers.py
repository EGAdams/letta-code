"""Failure classifiers (Chain of Responsibility).

Six small classifiers, each owns ONE failure fingerprint; first match wins.
build_default_chain() assembles them; the chain falls back to UNKNOWN -> ABORT.
"""
from __future__ import annotations

from typing import List, Optional

from .interfaces import IFailureClassifier, IFailureClassifierChain
from .models import (
    ExecutorFailure,
    FailureClassification,
    FailureKind,
    RecoveryAction,
)


def _classification(
    kind: FailureKind,
    retryable: bool,
    action: RecoveryAction,
    evidence: str,
    name: str,
) -> FailureClassification:
    return FailureClassification(
        kind=kind,
        retryable=retryable,
        recommended_action=action,
        evidence=evidence,
        classifier_name=name,
    )


class AllowlistClassifier(IFailureClassifier):           # F1
    name = "allowlist"

    def classify(self, failure: ExecutorFailure) -> Optional[FailureClassification]:
        if failure.status == 400 and "allowlist" in failure.detail.lower():
            return _classification(
                FailureKind.ALLOWLIST_BLOCKED,
                retryable=False,
                action=RecoveryAction.ABORT,
                evidence=f"executor rejected command (allowlist): {failure.detail}",
                name=self.name,
            )
        return None


class ServerReloadClassifier(IFailureClassifier):        # F2
    name = "server_reload"

    def classify(self, failure: ExecutorFailure) -> Optional[FailureClassification]:
        if failure.status == 500:
            return _classification(
                FailureKind.SERVER_RELOAD_500,
                retryable=True,
                action=RecoveryAction.RETRY,
                evidence=f"executor 500 (likely watchfiles reload): {failure.detail}",
                name=self.name,
            )
        return None


class TimeoutClassifier(IFailureClassifier):             # F3
    name = "timeout"

    def classify(self, failure: ExecutorFailure) -> Optional[FailureClassification]:
        if failure.status == 408 or "timed out" in failure.detail.lower():
            return _classification(
                FailureKind.REQUEST_TIMEOUT,
                retryable=True,
                action=RecoveryAction.NARROW,
                evidence=f"executor timed out — narrow the command: {failure.detail}",
                name=self.name,
            )
        return None


class ExecutorDownClassifier(IFailureClassifier):        # F4
    name = "executor_down"

    _SIGNATURES = ("econnrefused", "connection refused", "connectionerror", "no route")

    def classify(self, failure: ExecutorFailure) -> Optional[FailureClassification]:
        probe = (failure.transport_error or "").lower()
        if probe and any(sig in probe for sig in self._SIGNATURES):
            return _classification(
                FailureKind.EXECUTOR_DOWN,
                retryable=False,
                action=RecoveryAction.CIRCUIT_OPEN,
                evidence=f"executor unreachable: {failure.transport_error}",
                name=self.name,
            )
        return None


class EndTurnNoReturnClassifier(IFailureClassifier):     # F5
    name = "end_turn_no_return"

    def classify(self, failure: ExecutorFailure) -> Optional[FailureClassification]:
        detail = failure.detail.lower()
        if "end_turn" in detail and "tool_return" in detail:
            return _classification(
                FailureKind.END_TURN_NO_RETURN,
                retryable=True,
                action=RecoveryAction.FALLBACK,
                evidence="server ended turn with no tool_return — run client-side fallback",
                name=self.name,
            )
        return None


class PeerToolRuleClassifier(IFailureClassifier):        # F6
    name = "peer_tool_rule"

    def classify(self, failure: ExecutorFailure) -> Optional[FailureClassification]:
        detail = failure.detail.lower()
        if "max_steps" in detail and (
            "required_before_exit" in detail or "send_message" in detail
        ):
            return _classification(
                FailureKind.PEER_TOOL_RULE_HANG,
                retryable=False,
                action=RecoveryAction.ABORT,
                evidence="peer agent hung on an unsatisfiable tool rule — abort, do not retry",
                name=self.name,
            )
        return None


class FailureClassifierChain(IFailureClassifierChain):
    """Runs each link in order; falls back to FailureKind.UNKNOWN (-> ABORT)."""

    def __init__(self, links: List[IFailureClassifier]):
        self._links = links

    def classify(self, failure: ExecutorFailure) -> FailureClassification:
        for link in self._links:
            result = link.classify(failure)
            if result is not None:
                return result
        # Unmapped failures are NEVER silently retried.
        return _classification(
            FailureKind.UNKNOWN,
            retryable=False,
            action=RecoveryAction.ABORT,
            evidence=(
                "unclassified executor failure — aborting rather than blind-retrying: "
                f"status={failure.status} transport={failure.transport_error} "
                f"detail={failure.detail!r}"
            ),
            name="fallback",
        )


def build_default_chain() -> FailureClassifierChain:
    """Assemble the canonical F1..F6 chain."""
    return FailureClassifierChain(
        [
            AllowlistClassifier(),
            ServerReloadClassifier(),
            TimeoutClassifier(),
            ExecutorDownClassifier(),
            EndTurnNoReturnClassifier(),
            PeerToolRuleClassifier(),
        ]
    )
