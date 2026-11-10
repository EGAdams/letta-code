"""The gateway's queue-watch alerts reach the dashboard's failure cards, and "Got it" acknowledges them there."""
import io
import json
import urllib.error

import receptionist_alerts
from gateway_alerts import GatewayAlertSource


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _source(tmp_path):
    (tmp_path / 'w').write_text('worker-secret\n')
    (tmp_path / 'c').write_text('client-secret\n')
    return GatewayAlertSource('https://gw.example/v1/', tmp_path / 'w', tmp_path / 'c')


SNAPSHOT = {'alerts': [
    {'alert_id': 'al_1', 'kind': 'task_queued_too_long', 'task_id': 't_1', 'severity': 'escalated',
     'problem': 'Print job t_1 has waited 20 min.', 'recommended_action': 'Do not resend the print.', 'acknowledged': False},
    {'alert_id': 'al_2', 'kind': 'worker_silent', 'task_id': None, 'severity': 'notice',
     'problem': 'quiet', 'recommended_action': 'check', 'acknowledged': True}]}


def test_unacknowledged_alerts_become_cards_read_with_the_worker_token(tmp_path):
    seen = []

    def opener(request, timeout=None):
        seen.append((request.full_url, request.get_method(), request.headers['Authorization']))
        return _Response(json.dumps(SNAPSHOT).encode())

    out = _source(tmp_path).alerts(opener=opener)
    assert seen == [('https://gw.example/v1/alerts', 'GET', 'Bearer worker-secret')]
    assert out['ok'] and [a['id'] for a in out['alerts']] == ['al_1'], 'an acknowledged alert is not re-shown'
    card = out['alerts'][0]
    assert card['title'] == 'Star Trek Bridge: a task is stuck in the queue (ESCALATED)'
    assert card['spoken'] == 'Print job t_1 has waited 20 min. Do not resend the print.'
    assert 'secret' not in json.dumps(out)


def test_an_unreachable_gateway_is_reported_not_raised(tmp_path):
    def down(request, timeout=None):
        raise urllib.error.URLError('Name or service not known')

    out = _source(tmp_path).alerts(opener=down)
    assert out['ok'] is False and out['reachable'] is True and 'Name or service not known' in out['error']


def test_no_token_on_this_machine_is_quiet(tmp_path):
    out = GatewayAlertSource('https://gw', tmp_path / 'none', tmp_path / 'none').alerts()
    assert out == {'ok': False, 'reachable': False, 'alerts': [], 'error': 'no worker token on this machine'}


def test_got_it_acknowledges_each_id_with_the_client_credential(tmp_path):
    seen = []

    def opener(request, timeout=None):
        seen.append((request.full_url, request.get_method(), request.headers['Authorization'], request.data))
        return _Response(b'{}')

    out = _source(tmp_path).acknowledge_alerts(['al_1', 'al_3'], opener=opener)
    assert out == {'ok': True, 'acknowledged': 2}
    assert seen[0] == ('https://gw.example/v1/alerts/al_1/ack', 'POST', 'Bearer client-secret',
                       b'{"note": "Got it, on the dashboard"}')
    assert _source(tmp_path).acknowledge_alerts(None)['ok'] is False, 'no blanket acknowledgement'


def test_collect_tags_gateway_alerts_as_the_bridge(tmp_path):
    class Fake:
        name = 'Star Trek Bridge'

        def alerts(self):
            return {'ok': True, 'alerts': [{'id': 'al_1', 'title': 't', 'spoken': 's'}]}

        def acknowledge_alerts(self, ids):
            return {'ok': True}

    out = receptionist_alerts.collect({'bridge': Fake()})
    assert out['alerts'] == [{'id': 'al_1', 'title': 't', 'spoken': 's', 'agent': 'bridge', 'name': 'Star Trek Bridge'}]
