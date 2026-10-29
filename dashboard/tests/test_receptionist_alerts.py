"""Failure alerts from Toyota's and Sydney's sidecars reach the dashboard."""
import io
import json
import urllib.error

import receptionist_alerts
from receptionist_sidecar import ReceptionistAlertAckRequest, SidecarBridge


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _opener(payload, seen):
    def opener(request, timeout=None):
        seen.append(request if isinstance(request, str) else (request.full_url, request.data))
        return _Response(json.dumps(payload).encode())
    return opener


def _down(request, timeout=None):
    raise urllib.error.URLError('connection refused')


def _bridge(name='Sydney'):
    return SidecarBridge(name, 'http://127.0.0.1:8769', 'sydney-receptionist', 'X', 60)


def test_alerts_reads_the_sidecar():
    seen = []
    out = _bridge().alerts(opener=_opener({'ok': True, 'alerts': [{'id': 'a1', 'spoken': 'x'}]}, seen))
    assert seen == ['http://127.0.0.1:8769/alerts']
    assert out['ok'] and out['reachable'] and out['alerts'][0]['id'] == 'a1'


def test_alerts_from_a_down_sidecar_never_raise():
    out = _bridge().alerts(opener=_down)
    assert out == {'ok': False, 'reachable': False, 'alerts': [], 'error': 'connection refused'}


def test_acknowledge_posts_the_ids():
    seen = []
    out = _bridge().acknowledge_alerts(['a1'], opener=_opener({'ok': True, 'acknowledged': 1}, seen))
    assert seen == [('http://127.0.0.1:8769/alerts/ack', b'{"ids": ["a1"]}')]
    assert out == {'ok': True, 'acknowledged': 1}


class _Fake:
    def __init__(self, name, state):
        self.name, self._state, self.acked = name, state, []

    def alerts(self):
        return self._state

    def acknowledge_alerts(self, ids):
        self.acked.append(ids)
        return {'ok': True, 'acknowledged': len(ids or [])}


def test_collect_tags_alerts_and_reports_unreadable_boards_but_not_down_ones():
    bridges = {
        'toyota': _Fake('Toyota', {'ok': False, 'reachable': False, 'alerts': [], 'error': 'down'}),
        'sydney': _Fake('Sydney', {'ok': True, 'alerts': [{'id': 'a1', 'spoken': 'plan failed'}]}),
        'other': _Fake('Other', {'ok': False, 'reachable': True, 'alerts': [], 'error': 'PermissionError'}),
    }
    out = receptionist_alerts.collect(bridges)
    assert out['alerts'] == [{'id': 'a1', 'spoken': 'plan failed', 'agent': 'sydney', 'name': 'Sydney'}]
    assert out['errors'] == [{'agent': 'other', 'name': 'Other', 'error': 'PermissionError'}]


def test_acknowledge_goes_to_the_named_receptionist():
    sydney = _Fake('Sydney', {'ok': True, 'alerts': []})
    out = receptionist_alerts.acknowledge(
        ReceptionistAlertAckRequest(agent='sydney', ids=['a1']), {'sydney': sydney})
    assert out['acknowledged'] == 1 and sydney.acked == [['a1']]


def test_default_sources_are_the_three_sidecars():
    assert sorted(receptionist_alerts.sources()) == ['cashy', 'sydney', 'toyota']
