"""PauseControlService: the one entry point for pause/resume/priority intent.

`request_pause` / `request_resume` / `request_priority` are idempotent and
durable: a repeated request for the same task_id (by idempotency_key, or
just by action -- a second plain pause click while one is still open) returns
the existing record instead of creating a duplicate one. `acknowledge` is the
worker-side callback this process can validate and store today, but nothing
currently calls it -- the owner of the task ledger has to be taught to call
it (or an equivalent) before a request here ever becomes real. See
`docs/bridge-pause-resume.md`.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from pause_control.models import OPEN_STATUSES, ControlAction, ControlRecord, new_request_id, rfc3339
from pause_control.ports import IControlLedger, ITaskPausability

#: Display/dispatch rank for pending requests: priority first, then pause,
#: then resume, oldest first within a rank. Ordering here is a dashboard
#: presentation aid only -- it cannot reorder the real worker queue, which is
#: outside this workspace.
_RANK: dict[ControlAction, int] = {'priority': 0, 'pause': 1, 'resume': 2}


class ControlRefused(Exception):
    """A control request that will not be recorded. `code` and `http` go
    straight to the API; never a 2xx."""

    def __init__(self, code: str, message: str, http: int):
        super().__init__(message)
        self.code, self.http = code, http


class PauseControlService:
    def __init__(self, ledger: IControlLedger, pausability: ITaskPausability,
                 clock_ns: Callable[[], int] = time.time_ns):
        self._ledger, self._pausability, self._clock = ledger, pausability, clock_ns

    # -- requesting ------------------------------------------------------------
    def request_pause(self, task_id: str, requester: str, note: Optional[str] = None,
                       idempotency_key: Optional[str] = None) -> tuple[ControlRecord, bool]:
        pausable = self._pausability.can_pause(task_id)
        if pausable is False:
            raise ControlRefused('not_pausable', f'task {task_id} is marked as unsafe to pause', 409)
        if pausable is None:
            raise ControlRefused(
                'pausability_unknown',
                f'task {task_id} is not known to support a safe checkpoint pause; refusing', 409)
        return self._request('pause', task_id, requester, note, idempotency_key)

    def request_resume(self, task_id: str, requester: str, note: Optional[str] = None,
                        idempotency_key: Optional[str] = None) -> tuple[ControlRecord, bool]:
        open_pause = self._ledger.open_for_task(task_id, 'pause')
        if open_pause is None:
            raise ControlRefused(
                'no_pause_in_progress', f'task {task_id} has no open pause to resume', 409)
        return self._request('resume', task_id, requester, note, idempotency_key)

    def request_priority(self, task_id: str, requester: str, note: Optional[str] = None,
                          idempotency_key: Optional[str] = None) -> tuple[ControlRecord, bool]:
        return self._request('priority', task_id, requester, note, idempotency_key)

    def _request(self, action: ControlAction, task_id: str, requester: str, note: Optional[str],
                 idempotency_key: Optional[str]) -> tuple[ControlRecord, bool]:
        if not task_id:
            raise ControlRefused('bad_request', 'task_id is required', 400)
        now = self._clock()
        status = OPEN_STATUSES[action]
        record = ControlRecord(request_id=new_request_id(now), task_id=task_id, action=action, status=status,
                               requested_by=requester, requested_at=rfc3339(now), updated_at=rfc3339(now),
                               note=note)
        idem = (f'{action}:{requester}', idempotency_key) if idempotency_key else None
        created_record, created = self._ledger.create(record, now, idem)
        self._ledger.audit(created_record.request_id, requester, status if created else f'{status}_replayed',
                           task_id)
        return created_record, created

    # -- worker-side callback (pending agent_blocks integration) ----------------
    def acknowledge(self, request_id: str, status: str, actor: str, note: Optional[str] = None,
                    error: Optional[str] = None) -> ControlRecord:
        changes: dict[str, object] = {}
        if note is not None:
            changes['note'] = note
        if error is not None:
            changes['error'] = error
        record = self._ledger.transition(request_id, status, **changes)
        self._ledger.audit(request_id, actor, status, record.task_id)
        return record

    # -- reading -----------------------------------------------------------------
    def get(self, request_id: str) -> Optional[ControlRecord]:
        return self._ledger.get(request_id)

    def list_for_task(self, task_id: str) -> list[ControlRecord]:
        return self._ledger.list_for_task(task_id)

    def list_recent(self, limit: int = 50, order: str = 'time') -> list[ControlRecord]:
        records = self._ledger.list_recent(limit)
        if order != 'priority':
            return records
        return sorted(records, key=lambda r: (0 if r.open else 1, _RANK.get(r.action, 9), r.requested_at))
