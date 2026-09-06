"""The dashboard activity proxy is read-only and fails closed."""

import json

from health import claude_sdk_activity


def test_activity_payload_proxies_the_executor_feed(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return json.dumps({
                'ok': True,
                'current_run': {'status': 'running'},
                'events': [{'seq': 1, 'category': 'messages', 'text': 'hello'}],
            }).encode()

    monkeypatch.setattr(
        claude_sdk_activity.urllib.request,
        'urlopen',
        lambda *_args, **_kwargs: Response(),
    )

    payload = claude_sdk_activity.activity_payload()

    assert payload['current_run']['status'] == 'running'
    assert payload['events'][0]['text'] == 'hello'


def test_activity_payload_fails_closed_when_executor_is_unreachable(monkeypatch):
    monkeypatch.setattr(
        claude_sdk_activity.urllib.request,
        'urlopen',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError('offline')),
    )

    payload = claude_sdk_activity.activity_payload()

    assert payload['ok'] is False
    assert payload['events'] == []
    assert 'offline' in payload['error']
