"""A named model that didn't answer must not be reported as if it had.

parse_and_categorize.py falls back to free local OCR whenever the engine it
was given fails, and returns that as a normal success. Right for the "auto"
chain; wrong for a model the operator chose by name. Verified live on
2026-08-19: both Codex accounts were unusable (one out of weekly usage until
Aug 20, one with a dead refresh token), and the fallback answered for the DTE
gas bill with merchant "Account Number", date 2025-07-14 and no total -- which
would have filled the form under the label "Codex read this".
"""
import pytest

from finance import manual_entry
from finance.manual_entry import (
    LOCAL_FALLBACK_MODEL_NAME,
    PREVIEW_ENGINES,
    _answered_by_local_fallback,
    preview_receipt_parse,
)

DTE_FALLBACK_REPORT = {
    'transaction_date': '2025-07-14',
    'party': {'merchant_name': 'Account Number'},
    'totals': {'total_amount': None},
    'meta': {
        'model_name': LOCAL_FALLBACK_MODEL_NAME,
        'raw_text': 'MULTIPLE BILL STATEMENTS ENCLOSED\n'
                    'Due September 05, 2025 $28.08\n'
                    'Account Balance as of August 14, 2025 $28.07\n',
    },
}

REAL_READ_REPORT = {
    'transaction_date': '2025-08-14',
    'party': {'merchant_name': 'DTE Energy'},
    'totals': {'total_amount': 28.07},
    'meta': {'model_name': 'gpt-5.6-luna', 'raw_text': 'DTE Energy 28.07'},
}


def runner_for(report):
    return lambda _command: {'returncode': 0, 'report': report, 'stderr': ''}


def test_local_fallback_is_detected_for_every_named_model():
    for engine in sorted(PREVIEW_ENGINES - {'local'}):
        assert _answered_by_local_fallback(DTE_FALLBACK_REPORT, engine) is True


def test_the_local_engine_is_allowed_to_answer_with_local_ocr():
    # Asking for OCR and getting OCR is not a failure -- it is the request.
    assert _answered_by_local_fallback(DTE_FALLBACK_REPORT, 'local') is False


def test_a_real_model_read_is_not_mistaken_for_a_fallback():
    assert _answered_by_local_fallback(REAL_READ_REPORT, 'codex-only') is False


@pytest.mark.parametrize('meta', [None, 'garbage', {}, {'model_name': None}])
def test_a_payload_without_usable_meta_is_not_treated_as_a_fallback(meta):
    # Fail open here on purpose: this guard exists to catch a KNOWN stamp, and
    # discarding a real read because meta was shaped oddly would be worse.
    assert _answered_by_local_fallback({'meta': meta}, 'codex-only') is False


def test_a_fallback_preview_fills_nothing_and_says_which_model_went_quiet():
    ok, payload = preview_receipt_parse(
        '/scan.jpg', engine='codex-only', runner=runner_for(DTE_FALLBACK_REPORT))
    assert ok is False
    assert 'codex-only did not return a usable reading' in payload['error']
    # The junk fields never reach the form. "Account Number" as a merchant is
    # exactly the confident-looking wrong answer this guard exists to stop.
    assert 'merchant_name' not in payload
    assert 'transaction_date' not in payload
    assert 'total_amount' not in payload


def test_a_fallback_still_reports_the_statement_shape_it_could_see():
    # The OCR text is not thrown away entirely: whether the page LOOKS like a
    # statement is a shape question, not a value the form would fill in.
    _ok, payload = preview_receipt_parse(
        '/scan.jpg', engine='codex-only', runner=runner_for(DTE_FALLBACK_REPORT))
    assert payload['possible_statement'] is True


def test_a_genuine_read_is_untouched_by_the_guard():
    ok, payload = preview_receipt_parse(
        '/scan.jpg', engine='codex-only', runner=runner_for(REAL_READ_REPORT),
        vendor_lookup_fn=lambda *_a, **_k: {})
    assert ok is True
    assert payload['merchant_name'] == 'DTE Energy'
    assert payload['total_amount'] == 28.07


# ── carrying the model's own reason across (2026-08-19) ───────────────────
# When the model ANSWERED and still could not give the page a receipt's
# identity, parse_and_categorize.py stamps that reason onto the local-fallback
# report. Passing it through unchanged is what lets MazdaFillService re-read
# the page as a statement, and what lets the operator read what the model
# actually said instead of a quota error from a different model.

ANSWERED_NOT_A_RECEIPT = {
    'kind': 'no_receipt_identity',
    'model': 'gemini-3.6-flash',
    'missing': ['transaction_date', 'party.merchant_name'],
    'message': ('gemini-3.6-flash read this page and found no transaction date '
                'and no merchant name -- it does not look like a single receipt.'),
}

STATEMENT_FALLBACK_REPORT = {
    **DTE_FALLBACK_REPORT,
    'meta': {**DTE_FALLBACK_REPORT['meta'],
             'engine_failure': ANSWERED_NOT_A_RECEIPT},
}


def test_the_engines_own_reason_reaches_the_caller():
    ok, payload = preview_receipt_parse(
        '/staged/window.jpg', engine='gemini-only',
        runner=runner_for(STATEMENT_FALLBACK_REPORT))
    assert ok is False
    assert payload['engine_failure'] == ANSWERED_NOT_A_RECEIPT


def test_the_operator_reads_what_the_model_said_not_the_generic_line():
    _, payload = preview_receipt_parse(
        '/staged/window.jpg', engine='gemini-only',
        runner=runner_for(STATEMENT_FALLBACK_REPORT))
    assert payload['error'] == ANSWERED_NOT_A_RECEIPT['message']
    assert 'did not return a usable reading' not in payload['error']


def test_without_a_reason_the_wording_stays_true_of_every_failure():
    """No engine_failure covers two different events that arrive by the same
    route: a 429/503/missing key (nobody looked) and a model that answered with
    unusable output. Verified live 2026-08-19 -- haiku-only spent 4,071 input
    tokens on the window scan and returned something that was not valid JSON.
    "did not answer" would be false for the second, so nothing claims it."""
    _, payload = preview_receipt_parse(
        '/staged/dte.jpg', engine='gemini-only',
        runner=runner_for(DTE_FALLBACK_REPORT))
    assert 'did not return a usable reading' in payload['error']
    assert 'did not answer' not in payload['error']
    assert 'engine_failure' not in payload


def test_the_form_is_still_never_filled_from_local_ocr():
    """The guard this file exists for is unchanged by any of the above."""
    for report in (DTE_FALLBACK_REPORT, STATEMENT_FALLBACK_REPORT):
        ok, payload = preview_receipt_parse(
            '/staged/x.jpg', engine='gemini-only', runner=runner_for(report))
        assert ok is False
        assert 'merchant_name' not in payload
