"""Mazda's voice turn: shared recall around her unchanged Letta stream.

Offline: the Letta stream and the sidecar POST are both injected. What matters
is that recall fails open, the exchange is recorded, ordinary text streams
untouched, and an OPEN_AGENT: toyota reply is never spoken as-is.
"""
import threading

import pytest
from pydantic import ValidationError

import mazda_service
from letta_code.streaming import ConversationStreamRecord


def _delta(text):
    return ConversationStreamRecord.provider_event(
        {'type': 'stream_event', 'event': {'message_type': 'assistant_message', 'content': text}})


def _result():
    return ConversationStreamRecord.provider_event({'type': 'result', 'conversation_id': 'conv-1'})


class _Sidecar:
    def __init__(self, compose=None):
        self.compose = compose
        self.calls = []
        self.recorded = threading.Event()

    def __call__(self, route, payload):
        self.calls.append((route, payload))
        if route == '/memory/record':
            self.recorded.set()
            return {'ok': True}
        return self.compose or {'ok': False, 'error': 'URLError: refused'}


def _run(deltas, sidecar=None, text='hello Mazda'):
    sidecar = sidecar or _Sidecar()
    seen = []

    def stream(request):
        seen.append(request)
        yield from [_delta(d) for d in deltas]
        yield _result()

    out = list(mazda_service.stream_mazda_turn(
        mazda_service.MazdaTurnRequest(text=text), stream=stream, post=sidecar))
    assert sidecar.recorded.wait(2), 'exchange was never recorded'
    return out, seen[0], sidecar


def _spoken(out):
    return ''.join(mazda_service._assistant_delta(r.event) for r in out if r.type == 'event')


def test_recall_is_composed_in_front_of_the_users_words():
    sidecar = _Sidecar({'ok': True, 'prompt': '[memory]\nhello Mazda', 'recalled': 2})
    _, request, _ = _run(['Hi.'], sidecar)
    assert request.agent == mazda_service.MAZDA_AGENT_ID
    assert request.text.endswith('[memory]\nhello Mazda')
    assert mazda_service.HORN_NOTE in request.text


def test_a_dead_sidecar_costs_recall_not_the_turn():
    out, request, _ = _run(['Hi ', 'there.'])
    assert request.text.endswith('hello Mazda')
    assert _spoken(out) == 'Hi there.'
    assert out[-1].event['type'] == 'result'


def test_the_exchange_is_recorded_with_the_original_words():
    _, _, sidecar = _run(['Imported.'], text='import June')
    route, payload = sidecar.calls[-1]
    assert route == '/memory/record'
    assert payload == {'session': 'mazda', 'user': 'import June', 'agent': 'Imported.'}


def test_ordinary_text_streams_record_for_record():
    out, _, _ = _run(['Hello', ' world'])
    assert [r.event for r in out[:2]] == [_delta('Hello').event, _delta(' world').event]


def test_a_reply_that_starts_like_the_directive_but_diverges_is_spoken_whole():
    out, _, _ = _run(['OPE', 'N the file?'])
    assert _spoken(out) == 'OPEN the file?'
    assert not any(r.event.get('name') == 'agent_handoff' for r in out if r.event)


def test_put_toyota_on_the_horn_becomes_a_handoff_not_speech():
    out, _, sidecar = _run(['OPEN_AGENT:', ' toyota | Here she is.'])
    assert out[0].event == {
        'type': 'tool_result', 'name': 'agent_handoff',
        'handoff': {'agent': 'toyota', 'name': 'Toyota'}}
    assert _spoken(out) == 'Here she is.'
    assert 'OPEN_AGENT' not in _spoken(out)
    assert sidecar.calls[-1][1]['agent'] == 'Here she is.'


def test_the_route_refuses_another_agents_id():
    with pytest.raises(ValidationError):
        mazda_service.MazdaTurnRequest(text='hi', agent='agent-someone-else')
