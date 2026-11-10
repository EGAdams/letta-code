"""The Star Trek Bridge gateway's own alerts, as one more source for the dashboard's failure cards.

The gateway watches its queue from off this machine (agent_blocks'
agent_bridge/gateway/src/AlertWatch.php): a print stuck in the queue, a worker
that stopped polling, a failed or unconfirmed print, a crashed task. This reads
its GET /alerts with the worker token, which may only read, and acknowledges
with a client credential bound on the gateway, so "Got it" here is the same
acknowledgement ChatGPT's bridge_alert_acknowledge records.

Shaped like a receptionist sidecar's alerts so ReceptionistFailureAlert shows,
speaks and notifies them on whatever tab is open, with no front-end change.
Never raises; tokens are read per call and never logged or returned.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_URL = 'https://bridge.americansjewelry.com/api/agent-bridge/v1'
CONFIG_DIR = Path('~/.config/agent_bridge').expanduser()

KIND_TITLES = {
    'task_queued_too_long': 'a task is stuck in the queue',
    'worker_silent': 'a worker stopped checking in',
    'task_running_too_long': 'a task has run too long',
    'task_worker_lost': 'a running task lost its worker',
    'task_retried': 'a task is being retried',
    'task_crashed': 'a task crashed',
    'device_task_failed': 'a print or scan failed',
    'print_unconfirmed': 'a print was never confirmed',
    'print_ambiguous': 'a print may or may not have printed',
    'request_stalled': 'a request has stopped making progress',
    'request_blocked': 'a request is waiting on a blocker',
    'status_loop': 'status checks are repeating with no action taken',
    'request_watch_error': 'request supervision hit an error',
}


class GatewayAlertSource:
    """Satisfies receptionist_alerts.IAlertSource."""

    name = 'Star Trek Bridge'

    def __init__(self, base_url: str, read_token_file: Path, ack_token_file: Path) -> None:
        self.base_url = base_url.rstrip('/')
        self._read_token_file = read_token_file
        self._ack_token_file = ack_token_file

    def _request(self, path: str, token_file: Path, body: dict | None = None) -> urllib.request.Request:
        headers = {'Authorization': 'Bearer ' + token_file.read_text(encoding='utf-8').strip(),
                   'Accept': 'application/json', 'User-Agent': 'rol-dashboard/1'}
        data = None
        if body is not None:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(body).encode('utf-8')
        return urllib.request.Request(self.base_url + path, data=data, headers=headers,
                                      method='POST' if body is not None else 'GET')

    def alerts(self, timeout: float = 8, opener=urllib.request.urlopen) -> dict[str, Any]:
        """Unacknowledged gateway alerts as failure cards. An acknowledged one is gone from here
        even while its condition lasts; the gateway keeps it until it clears."""
        try:
            with opener(self._request('/alerts', self._read_token_file), timeout=timeout) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except FileNotFoundError:
            return {'ok': False, 'reachable': False, 'alerts': [], 'error': 'no worker token on this machine'}
        except urllib.error.URLError as exc:
            return {'ok': False, 'reachable': True, 'alerts': [],
                    'error': f'the gateway could not be asked for its alerts ({exc.reason})'}
        except Exception as exc:  # noqa: BLE001 -- a broken reply is reported, never raised
            return {'ok': False, 'reachable': True, 'alerts': [], 'error': f'{type(exc).__name__}'}
        if not isinstance(payload, dict) or not isinstance(payload.get('alerts'), list):
            return {'ok': False, 'reachable': True, 'alerts': [], 'error': 'malformed gateway alerts reply'}
        cards = [self._card(a) for a in payload['alerts']
                 if isinstance(a, dict) and a.get('alert_id') and not a.get('acknowledged')]
        return {'ok': True, 'reachable': True, 'alerts': cards}

    def supervision(self, timeout: float = 6, opener=urllib.request.urlopen) -> dict[str, Any]:
        """The gateway's supervised requests and its watch's health, for Worker Activity and
        All Monitors. Read-only, with the worker token. Never raises; unavailable is said, never
        shown as "no requests"."""
        try:
            with opener(self._request('/alerts', self._read_token_file), timeout=timeout) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except FileNotFoundError:
            return {'available': False, 'reason': 'no worker token on this machine'}
        except urllib.error.URLError as exc:
            return {'available': False, 'reason': f'the gateway could not be asked ({exc.reason})'}
        except Exception as exc:  # noqa: BLE001
            return {'available': False, 'reason': f'{type(exc).__name__}'}
        if not isinstance(payload, dict):
            return {'available': False, 'reason': 'malformed gateway alerts reply'}
        requests = payload.get('requests')
        watch = payload.get('watch') if isinstance(payload.get('watch'), dict) else {}
        alerts = [a for a in payload.get('alerts') or [] if isinstance(a, dict)]
        out: dict[str, Any] = {
            'available': isinstance(requests, dict),
            'reason': '' if isinstance(requests, dict) else 'this gateway does not supervise requests yet',
            'open': [], 'recently_closed': [], 'thresholds': {},
            'watch': {'checked_at': payload.get('checked_at'), 'now': payload.get('now'),
                      'checked_seconds_ago': watch.get('checked_seconds_ago'),
                      'refresh_seconds': watch.get('refresh_seconds'),
                      'unacknowledged': payload.get('unacknowledged'),
                      'request_alerts': [a.get('alert_id') for a in alerts
                                         if str(a.get('kind', '')).startswith(('request_', 'status_loop'))]},
        }
        if isinstance(requests, dict):
            for key in ('open', 'recently_closed'):
                out[key] = [r for r in requests.get(key) or [] if isinstance(r, dict)]
            out['thresholds'] = requests.get('thresholds') if isinstance(requests.get('thresholds'), dict) else {}
        return out

    @staticmethod
    def _card(alert: dict) -> dict[str, Any]:
        what = KIND_TITLES.get(str(alert.get('kind')), 'something needs attention')
        severity = str(alert.get('severity') or 'notice')
        return {'id': alert['alert_id'], 'task_id': alert.get('task_id'), 'kind': alert.get('kind'),
                'severity': severity,
                'title': f'Star Trek Bridge: {what}' + ('' if severity == 'notice' else f' ({severity.upper()})'),
                'spoken': f"{alert.get('problem', '')} {alert.get('recommended_action', '')}".strip()}

    def acknowledge_alerts(self, ids: list[str] | None, timeout: float = 8,
                           opener=urllib.request.urlopen) -> dict[str, Any]:
        """Acknowledges each id on the gateway. All ids are required: a blanket "Got it" for
        every Bridge alert is not offered."""
        if not ids:
            return {'ok': False, 'error': 'name the Bridge alert ids to acknowledge'}
        done, errors = 0, []
        for alert_id in ids:
            try:
                request = self._request(f'/alerts/{alert_id}/ack', self._ack_token_file,
                                        {'note': 'Got it, on the dashboard'})
                with opener(request, timeout=timeout) as response:
                    response.read()
                done += 1
            except FileNotFoundError:
                return {'ok': False, 'acknowledged': done, 'error': 'no client credential to acknowledge with'}
            except Exception as exc:  # noqa: BLE001
                errors.append(f'{alert_id}: {getattr(exc, "code", type(exc).__name__)}')
        return {'ok': not errors, 'acknowledged': done, **({'error': '; '.join(errors)} if errors else {})}


def from_environment() -> GatewayAlertSource:
    """The one place that names this machine's gateway URL and credential files."""
    return GatewayAlertSource(
        os.environ.get('BRIDGE_GATEWAY_URL', DEFAULT_URL),
        Path(os.environ.get('BRIDGE_WORKER_TOKEN_FILE', str(CONFIG_DIR / 'worker_token'))).expanduser(),
        Path(os.environ.get('BRIDGE_ALERT_ACK_TOKEN_FILE', str(CONFIG_DIR / 'toyota_client_token'))).expanduser())
