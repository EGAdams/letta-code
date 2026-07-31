from __future__ import annotations

import json
from io import BytesIO

import pytest
from pydantic import ValidationError

import server
from agents.fake_letta_gateway import FakeLettaGateway
from agents.letta_gateway import ILettaGateway, LettaAgentModel
from agents.model_options import AgentModelOptionsService
from agents.urllib_letta_gateway import UrllibLettaGateway


class _Response(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_agent_model_boundary_rejects_extra_and_coerced_fields():
    with pytest.raises(ValidationError):
        LettaAgentModel.model_validate({'current': '', 'unexpected': True})
    with pytest.raises(ValidationError):
        LettaAgentModel.model_validate({'current': 56})


def test_fake_letta_gateway_satisfies_port_and_records_calls():
    gateway = FakeLettaGateway(
        {'agent-1': LettaAgentModel(current='chatgpt-plus-pro/gpt-5.6-sol')})

    assert isinstance(gateway, ILettaGateway)
    assert gateway.get_agent_model('agent-1', timeout=9) == LettaAgentModel(
        current='chatgpt-plus-pro/gpt-5.6-sol')
    assert gateway.calls == [('agent-1', 9)]


def test_urllib_gateway_reads_handle_and_owns_url_construction():
    observed = {}

    def opener(url, timeout):
        observed.update(url=url, timeout=timeout)
        return _Response(json.dumps({
            'id': 'agent-1',
            'llm_config': {
                'handle': 'chatgpt-plus-pro/gpt-5.6-terra',
                'model': 'gpt-5.6-terra',
                'context_window': 272000,
            },
        }).encode())

    gateway = UrllibLettaGateway('http://letta.test/base/', opener=opener)

    assert gateway.get_agent_model('agent/with space', timeout=12) == (
        LettaAgentModel(current='chatgpt-plus-pro/gpt-5.6-terra'))
    assert observed == {
        'url': 'http://letta.test/base/v1/agents/agent%2Fwith%20space',
        'timeout': 12,
    }


@pytest.mark.parametrize('payload', [
    b'not-json',
    b'[]',
    b'{"llm_config":[]}',
    b'{"llm_config":{"handle":56}}',
])
def test_urllib_gateway_invalid_payload_fails_closed(payload):
    gateway = UrllibLettaGateway(
        'http://letta.test',
        opener=lambda _url, _timeout: _Response(payload),
    )

    assert gateway.get_agent_model('agent-1') is None


def test_urllib_gateway_transport_failure_fails_closed():
    def opener(_url, _timeout):
        raise TimeoutError('offline')

    gateway = UrllibLettaGateway('http://letta.test', opener=opener)

    assert gateway.get_agent_model('agent-1') is None


def test_model_options_service_preserves_existing_http_contract():
    gateway = FakeLettaGateway(
        {'agent-1': LettaAgentModel(current='lc-gemini/gemini-2.5-flash-lite')})
    service = AgentModelOptionsService(
        gateway,
        ('chatgpt-plus-pro/gpt-5.6-sol', 'chatgpt-plus-pro/gpt-5.6-terra'),
    )

    assert service.get_options('agent-1').to_http() == {
        'ok': True,
        'current': 'lc-gemini/gemini-2.5-flash-lite',
        'options': [
            'lc-gemini/gemini-2.5-flash-lite',
            'chatgpt-plus-pro/gpt-5.6-sol',
            'chatgpt-plus-pro/gpt-5.6-terra',
        ],
    }


def test_server_forwarding_shim_accepts_injected_model_service():
    service = AgentModelOptionsService(
        FakeLettaGateway({
            'agent-1': LettaAgentModel(
                current='chatgpt-plus-pro/gpt-5.6-luna'),
        }),
        ('chatgpt-plus-pro/gpt-5.6-sol', 'chatgpt-plus-pro/gpt-5.6-luna'),
    )

    assert server.agent_model_payload('agent-1', service=service) == {
        'ok': True,
        'current': 'chatgpt-plus-pro/gpt-5.6-luna',
        'options': [
            'chatgpt-plus-pro/gpt-5.6-sol',
            'chatgpt-plus-pro/gpt-5.6-luna',
        ],
    }
