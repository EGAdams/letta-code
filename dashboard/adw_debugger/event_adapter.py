"""Adapter: an SSSF event row becomes the debugger's DebugEvent.

GoF Adapter. An instrumented ADW puts its details under payload['adw_debug'];
every other row is mapped from SSSF's own event types, so an ADW that has not
adopted the instrumentation still shows its phases, logs and outcomes. Text is
passed through whole -- nothing here shortens, summarizes or redacts it.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from .models import DebugEvent, RawEvent

_PHASE_END_STATUS = {'success': 'pass', 'fail': 'fail'}


def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False, default=str)


def _deadline(recorded_at: str, seconds: Any) -> str | None:
    try:
        return (datetime.fromisoformat(recorded_at) + timedelta(seconds=float(seconds))).isoformat(timespec='milliseconds')
    except (TypeError, ValueError):
        return None


def _instrumented(event: DebugEvent, detail: dict[str, Any]) -> DebugEvent:
    kind = str(detail.get('kind', 'log'))
    event.kind = kind
    event.instance_id = str(detail.get('instance_id') or event.phase_id)
    event.phase_name = str(detail.get('phase_name') or event.phase_name)
    if isinstance(detail.get('attempt'), int):
        event.attempt = detail['attempt']
    event.tool = str(detail.get('tool', ''))
    event.call_id = str(detail.get('call_id', ''))
    event.source_instance = str(detail.get('source_instance', ''))
    event.target_instance = str(detail.get('target_instance', ''))
    if kind == 'constructed':
        event.message = f"constructed {detail.get('class_name', 'phase')} for phase {event.phase_name}"
    elif kind == 'bound':
        event.message = f'phase instance started as {event.phase_id}'
    elif kind == 'cleanup':
        parts = [f"cleanup {detail.get('result', 'unknown')}"]
        parts += [str(detail[key]) for key in ('error', 'note') if detail.get(key)]
        event.message = ' -- '.join(parts)
    elif kind == 'tool_call':
        event.message = f"{event.tool} [{event.call_id}]\n{_text(detail.get('arguments', {}))}"
    elif kind == 'tool_result':
        event.message = f"{event.tool} [{event.call_id}] returned\n{_text(detail.get('result', ''))}"
    else:
        event.message = _text(detail.get('text', ''))
    if kind == 'waiting':
        event.deadline_at = _deadline(event.recorded_at, detail.get('deadline_seconds'))
    return event


def _plain(event: DebugEvent, raw: RawEvent, payload: dict[str, Any]) -> DebugEvent:
    event.instance_id = event.phase_id
    if raw.type == 'phase_start':
        event.kind, event.status = 'phase_start', 'running'
        event.message = _text(payload.get('description', ''))
    elif raw.type == 'phase_end':
        event.kind = 'phase_end'
        event.status = _PHASE_END_STATUS.get(str(payload.get('status')))
        event.message = f"phase ended: {payload.get('status', 'unknown')}"
    elif raw.type == 'error':
        event.kind = 'error'
        event.message = _text(payload.get('error') or payload.get('reason') or payload)
    elif raw.type == 'log' and isinstance(payload.get('message'), str):
        event.kind, event.message = 'console', payload['message']
    else:
        event.kind, event.message = raw.type or 'log', _text(payload)
    return event


def adapt(raw: RawEvent, machine: str) -> DebugEvent:
    try:
        payload = json.loads(raw.payload_json) if raw.payload_json else {}
    except ValueError:
        payload = {'unparsed': raw.payload_json}
    if not isinstance(payload, dict):
        payload = {'value': payload}
    event = DebugEvent(cursor=raw.cursor, event_id=raw.event_id, recorded_at=raw.recorded_at,
                       kind=raw.type, payload=payload, machine=machine, adw_name=raw.adw_name,
                       run_id=raw.run_id, phase_id=raw.phase_id,
                       phase_name=raw.name if raw.phase_id else '')
    detail = payload.get('adw_debug')
    return _instrumented(event, detail) if isinstance(detail, dict) else _plain(event, raw, payload)
