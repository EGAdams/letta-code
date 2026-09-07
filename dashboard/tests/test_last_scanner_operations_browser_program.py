import importlib.util
import sys
from pathlib import Path
from typing import Any

from scanner_repair_dispatch import build_repair_instruction, response_used_sdk
from scanner_repair_reporting import render_message, verify_repair
from scanner_repair_workflow import ForegroundRepairWorkflow


SCRIPT = Path(__file__).with_name('last_scanner_operations_browser_test.py')
SPEC = importlib.util.spec_from_file_location('last_scanner_browser_program', SCRIPT)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_repair_instruction_requires_one_sonnet_sdk_run_with_failure_context():
    state = MODULE.ReportState(
        kind='failure',
        status='Pipeline failed: report audit did not pass',
        conversation_id='conv-test',
        document_path='/tmp/window.jpg',
    )

    instruction = build_repair_instruction('window', state.status, state.document_path)

    assert "run_claude_code_sdk exactly once" in instruction
    assert "model='sonnet'" in instruction
    assert state.status in instruction
    assert state.document_path in instruction
    assert 'Preserve unrelated working-tree work' in instruction
    assert 'Do not launch an immediate retry' in instruction
    assert '/home/adamsl/rol_finances/.venv command' in instruction
    assert 'REPAIR_RESULT: PASSED' in instruction


def test_only_an_actual_sdk_tool_call_counts_as_dispatch():
    user_echo = {'messages': [{'message_type': 'user_message',
                               'content': 'run_claude_code_sdk'}]}
    tool_call = {'messages': [{'message_type': 'tool_call_message',
                               'tool_call': {'name': 'run_claude_code_sdk'}}]}

    assert response_used_sdk(user_echo) is False
    assert response_used_sdk(tool_call) is True


def _sdk_messages(
    result: str = 'PASSED', tool_return: str = 'SDK_REPAIR_RESULT: PASSED'
) -> list[dict[str, Any]]:
    return [
        {
            'id': 'call',
            'message_type': 'tool_call_message',
            'tool_call': {
                'name': 'run_claude_code_sdk',
                'arguments': '{"task":"fix it","model":"sonnet"}',
            },
        },
        {
            'id': 'return',
            'message_type': 'tool_return_message',
            'name': 'run_claude_code_sdk',
            'tool_return': tool_return,
            'stdout': ['test stdout'],
            'stderr': ['test stderr'],
        },
        {
            'id': 'assistant',
            'message_type': 'assistant_message',
            'content': f'Repair finished.\nREPAIR_RESULT: {result}',
        },
    ]


def test_tool_return_renders_sdk_output_stdout_and_stderr():
    output: list[str] = []

    render_message(_sdk_messages()[1], output.append)

    rendered = '\n'.join(output)
    assert 'Claude Code SDK -> Mazda (final output)' in rendered
    assert 'SDK_REPAIR_RESULT: PASSED' in rendered
    assert 'test stdout' in rendered
    assert 'test stderr' in rendered


def test_repair_verification_fails_closed_on_sdk_error():
    messages = _sdk_messages(
        result='FAILED', tool_return='ERROR contacting executor: HTTP 400'
    )

    outcome = verify_repair(messages, '', '')

    assert outcome.passed is False
    assert 'HTTP 400' in outcome.detail
    assert 'REPAIR_RESULT: FAILED' in outcome.detail


def test_foreground_workflow_waits_for_sdk_terminal_event_and_reports_pass():
    messages = _sdk_messages()
    events: list[dict[str, Any]] = [
        {
            'seq': 11,
            'run_id': 'sdk-1',
            'category': 'status',
            'text': 'Started sonnet in /workspace',
        },
        {
            'seq': 12,
            'run_id': 'sdk-1',
            'category': 'messages',
            'message_type': 'assistant',
            'text': 'Investigating the parser.',
        },
        {
            'seq': 13,
            'run_id': 'sdk-1',
            'category': 'status',
            'status': 'complete',
            'text': 'Completed',
        },
    ]

    class Telemetry:
        message_reads: int = 0
        activity_reads: int = 0

        def messages(self) -> list[dict[str, Any]]:
            self.message_reads += 1
            return [] if self.message_reads == 1 else messages

        def activity(self) -> dict[str, Any]:
            self.activity_reads += 1
            if self.activity_reads == 1:
                baseline: list[dict[str, Any]] = [{'seq': 10}]
            elif self.activity_reads == 2:
                baseline = [{'seq': 10}, events[0]]
            else:
                baseline = [{'seq': 10}, *events]
            return {'ok': True, 'events': baseline}

        def dispatch(self, instruction: str) -> object:
            assert instruction == 'exact repair request'
            return {'messages': messages}

    output: list[str] = []
    telemetry = Telemetry()
    outcome = ForegroundRepairWorkflow(
        telemetry, emit=output.append, poll_interval=0
    ).run('exact repair request')

    rendered = '\n'.join(output)
    assert outcome.passed is True
    assert outcome.sdk_run_id == 'sdk-1'
    assert telemetry.activity_reads >= 3
    assert 'Sending repair request to Mazda:\nexact repair request' in rendered
    assert 'Investigating the parser.' in rendered
    assert 'Running verification...' in rendered
    assert 'Final result:\nPASSED' in rendered
