"""The read is allowed to overrule the classifier.

Regression for 2026-08-19: a window scan holding a statement was classified
'unknown', guessed as a receipt, read by Gemini -- which answered "no
transaction date, no merchant name" -- and the operator got an empty form plus
a 429 quota error belonging to a *different* model further down Gemini's
ladder. Every fact needed to do better was already in hand and thrown away.
"""

import pytest

from finance.receipt_read_outcome import (
    NO_RECEIPT_IDENTITY,
    EngineFailure,
    ReceiptReadOutcome,
)

# What parse_and_categorize.py actually stamps on the local-fallback report,
# copied from a live run against the window scan (2026-08-19).
LIVE_ENGINE_FAILURE = {
    'kind': 'no_receipt_identity',
    'model': 'gemini-3.6-flash',
    'missing': ['transaction_date', 'party.merchant_name'],
    'message': ('gemini-3.6-flash read this page and found no transaction date '
                'and no merchant name -- it does not look like a single receipt.'),
}


# ── EngineFailure ──────────────────────────────────────────────────────────

def test_reads_the_live_shape():
    failure = EngineFailure.from_payload({'engine_failure': LIVE_ENGINE_FAILURE})
    assert failure.kind == NO_RECEIPT_IDENTITY
    assert failure.model == 'gemini-3.6-flash'
    assert failure.missing == ('transaction_date', 'party.merchant_name')
    assert failure.answered is True


@pytest.mark.parametrize('payload', [
    {},                              # a 429/503: nobody looked at the document
    {'engine_failure': None},
    {'engine_failure': 'nope'},
    'not a mapping',
    None,
])
def test_absent_or_junk_reads_as_no_failure(payload):
    """An older parse_and_categorize.py simply omits the key. The producer is a
    separate repo on a separate release cycle, so this must not raise."""
    assert EngineFailure.from_payload(payload) is None


def test_a_failure_that_is_not_an_answer_is_not_an_answer():
    failure = EngineFailure.from_payload(
        {'engine_failure': {'kind': 'rate_limited', 'model': 'x'}})
    assert failure.answered is False


def test_missing_survives_junk_entries():
    failure = EngineFailure.from_payload(
        {'engine_failure': {'kind': NO_RECEIPT_IDENTITY, 'missing': ['a', 7, None]}})
    assert failure.missing == ('a',)


# ── when a second read is warranted ────────────────────────────────────────

def _outcome(*, ok=False, possible_statement=True, failure=LIVE_ENGINE_FAILURE):
    payload = {'error': 'something', 'possible_statement': possible_statement}
    if failure is not None:
        payload['engine_failure'] = failure
    return ReceiptReadOutcome.from_reader(ok, payload)


def test_an_answer_without_receipt_identity_is_worth_a_second_read():
    assert _outcome().warrants_statement_retry is True


def test_a_model_that_never_answered_is_not_evidence_of_anything():
    """A 429, a 503 or a missing key mean nobody read the page. Re-reading it
    with the statement extractor on that basis would be a guess, and guessing
    the shape is the whole defect."""
    assert _outcome(failure=None).warrants_statement_retry is False


def test_the_ocr_heuristic_gets_no_vote():
    """It answered False for the live window scan -- a page that is plainly a
    statement -- and scored the DTE gas bill 0 before that. Letting it veto the
    retry would put a weak guess in charge of whether the reader that can
    actually settle the question ever gets asked."""
    assert _outcome(possible_statement=False).warrants_statement_retry is True


def test_a_successful_read_is_never_second_guessed():
    assert _outcome(ok=True).warrants_statement_retry is False


# ── which sentence the operator sees ───────────────────────────────────────

def test_the_engines_own_sentence_wins():
    """The specific thing the model said beats the generic wrapper -- and beats
    the quota error from an unrelated model that this used to report."""
    assert _outcome().best_error == LIVE_ENGINE_FAILURE['message']


def test_without_an_answer_the_generic_error_stands():
    outcome = ReceiptReadOutcome.from_reader(
        False, {'error': 'gemini-only did not answer'})
    assert outcome.best_error == 'gemini-only did not answer'


def test_a_reader_payload_that_is_not_a_mapping_is_survivable():
    outcome = ReceiptReadOutcome.from_reader(False, None)
    assert outcome.ok is False
    assert outcome.best_error == ''
    assert outcome.warrants_statement_retry is False
