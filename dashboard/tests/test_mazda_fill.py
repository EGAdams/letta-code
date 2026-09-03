"""Mazda Fill: classify the page, then hand it to the reader built for it.

The defect these cover: the manual-entry form used to ask the OPERATOR which
parser to aim at, from five buttons. The receipt parser answers with one
merchant/date/amount because a receipt has one -- so a statement page pressed
through it silently became a single expense. The DTE gas bill on 2026-08-19
was filed as one $28.07 expense that way, and the local-OCR heuristic added to
catch it scored the page 0 because every date on it is spelled out.

The shape is now an OUTPUT of reading the document, decided by the same
deterministic classify (mazda_intake.py) the automatic pipeline already runs
first. The operator's only remaining choice is which cheap model reads.
"""
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from finance.manual_entry import PREVIEW_ENGINES
from finance.receipt_read_contracts import (
    RECEIPT_READ_MODELS,
    SHAPE_MANY_EXPENSES,
    SHAPE_ONE_EXPENSE,
    ReceiptReadIntent,
    ReceiptReadRequest,
    assert_models_are_supported,
)
from finance.receipt_read_service import (
    CallableDocumentClassifier,
    CallableForensicReceiptReader,
    ForensicReceiptReadStrategy,
)
from finance.statement_models import (
    STATEMENT_ENGINES,
    StatementBreakupResponse,
)

DASHBOARD_DIR = Path(__file__).resolve().parent.parent


def forensic_request(**values):
    return ReceiptReadRequest(
        intent=ReceiptReadIntent.SEVERAL_EXPENSES,
        **values,
    )


class FakeStatements:
    """Stands in for StatementBreakupService -- records what it was asked."""

    def __init__(self, response):
        self._response = response
        self.requests = []

    def break_up(self, request):
        self.requests.append(request)
        return self._response


def statement_response(**overrides):
    payload = {
        'ok': True,
        'bank_name': 'DTE Energy',
        'account_last4': '0544',
        'transactions': [
            {'transaction_date': '2025-08-14', 'description': 'Gas service',
             'amount': -28.07},
            {'transaction_date': '2025-08-14', 'description': 'Electric service',
             'amount': -41.12},
        ],
    }
    payload.update(overrides)
    return StatementBreakupResponse(**payload)


def build_service(doc_kind='receipt', receipt=(True, {'merchant_name': 'Kroger'}),
                  statements=None):
    fake_statements = statements or FakeStatements(statement_response())
    reads = []

    def read(image_path, model):
        reads.append((image_path, model))
        return receipt

    service = ForensicReceiptReadStrategy(
        CallableDocumentClassifier(lambda _path: doc_kind),
        CallableForensicReceiptReader(read),
        fake_statements,
    )
    return service, fake_statements, reads


# ── the model list ────────────────────────────────────────────────────────
def test_only_models_both_readers_accept_are_offered():
    # One dropdown drives both readers. A model only one of them accepts would
    # work on a receipt and 400 on a statement -- a split-brain failure the
    # operator has no way to diagnose.
    assert set(RECEIPT_READ_MODELS) <= set(PREVIEW_ENGINES) & set(STATEMENT_ENGINES)
    assert_models_are_supported()


def test_the_free_ocr_tier_and_the_paid_chain_are_both_excluded():
    # 'local' is the tesseract pass that misread the DTE bill; 'auto' falls
    # through to paid tiers on failure. Neither belongs behind a button whose
    # whole point is a cheap, deliberate read.
    assert 'local' not in RECEIPT_READ_MODELS
    assert 'auto' not in RECEIPT_READ_MODELS


def test_the_js_dropdown_offers_exactly_the_same_models():
    """The frontend list crosses a language boundary; nothing type-checks it.

    A model added on one side alone would offer the operator a choice the
    server rejects as a 400 (or hide one it accepts).
    """
    source = (DASHBOARD_DIR / 'js' / 'abstract' / 'receipt-read.interface.js').read_text()
    block = source[source.index('RECEIPT_READ_MODELS'):]
    block = block[:block.index(']')]
    assert sorted(re.findall(r'model:\s*"([^"]+)"', block)) == sorted(RECEIPT_READ_MODELS)


def test_codex_is_offered_and_names_the_model_that_actually_runs():
    # "Codex luna": codex_cli_vision's default is gpt-5.6-luna. The label
    # says luna because that is what answers, and the operator picks by model,
    # not by which CLI flag happens to be passed.
    assert RECEIPT_READ_MODELS['codex-only'] == 'Codex (luna)'


def test_every_offered_model_names_one_flat_fee_subscription():
    # None of the three can reach a metered tier: 'openai' (an API key) and
    # 'auto' (falls through to it) are both absent by construction.
    assert sorted(RECEIPT_READ_MODELS) == ['codex-only', 'gemini-only', 'haiku-only']
    assert 'openai' not in RECEIPT_READ_MODELS
    assert 'chatgpt-oauth' not in RECEIPT_READ_MODELS


# ── the request boundary ──────────────────────────────────────────────────
def test_an_unknown_model_is_refused_at_the_boundary():
    with pytest.raises(ValidationError):
        ReceiptReadRequest.from_http({
            'image_path': '/scan.jpg',
            'intent': 'total-only',
            'model': 'openai',
        })


def test_a_missing_image_path_is_refused():
    with pytest.raises(ValidationError):
        ReceiptReadRequest.from_http({
            'image_path': '   ', 'intent': 'total-only'})


def test_from_http_requires_intent_and_defaults_the_model():
    with pytest.raises((ValidationError, ValueError)):
        ReceiptReadRequest.from_http({'image_path': '/scan.jpg'})
    request = ReceiptReadRequest.from_http({
        'image_path': '/scan.jpg', 'intent': 'total-only'})
    assert request.model in RECEIPT_READ_MODELS
    assert request.bank_name == ''
    assert request.account_last4 == ''


# ── routing ───────────────────────────────────────────────────────────────
def test_a_receipt_is_read_by_the_receipt_reader_with_the_chosen_model():
    service, statements, reads = build_service(doc_kind='receipt')
    response = service.read(
        forensic_request(image_path='/scan.jpg', model='haiku-only'))
    assert response.shape == SHAPE_ONE_EXPENSE
    assert response.ok is True
    assert response.receipt['merchant_name'] == 'Kroger'
    assert response.statement is None
    assert reads == [('/scan.jpg', 'haiku-only')]
    assert statements.requests == []


@pytest.mark.parametrize('doc_kind', ['statement', 'bank_statement'])
def test_a_statement_is_read_by_the_statement_reader(doc_kind):
    service, statements, reads = build_service(doc_kind=doc_kind)
    response = service.read(
        forensic_request(image_path='/scan.jpg', model='gemini-only'))
    assert response.shape == SHAPE_MANY_EXPENSES
    assert len(response.statement['transactions']) == 2
    assert response.receipt is None
    # The receipt parser -- the one that would have answered with a single
    # expense -- is never reached for a statement.
    assert reads == []
    assert statements.requests[0].engine == 'gemini-only'


def test_the_operators_typed_bank_and_account_reach_the_statement_reader():
    service, statements, _ = build_service(doc_kind='statement')
    service.read(forensic_request(
        image_path='/scan.jpg', model='gemini-only',
        bank_name='Choice Privileges', account_last4='5596'))
    assert statements.requests[0].bank_name == 'Choice Privileges'
    assert statements.requests[0].account_last4 == '5596'


def test_an_unknown_doc_kind_is_read_as_a_receipt():
    # The recoverable guess. A receipt shown wrong costs the human three field
    # corrections; a statement shown as one expense loses every other
    # transaction silently, which is the defect this module exists to end.
    service, _, reads = build_service(doc_kind='')
    response = service.read(forensic_request(image_path='/scan.jpg'))
    assert response.shape == SHAPE_ONE_EXPENSE
    assert len(reads) == 1


def test_a_classifier_that_raises_does_not_take_the_form_down():
    def boom(_path):
        raise RuntimeError('mazda_intake.py not found')

    service = ForensicReceiptReadStrategy(
        CallableDocumentClassifier(boom),
        CallableForensicReceiptReader(lambda _p, _m: (True, {'merchant_name': 'Kroger'})),
        FakeStatements(statement_response()),
    )
    response = service.read(forensic_request(image_path='/scan.jpg'))
    assert response.shape == SHAPE_ONE_EXPENSE
    assert response.ok is True


# ── failure reporting ─────────────────────────────────────────────────────
def test_a_failed_receipt_read_reports_why_and_still_names_the_shape():
    service, _, _ = build_service(
        doc_kind='receipt', receipt=(False, {'error': 'quota exhausted'}))
    response = service.read(forensic_request(image_path='/scan.jpg'))
    assert response.ok is False
    assert response.error == 'quota exhausted'
    # Shape is still reported: the form has to know which half to render even
    # when there is nothing in it.
    assert response.shape == SHAPE_ONE_EXPENSE
    assert response.receipt['ok'] is False


def test_needs_statement_metadata_is_not_a_failure():
    # Every transaction WAS read; only whose account they are is missing. The
    # form shows the rows while the operator types the bank in, so reporting
    # this as ok:False would hide the work that was already paid for.
    statements = FakeStatements(statement_response(
        ok=False, account_last4='', needs_statement_metadata=True,
        missing_fields=['account_last4']))
    service, _, _ = build_service(doc_kind='statement', statements=statements)
    response = service.read(forensic_request(image_path='/scan.jpg'))
    assert response.ok is True
    assert response.statement['needs_statement_metadata'] is True
    assert len(response.statement['transactions']) == 2


def test_to_http_carries_both_halves_and_the_model_that_read_it():
    service, _, _ = build_service(doc_kind='receipt')
    payload = service.read(
        forensic_request(image_path='/scan.jpg', model='haiku-only')).to_http()
    assert payload['shape'] == SHAPE_ONE_EXPENSE
    assert payload['model'] == 'haiku-only'
    assert payload['doc_kind'] == 'receipt'
    assert 'receipt' in payload and 'statement' in payload


# ── the read overrules the classifier (2026-08-19) ────────────────────────
# `mazda_intake.py` answers 'unknown' often, and 'unknown' lands here in the
# receipt branch. The model that then READS the page knows more than the guess
# that sent it there, and until now that knowledge was discarded: the window
# scan came back as an empty form plus a 429 belonging to a different model
# further down Gemini's ladder.

#: What parse_and_categorize.py stamps on the local-fallback report when a
#: model answered and could not give the page a receipt's identity. Copied
#: from a live run against the window scan.
ANSWERED_NOT_A_RECEIPT = {
    'error': 'gemini-only did not answer',
    'possible_statement': True,
    'engine_failure': {
        'kind': 'no_receipt_identity',
        'model': 'gemini-3.6-flash',
        'missing': ['transaction_date', 'party.merchant_name'],
        'message': ('gemini-3.6-flash read this page and found no transaction '
                    'date and no merchant name -- it does not look like a '
                    'single receipt.'),
    },
}


def test_a_page_the_model_says_is_not_a_receipt_is_read_again_as_a_statement():
    service, statements, reads = build_service(
        doc_kind='unknown', receipt=(False, ANSWERED_NOT_A_RECEIPT))
    response = service.read(forensic_request(image_path='/staged/window.jpg'))

    assert response.shape == SHAPE_MANY_EXPENSES
    assert response.ok is True
    assert len(response.statement['transactions']) == 2
    # Same page, same model -- the operator's choice is not quietly changed.
    assert statements.requests[0].image_path == '/staged/window.jpg'
    assert statements.requests[0].engine == reads[0][1]


def test_the_re_read_says_why_it_happened():
    """Silently answering a different question than the one asked is how an
    operator stops trusting the button. The reason travels with the answer."""
    service, _, _ = build_service(
        doc_kind='unknown', receipt=(False, ANSWERED_NOT_A_RECEIPT))
    response = service.read(forensic_request(image_path='/staged/window.jpg'))
    assert 'no transaction date' in response.reread_after


def test_a_first_time_right_read_carries_no_re_read_note():
    service, _, _ = build_service(doc_kind='receipt')
    assert service.read(forensic_request(image_path='/x.jpg')).reread_after == ''
    service, _, _ = build_service(doc_kind='statement')
    assert service.read(forensic_request(image_path='/x.jpg')).reread_after == ''


def test_an_engine_that_never_answered_is_not_re_read():
    """A 429/503/missing key means nobody looked at the page. Re-reading it as
    a statement on that basis would be a guess -- and guessing the shape is the
    defect this whole module exists to remove."""
    never_answered = {'error': 'gemini-only did not answer',
                      'possible_statement': True}
    service, statements, _ = build_service(
        doc_kind='unknown', receipt=(False, never_answered))
    response = service.read(forensic_request(image_path='/x.jpg'))
    assert response.shape == SHAPE_ONE_EXPENSE
    assert statements.requests == []


def test_the_ocr_heuristic_cannot_veto_the_second_read():
    """It said False about the live window scan, a page that is plainly a
    statement. The retry happens on the model's answer alone."""
    payload = {**ANSWERED_NOT_A_RECEIPT, 'possible_statement': False}
    service, statements, _ = build_service(
        doc_kind='unknown', receipt=(False, payload))
    response = service.read(forensic_request(image_path='/x.jpg'))
    assert response.shape == SHAPE_MANY_EXPENSES
    assert len(statements.requests) == 1


def test_an_unreadable_receipt_keeps_the_receipt_readers_answer():
    """Both readers came back empty, so the page really was a receipt nobody
    could read. Showing a statement extractor's complaint about a page that was
    never a statement would be the less useful of the two answers."""
    empty = FakeStatements(statement_response(ok=False, transactions=[],
                                              error='no transactions found'))
    service, statements, _ = build_service(
        doc_kind='unknown', receipt=(False, ANSWERED_NOT_A_RECEIPT),
        statements=empty)
    response = service.read(forensic_request(image_path='/x.jpg'))
    assert response.shape == SHAPE_ONE_EXPENSE
    assert response.error == ANSWERED_NOT_A_RECEIPT['engine_failure']['message']
    assert len(statements.requests) == 1  # it was asked, and had nothing


def test_the_failing_read_reports_the_models_own_sentence():
    """Not the generic wrapper, and emphatically not a quota error from an
    unrelated model further down the ladder."""
    empty = FakeStatements(statement_response(ok=False, transactions=[]))
    service, _, _ = build_service(
        doc_kind='unknown', receipt=(False, ANSWERED_NOT_A_RECEIPT),
        statements=empty)
    response = service.read(forensic_request(image_path='/x.jpg'))
    assert response.error == ANSWERED_NOT_A_RECEIPT['engine_failure']['message']
