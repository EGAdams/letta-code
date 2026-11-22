"""Idempotent dispatch of an "Execute agent" remediation request from an alert card.

The card (js/implementation/receptionist-failure-alert.js) builds a redacted,
copy-paste-ready prompt from the alert's own metadata and posts it here once.
This module's job is policy only: look the chosen model up in the registry
(monitoring/model_registry.py) -- the same registry Worker Activity already
renders as disabled buttons for anything unconfigured, so Claude Opus is
refused here for the identical reason it shows disabled there -- then hand a
configured model's request to the one IRemediationRunner Strategy
(remediation_runner.py). A small on-disk ledger, shaped like
adw_task_alerts.py's ack file, remembers which alert_key has already been
submitted so a duplicate click (or a second browser tab) gets back the first
attempt's result instead of dispatching twice.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from monitoring import model_registry
from remediation_runner import IRemediationRunner, IRemediationStatusReader, default_runner

DEFAULT_STATE_PATH = Path(os.path.expanduser('~/.cache/agent_bridge/remediation_dispatch_state.json'))

#: Dispatch is refused for a model picked that cannot do this kind of work,
#: even if some other capability later gets added to its registry row.
REQUIRED_CAPABILITIES = {'diagnose', 'write'}


class RemediationDispatchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    alert_key: str = Field(min_length=1, max_length=200)
    model_id: str = Field(default='claude-sonnet', min_length=1, max_length=100)
    prompt: str = Field(min_length=1, max_length=20000)
    title: str = Field(default='', max_length=500)
    agent: str = Field(default='', max_length=100)
    task_id: str = Field(default='', max_length=200)


class RemediationDispatchService:
    def __init__(self, state_path: Path, runner: IRemediationRunner,
                registry_path: Path = model_registry.CONFIG_PATH, clock=time.time,
                status_reader: IRemediationStatusReader | None = None):
        self._state_path = state_path
        self._runner = runner
        self._status_reader = status_reader
        self._registry_path = registry_path
        self._clock = clock
        self._lock = threading.Lock()

    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self._state_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, state: dict[str, Any]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._state_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(state))
        os.replace(tmp, self._state_path)

    def _model(self, model_id: str) -> dict | None:
        for row in model_registry.registry(self._registry_path):
            if row['id'] == model_id:
                return row
        return None

    def dispatch(self, data: dict) -> dict[str, Any]:
        """Never raises except on a malformed request body (pydantic ValidationError,
        left to the caller to turn into a 400); every policy/runner outcome is a
        normal ``{"ok": ...}`` dict so one bad alert can't take the route down."""
        request = RemediationDispatchRequest.model_validate(data)
        with self._lock:
            state = self._load()
            existing = state.get(request.alert_key)
            if isinstance(existing, dict) and existing.get('status') == 'submitted':
                return {'ok': True, 'already_submitted': True,
                        'status': existing.get('task_state') or existing.get('status'),
                        'task_id': existing.get('task_id'), 'model_id': existing.get('model_id')}

            entry = self._model(request.model_id)
            if entry is None:
                return {'ok': False, 'already_submitted': False, 'error': 'unknown_model',
                        'detail': f'"{request.model_id}" is not a registered model'}
            if not REQUIRED_CAPABILITIES.intersection(entry['task_capabilities']):
                return {'ok': False, 'already_submitted': False, 'error': 'model_not_capable',
                        'detail': f'"{request.model_id}" is not registered for diagnosis or writes'}
            if not entry['configured']:
                return {'ok': False, 'already_submitted': False, 'error': 'model_unavailable',
                        'detail': entry['detail']}

            outcome = self._runner.run(request.alert_key, request.model_id, request.prompt)
            now = self._clock()
            if outcome.ok:
                state[request.alert_key] = {
                    'status': 'submitted', 'task_state': outcome.status,
                    'task_id': outcome.task_id, 'model_id': request.model_id,
                    'submitted_at': now, 'title': request.title, 'agent': request.agent,
                    'task_ref': request.task_id,
                }
                self._save(state)
                return {'ok': True, 'already_submitted': False, 'status': outcome.status,
                        'task_id': outcome.task_id, 'model_id': request.model_id}

            state[request.alert_key] = {
                'status': 'failed', 'error': outcome.error, 'model_id': request.model_id, 'submitted_at': now,
            }
            self._save(state)
            return {'ok': False, 'already_submitted': False, 'error': outcome.error,
                    'detail': outcome.detail, 'status': outcome.status}

    def status(self, alert_key: str) -> dict[str, Any]:
        """The live state of the one task this dashboard submitted for ``alert_key``.

        Looked up by alert key, never by a caller-supplied task id, so the route
        can only ever report on tasks this ledger itself dispatched. Never raises."""
        with self._lock:
            existing = self._load().get(alert_key)
        if not isinstance(existing, dict) or existing.get('status') != 'submitted':
            return {'ok': False, 'error': 'not_submitted',
                    'detail': 'no task has been dispatched for this alert'}
        task_id = str(existing.get('task_id') or '')
        if self._status_reader is None:
            return {'ok': False, 'error': 'status_unsupported', 'task_id': task_id,
                    'state': existing.get('task_state') or 'submitted',
                    'detail': 'this host\'s runner cannot report task progress'}
        live = self._status_reader.status(task_id)
        if not live.ok:
            return {'ok': False, 'error': live.error, 'detail': live.detail, 'task_id': task_id,
                    'state': existing.get('task_state') or 'submitted'}
        if live.state != existing.get('task_state'):
            with self._lock:
                state = self._load()
                if isinstance(state.get(alert_key), dict):
                    state[alert_key]['task_state'] = live.state
                    self._save(state)
        return {'ok': True, 'task_id': task_id, 'state': live.state, 'terminal': live.terminal,
                'succeeded': live.succeeded, 'summary': live.summary, 'detail': live.detail}


def from_environment() -> RemediationDispatchService:
    """The one place that names this host's dispatch-state file and runner."""
    state = Path(os.environ.get('REMEDIATION_DISPATCH_STATE_PATH', str(DEFAULT_STATE_PATH))).expanduser()
    runner = default_runner()
    reader = runner if callable(getattr(runner, 'status', None)) else None
    return RemediationDispatchService(state, runner, status_reader=reader)


def dispatch(data: dict) -> dict[str, Any]:
    """POST /api/alert-remediation/dispatch, routed from http_app/post_routes.py."""
    return from_environment().dispatch(data)


def status(alert_key: str) -> dict[str, Any]:
    """GET /api/alert-remediation/status?alert_key=..., routed from http_app/get_routes.py."""
    if not alert_key or len(alert_key) > 200:
        return {'ok': False, 'error': 'invalid_alert_key', 'detail': 'alert_key is required'}
    return from_environment().status(alert_key)
