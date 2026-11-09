"""Independent service probes and durable observed outage history."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import threading
import time

from monitoring.service_catalog import configured_services
from monitoring.service_management_models import (
    IServiceHistory, IServiceProbe, ServiceDefinition, ServiceHistoryEntry,
    ServiceObservation, ServicePage,
)

PROPERTIES = ('LoadState', 'ActiveState', 'SubState', 'UnitFileState', 'MainPID',
              'NRestarts', 'Result', 'ActiveEnterTimestamp', 'StateChangeTimestamp')


def _timestamp(value: str) -> float | None:
    try:
        number = float(value.lstrip('@'))
        return number if number > 0 else None
    except ValueError:
        return None


class SystemdServiceProbe:
    """Read fixed systemd properties without depending on the monitored API."""

    def observe(self, service: ServiceDefinition, now: float) -> ServiceObservation:
        observation = ServiceObservation(**service.model_dump(), checked_at=now)
        args = ['systemctl', *(['--user'] if service.scope == 'user' else []),
                'show', service.unit, '--timestamp=unix',
                '--property=' + ','.join(PROPERTIES)]
        try:
            result = subprocess.run(args, capture_output=True, text=True,
                                    timeout=4, check=False, shell=False)
        except (OSError, subprocess.SubprocessError):
            observation.detail = 'Systemd could not be reached; service state is unknown.'
            return observation
        values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        if result.returncode != 0:
            observation.detail = 'Systemd check failed; service state is unknown.'
            return observation
        observation.loaded = values.get('LoadState', '')
        observation.active = values.get('ActiveState', 'unknown')
        observation.sub = values.get('SubState', '')
        observation.enabled = values.get('UnitFileState') or 'unknown'
        observation.result = values.get('Result', '')
        try:
            observation.pid = int(values.get('MainPID') or 0)
            observation.restarts = int(values.get('NRestarts') or 0)
        except ValueError:
            observation.detail = 'Systemd returned invalid process metadata.'
            return observation
        if observation.loaded == 'not-found':
            observation.status = 'concern'
            observation.detail = 'Unit is not installed in this scope on this host.'
        elif observation.loaded != 'loaded':
            observation.detail = 'Unit load state could not be verified.'
        elif observation.active == 'active':
            observation.status = 'up'
            observation.since = _timestamp(values.get('ActiveEnterTimestamp', ''))
            observation.detail = 'Service is active.'
        elif observation.active in {'inactive', 'failed', 'activating', 'deactivating', 'reloading'}:
            observation.status = 'concern' if observation.active == 'reloading' else 'down'
            observation.since = _timestamp(values.get('StateChangeTimestamp', ''))
            observation.detail = f'Service is {observation.active} ({observation.sub}).'
        else:
            observation.detail = 'Systemd did not report a recognized service state.'
        return observation


class JsonServiceHistory:
    """Bounded transition history, persisted only when an observation changes."""

    def __init__(self, path: Path):
        self.path = path

    def record(self, observations: list[ServiceObservation]) -> str:
        try:
            state = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(state, dict) or not all(isinstance(v, dict) for v in state.values()):
                raise ValueError('Invalid history')
            state = {key: ServiceHistoryEntry.model_validate(value).model_dump(exclude_none=True)
                     for key, value in state.items()}
        except FileNotFoundError:
            state = {}
        except (OSError, ValueError, UnicodeError):
            return 'Service history could not be read; live service states are still available.'
        changed = False
        for observation in observations:
            identity = f'{observation.scope}:{observation.unit}'
            previous = state.get(identity, {})
            events = previous.get('events', [])
            if not isinstance(events, list):
                return 'Service history is invalid; live service states are still available.'
            down_since = previous.get('down_since')
            if observation.status == 'down':
                down_since = down_since or observation.since or observation.checked_at
                observation.down_since = down_since
                observation.down_for_seconds = max(0, int(observation.checked_at - down_since))
            if previous.get('status') != observation.status or previous.get('active') != observation.active:
                event = {'at': observation.checked_at, 'status': observation.status,
                         'active': observation.active, 'detail': observation.detail}
                if observation.status == 'up' and down_since:
                    event['outage_seconds'] = max(0, int((observation.since or observation.checked_at) - down_since))
                events = [event, *events][:50]
                changed = True
            if observation.status == 'up':
                down_since = None
            observation.events = events[:20]
            state[identity] = {'status': observation.status, 'active': observation.active,
                               'down_since': down_since, 'events': events}
        if changed:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_suffix('.tmp')
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                    json.dump(state, handle)
                temporary.replace(self.path)
            except OSError:
                return 'Service history could not be saved; live service states are still available.'
        return ''


class ServiceMonitor:
    """Serialize and cache probes across dashboard clients."""

    def __init__(self, probe: IServiceProbe, history: IServiceHistory):
        self.probe = probe
        self.history = history
        self.lock = threading.Lock()
        self.cached: dict | None = None
        self.cached_at = 0.0

    def payload(self) -> dict:
        with self.lock:
            if self.cached is not None and time.monotonic() - self.cached_at < 10:
                return self.cached
            definitions, error = configured_services()
            now = time.time()
            observations = [self.probe.observe(service, now) for service in definitions]
            history_error = self.history.record(observations)
            statuses = {item.status for item in observations}
            status = ('down' if 'down' in statuses else 'concern'
                      if error or history_error or statuses != {'up'} else 'up')
            self.cached = ServicePage(services=observations, status=status, checked_at=now,
                                      configuration_error=error, history_error=history_error).model_dump()
            self.cached_at = time.monotonic()
            return self.cached

    def run(self, stop: threading.Event | None = None) -> None:
        """Observe services even when no browser is open."""
        stop = stop or threading.Event()
        while not stop.is_set():
            self.payload()
            stop.wait(15)


MONITOR = ServiceMonitor(SystemdServiceProbe(), JsonServiceHistory(
    Path.home() / '.local/state/factory-ops/service-management.json'))


def service_management_payload() -> dict:
    return MONITOR.payload()
