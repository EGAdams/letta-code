"""Contracts for the three manual receipt-reading Strategies."""
import subprocess
from types import SimpleNamespace

import pytest

from finance.focused_receipt_reader import FocusedReceiptReader
from finance.receipt_prefill_prompts import prompt_for
from finance.receipt_read_contracts import (
    IReceiptReadStrategy,
    ReceiptReadIntent,
    ReceiptReadRequest,
    ReceiptReadResponse,
    SHAPE_ONE_EXPENSE,
)
from finance.receipt_read_service import (
    FocusedReceiptReadStrategy,
    ReceiptReadService,
)


class FakeFocusedReader:
    def __init__(self, result=(True, {'total_amount': 7.18})):
        self.result = result
        self.calls = []

    def read(self, image_path, model, intent):
        self.calls.append((image_path, model, intent))
        return self.result


class RecordingStrategy(IReceiptReadStrategy):
    def __init__(self, intent):
        self.intent = intent
        self.requests = []

    def read(self, request):
        self.requests.append(request)
        return ReceiptReadResponse(
            ok=True,
            shape=SHAPE_ONE_EXPENSE,
            intent=self.intent,
            model=request.model,
        )


def request(intent):
    return ReceiptReadRequest(
        image_path='/scan.jpg',
        intent=intent,
        model='gemini-only',
    )


def test_context_delegates_each_intent_to_its_injected_strategy():
    strategies = {intent: RecordingStrategy(intent) for intent in ReceiptReadIntent}
    service = ReceiptReadService(strategies)

    for intent in ReceiptReadIntent:
        response = service.read(request(intent))
        assert response.intent is intent
        assert strategies[intent].requests == [request(intent)]


def test_context_refuses_an_incomplete_strategy_registry():
    with pytest.raises(ValueError, match='missing receipt-read strategies'):
        ReceiptReadService({
            ReceiptReadIntent.TOTAL_ONLY:
                RecordingStrategy(ReceiptReadIntent.TOTAL_ONLY),
        })


@pytest.mark.parametrize('intent', [
    ReceiptReadIntent.CIRCLED_ONLY,
    ReceiptReadIntent.TOTAL_ONLY,
])
def test_focused_strategies_never_invoke_the_forensic_shape(intent):
    reader = FakeFocusedReader()
    strategy = FocusedReceiptReadStrategy(intent, reader)

    response = strategy.read(request(intent))

    assert response.shape == SHAPE_ONE_EXPENSE
    assert response.receipt['total_amount'] == 7.18
    assert reader.calls == [('/scan.jpg', 'gemini-only', intent)]


def test_focused_strategy_preserves_a_fail_closed_reader_error():
    reader = FakeFocusedReader((False, {'error': 'no marked items'}))
    response = FocusedReceiptReadStrategy(
        ReceiptReadIntent.CIRCLED_ONLY, reader,
    ).read(request(ReceiptReadIntent.CIRCLED_ONLY))

    assert response.ok is False
    assert response.error == 'no marked items'


def test_total_prompt_forbids_the_expensive_itemized_output():
    prompt = prompt_for(ReceiptReadIntent.TOTAL_ONLY)
    assert 'three fields' in prompt
    assert 'Do not return line items' in prompt


def test_circled_prompt_is_fail_closed_and_excludes_unselected_rows():
    prompt = prompt_for(ReceiptReadIntent.CIRCLED_ONLY)
    assert 'total_amount=null' in prompt
    assert 'Do not extract or return unselected item rows' in prompt


def test_subprocess_adapter_resolves_vendor_after_a_valid_read():
    completed = SimpleNamespace(
        returncode=0,
        stdout='noise\n{"ok":true,"merchant_name":"Kroger",'
               '"transaction_date":"2026-08-30","total_amount":7.18}\n',
        stderr='',
    )
    category_namer = object()
    reader = FocusedReceiptReader(
        lambda: category_namer,
        runner=lambda *_args, **_kwargs: completed,
    )

    ok, payload = reader.read(
        '/scan.jpg', 'gemini-only', ReceiptReadIntent.TOTAL_ONLY)

    assert ok is True
    assert payload['merchant_name'] == 'Kroger'
    assert payload['total_amount'] == 7.18


def test_subprocess_adapter_returns_the_cli_error_without_guessing():
    completed = SimpleNamespace(
        returncode=1,
        stdout='{"ok":false,"error":"No circled items were found"}\n',
        stderr='',
    )
    reader = FocusedReceiptReader(
        lambda: object(),
        runner=lambda *_args, **_kwargs: completed,
    )

    ok, payload = reader.read(
        '/scan.jpg', 'gemini-only', ReceiptReadIntent.CIRCLED_ONLY)

    assert ok is False
    assert payload == {'error': 'No circled items were found'}


def test_subprocess_adapter_launch_environment_can_import_dashboard_finance():
    def import_checking_runner(command, **kwargs):
        probe = subprocess.run(
            [command[0], command[1], '--help'],
            capture_output=True,
            text=True,
            timeout=5,
            env=kwargs['env'],
        )
        assert probe.returncode == 0, probe.stderr
        return SimpleNamespace(
            returncode=1,
            stdout='{"ok":false,"error":"probe complete"}\n',
            stderr='',
        )

    reader = FocusedReceiptReader(
        lambda: object(),
        runner=import_checking_runner,
    )

    ok, payload = reader.read(
        '/scan.jpg', 'gemini-only', ReceiptReadIntent.CIRCLED_ONLY)

    assert ok is False
    assert payload == {'error': 'probe complete'}
