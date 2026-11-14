"""The independent ADW task supervisor's per-task problems, as one more source for the dashboard's failure cards.

monitoring/adw_supervisor.py (see docs/adw-supervisor.md) already watches every observed ADW task --
remote-worker jobs, the Worker Activity "Terminal" event log, anything the local post office sees -- and
publishes an `alerts` entry whenever a task stalls past a threshold, ends in a failed/timed-out status, or
has telemetry that cannot be trusted. Until now that list was only visible on the Worker Activity page's
own table, and only to someone who opened it (see worker-escalation-render.js / renderWorkerEscalation).
Nothing carried it to the failure cards every tab already watches, the way gateway_alerts and
factory_alerts do for their own sources.

Read-only, same as the supervisor it reads: this module never dispatches, resubmits, retries, or restarts
anything, and it changes no credentials. A task leaving the published `alerts` list (it finished, or its
tier dropped back to "ok") is the supervisor's own signal that the problem cleared; its card simply stops
being emitted on the next poll, the same way a resolved Factory Watchdog problem does.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from monitoring.supervisor_contracts import PublishedSupervisorState

DEFAULT_STATE_PATH = Path(os.path.expanduser('~/.cache/agent_bridge/adw_supervisor_state.json'))
DEFAULT_ACK_FILE = Path(os.path.expanduser('~/.cache/agent_bridge/adw_task_alert_acks.json'))
# The supervisor's own poll loop defaults to 20 s; worker_activity.py treats its state file as stale
# past 120 s. Reuse that definition of "stale" rather than inventing a second one.
STALE_SECONDS = 120
COMPLETION_RECENT_SECONDS = 86400

TIER_SEVERITY = {'warn': 'notice', 'recommend': 'notice', 'diagnose': 'escalated', 'incident': 'urgent'}
TIER_WHAT = {
    'warn': 'is not making progress',
    'recommend': 'needs a look',
    'diagnose': 'needs independent diagnosis',
    'incident': 'is a live incident',
}


class AdwTaskAlertSource:
    """Satisfies receptionist_alerts.IAlertSource."""

    name = 'ADW Supervisor'

    def __init__(self, state_path: Path, ack_file: Path, clock=time.time) -> None:
        self._state_path = state_path
        self._ack_file = ack_file
        self._clock = clock

    def _acked(self) -> set[str]:
        try:
            data = json.loads(self._ack_file.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return set()
        return {str(i) for i in data} if isinstance(data, list) else set()

    def _state(self) -> PublishedSupervisorState | None:
        try:
            raw = json.loads(self._state_path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return None
        if not isinstance(raw, dict):
            raise ValueError('adw_supervisor_state.json is not an object')
        try:
            state = PublishedSupervisorState.model_validate(raw)
        except ValidationError as exc:
            raise ValueError('adw_supervisor_state.json has invalid telemetry fields') from exc
        heartbeat = state.heartbeat_at or state.generated_at or 0
        if self._clock() - heartbeat > STALE_SECONDS:
            raise ValueError('adw_supervisor heartbeat is stale; not reporting its last-known alerts as current')
        return state

    @staticmethod
    def _card(alert: dict[str, Any]) -> dict[str, Any] | None:
        task_id = alert.get('task_id')
        if not isinstance(task_id, str) or not task_id:
            return None
        failure = alert.get('failure') if isinstance(alert.get('failure'), dict) else None
        events = [e for e in alert.get('recent_events') or [] if isinstance(e, dict)]
        last_message = events[-1].get('message') if events else None

        if failure:
            status = str(failure.get('status') or 'failed')
            ended = failure.get('ended_at')
            card_id = f"adw-{task_id}-failed-{int(ended) if isinstance(ended, (int, float)) else 'unknown'}"
            return {'id': card_id, 'kind': 'task_failed', 'task_id': task_id, 'severity': 'urgent',
                    'title': f"ADW supervisor: task {task_id} {status} (URGENT)",
                    'spoken': str(failure.get('message') or last_message or f'Task {task_id} ended {status}.')}

        observation_error = alert.get('observation_error')
        if observation_error:
            return {'id': f"adw-{task_id}-unreadable", 'kind': 'task_unreadable', 'task_id': task_id,
                    'severity': 'notice', 'title': f"ADW supervisor: task {task_id} telemetry is unreadable",
                    'spoken': str(observation_error)}

        tier = str(alert.get('tier') or 'warn')
        if tier == 'ok':
            return None
        severity = TIER_SEVERITY.get(tier, 'notice')
        what = TIER_WHAT.get(tier, 'needs attention')
        title = f"ADW supervisor: task {task_id} {what}" + ('' if severity == 'notice' else f' ({severity.upper()})')
        return {'id': f"adw-{task_id}-{tier}", 'kind': f'task_{tier}', 'task_id': task_id, 'severity': severity,
                'title': title, 'spoken': str(last_message or f'Task {task_id} {what}.')}

    def _cards(self) -> list[dict[str, Any]]:
        state = self._state()
        if state is None:
            return []
        cards = []
        for alert in state.alerts:
            if not isinstance(alert, dict):
                continue
            card = self._card(alert)
            if card is not None:
                cards.append(card)
        # The supervisor deliberately keeps terminal task state after it has
        # left ``alerts``.  Preserve that completion signal for the dashboard
        # for one day, so a successful ADW is visible without turning the
        # retained ledger into an endless stream of old cards.
        now = self._clock()
        for task_id, task in state.tasks.items():
            if not isinstance(task_id, str) or not isinstance(task, dict):
                continue
            if task.get('failure') or task.get('observation_error'):
                continue
            status = task.get('last_status')
            if status not in {'succeeded', 'completed'}:
                continue
            completed_at = task.get('last_observed_at')
            if not isinstance(completed_at, (int, float)) or now - completed_at > COMPLETION_RECENT_SECONDS:
                continue
            cards.append({
                'id': f'adw-{task_id}-completed-{int(completed_at)}',
                'kind': 'task_completed',
                'task_id': task_id,
                'severity': 'notice',
                'title': f'ADW supervisor: task {task_id} completed',
                'spoken': f'Task {task_id} completed successfully.',
            })
        return cards

    def alerts(self) -> dict[str, Any]:
        """Open ADW task problems as failure cards. An unreadable or stale supervisor state is
        reported as a read error (never shown as "no problems"); a missing one (not installed/
        activated on this host, per docs/adw-supervisor.md) is quietly unreachable, same as a
        receptionist sidecar that isn't running here."""
        try:
            cards = self._cards()
        except ValueError as exc:
            return {'ok': False, 'reachable': True, 'alerts': [],
                    'error': f'adw_supervisor state could not be read: {exc}'}
        if not self._state_path.is_file():
            return {'ok': False, 'reachable': False, 'alerts': [],
                    'error': 'adw_supervisor has not written a state file; it may not be running here'}
        acked = self._acked()
        return {'ok': True, 'reachable': True, 'alerts': [c for c in cards if c['id'] not in acked]}

    def acknowledge_alerts(self, ids: list[str] | None) -> dict[str, Any]:
        """Hides each named card. All ids are required, as for the Factory Watchdog's and the
        gateway's own cards -- there is no blanket "Got it" for every ADW task problem."""
        if not ids:
            return {'ok': False, 'error': 'name the ADW task alert ids to acknowledge'}
        try:
            # Forget acks for cards that are gone, so an old id can't silently swallow a
            # brand-new problem that happens to reuse it.
            current = {c['id'] for c in self._cards()}
            keep = (self._acked() & current) | set(ids)
            self._ack_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._ack_file.with_suffix('.tmp')
            tmp.write_text(json.dumps(sorted(keep)), encoding='utf-8')
            os.replace(tmp, self._ack_file)
        except (OSError, ValueError) as exc:
            return {'ok': False, 'acknowledged': 0, 'error': type(exc).__name__}
        return {'ok': True, 'acknowledged': len(ids)}


def from_environment() -> AdwTaskAlertSource:
    """The one place that names this machine's adw_supervisor state and ack files."""
    state = Path(os.environ.get('ADW_SUPERVISOR_STATE_PATH', str(DEFAULT_STATE_PATH))).expanduser()
    ack = Path(os.environ.get('ADW_TASK_ALERT_ACK_FILE', str(DEFAULT_ACK_FILE))).expanduser()
    return AdwTaskAlertSource(state, ack)
