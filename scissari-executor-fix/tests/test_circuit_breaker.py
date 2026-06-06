"""Red-phase tests for the CircuitBreaker — kills the 14x spin on a dead executor."""
from scissari_executor.breaker import CircuitBreaker
from scissari_executor.models import FailureKind


def test_opens_after_two_executor_down_and_stops_the_spin():
    cb = CircuitBreaker(threshold=2)
    assert cb.allow() is True
    cb.record_failure(FailureKind.EXECUTOR_DOWN)
    cb.record_failure(FailureKind.EXECUTOR_DOWN)
    assert cb.allow() is False        # would have spun 14x before this fix


def test_success_resets_the_breaker():
    cb = CircuitBreaker(threshold=2)
    cb.record_failure(FailureKind.EXECUTOR_DOWN)
    cb.record_success()
    cb.record_failure(FailureKind.EXECUTOR_DOWN)
    assert cb.allow() is True          # single failures don't latch open
