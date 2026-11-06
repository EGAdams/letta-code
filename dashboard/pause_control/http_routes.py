"""/api/pause-control/v1 -- the token-protected pause/resume/priority façade.

**Not wired into the dashboard yet.** `http_app/get_routes.py` and
`http_app/post_routes.py` own the live route ladders and both had uncommitted,
in-progress edits (Notes / Worker Activity work) when this module was written;
touching either risked clobbering that work mid-edit. `pause_control_dispatch`
is written the same way `scan_jobs.http_routes.scan_bridge_dispatch` is --
pure, request-in/response-out, no handler-object coupling -- specifically so
wiring it in later is a 3-line addition once those files are free:

    from pause_control.http_routes import PREFIX as PC_PREFIX, serve as pc_serve
    if self.path.startswith(PC_PREFIX):
        return pc_serve(self, 'GET')   # or 'POST', with the request body

See docs/bridge-pause-resume.md for the full blocker writeup, including why a
200 from this façade still does not mean the task actually paused.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

from contracts import StrictModel
from pause_control import composition
from pause_control.models import TERMINAL_STATUSES
from pause_control.repository import ControlRequestNotFound, InvalidTransition
from pause_control.service import ControlRefused

PREFIX = '/api/pause-control/v1'
_ACTIONS = {'pause', 'resume', 'priority'}
_IDEM_RE = re.compile(r'^[A-Za-z0-9._:-]{8,100}$')
_ROUTE = re.compile(r'^/requests(?:/(?P<id>[^/]+)(?:/(?P<sub>acknowledge))?)?$')

log = logging.getLogger('pause_control.http')


class ControlHttpRequest(StrictModel):
    method: str
    path: str
    query: str = ''
    headers: dict[str, str]
    body: bytes = b''


class ControlHttpResponse(StrictModel):
    code: int
    content_type: str
    body: bytes


def _json(code: int, data: object) -> ControlHttpResponse:
    return ControlHttpResponse(code=code, content_type='application/json',
                               body=json.dumps(data, indent=1).encode())


def _error(code: int, err: str, message: str) -> ControlHttpResponse:
    return _json(code, {'error': {'code': err, 'message': message}})


def pause_control_dispatch(request: ControlHttpRequest) -> ControlHttpResponse:
    try:
        return _dispatch(request)
    except ControlRefused as exc:
        return _error(exc.http, exc.code, str(exc))
    except ControlRequestNotFound:
        return _error(404, 'request_not_found', 'no control request with that id')
    except InvalidTransition as exc:
        return _error(409, 'invalid_transition', str(exc))
    except ValueError as exc:
        return _error(400, 'bad_request', str(exc)[:200])
    except Exception:  # noqa: BLE001 -- never leak a traceback through the façade
        log.exception('pause control request failed')
        return _error(500, 'internal_error', 'pause control request failed')


def serve(handler, method: str, body: bytes = b'') -> None:
    """Adapt a dashboard request handler to the façade and write its answer."""
    parsed = urlparse(handler.path)
    response = pause_control_dispatch(ControlHttpRequest(
        method=method, path=parsed.path, query=parsed.query,
        headers={name.lower(): value for name, value in handler.headers.items()}, body=body))
    handler._write(response.body, response.content_type, response.code)


def _authorize(headers: dict[str, str]) -> None:
    auth = composition.authorizer()
    if not auth.configured():
        raise ControlRefused('not_configured', 'pause control is not configured on this machine', 503)
    if not auth.authorize(headers.get('authorization')):
        raise ControlRefused('unauthorized', 'missing or incorrect bearer token', 401)


def _dispatch(request: ControlHttpRequest) -> ControlHttpResponse:
    match = _ROUTE.match(request.path[len(PREFIX):]) if request.path.startswith(PREFIX) else None
    if not match:
        return _error(404, 'not_found', 'unknown pause control route')
    _authorize(request.headers)
    request_id, sub = match.group('id'), match.group('sub')
    service = composition.service()

    if request_id is None:
        if request.method == 'POST':
            return _create(request, service)
        if request.method == 'GET':
            query = parse_qs(request.query)
            task_id = _one(query, 'task_id')
            order = _one(query, 'order') or 'time'
            records = service.list_for_task(task_id) if task_id else service.list_recent(
                _int(query, 'limit', 50), order)
            return _json(200, {'requests': [r.public() for r in records]})
        return _error(405, 'method_not_allowed', 'use GET or POST')

    if sub == 'acknowledge':
        if request.method != 'POST':
            return _error(405, 'method_not_allowed', 'use POST')
        return _acknowledge(request, request_id, service)
    if request.method != 'GET':
        return _error(405, 'method_not_allowed', 'use GET')
    record = service.get(request_id)
    if record is None:
        raise ControlRequestNotFound(request_id)
    return _json(200, record.public())


def _body(request: ControlHttpRequest) -> dict:
    try:
        data = json.loads(request.body or b'{}')
    except ValueError:
        raise ValueError('body must be JSON') from None
    if not isinstance(data, dict):
        raise ValueError('body must be a JSON object')
    return data


def _create(request: ControlHttpRequest, service) -> ControlHttpResponse:
    data = _body(request)
    allowed = {'task_id', 'action', 'note', 'idempotency_key', 'requested_by'}
    if set(data) - allowed:
        return _error(400, 'bad_request', f'body takes only {sorted(allowed)}')
    action = data.get('action')
    if action not in _ACTIONS:
        return _error(400, 'bad_request', 'action must be pause, resume or priority')
    key = data.get('idempotency_key') or request.headers.get('idempotency-key')
    if key is not None and not (isinstance(key, str) and _IDEM_RE.match(key)):
        return _error(400, 'bad_request', 'idempotency_key must be 8-100 of [A-Za-z0-9._:-]')
    requester = str(data.get('requested_by') or 'dashboard')[:80]
    task_id = str(data.get('task_id') or '')
    note = data.get('note')
    method = {'pause': service.request_pause, 'resume': service.request_resume,
              'priority': service.request_priority}[action]
    record, created = method(task_id, requester, note=note, idempotency_key=key)
    return _json(201 if created else 200, {**record.public(), 'replayed': not created})


def _acknowledge(request: ControlHttpRequest, request_id: str, service) -> ControlHttpResponse:
    data = _body(request)
    allowed = {'status', 'note', 'error', 'actor'}
    if set(data) - allowed:
        return _error(400, 'bad_request', f'body takes only {sorted(allowed)}')
    status = data.get('status')
    if status not in TERMINAL_STATUSES:
        return _error(400, 'bad_request', f'status must be one of {sorted(TERMINAL_STATUSES)}')
    actor = str(data.get('actor') or 'worker')[:80]
    record = service.acknowledge(request_id, status, actor, note=data.get('note'), error=data.get('error'))
    return _json(200, record.public())


def _one(query: dict, name: str) -> Optional[str]:
    values = query.get(name) or []
    return values[0] if values else None


def _int(query: dict, name: str, default: int) -> int:
    raw = _one(query, name)
    if raw is None:
        return default
    if not raw.isdigit() or len(raw) > 4:
        raise ValueError(f'{name} must be a small positive integer')
    return int(raw)
