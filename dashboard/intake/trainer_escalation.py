"""Problem-only Trainer escalation policy and coordinator."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

from intake.trainer_contracts import (
    IDeadlineHandle,
    IDeadlineScheduler,
    ITrainerEscalationService,
    ITrainerEscalationRecorder,
    ITrainerNotifier,
    IntakeCallback,
    TrainerEscalationResult,
    TrainerEscalationNotice,
    TrainerLaunchRequest,
)


class ThreadingDeadlineHandle(IDeadlineHandle):
    def __init__(self, timer: threading.Timer):
        self._timer = timer

    def cancel(self) -> None:
        self._timer.cancel()


class ThreadingDeadlineScheduler(IDeadlineScheduler):
    def schedule(self, delay_seconds, callback):
        timer = threading.Timer(delay_seconds, callback)
        timer.daemon = True
        timer.start()
        return ThreadingDeadlineHandle(timer)


class ProblemOnlyTrainerPolicy:
    """Decide whether callback evidence needs expert review."""

    def escalation_reason(self, callback: IntakeCallback) -> str:
        if callback.status in {'fail', 'stalled'}:
            return f'callback reported terminal status {callback.status}'
        if callback.parsed is None or callback.stored is None:
            return 'callback omitted parsed or stored evidence'
        persisted = (
            callback.stored
            + callback.deposits_stored
            + len(callback.expense_ids)
            + len(callback.duplicate_expense_ids)
        )
        if callback.parsed <= 0 and persisted <= 0:
            return 'callback reported no parsed or persisted records'
        if callback.parsed > 0 and persisted <= 0:
            return 'callback parsed records but reported no persisted outcome'
        return ''


class NullTrainerEscalationRecorder(ITrainerEscalationRecorder):
    def record(self, notice: TrainerEscalationNotice) -> None:
        return None


class CallbackTrainerEscalationRecorder(ITrainerEscalationRecorder):
    def __init__(self, merge_event: Callable[[dict[str, Any]], Any]):
        self._merge_event = merge_event

    def record(self, notice: TrainerEscalationNotice) -> None:
        request = notice.request
        self._merge_event({
            'conversation_id': request.conversation_id,
            'document_path': request.scan_path,
            'dispatched_at': request.dispatched_at,
            'trainer_dispatched': notice.summoned,
            'trainer_escalation_reason': notice.reason,
            'status': 'processing' if notice.summoned else 'fail',
            'status_detail': (
                f'Trainer summoned: {notice.reason}'
                if notice.summoned
                else f'Trainer launch failed: {notice.reason}'
            ),
        })


@dataclass(frozen=True)
class _PendingTrainerWatch:
    request: TrainerLaunchRequest
    deadline: IDeadlineHandle


class ProblemOnlyTrainerEscalationService(ITrainerEscalationService):
    def __init__(
        self,
        notifier: ITrainerNotifier,
        scheduler: IDeadlineScheduler,
        callback_timeout_seconds: float,
        policy: ProblemOnlyTrainerPolicy | None = None,
        recorder: ITrainerEscalationRecorder | None = None,
    ):
        self._notifier = notifier
        self._scheduler = scheduler
        self._callback_timeout_seconds = callback_timeout_seconds
        self._policy = policy or ProblemOnlyTrainerPolicy()
        self._recorder = recorder or NullTrainerEscalationRecorder()
        self._pending: dict[tuple[str, int], _PendingTrainerWatch] = {}
        self._lock = threading.Lock()

    def watch(self, request: TrainerLaunchRequest) -> bool:
        key = request.correlation_key
        with self._lock:
            if key in self._pending:
                return False
            deadline = self._scheduler.schedule(
                self._callback_timeout_seconds,
                lambda: self._deadline_reached(key),
            )
            self._pending[key] = _PendingTrainerWatch(request, deadline)
        return True

    def observe(self, callback: IntakeCallback) -> TrainerEscalationResult:
        with self._lock:
            pending = self._pending.pop(callback.correlation_key, None)
        if pending is None:
            return TrainerEscalationResult(
                matched=False,
                summon_required=False,
                summoned=False,
            )
        pending.deadline.cancel()
        reason = self._policy.escalation_reason(callback)
        summoned = self._notifier.notify(pending.request) if reason else False
        if reason:
            self._recorder.record(TrainerEscalationNotice(
                request=pending.request,
                reason=reason,
                summoned=summoned,
            ))
        return TrainerEscalationResult(
            matched=True,
            summon_required=bool(reason),
            summoned=summoned,
            reason=reason,
        )

    def _deadline_reached(self, key: tuple[str, int]) -> None:
        with self._lock:
            pending = self._pending.pop(key, None)
        if pending is not None:
            reason = 'expense-stored callback deadline expired'
            summoned = self._notifier.notify(pending.request)
            self._recorder.record(TrainerEscalationNotice(
                request=pending.request,
                reason=reason,
                summoned=summoned,
            ))


class NullTrainerEscalationService(ITrainerEscalationService):
    def watch(self, request: TrainerLaunchRequest) -> bool:
        return False

    def observe(self, callback: IntakeCallback) -> TrainerEscalationResult:
        return TrainerEscalationResult(
            matched=False,
            summon_required=False,
            summoned=False,
        )
