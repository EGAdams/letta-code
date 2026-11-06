"""Boundary data for pause/resume/priority control requests (StrictModel: strict,
frozen, extra='forbid').

A control request is the one durable answer to "did anyone ask for this task
to pause?". It is intent, not fact: the worker that owns the task ledger is
outside this workspace, so a request can sit in `pause_requested` forever if
nothing ever acknowledges it. That is treated as an honest, visible state,
never silently upgraded to `paused`.
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import Field

from contracts import StrictModel

ControlAction = Literal['pause', 'resume', 'priority']
ControlStatus = Literal[
    'pause_requested', 'paused',
    'resume_requested', 'resumed',
    'priority_requested', 'priority_dispatched',
    'rejected', 'failed',
]

#: Requested-but-not-yet-settled statuses -- an "open" request for its action.
OPEN_STATUSES: dict[ControlAction, str] = {
    'pause': 'pause_requested', 'resume': 'resume_requested', 'priority': 'priority_requested',
}

#: The only moves a control request may make. Everything not listed is terminal,
#: the same closed-world rule scan_jobs.models.TRANSITIONS uses.
TRANSITIONS: dict[str, frozenset[str]] = {
    'pause_requested': frozenset({'paused', 'rejected', 'failed'}),
    'resume_requested': frozenset({'resumed', 'rejected', 'failed'}),
    'priority_requested': frozenset({'priority_dispatched', 'rejected', 'failed'}),
}

TERMINAL_STATUSES: frozenset[str] = frozenset(
    status for moves in TRANSITIONS.values() for status in moves)

REQUEST_ID_RE = re.compile(r'^pc_[0-9A-HJKMNP-TV-Z]{26}$')
_CROCKFORD = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'


def new_request_id(now_ns: Optional[int] = None) -> str:
    """A sortable ULID-shaped id, same scheme as scan_jobs.models.new_scan_id."""
    ms = (now_ns if now_ns is not None else time.time_ns()) // 1_000_000
    value = (ms << 80) | int.from_bytes(os.urandom(10), 'big')
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return 'pc_' + ''.join(reversed(chars))


def rfc3339(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


class ControlRecord(StrictModel):
    request_id: str = Field(pattern=REQUEST_ID_RE.pattern)
    task_id: str = Field(min_length=1, max_length=120)
    action: ControlAction
    status: ControlStatus
    requested_by: str = Field(min_length=1, max_length=80)
    requested_at: str
    updated_at: str
    note: Optional[str] = Field(default=None, max_length=600)
    error: Optional[str] = Field(default=None, max_length=600)

    @property
    def open(self) -> bool:
        return self.status not in TERMINAL_STATUSES

    def public(self) -> dict:
        return self.model_dump(mode='json')
