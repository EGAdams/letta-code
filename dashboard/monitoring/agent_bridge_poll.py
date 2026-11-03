"""The Poll Settings tab: is the ChatGPT bridge worker polling, and when is its next check?

The worker (`agent-bridge-worker.service`, in agent_blocks) polls
bridge.americansjewelry.com for tasks ChatGPT queued. It keeps two small files
this module only reads:

* `poll_settings.json` -- the numbers EG chose (30 s idle, and so on). Editing
  it and restarting the service is how they change.
* `~/.cache/agent_bridge/poll_state.json` -- written by the worker after every
  check: what it is doing and when it checks next. Times and counts only.

Nothing here talks to HostGator. Showing the page never adds a request to the
gateway; the countdown is drawn from the worker's own file.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

SERVICE = 'agent-bridge-worker.service'
SETTINGS_PATH = Path(os.path.expanduser(
    '~/agent_blocks/lancedb_memory/agent_bridge_worker/poll_settings.json'))
STATE_PATH = Path(os.path.expanduser('~/.cache/agent_bridge/poll_state.json'))

#: One row per setting, in page order: (key, label, what it means, unit).
#: The worker owns the values and their defaults; this is only how to say them.
SETTING_ROWS = (
    ('idle_seconds', 'Check interval while idle',
     'How long the worker waits between checks when nothing is happening.', 's'),
    ('burst_seconds', 'Fast interval after a task',
     'While a conversation is recent, check this often so a follow-up is picked up quickly.', 's'),
    ('burst_window_seconds', 'How long "recent conversation" lasts',
     'After a task finishes, use the fast interval for this long, then go back to idle.', 's'),
    ('slow_down_seconds', 'Back-off when HostGator says slow down',
     'After HTTP 429 or 503 from the gateway, wait this long before trying again.', 's'),
    ('error_base_seconds', 'First wait after an error',
     'Any other failure (no network, 500, timeout) waits this long, doubling each time it repeats.', 's'),
    ('error_max_seconds', 'Longest wait after errors',
     'The doubling stops here. One good check resets it.', 's'),
    ('active_hours', 'Active hours (ignore times)',
     'Outside these hours the worker does not check at all. An end earlier than the start runs overnight (22:00 to 06:00). Empty means around the clock.', ''),
)


class ServiceState(BaseModel):
    model_config = ConfigDict(extra='forbid')

    active: str = 'unknown'        # systemd ActiveState: active, inactive, failed...
    sub: str = ''
    enabled: str = 'unknown'       # UnitFileState: enabled, disabled...
    pid: int = 0
    started_at: float | None = None


class SettingRow(BaseModel):
    model_config = ConfigDict(extra='forbid')

    key: str
    label: str
    help: str
    unit: str
    value: float | int | str | dict | None
    in_file: bool


class PollPagePayload(BaseModel):
    model_config = ConfigDict(extra='forbid')

    polling: Literal['active', 'paused', 'disabled']
    reason: str
    service: ServiceState
    state: dict | None
    settings: list[SettingRow]
    settings_error: str = ''
    settings_path: str
    settings_changed_since_start: bool = False
    restart_command: str = f'systemctl --user restart {SERVICE}'
    now: float


def _systemctl_show() -> ServiceState:
    try:
        out = subprocess.run(
            ['systemctl', '--user', 'show', SERVICE, '--timestamp=unix',
             '-p', 'ActiveState', '-p', 'SubState', '-p', 'UnitFileState',
             '-p', 'MainPID', '-p', 'ActiveEnterTimestamp'],
            capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return ServiceState()
    return parse_show(out)


def parse_show(out: str) -> ServiceState:
    """`systemctl show` key=value lines into a ServiceState. Pure."""
    kv = dict(line.split('=', 1) for line in out.splitlines() if '=' in line)
    started = kv.get('ActiveEnterTimestamp', '').lstrip('@')
    return ServiceState(
        active=kv.get('ActiveState') or 'unknown', sub=kv.get('SubState', ''),
        enabled=kv.get('UnitFileState') or 'unknown',
        pid=int(kv.get('MainPID') or 0),
        started_at=float(started) if started.isdigit() and int(started) else None)


def _read_json(path: Path) -> tuple[dict | None, str]:
    try:
        return json.loads(path.read_text(encoding='utf-8')), ''
    except FileNotFoundError:
        return None, f'{path.name} not found'
    except (OSError, ValueError) as error:
        return None, f'{path.name} unreadable: {error}'


def setting_rows(raw: dict | None) -> list[SettingRow]:
    raw = raw or {}
    return [SettingRow(key=key, label=label, help=help_, unit=unit,
                       value=raw.get(key), in_file=key in raw)
            for key, label, help_, unit in SETTING_ROWS]


def outside_hours(raw: dict | None, hour: int) -> bool:
    """True when `active_hours` is set and `hour` (local) is outside it. Pure."""
    hours = (raw or {}).get('active_hours')
    if not isinstance(hours, dict):
        return False
    start, end = hours.get('start_hour', 7), hours.get('end_hour', 24)
    if end < start:                                   # overnight, e.g. 22 to 6
        return not (hour >= start or hour < end)
    return not (start <= hour < end)


def classify(service: ServiceState, state: dict | None,
             raw: dict | None = None, hour: int = 12) -> tuple[str, str]:
    """('active'|'paused'|'disabled', why). Pure.

    Green needs both: systemd says the service runs, and the state file says the
    loop is waiting or working (written by that same process, not a stale one).
    """
    if service.active != 'active':
        why = f'service is {service.active}'
        if service.enabled != 'enabled':
            why += f' and {service.enabled} at login'
        return 'disabled', why
    if not state:
        return 'disabled', 'service is running but has not reported a check yet'
    if state.get('phase') == 'stopped':
        return 'disabled', 'the poll loop reported that it stopped'
    if service.pid and state.get('pid') and state['pid'] != service.pid:
        return 'disabled', 'the state file is from an older worker process'
    if state.get('phase') == 'working':
        return 'active', 'running a task'
    if outside_hours(raw, hour):
        return 'paused', 'outside active hours; no checks until they open'
    return 'active', 'polling'


def agent_bridge_poll_payload() -> dict:
    service = _systemctl_show()
    state, _ = _read_json(STATE_PATH)
    raw, settings_error = _read_json(SETTINGS_PATH)
    polling, reason = classify(service, state, raw, time.localtime().tm_hour)
    changed = False
    try:
        changed = bool(service.started_at and SETTINGS_PATH.stat().st_mtime > service.started_at)
    except OSError:
        pass
    return PollPagePayload(
        polling=polling, reason=reason, service=service, state=state,
        settings=setting_rows(raw), settings_error=settings_error,
        settings_path=str(SETTINGS_PATH), settings_changed_since_start=changed,
        now=time.time()).model_dump(mode='json')
