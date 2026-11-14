"""The independent ADW task supervisor's per-task problems reach the failure cards."""
import json

import receptionist_alerts
from adw_task_alerts import AdwTaskAlertSource

NOW = 1_800_000_000.0


def _source(tmp_path, alerts, heartbeat=NOW - 10, clock=NOW, generated_at=None):
    state = {'heartbeat_at': heartbeat, 'generated_at': generated_at if generated_at is not None else heartbeat,
             'alerts': alerts}
    path = tmp_path / 'adw_supervisor_state.json'
    path.write_text(json.dumps(state))
    return AdwTaskAlertSource(path, tmp_path / 'acks.json', clock=lambda: clock)


STALL = {'task_id': 't_1', 'tier': 'diagnose', 'observation_error': None, 'failure': None,
         'recent_events': [{'message': 'No recorded task progress past the diagnose threshold.'}]}
FAILURE = {'task_id': 't_2', 'tier': 'incident', 'observation_error': None,
           'failure': {'status': 'failed', 'ended_at': NOW - 30, 'error': 'boom',
                       'message': 'The task ended failed. RECOMMENDATION: tell the person who asked for it.'}}
UNREADABLE = {'task_id': 't_3', 'tier': 'warn', 'observation_error': 'No valid queue/progress timestamp; task health is unknown.',
              'failure': None}
OK = {'task_id': 't_4', 'tier': 'ok', 'observation_error': None, 'failure': None}


def test_a_stalled_task_becomes_a_card(tmp_path):
    out = _source(tmp_path, [STALL]).alerts()
    assert out['ok'] and len(out['alerts']) == 1
    card = out['alerts'][0]
    assert card['id'] == 'adw-t_1-diagnose'
    assert card['task_id'] == 't_1'
    assert card['severity'] == 'escalated'
    assert 'needs independent diagnosis' in card['title']
    assert card['spoken'] == 'No recorded task progress past the diagnose threshold.'


def test_a_failed_task_becomes_an_urgent_card(tmp_path):
    out = _source(tmp_path, [FAILURE]).alerts()
    assert len(out['alerts']) == 1
    card = out['alerts'][0]
    assert card['id'] == f'adw-t_2-failed-{int(NOW - 30)}'
    assert card['severity'] == 'urgent'
    assert 't_2 failed' in card['title'] and '(URGENT)' in card['title']
    assert card['spoken'].startswith('The task ended failed.')


def test_unreadable_telemetry_becomes_a_notice_card_not_a_tier_card(tmp_path):
    out = _source(tmp_path, [UNREADABLE]).alerts()
    assert len(out['alerts']) == 1
    card = out['alerts'][0]
    assert card['kind'] == 'task_unreadable'
    assert card['severity'] == 'notice'
    assert card['spoken'] == UNREADABLE['observation_error']


def test_an_ok_tier_entry_produces_no_card(tmp_path):
    assert _source(tmp_path, [OK]).alerts() == {'ok': True, 'reachable': True, 'alerts': []}


def test_a_recent_successful_task_becomes_a_completion_card(tmp_path):
    source = _source(tmp_path, [], clock=NOW)
    state = json.loads((tmp_path / 'adw_supervisor_state.json').read_text())
    state['tasks'] = {'t_done': {'last_status': 'completed', 'last_observed_at': NOW - 5}}
    (tmp_path / 'adw_supervisor_state.json').write_text(json.dumps(state))
    out = source.alerts()
    assert len(out['alerts']) == 1
    card = out['alerts'][0]
    assert card['kind'] == 'task_completed'
    assert card['severity'] == 'notice'
    assert card['title'] == 'ADW supervisor: task t_done completed'


def test_old_successful_task_is_not_presented_as_new(tmp_path):
    source = _source(tmp_path, [], clock=NOW)
    state = json.loads((tmp_path / 'adw_supervisor_state.json').read_text())
    state['tasks'] = {'t_old': {'last_status': 'succeeded', 'last_observed_at': NOW - 86401}}
    (tmp_path / 'adw_supervisor_state.json').write_text(json.dumps(state))
    assert source.alerts()['alerts'] == []


def test_a_resolved_task_simply_stops_appearing(tmp_path):
    # The supervisor itself drops a cleared task from its published `alerts`
    # list; this source has no memory of its own to fight that signal.
    assert _source(tmp_path, []).alerts() == {'ok': True, 'reachable': True, 'alerts': []}


def test_got_it_hides_the_card_until_it_escalates(tmp_path):
    source = _source(tmp_path, [STALL])
    card_id = source.alerts()['alerts'][0]['id']
    assert source.acknowledge_alerts([card_id]) == {'ok': True, 'acknowledged': 1}
    assert source.alerts()['alerts'] == []
    worse = _source(tmp_path, [{**STALL, 'tier': 'incident'}])
    cards = worse.alerts()['alerts']
    assert [c['severity'] for c in cards] == ['urgent'], 'a new tier is a new card id, shown again'


def test_blanket_got_it_is_refused(tmp_path):
    assert _source(tmp_path, [STALL]).acknowledge_alerts(None)['ok'] is False


def test_no_supervisor_state_on_this_host_is_quiet(tmp_path):
    missing = AdwTaskAlertSource(tmp_path / 'none.json', tmp_path / 'acks.json')
    out = missing.alerts()
    assert out == {'ok': False, 'reachable': False, 'alerts': [], 'error': out['error']}
    assert 'may not be running' in out['error']


def test_malformed_state_is_reported_not_raised(tmp_path):
    path = tmp_path / 'adw_supervisor_state.json'
    path.write_text('{not json')
    out = AdwTaskAlertSource(path, tmp_path / 'acks.json').alerts()
    assert out['ok'] is False and out['reachable'] is True
    assert 'could not be read' in out['error']


def test_a_state_that_is_not_an_object_is_reported(tmp_path):
    path = tmp_path / 'adw_supervisor_state.json'
    path.write_text('[1, 2, 3]')
    out = AdwTaskAlertSource(path, tmp_path / 'acks.json').alerts()
    assert out['ok'] is False and 'not an object' in out['error']


def test_a_stale_heartbeat_is_reported_not_shown_as_current(tmp_path):
    out = _source(tmp_path, [STALL], heartbeat=NOW - 600).alerts()
    assert out['ok'] is False and out['reachable'] is True
    assert 'stale' in out['error']


def test_entries_missing_a_task_id_are_skipped(tmp_path):
    out = _source(tmp_path, [{'tier': 'incident'}]).alerts()
    assert out == {'ok': True, 'reachable': True, 'alerts': []}


def test_collect_tags_adw_task_cards_with_the_source_name(tmp_path):
    out = receptionist_alerts.collect({'adw_tasks': _source(tmp_path, [STALL])})
    assert [(a['agent'], a['name']) for a in out['alerts']] == [('adw_tasks', 'ADW Supervisor')]
