from __future__ import annotations

import json
import inspect
from io import BytesIO
from pathlib import Path

import pytest
from pydantic import ValidationError

import server
from agents.fake_letta_gateway import FakeLettaGateway
from agents.letta_gateway import ILettaGateway, LettaAgentMessage, LettaAgentModel
from agents.model_options import AgentModelOptionsService
from agents.urllib_letta_gateway import UrllibLettaGateway, _string_dict


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
        opener=lambda _url, timeout: _Response(payload),
    )

    assert gateway.get_agent_model('agent-1') is None


def test_urllib_gateway_transport_failure_fails_closed():
    def opener(_url, timeout):
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


def test_agent_message_boundary_rejects_extra_and_coerced_fields():
    with pytest.raises(ValidationError):
        LettaAgentMessage.model_validate({
            'message_type': 'assistant_message',
            'unexpected': True,
        })
    with pytest.raises(ValidationError):
        LettaAgentMessage.model_validate({'message_type': 56})


def test_agent_message_legacy_adapter_covers_present_and_absent_fields():
    assert LettaAgentMessage().to_legacy() == {'message_type': ''}
    assert LettaAgentMessage(
        message_type='assistant_message',
        created_at='2026-07-31T17:00:00',
        content='hello',
    ).to_legacy() == {
        'message_type': 'assistant_message',
        'created_at': '2026-07-31T17:00:00',
        'content': 'hello',
    }


def test_fake_letta_gateway_returns_typed_messages_and_records_calls():
    message = LettaAgentMessage(
        message_type='assistant_message',
        created_at='2026-07-31T17:00:00',
        content='hello',
    )
    gateway = FakeLettaGateway(messages={'agent-1': (message,)})

    assert gateway.get_agent_messages(
        'agent-1', limit=25, timeout=9,
    ) == (message,)
    assert gateway.message_calls == [('agent-1', 25, 9)]


@pytest.mark.parametrize('envelope_key', [None, 'messages', 'results'])
def test_urllib_gateway_reads_and_normalizes_agent_messages(envelope_key):
    observed = {}
    raw_messages = [{
        'message_type': 'tool_call_message',
        'created_at': '2026-07-31T17:00:00.123Z',
        'content': [{'text': 'ignored'}, {'text': 'content'}],
        'tool_call': {
            'name': 'search',
            'arguments': '{"query":"rose mary","limit":2}',
        },
    }]
    payload = raw_messages if envelope_key is None else {envelope_key: raw_messages}

    def opener(url, timeout):
        observed.update(url=url, timeout=timeout)
        return _Response(json.dumps(payload).encode())

    gateway = UrllibLettaGateway('http://letta.test/base/', opener=opener)

    assert gateway.get_agent_messages(
        'agent/with space', limit=25, timeout=12,
    ) == (LettaAgentMessage(
        message_type='tool_call_message',
        created_at='2026-07-31T17:00:00.123Z',
        content='ignored content',
        tool_call_name='search',
        tool_call_arguments=(('query', 'rose mary'), ('limit', '2')),
    ),)
    assert observed == {
        'url': (
            'http://letta.test/base/v1/agents/'
            'agent%2Fwith%20space/messages?limit=25'
        ),
        'timeout': 12,
    }


@pytest.mark.parametrize('payload', [
    b'not-json',
    b'{}',
    b'{"messages":{}}',
    b'{"results":[56]}',
])
def test_urllib_gateway_invalid_message_payload_fails_closed(payload):
    gateway = UrllibLettaGateway(
        'http://letta.test',
        opener=lambda _url, timeout: _Response(payload),
    )

    assert gateway.get_agent_messages('agent-1') == ()


@pytest.mark.parametrize('message', [
    {'message_type': 56},
    {'message_type': 'assistant_message', 'created_at': 56},
    {'message_type': 'tool_call_message', 'tool_call': []},
    {'message_type': 'tool_call_message', 'tool_call': {'name': 56}},
    {'message_type': 'approval_request_message', 'tool_calls': {}},
])
def test_urllib_gateway_invalid_message_shapes_fail_closed(message):
    gateway = UrllibLettaGateway(
        'http://letta.test',
        opener=lambda _url, timeout: _Response(json.dumps([message]).encode()),
    )

    assert gateway.get_agent_messages('agent-1') == ()


def test_urllib_gateway_normalizes_message_variants_for_legacy_formatters():
    payload = [{
        'message_type': 'approval_request_message',
        'content': 56,
        'tool_call': {'name': 'broken_args', 'arguments': 'not-json'},
        'tool_return': {'content': 42},
        'tool_calls': [{'name': 'shell'}, {'other': 'ignored'}, 'ignored'],
        'reasoning': {'summary': 'working'},
    }]
    gateway = UrllibLettaGateway(
        'http://letta.test',
        opener=lambda _url, timeout: _Response(json.dumps(payload).encode()),
    )

    assert gateway.get_agent_messages('agent-1')[0].to_legacy() == {
        'message_type': 'approval_request_message',
        'content': '56',
        'tool_call': {'name': 'broken_args', 'arguments': {}},
        'tool_return': '42',
        'tool_calls': [{'name': 'shell'}, {'name': '?'}],
        'reasoning': "{'summary': 'working'}",
    }


def test_urllib_gateway_message_transport_and_invalid_request_fail_closed():
    calls = []

    def opener(url, timeout):
        calls.append((url, timeout))
        raise TimeoutError('offline')

    gateway = UrllibLettaGateway('http://letta.test', opener=opener)

    assert gateway.get_agent_messages('agent-1') == ()
    assert gateway.get_agent_messages('') == ()
    assert gateway.get_agent_messages('agent-1', limit=0) == ()
    assert gateway.get_agent_messages('agent-1', limit=True) == ()
    assert len(calls) == 1


def test_urllib_gateway_rejects_blank_base_url_and_non_string_mapping_keys():
    with pytest.raises(ValueError, match='base_url cannot be blank'):
        UrllibLettaGateway('')
    assert _string_dict({1: 'not-json'}) is None


def test_urllib_gateway_model_empty_id_defaults_and_invalid_model_fail_closed():
    payloads = iter([
        b'{}',
        b'{"llm_config":{"model":56}}',
    ])
    gateway = UrllibLettaGateway(
        'http://letta.test',
        opener=lambda _url, timeout: _Response(next(payloads)),
    )

    assert gateway.get_agent_model('') is None
    assert gateway.get_agent_model('agent-1') == LettaAgentModel(current='')
    assert gateway.get_agent_model('agent-1') is None


def test_urllib_gateway_message_normalization_covers_optional_invalid_parts():
    payload = [{
        'message_type': 'assistant_message',
        'content': [56, {'text': 42}, {'text': 'kept'}],
        'tool_call': {'name': 'without_args'},
        'tool_calls': [56, {'name': 42}, {'name': 'shell'}],
    }, {
        'message_type': 'tool_call_message',
        'tool_call': {'name': 'non_mapping_args', 'arguments': 56},
    }]
    gateway = UrllibLettaGateway(
        'http://letta.test',
        opener=lambda _url, timeout: _Response(json.dumps(payload).encode()),
    )

    messages = gateway.get_agent_messages('agent-1')

    assert messages[0].content == 'kept'
    assert messages[0].tool_call_arguments == ()
    assert messages[0].approval_tool_names == ('shell',)
    assert messages[1].tool_call_arguments == ()


def test_urllib_gateway_rejects_non_string_message_date():
    gateway = UrllibLettaGateway(
        'http://letta.test',
        opener=lambda _url, timeout: _Response(
            b'[{"message_type":"assistant_message","date":56}]'),
    )

    assert gateway.get_agent_messages('agent-1') == ()


def test_server_letta_messages_shim_uses_injected_gateway():
    message = LettaAgentMessage(
        message_type='reasoning_message',
        date='2026-07-31T17:01:00',
        reasoning='thinking',
    )
    gateway = FakeLettaGateway(messages={'agent-1': (message,)})

    assert server.letta_messages(
        'agent-1', limit=40, gateway=gateway,
    ) == [{
        'message_type': 'reasoning_message',
        'date': '2026-07-31T17:01:00',
        'reasoning': 'thinking',
    }]
    assert gateway.message_calls == [('agent-1', 40, 25)]


def test_agent_application_service_depends_on_gateway_interface_only():
    source = (
        Path(__file__).parents[1] / 'agents' / 'model_options.py'
    ).read_text(encoding='utf-8')

    assert 'from agents.letta_gateway import ILettaGateway' in source
    assert 'urllib_letta_gateway' not in source
    assert 'fake_letta_gateway' not in source


def test_composition_root_exposes_gateway_through_interface():
    assert server.__annotations__['_LETTA_GATEWAY'] is ILettaGateway
    gateway_parameter = inspect.signature(server.letta_messages).parameters[
        'gateway'
    ]
    assert gateway_parameter.annotation == ILettaGateway | None
