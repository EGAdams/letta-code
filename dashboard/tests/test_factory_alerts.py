"""The factory watchdog's problems reach the failure cards; a silent watchdog is a card of its own."""
import json

import receptionist_alerts
from factory_alerts import FactoryWatchSource

NOW = 1_800_000_000.0


def _source(tmp_path, problems, heartbeat=NOW - 10, clock=NOW):
    (tmp_path / 'watch_status.json').write_text(json.dumps(
        {'heartbeat_at': heartbeat, 'interval': 30, 'problems': problems}))
    return FactoryWatchSource(tmp_path / 'watch_status.json', tmp_path / 'acks.json', clock=lambda: clock)


STALLED = {'key': 'worker_not_polling:express', 'title': 'the express Bridge worker is running but not checking the queue',
           'detail': 'its next queue check was due 9 min ago.', 'since': NOW - 540, 'level': 'investigate', 'open': True}
PENDING = {'key': 'worker_down:general', 'title': 't', 'detail': 'd', 'since': NOW - 5, 'level': 'notice', 'open': False}


def test_open_problems_become_cards_and_pending_ones_do_not(tmp_path):
    out = _source(tmp_path, [STALLED, PENDING]).alerts()
    assert out['ok'] and len(out['alerts']) == 1
    card = out['alerts'][0]
    assert card['id'] == f'fw-worker_not_polling-express-{int(NOW - 540)}-investigate'
    assert card['title'] == 'Factory Watchdog: the express Bridge worker is running but not checking the queue (ESCALATED)'
    assert card['spoken'] == 'its next queue check was due 9 min ago.'


def test_got_it_hides_the_card_until_it_escalates(tmp_path):
    source = _source(tmp_path, [STALLED])
    card_id = source.alerts()['alerts'][0]['id']
    assert source.acknowledge_alerts([card_id]) == {'ok': True, 'acknowledged': 1}
    assert source.alerts()['alerts'] == []
    worse = _source(tmp_path, [{**STALLED, 'level': 'incident'}])
    cards = worse.alerts()['alerts']
    assert [c['severity'] for c in cards] == ['urgent'], 'an escalation is shown again'


def test_a_resolved_problem_leaves_no_card(tmp_path):
    assert _source(tmp_path, []).alerts() == {'ok': True, 'reachable': True, 'alerts': []}


def test_a_silent_watchdog_is_an_urgent_card(tmp_path):
    out = _source(tmp_path, [], heartbeat=NOW - 600).alerts()
    assert [c['kind'] for c in out['alerts']] == ['watchdog_silent']
    assert out['alerts'][0]['severity'] == 'urgent' and '10 minutes' in out['alerts'][0]['spoken']


def test_no_watchdog_on_this_machine_is_quiet_and_garbage_is_reported(tmp_path):
    missing = FactoryWatchSource(tmp_path / 'none.json', tmp_path / 'acks.json')
    assert missing.alerts()['reachable'] is False
    (tmp_path / 'bad.json').write_text('{not json')
    bad = FactoryWatchSource(tmp_path / 'bad.json', tmp_path / 'acks.json').alerts()
    assert bad['ok'] is False and bad['reachable'] is True


def test_blanket_got_it_is_refused(tmp_path):
    assert _source(tmp_path, [STALLED]).acknowledge_alerts(None)['ok'] is False


def test_collect_tags_watchdog_cards_as_factory(tmp_path):
    out = receptionist_alerts.collect({'factory': _source(tmp_path, [STALLED])})
    assert [(a['agent'], a['name']) for a in out['alerts']] == [('factory', 'Factory Watchdog')]
