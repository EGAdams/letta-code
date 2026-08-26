"""Coverage for the Token-dropdown contract: agent_oauth_account_payload lists
every provider across both model families, and patch_agent_oauth_account can
jump an agent to a provider outside its current family."""

import json

import server


def test_payload_lists_every_provider_across_both_families(monkeypatch):
    monkeypatch.setattr(server, 'letta_get', lambda *_a, **_kw: {
        'llm_config': {'provider_name': 'claude-pro-max', 'model': 'claude-sonnet-5'},
    })

    payload = server.agent_oauth_account_payload('letta-id-123')

    assert payload['ok'] is True
    assert payload['current'] == 'claude-pro-max'
    providers = {opt['provider'] for opt in payload['options']}
    assert providers == set(server.OAUTH_PROVIDER_ACCOUNTS)
    aol_option = next(opt for opt in payload['options'] if opt['provider'] == 'chatgpt-plus-pro-mom')
    assert aol_option['label'] == 'rbarnesrol@aol.com'


def test_payload_current_prefers_pending_model_over_live_provider(monkeypatch):
    monkeypatch.setattr(server, 'letta_get', lambda *_a, **_kw: {
        'llm_config': {'provider_name': 'claude-pro-max', 'model': 'claude-sonnet-5'},
    })

    payload = server.agent_oauth_account_payload(
        'letta-id-123', pending_model='chatgpt-plus-pro-mom/gpt-5.6-luna')

    assert payload['current'] == 'chatgpt-plus-pro-mom'


def test_patch_same_family_switch_keeps_current_model_id(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({'llm_config': {'handle': 'claude-pro-max-eg/claude-sonnet-5'}}).encode()

    monkeypatch.setattr(server, 'letta_id_for', lambda _agent_id: 'letta-id-123')
    monkeypatch.setattr(server, 'letta_get', lambda *_a, **_kw: {
        'llm_config': {'provider_name': 'claude-pro-max', 'model': 'claude-sonnet-5'},
    })
    monkeypatch.setattr(server.urllib.request, 'urlopen', lambda *_a, **_kw: Response())

    result = server.patch_agent_oauth_account('agent-x', 'claude-pro-max-eg')

    assert result == {
        'ok': True, 'account': 'eg', 'provider': 'claude-pro-max-eg',
        'model': 'claude-pro-max-eg/claude-sonnet-5',
    }


def test_patch_cross_family_switch_uses_default_model_for_target_family(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({'llm_config': {}}).encode()

    monkeypatch.setattr(server, 'letta_id_for', lambda _agent_id: 'letta-id-123')
    monkeypatch.setattr(server, 'letta_get', lambda *_a, **_kw: {
        'llm_config': {'provider_name': 'claude-pro-max', 'model': 'claude-sonnet-5'},
    })
    captured = {}

    def fake_urlopen(req, *_a, **_kw):
        captured['body'] = json.loads(req.data.decode())
        return Response()

    monkeypatch.setattr(server.urllib.request, 'urlopen', fake_urlopen)

    result = server.patch_agent_oauth_account('agent-x', 'chatgpt-plus-pro-mom')

    assert result['ok'] is True
    assert result['account'] == 'mom'
    assert result['provider'] == 'chatgpt-plus-pro-mom'
    assert captured['body']['model'].startswith('chatgpt-plus-pro-mom/')


def test_patch_rejects_unknown_provider(monkeypatch):
    monkeypatch.setattr(server, 'letta_id_for', lambda _agent_id: 'letta-id-123')

    result = server.patch_agent_oauth_account('agent-x', 'not-a-real-provider')

    assert result == {'ok': False, 'error': "unknown provider 'not-a-real-provider'"}
