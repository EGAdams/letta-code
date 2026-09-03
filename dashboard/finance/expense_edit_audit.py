"""Append-only audit evidence for the dashboard's Edit Expense command.

The HTTP access log proves only that a request returned HTTP 200. Edit Expense
uses JSON ``ok``/``error`` results inside that response, so the access line
cannot say what the operator submitted, whether the edit succeeded, or which
warning the browser displayed. This narrow port preserves that evidence
without teaching the expense repository or HTTP transport about log files.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any


DEFAULT_EXPENSE_EDIT_AUDIT_PATH = os.path.expanduser(
    '~/.local/state/letta-dashboard/expense-edit-audit.jsonl')

_REQUEST_FIELDS = (
    'expense_id',
    'merchant_name',
    'transaction_date',
    'total_amount',
    'category_name',
    'vendor_key',
    'learn_vendor',
)
_RESPONSE_FIELDS = (
    'ok',
    'error',
    'changed_fields',
    'warnings',
    'record',
    'vendor_remembered',
    'image',
)


class IExpenseEditAuditLog(ABC):
    """Port: retain the diagnostic outcome of one Edit Expense request."""

    @abstractmethod
    def record(self, request: Mapping[str, Any],
               response: Mapping[str, Any]) -> None:
        """Append one complete request/result event."""


class NullExpenseEditAuditLog(IExpenseEditAuditLog):
    """Inert adapter for tests that exercise edits but not audit persistence."""

    def record(self, request, response):
        return None


class IExpenseEditCommand(ABC):
    """Command boundary used by the audit decorator."""

    @abstractmethod
    def execute(self, request: Any) -> dict:
        """Handle one Edit Expense request."""


class CallableExpenseEditCommand(IExpenseEditCommand):
    """Adapt the existing application function to the command boundary."""

    def __init__(self, handler: Callable[[Any], dict]):
        self._handler = handler

    def execute(self, request):
        return self._handler(request)


class AuditedExpenseEditCommand(IExpenseEditCommand):
    """Decorator that observes a command without changing its outcome."""

    def __init__(self, delegate: IExpenseEditCommand,
                 audit_log: IExpenseEditAuditLog):
        self._delegate = delegate
        self._audit_log = audit_log

    def _record(self, request, response):
        try:
            self._audit_log.record(request, response)
        except Exception as exc:  # the expense result remains authoritative
            print(f'[expense-edit-audit] Could not record request: '
                  f'{type(exc).__name__}: {exc}')

    def execute(self, request):
        audit_request = request if isinstance(request, dict) else {}
        try:
            response = self._delegate.execute(request)
        except Exception as exc:
            self._record(audit_request, {
                'ok': False,
                'error': f'Unhandled {type(exc).__name__}: {exc}',
            })
            raise
        self._record(audit_request, response)
        return response


def _json_safe(value: Any) -> Any:
    """Keep JSON values intact and identify unexpected in-process objects."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return {'unsupported_type': type(value).__name__}


def _selected(source: Mapping[str, Any], fields: tuple[str, ...]) -> dict:
    return {
        field: _json_safe(source[field])
        for field in fields
        if field in source
    }


class JsonlExpenseEditAuditLog(IExpenseEditAuditLog):
    """Local, append-only JSON Lines implementation.

    Only the declared expense fields are retained. ``request_keys`` records
    misspellings or unexpected browser fields without persisting their values.
    The file is mode 0600 because merchant and amount details are financial
    data. One object is shared by the server, so its lock also prevents two
    threaded requests from interleaving bytes.
    """

    def __init__(
        self,
        path: str = DEFAULT_EXPENSE_EDIT_AUDIT_PATH,
        *,
        clock: Callable[[], str] | None = None,
        id_factory: Callable[[], str] | None = None,
    ):
        self.path = os.path.abspath(os.path.expanduser(path))
        self._clock = clock or (
            lambda: datetime.now(timezone.utc).isoformat(timespec='milliseconds'))
        self._id_factory = id_factory or (lambda: str(uuid.uuid4()))
        self._lock = threading.Lock()

    def record(self, request, response):
        request = request if isinstance(request, Mapping) else {}
        response = response if isinstance(response, Mapping) else {}
        event = {
            'action_id': self._id_factory(),
            'timestamp': self._clock(),
            'status': 'succeeded' if response.get('ok') is True else 'failed',
            'request': _selected(request, _REQUEST_FIELDS),
            'request_keys': sorted(str(key) for key in request),
            'response': _selected(response, _RESPONSE_FIELDS),
        }
        encoded = (json.dumps(event, ensure_ascii=False, separators=(',', ':'))
                   + '\n').encode('utf-8')
        parent = os.path.dirname(self.path)
        with self._lock:
            os.makedirs(parent, mode=0o700, exist_ok=True)
            fd = os.open(
                self.path,
                os.O_APPEND | os.O_CREAT | os.O_WRONLY,
                0o600,
            )
            try:
                os.write(fd, encoded)
            finally:
                os.close(fd)
