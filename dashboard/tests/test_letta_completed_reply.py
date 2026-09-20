"""Recovery reads only a settled answer from the requested conversation."""

from datetime import datetime, timezone

from letta_code.completed_reply import LettaCompletedReplyProbe


AGENT = 'agent-frita'
CONVERSATION = 'conv-frita'
START = datetime(2026, 9, 20, 22, 52, tzinfo=timezone.utc)
NOW = datetime(2026, 9, 20, 22, 59, tzinfo=timezone.utc)


def _run(**changes):
    return {
        'agent_id': AGENT,
        'conversation_id': CONVERSATION,
        'status': 'completed',
        'stop_reason': 'end_turn',
        'created_at': '2026-09-20T22:57:29Z',
        'completed_at': '2026-09-20T22:57:39',
        **changes,
    }


def test_collects_persisted_final_messages_from_this_turn_in_order(monkeypatch):
    probe = LettaCompletedReplyProbe(now=lambda: NOW)
    paths = []

    def get(path):
        paths.append(path)
        if path.startswith('/v1/runs/'):
            return [_run()]
        return [
            {'message_type': 'assistant_message', 'date': '2026-09-20T22:57:39Z',
             'content': [{'type': 'text', 'text': 'Correction: tests passed.'}]},
            {'message_type': 'tool_return_message', 'date': '2026-09-20T22:57:30Z',
             'content': 'private tool output'},
            {'message_type': 'assistant_message', 'date': '2026-09-20T22:56:43Z',
             'content': 'System check: healthy.'},
            {'message_type': 'assistant_message', 'date': '2026-09-20T22:50:46Z',
             'content': 'stale previous answer'},
        ]

    monkeypatch.setattr(probe, '_get', get)
    assert probe.completed_reply(AGENT, CONVERSATION, START) == (
        'System check: healthy.\n\nCorrection: tests passed.')
    assert f'conversation_id={CONVERSATION}' in paths[0]
    assert f'/v1/conversations/{CONVERSATION}/messages' in paths[1]


def test_does_not_recover_an_unfinished_or_still_settling_run(monkeypatch):
    probe = LettaCompletedReplyProbe(now=lambda: NOW)
    calls = []

    def get(path):
        calls.append(path)
        return [_run(status='running')]

    monkeypatch.setattr(probe, '_get', get)
    assert probe.completed_reply(AGENT, CONVERSATION, START) is None
    assert len(calls) == 1

    monkeypatch.setattr(probe, '_get', lambda path: [
        _run(completed_at='2026-09-20T22:58:45Z')])
    assert probe.completed_reply(AGENT, CONVERSATION, START) is None


def test_does_not_return_an_older_or_other_agents_answer(monkeypatch):
    probe = LettaCompletedReplyProbe(now=lambda: NOW)
    for run in (
        _run(created_at='2026-09-20T22:50:00Z'),
        _run(agent_id='agent-other'),
        _run(conversation_id='conv-other'),
        _run(stop_reason='requires_approval'),
    ):
        monkeypatch.setattr(probe, '_get', lambda path, run=run: [run])
        assert probe.completed_reply(AGENT, CONVERSATION, START) is None


def test_waits_for_background_tool_result_even_after_an_assistant_message(monkeypatch):
    probe = LettaCompletedReplyProbe(now=lambda: NOW)
    messages = [
        {'message_type': 'assistant_message', 'date': '2026-09-20T22:57:39Z',
         'content': 'Preliminary answer.'},
        {'message_type': 'approval_request_message', 'date': '2026-09-20T22:56:00Z',
         'tool_call': {'name': 'Task', 'tool_call_id': 'call-task'}},
    ]

    def get(path):
        return [_run()] if path.startswith('/v1/runs/') else messages

    monkeypatch.setattr(probe, '_get', get)
    assert probe.completed_reply(AGENT, CONVERSATION, START) is None

    messages.insert(0, {
        'message_type': 'approval_response_message',
        'date': '2026-09-20T22:57:45Z',
        'approvals': [{'tool_call_id': 'call-task', 'status': 'success'}],
    })
    assert probe.completed_reply(AGENT, CONVERSATION, START) == 'Preliminary answer.'
