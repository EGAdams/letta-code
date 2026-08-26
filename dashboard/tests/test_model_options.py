"""Coverage for AgentModelOptionsService's family filtering: the Model
dropdown must never mix claude and chatgpt handles, even when the agent's
live provider carries a per-human suffix (e.g. 'chatgpt-plus-pro-mom') that
never appears verbatim in the curated AGENT_MODEL_OPTIONS catalog."""

from agents.letta_gateway import LettaAgentModel
from agents.model_options import AgentModelOptionsService


ALLOWED = (
    'chatgpt-plus-pro/gpt-5.6-sol',
    'chatgpt-plus-pro/gpt-5.6-luna',
    'chatgpt-plus-pro/gpt-5.6-terra',
    'claude-pro-max/claude-haiku-4-5-20251001',
    'claude-pro-max/claude-sonnet-5',
    'claude-pro-max/claude-opus-5',
)


class FakeGateway:
    def __init__(self, current):
        self._current = current

    def get_agent_model(self, agent_id, *, timeout=15):
        return LettaAgentModel(current=self._current)


def test_infers_family_from_a_suffixed_live_provider():
    service = AgentModelOptionsService(FakeGateway('chatgpt-plus-pro-mom/gpt-5.6-sol'), ALLOWED)

    result = service.get_options('agent-x')

    assert all(h.startswith('chatgpt-plus-pro/') for h in result.options)
    assert result.current == 'chatgpt-plus-pro/gpt-5.6-sol'


def test_explicit_family_prefix_overrides_the_live_provider():
    service = AgentModelOptionsService(FakeGateway('claude-pro-max/claude-sonnet-5'), ALLOWED)

    result = service.get_options('agent-x', family_prefix='chatgpt-plus-pro')

    assert all(h.startswith('chatgpt-plus-pro/') for h in result.options)
    assert 'claude-pro-max/claude-sonnet-5' not in result.options


def test_a_model_id_with_no_catalog_match_is_prepended_not_dropped():
    service = AgentModelOptionsService(FakeGateway('chatgpt-plus-pro-mom/gpt-5.9-custom'), ALLOWED)

    result = service.get_options('agent-x')

    assert result.current == 'chatgpt-plus-pro-mom/gpt-5.9-custom'
    assert result.options[0] == 'chatgpt-plus-pro-mom/gpt-5.9-custom'
    assert all(h.startswith(('chatgpt-plus-pro/', 'chatgpt-plus-pro-mom/')) for h in result.options)
