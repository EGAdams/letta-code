"""The bridge to Cashy's sidecar (agent_blocks/adws/adw_cashy_service.py).

Same SidecarBridge as Toyota's and Sydney's, at :8770. Worth asserting: her
turns reach HER port, a dead sidecar names HER unit, a hand-off she sends
reaches the browser like Sydney's, and the Agent Management tab lists her.
Offline -- the opener is faked.
"""
import io
import json
import threading
import urllib.error

import cashy_service
from monitoring import agent_list
from receptionist_sidecar import SidecarTurnRequest


def _opener(*records):
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
    return list(cashy_service.stream_cashy_turn(SidecarTurnRequest(text='open Chase'), opener=opener))


def test_her_turns_go_to_her_own_port():
    opener, seen = _opener({'kind': 'reply', 'text': 'Opened Chase.'}, {'kind': 'result', 'session': 'default'})
    out = _turn(opener)
    assert seen == [f'{cashy_service.CASHY_SERVICE_URL}/turn']
    assert cashy_service.CASHY_SERVICE_URL.endswith(':8770')
    assert out[0].event == {'message_type': 'assistant_message', 'content': 'Opened Chase.'}


def test_a_handoff_to_toyota_reaches_the_browser():
    opener, _ = _opener({'kind': 'handoff', 'handoff': {'agent': 'toyota', 'name': 'Toyota'}},
                        {'kind': 'result', 'session': 'default'})
    assert _turn(opener)[0].event == {'type': 'tool_result', 'name': 'agent_handoff',
                                      'handoff': {'agent': 'toyota', 'name': 'Toyota'}}


def test_a_dead_sidecar_names_cashy_and_her_unit():
    def opener(*a, **k):
        raise urllib.error.URLError('Connection refused')

    out = _turn(opener)
    assert out[0].type == 'error'
    assert 'Cashy' in out[0].error and 'cashy-agent' in out[0].error


def test_the_agent_management_tab_lists_her():
    deps = agent_list.Collaborators(
        letta_agents=[], get_letta_id=lambda cfg: None, cache={}, cache_lock=threading.Lock(),
        cache_ttl=60, build_agent_list=lambda **k: None, listed_agents=(cashy_service.LISTING,))
    rows = agent_list.build_agent_list(deps, force_refresh=True)
    rows = rows['agents'] if isinstance(rows, dict) else rows
    assert any(r['id'] == cashy_service.CASHY_AGENT_ID and r['name'] == 'Cashy' for r in rows)


def test_server_py_lists_her():
    import server
    assert cashy_service.LISTING in server._agent_list_deps().listed_agents
    assert any(s['key'] == 'cashy-agent' for s in server.SERVERS)
