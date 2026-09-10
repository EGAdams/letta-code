import pytest
from pydantic import ValidationError

from terminal.contracts import TerminalTarget


def test_conversation_target_builds_the_exact_resume_command():
    target = TerminalTarget.from_browser_values(
        'Mazda', 'conv-scan-123', lambda _name: 'agent-wrong')

    assert target.agent_id == ''
    assert target.conversation_id == 'conv-scan-123'
    assert target.command_line == 'letta --conversation conv-scan-123'


def test_agent_target_is_resolved_when_no_conversation_was_requested():
    target = TerminalTarget.from_browser_values(
        'Mazda', '', lambda _name: 'agent-mazda')

    assert target.command_line == 'letta --agent agent-mazda'


def test_bad_conversation_never_falls_back_to_the_agent_context():
    target = TerminalTarget.from_browser_values(
        'Mazda', 'conv-ok;echo wrong', lambda _name: 'agent-mazda')

    assert target == TerminalTarget()
    assert target.command_line == ''


def test_bad_resolved_agent_opens_only_a_plain_shell():
    target = TerminalTarget.from_browser_values(
        'Mazda', '', lambda _name: 'agent-ok;echo wrong')

    assert target == TerminalTarget()


def test_model_forbids_both_letta_selectors():
    with pytest.raises(ValidationError, match='one Letta selector'):
        TerminalTarget(agent_id='agent-mazda', conversation_id='conv-scan')
