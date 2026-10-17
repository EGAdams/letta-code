"""agents/conversation_management.py -- Context bar + Save to Memory + Clear.

Self-contained module (see its docstring for why it duplicates the tiny
letta-id-shape check instead of importing server), so these tests patch
`urllib.request.urlopen` directly rather than going through server.py.
"""
import json

from agents import conversation_management as cm


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self._payload).encode()


def test_context_payload_reports_current_and_max(monkeypatch):
    def fake_urlopen(url, timeout=0):
        assert url == 'http://100.80.49.10:8283/v1/agents/agent-toyota-uuid/context'
        return _Resp({
            'context_window_size_current': 5489,
            'context_window_size_max': 128000,
        })

    monkeypatch.setattr(cm.urllib.request, 'urlopen', fake_urlopen)
    result = cm.context_payload('agent-toyota-uuid')
    assert result == {'ok': True, 'current': 5489, 'max': 128000}


def test_context_payload_not_a_letta_agent():
    assert cm.context_payload('agent-claude')['ok'] is False
    assert cm.context_payload('')['ok'] is False


def test_context_payload_letta_unreachable(monkeypatch):
    def fake_urlopen(url, timeout=0):
        raise OSError('unreachable')

    monkeypatch.setattr(cm.urllib.request, 'urlopen', fake_urlopen)
    result = cm.context_payload('agent-toyota-uuid')
    assert result['ok'] is False


def test_compact_posts_summarize_and_reports_counts(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=0):
        captured['url'] = req.full_url
        captured['method'] = req.method
        return _Resp({
            'summary': 'The user and Toyota discussed the schedule.',
            'num_messages_before': 40,
            'num_messages_after': 3,
        })

    monkeypatch.setattr(cm.urllib.request, 'urlopen', fake_urlopen)

    result = cm.compact('agent-toyota-uuid')

    assert result == {
        'ok': True,
        'summary': 'The user and Toyota discussed the schedule.',
        'num_messages_before': 40,
        'num_messages_after': 3,
    }
    assert captured['method'] == 'POST'
    assert captured['url'].endswith('/v1/agents/agent-toyota-uuid/summarize')


def test_compact_not_a_letta_agent():
    assert cm.compact('agent-claude') == {'ok': False, 'error': 'not a Letta agent'}


def test_compact_reports_letta_errors(monkeypatch):
    def fake_urlopen(req, timeout=0):
        raise OSError('boom')

    monkeypatch.setattr(cm.urllib.request, 'urlopen', fake_urlopen)
    result = cm.compact('agent-toyota-uuid')
    assert result['ok'] is False


def test_reset_messages_patches_without_default_initial_messages(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=0):
        captured['url'] = req.full_url
        captured['method'] = req.method
        captured['body'] = json.loads(req.data.decode())
        return _Resp({})

    monkeypatch.setattr(cm.urllib.request, 'urlopen', fake_urlopen)

    result = cm.reset_messages('agent-toyota-uuid')

    assert result == {'ok': True}
    assert captured['method'] == 'PATCH'
    assert captured['url'].endswith('/v1/agents/agent-toyota-uuid/reset-messages')
    assert captured['body'] == {'add_default_initial_messages': False}


def test_reset_messages_not_a_letta_agent():
    assert cm.reset_messages('agent-claude') == {'ok': False, 'error': 'not a Letta agent'}


def test_reset_messages_reports_letta_errors(monkeypatch):
    def fake_urlopen(req, timeout=0):
        raise OSError('boom')

    monkeypatch.setattr(cm.urllib.request, 'urlopen', fake_urlopen)
    result = cm.reset_messages('agent-toyota-uuid')
    assert result['ok'] is False
