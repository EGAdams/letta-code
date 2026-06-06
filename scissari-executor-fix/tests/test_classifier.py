"""Red-phase tests for the Chain of Responsibility classifier.

Fixtures are the six real failure bodies (F1-F6) pulled from executor logs /
chunk logs. These FAIL until classifiers.py is implemented.
"""
import pytest

from scissari_executor.models import ExecutorFailure, FailureKind, RecoveryAction
from scissari_executor.classifiers import build_default_chain


CASES = [
    # (ExecutorFailure fixture, expected kind, expected retryable)
    (ExecutorFailure(status=400, detail="Command not in allowlist: /x/run.sh"),
        FailureKind.ALLOWLIST_BLOCKED, False),
    (ExecutorFailure(status=500, detail="watchfiles reload"),
        FailureKind.SERVER_RELOAD_500, True),
    (ExecutorFailure(status=408, detail="timed out"),
        FailureKind.REQUEST_TIMEOUT, True),
    (ExecutorFailure(transport_error="ECONNREFUSED"),
        FailureKind.EXECUTOR_DOWN, False),
    (ExecutorFailure(detail="end_turn with no tool_return_message"),
        FailureKind.END_TURN_NO_RETURN, True),
    (ExecutorFailure(detail="max_steps: peer required_before_exit send_message"),
        FailureKind.PEER_TOOL_RULE_HANG, False),
]


@pytest.mark.parametrize("failure,kind,retryable", CASES)
def test_chain_classifies_each_failure_mode(failure, kind, retryable):
    chain = build_default_chain()
    result = chain.classify(failure)
    assert result.kind == kind
    assert result.retryable is retryable
    assert result.evidence  # MUST capture a reason (kills "no error captured")


def test_unknown_failure_never_retries():
    chain = build_default_chain()
    result = chain.classify(ExecutorFailure(detail="something nobody mapped"))
    assert result.kind == FailureKind.UNKNOWN
    assert result.recommended_action == RecoveryAction.ABORT
