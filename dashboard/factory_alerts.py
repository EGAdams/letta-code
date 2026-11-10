"""The factory watchdog's problems, as one more source for the dashboard's failure cards.

factory-ops-watch (~/factory_machine_ops, factory_ops/fleet.py) checks every
30 s that each Bridge worker lane is running *and* checking the queue, that the
Bridge worker supervisor and the ADW supervisor are running *and* reporting,
and publishes what is wrong, with its own heartbeat, to watch_status.json.
This turns each open problem into a card, and raises one more card when that
heartbeat stops, so a dead watchdog is as visible as a dead worker.

A card lasts while its problem does (the watchdog clears it when the condition
ends) or until "Got it"; an escalation (warning -> investigate -> escalate ->
incident) is a new card, so a problem that keeps getting older is shown again.
Acknowledgements are kept in a small file next to the status, by card id.
Never raises.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

STATE_DIR = Path('~/.local/state/factory-ops').expanduser()
SEVERITY = {'notice': 'notice', 'warning': 'notice', 'investigate': 'escalated',
            'escalate': 'escalated', 'incident': 'urgent'}


class FactoryWatchSource:
    """Satisfies receptionist_alerts.IAlertSource."""

    name = 'Factory Watchdog'

    def __init__(self, status_file: Path, ack_file: Path, clock=time.time) -> None:
        self._status_file = status_file
        self._ack_file = ack_file
        self._clock = clock

    def _acked(self) -> set[str]:
        try:
            data = json.loads(self._ack_file.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return set()
        return {str(i) for i in data} if isinstance(data, list) else set()

    def _cards(self) -> list[dict[str, Any]] | None:
        try:
            status = json.loads(self._status_file.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return None
        if not isinstance(status, dict):
            raise ValueError('watch_status.json is not an object')
        cards = []
        beat, interval = float(status.get('heartbeat_at') or 0), float(status.get('interval') or 30)
        quiet = self._clock() - beat
        if quiet > max(120.0, 4 * interval):
            minutes = round(quiet / 60)
            cards.append({'id': f'fw-watchdog-silent-{int(beat)}', 'kind': 'watchdog_silent', 'severity': 'urgent',
                          'title': 'Factory Watchdog: the watchdog itself stopped (URGENT)',
                          'spoken': f'The factory watchdog has not checked the Bridge workers or supervisors for '
                                    f'{minutes} minutes, so their failures would go unseen on this machine. Check '
                                    'factory-ops-watch in Server Management. The Star Trek Bridge gateway still '
                                    'watches the workers from off this machine.'})
        for problem in status.get('problems') or []:
            if not isinstance(problem, dict) or not problem.get('open') or not problem.get('key'):
                continue
            level = str(problem.get('level') or 'notice')
            severity = SEVERITY.get(level, 'notice')
            key = str(problem['key']).replace(':', '-')
            cards.append({'id': f"fw-{key}-{int(float(problem.get('since') or 0))}-{level}",
                          'kind': str(problem['key']).split(':')[0], 'severity': severity,
                          'title': f"Factory Watchdog: {problem.get('title', 'something stopped working')}"
                                   + ('' if severity == 'notice' else f' ({severity.upper()})'),
                          'spoken': str(problem.get('detail') or '')})
        return cards

    def alerts(self) -> dict[str, Any]:
        try:
            cards = self._cards()
        except Exception as exc:  # noqa: BLE001 -- an unreadable status is reported, never raised
            return {'ok': False, 'reachable': True, 'alerts': [],
                    'error': f'watch_status.json could not be read ({type(exc).__name__})'}
        if cards is None:
            return {'ok': False, 'reachable': False, 'alerts': [], 'error': 'the factory watchdog does not run here'}
        acked = self._acked()
        return {'ok': True, 'reachable': True, 'alerts': [c for c in cards if c['id'] not in acked]}

    def acknowledge_alerts(self, ids: list[str] | None) -> dict[str, Any]:
        """Hides each named card. All ids are required, as for the gateway's."""
        if not ids:
            return {'ok': False, 'error': 'name the watchdog alert ids to acknowledge'}
        try:
            current = {c['id'] for c in self._cards() or []}
            keep = (self._acked() & current) | set(ids)   # forget acks for cards that are gone
            tmp = self._ack_file.with_suffix('.tmp')
            tmp.write_text(json.dumps(sorted(keep)), encoding='utf-8')
            os.replace(tmp, self._ack_file)
        except Exception as exc:  # noqa: BLE001
            return {'ok': False, 'acknowledged': 0, 'error': type(exc).__name__}
        return {'ok': True, 'acknowledged': len(ids)}


def from_environment() -> FactoryWatchSource:
    """The one place that names this machine's watchdog files."""
    state = Path(os.environ.get('FACTORY_OPS_STATE_DIR', str(STATE_DIR))).expanduser()
    return FactoryWatchSource(state / 'watch_status.json', state / 'dashboard_acks.json')
