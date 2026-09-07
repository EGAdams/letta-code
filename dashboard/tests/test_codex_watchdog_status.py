"""status_payload(): shape and the fail-soft contract.

Real inspector/reader are exercised here (no fakes) since this box always has
*some* /proc to read -- the interesting behaviour is that a broken dependency
degrades to `ok: False` rather than 500ing the Server Management page.
"""

from __future__ import annotations

from health import codex_watchdog_status
from health.codex_watchdog_contracts import WatchdogAction
from health.codex_watchdog_status import status_payload
from health.codex_watchdog_store import InMemoryWatchdogActionStore


def test_returns_ok_shape_on_a_healthy_box():
    payload = status_payload()

    assert payload['ok'] is True
    assert payload['error'] is None
    assert isinstance(payload['sessions'], list)
    assert isinstance(payload['recent_actions'], list)
    assert payload['thresholds']['kill_percent'] == 90.0
    assert payload['thresholds']['max_concurrent'] == 1


def test_includes_recorded_actions_from_the_store(monkeypatch):
    store = InMemoryWatchdogActionStore()
    store.record(WatchdogAction(timestamp=1.0, action='terminate_quota',
                                 pgid=1, cmd='node bin/codex', reason='97%'))
    monkeypatch.setattr(codex_watchdog_status, 'default_store', lambda: store)

    payload = status_payload()

    assert len(payload['recent_actions']) == 1
    assert payload['recent_actions'][0]['action'] == 'terminate_quota'


def test_a_broken_inspector_fails_soft_instead_of_raising(monkeypatch):
    def _boom():
        raise RuntimeError('no /proc here')

    monkeypatch.setattr(codex_watchdog_status, 'ProcProcessInspector', _boom)

    payload = status_payload()

    assert payload['ok'] is False
    assert 'no /proc here' in payload['error']
    assert payload['sessions'] == []
