"""The bridge to Sydney's receptionist_team sidecar.

Sydney is Toyota's engine run as ``--agent sydney`` on :8769, so her bridge is
the same SidecarBridge (an IReceptionistSidecar) as Toyota's and Mazda's at
a different address. What is worth asserting: her turns reach
HER port, every error names HER and HER unit (a "start toyota-receptionist"
hint in Sydney's box would send someone to restart the wrong service), the
envelope is Toyota's exactly, and she is listed and routed like any agent.
Offline -- the opener is faked, same as test_toyota_service.py.
"""
import io
import json
import urllib.error

import sydney_service
import toyota_service
from monitoring import agent_list
from receptionist_sidecar import SidecarBridge, SidecarTurnRequest


def _recording_opener(*records):
    seen = []
    payload = ''.join(json.dumps(r) + '\n' for r in records).encode()

    class _Response(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def opener(request, timeout=None):
        seen.append(request.full_url)
        return _Response(payload)

    return opener, seen


def _turn(opener):
    request = SidecarTurnRequest(text='ask the mechanic why Toyota is slow')
    return list(sydney_service.stream_sydney_turn(request, opener=opener))


def test_her_turns_go_to_her_own_port():
    opener, seen = _recording_opener({'kind': 'reply', 'text': 'On it.'},
                                     {'kind': 'result', 'session': 'sydney'})
    out = _turn(opener)
    assert seen == [f'{sydney_service.SYDNEY_SERVICE_URL}/turn']
    assert sydney_service.SYDNEY_SERVICE_URL.endswith(':8769')
    assert out[0].event == {'message_type': 'assistant_message', 'content': 'On it.'}
    assert out[-1].event == {'type': 'result', 'conversation_id': 'sydney'}


def test_a_handoff_to_toyota_reaches_the_browser():
    opener, _ = _recording_opener(
        {'kind': 'handoff', 'handoff': {'agent': 'toyota', 'name': 'Toyota'}},
        {'kind': 'result', 'session': 'sydney'})
    out = _turn(opener)
    assert out[0].event == {'type': 'tool_result', 'name': 'agent_handoff',
                            'handoff': {'agent': 'toyota', 'name': 'Toyota'}}


def test_a_dead_sidecar_names_sydney_and_her_unit_not_toyotas():
    def opener(*a, **k):
        raise urllib.error.URLError('Connection refused')

    out = _turn(opener)
    assert out[0].type == 'error'
    assert 'Sydney' in out[0].error and 'sydney-receptionist' in out[0].error
    assert 'Toyota' not in out[0].error and 'toyota-receptionist' not in out[0].error


def test_a_stream_without_a_result_names_her():
    opener, _ = _recording_opener({'kind': 'reply', 'text': 'half'})
    out = _turn(opener)
    assert out[-1].type == 'error' and "Sydney's stream" in out[-1].error


def test_toyota_and_sydney_are_one_implementation_at_two_addresses():
    import mazda_receptionist_service
    bridges = (sydney_service.BRIDGE, toyota_service.BRIDGE, mazda_receptionist_service.BRIDGE)
    assert all(type(b) is SidecarBridge for b in bridges)
    assert len({b.base_url for b in bridges}) == 3
    assert sydney_service.BRIDGE.unit == 'sydney-receptionist'


def test_both_turn_routes_go_through_the_one_route_table():
    from http_app.post_routes import RECEPTIONIST_TURN_ROUTES
    seen = []
    original = sydney_service.stream_sydney_turn
    sydney_service.stream_sydney_turn = lambda request: seen.append(request.text) or iter(())
    try:
        list(RECEPTIONIST_TURN_ROUTES['/api/sydney-turn'](SidecarTurnRequest(text='hi')))
    finally:
        sydney_service.stream_sydney_turn = original
    assert seen == ['hi']
    assert set(RECEPTIONIST_TURN_ROUTES) == {'/api/receptionist-turn', '/api/sydney-turn'}


def test_compact_asks_her_own_sidecar_and_passes_its_reply_back():
    opener, seen = _recording_opener({'ok': True, 'session': 'sydney--ctx1', 'summary': 'Hi.'})
    assert sydney_service.BRIDGE.compact(opener=opener) == {
        'ok': True, 'session': 'sydney--ctx1', 'summary': 'Hi.'}
    assert seen == [f'{sydney_service.SYDNEY_SERVICE_URL}/compact']


def test_compact_against_a_dead_sidecar_names_her_unit():
    def opener(*a, **k):
        raise urllib.error.URLError('Connection refused')

    out = sydney_service.BRIDGE.compact(opener=opener)
    assert out['ok'] is False and 'sydney-receptionist' in out['error']


def test_the_compact_route_reaches_each_receptionist():
    from http_app.post_routes import RECEPTIONIST_COMPACTS
    original = (toyota_service.compact, sydney_service.compact)
    toyota_service.compact = lambda: {'ok': True, 'who': 'toyota'}
    sydney_service.compact = lambda: {'ok': True, 'who': 'sydney'}
    try:
        assert {k: f()['who'] for k, f in RECEPTIONIST_COMPACTS.items()} == {
            'toyota': 'toyota', 'sydney': 'sydney'}
    finally:
        toyota_service.compact, sydney_service.compact = original


def _listing(listed):
    deps = agent_list.Collaborators(
        letta_agents=[], get_letta_id=lambda cfg: None, cache={},
        cache_lock=__import__('threading').Lock(), cache_ttl=60,
        build_agent_list=lambda **k: None, listed_agents=listed)
    return agent_list.build_agent_list(deps, force_refresh=True)


def test_the_agent_list_shows_whatever_listed_agents_it_is_given():
    class _Other:
        def as_agent_row(self):
            return {'id': 'agent-other', 'name': 'Other', 'model': '', 'letta': False}

    names = [a['name'] for a in _listing((_Other(),))]
    assert names == ['Other', 'Claude']
    assert [a['name'] for a in _listing(())] == ['Claude']


def test_she_is_listed_on_the_agent_management_tab():
    # Wiring, not a roster fetch: server.py is the composition root that hands
    # her listing to the agent list, which never names her itself.
    import server
    assert sydney_service.LISTING in server._agent_list_deps().listed_agents
    row = sydney_service.LISTING.as_agent_row()
    assert row['id'] == sydney_service.SYDNEY_AGENT_ID and row['name'] == 'Sydney'
    assert row['letta'] is False


def test_her_id_is_never_mistaken_for_a_letta_agent():
    import server
    assert server.letta_id_for(sydney_service.SYDNEY_AGENT_ID) is None


def test_server_management_can_see_and_restart_her():
    import server
    spec = next(s for s in server.SERVER_SPECS if s.key == 'sydney-receptionist')
    assert spec.probe.health_url == f'{sydney_service.SYDNEY_SERVICE_URL}/health'
    assert 'sydney-receptionist' in server.RESTARTABLE_KEYS
