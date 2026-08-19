"""Tests for breaking one scanned statement into many expenses by hand.

Both subprocesses are injected, so these run offline: the real
parse_statement_scan.py needs a Gemini key and the real
store_statement_transactions.py needs the finance DB, and neither belongs in a
unit test. What IS asserted here is that this path hands those two tools
exactly the arguments Mazda's own STATEMENT BRANCH hands them.
"""
import json
import os

import pytest
from pydantic import ValidationError

from finance.statement_commands import (
    ANNOTATION_SCRIPT,
    STORE_SCRIPT,
    build_annotation_command,
    build_store_command,
    build_store_payload,
)
from finance.statement_extraction_adapter import PreflightStatementExtractor
from finance.statement_models import (
    CommandResult,
    StatementBreakupRequest,
    StatementRow,
    StatementStoreRequest,
    StatementStoreResponse,
)
from finance.statement_ports import (
    ICommandRunner,
    IStatementPreflightGateway,
    IStatementStore,
    NullStatementIntakeRecorder,
)
from finance.statement_service import StatementBreakupService
from finance.statement_store import ScriptStatementStore

# The six rows off the 2026-08-19 Last Window Scan (Choice Privileges
# Mastercard, billing cycle 05/23-06/20). One is the $2,900 payment and one is
# a $0.00 interest line -- exactly why a form that pre-judged the sign, or
# treated every printed line as an expense, would be wrong.
CHOICE_PRIVILEGES_ROWS = [
    {'date': '2025-05-23', 'description': 'QUALITY INNS JASPER TN', 'amount': -93.99},
    {'date': '2025-05-23', 'description': 'ECONO LODGE VALDOSTA GA', 'amount': -87.80},
    {'date': '2025-05-23', 'description': 'CRACKER BARREL #428 CAVE CITY KY',
     'amount': -28.73},
    {'date': '2025-05-31', 'description': 'PAYMENT - THANK YOU', 'amount': 2900.00},
    {'date': '2025-06-07', 'description': 'ELLIS SEARS LOT GRAND RAPIDS MI',
     'amount': -6.00},
    {'date': '2025-06-20', 'description': 'Interest Charge on Purchases',
     'amount': 0.00},
]


class FakePreflight(IStatementPreflightGateway):
    def __init__(self, result, rows=None):
        self._result = result
        self._rows = CHOICE_PRIVILEGES_ROWS if rows is None else rows
        self.calls = []

    def run(self, image_path, metadata, engine):
        self.calls.append((image_path, dict(metadata), engine))
        return self._result

    def rows(self, image_path, preflight):
        return list(self._rows)


class FakeRunner(ICommandRunner):
    def __init__(self, *results):
        self._results = list(results)
        self.commands = []

    def run(self, command):
        self.commands.append(list(command))
        if not self._results:
            return CommandResult(returncode=0, report={'ok': True})
        return self._results.pop(0)


def _ok_preflight(**overrides):
    result = {
        'ok': True,
        'bank_name': 'Choice Privileges Mastercard',
        'account_last4': '5596',
        'last4_source': 'known_cards_workbook',
        'statement_total': 140.45,
    }
    result.update(overrides)
    return result


def _store_request(**overrides):
    fields = dict(
        image_path='/staged/window_scan.jpg',
        bank_name='Choice Privileges Mastercard',
        account_last4='5596',
        statement_total=140.45,
        last4_source='known_cards_workbook',
        conversation_id='conv-1',
        transactions=[
            StatementRow(transaction_date='2025-05-23',
                         description='QUALITY INNS JASPER TN', amount=-93.99),
            StatementRow(transaction_date='2025-05-31',
                         description='PAYMENT - THANK YOU', amount=2900.00),
        ],
    )
    fields.update(overrides)
    return StatementStoreRequest(**fields)


# --- the split: one page in, many walkable expenses out ---------------------

def test_breakup_returns_one_item_per_transaction():
    """The defect this whole path exists for: five transactions, one row.

    Every fill button asks the RECEIPT parser, which answers with a single
    merchant/date/amount -- so the Prev/Next navigation the form already had
    was walking a one-item list on a five-transaction page.
    """
    extractor = PreflightStatementExtractor(FakePreflight(_ok_preflight()))
    response = extractor.extract(
        StatementBreakupRequest(image_path='/staged/window_scan.jpg'))
    assert response.ok
    assert len(response.transactions) == 6
    assert response.transactions[0].description == 'QUALITY INNS JASPER TN'
    assert response.bank_name == 'Choice Privileges Mastercard'
    assert response.account_last4 == '5596'
    assert response.statement_total == 140.45


def test_breakup_keeps_a_credit_row_for_the_operator_to_see():
    """A payment line is not an expense, but it IS on the page.

    Dropping it here would leave the operator unable to tell a
    correctly-skipped credit from a row the parser missed. The decision belongs
    to store_statement_transactions.py's split_expenses_and_credits.
    """
    extractor = PreflightStatementExtractor(FakePreflight(_ok_preflight()))
    response = extractor.extract(
        StatementBreakupRequest(image_path='/staged/window_scan.jpg'))
    payments = [row for row in response.transactions
                if 'PAYMENT' in row.description]
    assert len(payments) == 1
    assert payments[0].amount == 2900.00


def test_breakup_flags_the_payment_and_the_zero_line_as_not_reviewable():
    """The payment and the $0.00 interest line are on the page but are not
    expenses -- store_statement_transactions.py's split_expenses_and_credits
    was always going to skip both, so the operator should never see them on
    the Prev/Next review list looking like something to categorize."""
    extractor = PreflightStatementExtractor(FakePreflight(_ok_preflight()))
    response = extractor.extract(
        StatementBreakupRequest(image_path='/staged/window_scan.jpg'))
    by_description = {row.description: row.reviewable
                      for row in response.transactions}
    assert by_description['PAYMENT - THANK YOU'] is False
    assert by_description['Interest Charge on Purchases'] is False
    assert by_description['QUALITY INNS JASPER TN'] is True
    assert by_description['ECONO LODGE VALDOSTA GA'] is True
    assert by_description['CRACKER BARREL #428 CAVE CITY KY'] is True
    assert by_description['ELLIS SEARS LOT GRAND RAPIDS MI'] is True
    assert sum(row.reviewable for row in response.transactions) == 4


def test_reviewable_flag_uses_the_whole_pages_signs_not_a_lone_row():
    """A page of ALL positive amounts can't use the mixed-sign shortcut, so a
    positive, non-pattern-matching row must fall back to the description
    pattern instead of being flagged a credit just for being positive."""
    rows = [
        {'date': '2025-05-23', 'description': 'GROCERY STORE', 'amount': 12.34},
        {'date': '2025-05-24', 'description': 'GAS STATION', 'amount': 45.00},
    ]
    extractor = PreflightStatementExtractor(
        FakePreflight(_ok_preflight(), rows=rows))
    response = extractor.extract(
        StatementBreakupRequest(image_path='/staged/window_scan.jpg'))
    assert all(row.reviewable for row in response.transactions)


def test_breakup_skips_only_the_rows_it_cannot_read():
    """An unreadable row must not cost the operator the readable ones."""
    rows = CHOICE_PRIVILEGES_ROWS + [{'date': '', 'description': '', 'amount': None}]
    extractor = PreflightStatementExtractor(
        FakePreflight(_ok_preflight(), rows=rows))
    response = extractor.extract(
        StatementBreakupRequest(image_path='/staged/window_scan.jpg'))
    assert len(response.transactions) == 6


def test_breakup_passes_operator_metadata_to_the_preflight():
    preflight = FakePreflight(_ok_preflight())
    PreflightStatementExtractor(preflight).extract(StatementBreakupRequest(
        image_path='/staged/window_scan.jpg',
        bank_name='Wells Fargo', account_last4='5596'))
    assert preflight.calls == [(
        '/staged/window_scan.jpg',
        {'bank_name': 'Wells Fargo', 'account_last4': '5596'}, 'auto')]


def test_breakup_passes_the_chosen_engine_to_the_preflight():
    # A human clicking "Read with Haiku" must get exactly Haiku -- passing
    # the wrong engine (or silently defaulting to auto) would run a different
    # provider than the button the operator actually pressed.
    preflight = FakePreflight(_ok_preflight())
    PreflightStatementExtractor(preflight).extract(StatementBreakupRequest(
        image_path='/staged/window_scan.jpg', engine='haiku-only'))
    assert preflight.calls[0][2] == 'haiku-only'


def test_needs_metadata_still_returns_the_rows():
    """The rows were read; only the account identity is missing.

    Answering with a bare error would put the operator in front of an empty
    form while asking them to confirm a statement they can no longer see.
    """
    extractor = PreflightStatementExtractor(FakePreflight(_ok_preflight(
        ok=False, needs_statement_metadata=True,
        missing_fields=['account_last4'], account_last4=None,
        error='Statement needs bank name and account last four before storage.')))
    response = extractor.extract(
        StatementBreakupRequest(image_path='/staged/window_scan.jpg'))
    assert response.ok is False
    assert response.needs_statement_metadata is True
    assert response.missing_fields == ['account_last4']
    assert len(response.transactions) == 6


def test_non_statement_document_is_reported_not_guessed():
    class NoPreflight(IStatementPreflightGateway):
        def run(self, image_path, metadata, engine):
            return None

        def rows(self, image_path, preflight):
            return []

    response = PreflightStatementExtractor(NoPreflight()).extract(
        StatementBreakupRequest(image_path='/staged/receipt.jpg'))
    assert response.ok is False
    assert 'preflight' in (response.error or '')


# --- the store: Mazda's own command, built by hand ---------------------------

def test_store_payload_is_the_parsers_own_envelope():
    """Corrected rows must be indistinguishable from correctly-parsed ones."""
    payload = build_store_payload(_store_request())
    assert payload['ok'] is True
    assert payload['doc_kind'] == 'statement'
    assert payload['statement_count'] == 1
    statement = payload['statements'][0]
    assert statement['bank_name'] == 'Choice Privileges Mastercard'
    assert statement['account_number'] == '5596'
    assert statement['transactions'] == [
        {'date': '2025-05-23', 'description': 'QUALITY INNS JASPER TN',
         'amount': -93.99},
        {'date': '2025-05-31', 'description': 'PAYMENT - THANK YOU',
         'amount': 2900.00},
    ]


def test_store_command_matches_mazdas_statement_branch():
    command = build_store_command(_store_request(), '/tmp/payload.json')
    assert command[1] == STORE_SCRIPT
    assert command[2:4] == ['-f', '/tmp/payload.json']
    assert '--source-file=/staged/window_scan.jpg' in command
    assert '--bank-name=Choice Privileges Mastercard' in command
    assert '--account-last4=5596' in command
    assert '--account-last4-source' in command
    assert command[command.index('--account-last4-source') + 1] == (
        'known_cards_workbook')


def test_store_command_uses_equals_form_for_free_text():
    """argparse reads a separate value starting with '-' as an option.

    Same bug, same fix, as manual_entry.build_save_command's merchant override:
    a dash-leading bank name would fail the RUN, not the field.
    """
    command = build_store_command(
        _store_request(bank_name='-Wells Fargo'), '/tmp/payload.json')
    assert '--bank-name=-Wells Fargo' in command
    # Never as a bare, separately-passed value argparse would read as an option.
    assert '-Wells Fargo' not in command


def test_store_omits_last4_source_when_the_operator_typed_it():
    command = build_store_command(
        _store_request(last4_source=''), '/tmp/payload.json')
    assert '--account-last4-source' not in command


def test_store_reports_the_scripts_own_counts():
    runner = FakeRunner(CommandResult(returncode=0, report={
        'ok': True, 'transactions_parsed': 5, 'skipped_credits': 1,
        'duplicates': 2, 'stored': 2, 'uncategorized': 1, 'failed': 0,
        'expense_ids': [1601, 1602], 'problems': [],
    }))
    response = ScriptStatementStore(runner, FakeRunner(
        CommandResult(returncode=0, report={'ok': True}))).store(_store_request())
    assert response.ok
    assert response.transactions_parsed == 5
    assert response.skipped_credits == 1
    assert response.duplicates == 2
    assert response.stored == 2
    assert response.expense_ids == [1601, 1602]


def test_store_deletes_the_staged_payload_file():
    runner = FakeRunner(CommandResult(returncode=0, report={'ok': True}))
    ScriptStatementStore(runner, FakeRunner()).store(_store_request())
    payload_path = runner.commands[0][3]
    assert not os.path.exists(payload_path)


def test_store_failure_keeps_the_counts_it_did_reach():
    """"3 stored, 1 failed" must not come back as zeros.

    The operator has to know what already landed before deciding what to retry.
    """
    runner = FakeRunner(CommandResult(
        returncode=2, report={'ok': False, 'stored': 3, 'failed': 1,
                              'error': 'row 4 has no vendor'}))
    response = ScriptStatementStore(runner, FakeRunner()).store(_store_request())
    assert response.ok is False
    assert response.stored == 3
    assert response.failed == 1
    assert 'row 4' in (response.error or '')


def test_annotation_runs_for_stored_and_duplicate_rows():
    """A duplicate still earns the marked-up scan as evidence.

    Same two lists statement_review.resolve_review annotates, for the same
    reason -- an already-stored expense gains a supporting document.
    """
    store_runner = FakeRunner(CommandResult(returncode=0, report={
        'ok': True, 'expense_ids': [1601], 'duplicate_expense_ids': [1499, 1601]}))
    annotation_runner = FakeRunner(
        CommandResult(returncode=0, report={'ok': True}))
    response = ScriptStatementStore(
        store_runner, annotation_runner).store(_store_request())
    assert response.ok
    assert annotation_runner.commands, 'annotation pass never ran'
    command = annotation_runner.commands[0]
    assert command[1] == ANNOTATION_SCRIPT
    assert '--image=/staged/window_scan.jpg' in command
    # 1601 once, not twice, and in first-seen order.
    assert command[command.index('--expense-ids') + 1] == '1601,1499'


def test_annotation_failure_is_reported_without_losing_the_store():
    store_runner = FakeRunner(CommandResult(returncode=0, report={
        'ok': True, 'stored': 2, 'expense_ids': [1601, 1602]}))
    annotation_runner = FakeRunner(CommandResult(
        returncode=1, report={'ok': False, 'problems': ['no handwriting found']}))
    response = ScriptStatementStore(
        store_runner, annotation_runner).store(_store_request())
    assert response.ok is False
    assert response.stored == 2
    assert 'no handwriting' in (response.error or '')


def test_no_annotation_call_when_nothing_was_stored():
    store_runner = FakeRunner(CommandResult(returncode=0, report={
        'ok': True, 'transactions_parsed': 1, 'skipped_credits': 1,
        'stored': 0, 'expense_ids': []}))
    annotation_runner = FakeRunner()
    response = ScriptStatementStore(
        store_runner, annotation_runner).store(_store_request())
    assert response.ok
    assert annotation_runner.commands == []


# --- boundary models ---------------------------------------------------------

def test_row_allows_a_negative_amount():
    """Statement sign conventions vary; the store decides, not this model."""
    assert StatementRow(transaction_date='2025-05-31',
                        description='PAYMENT - THANK YOU', amount=-2900.0)


def test_row_rejects_a_non_iso_date():
    with pytest.raises(ValidationError):
        StatementRow(transaction_date='05/31/2025', description='X', amount=1.0)


def test_row_rejects_a_blank_description():
    with pytest.raises(ValidationError):
        StatementRow(transaction_date='2025-05-31', description='  ', amount=1.0)


def test_store_request_needs_at_least_one_transaction():
    with pytest.raises(ValidationError):
        _store_request(transactions=[])


def test_store_request_rejects_an_unknown_last4_source():
    """store_statement_transactions.py's --account-last4-source is a choice.

    An unrecognized value is an argparse error, which never reaches the report
    the operator reads -- so it is refused here, where it can be explained.
    """
    with pytest.raises(ValidationError):
        _store_request(last4_source='guessed')


def test_from_http_coerces_the_strings_a_browser_sends():
    request = StatementStoreRequest.from_http({
        'image_path': '/staged/window_scan.jpg',
        'bank_name': ' Choice  Privileges ',
        'account_last4': '5596',
        'statement_total': '140.45',
        'transactions': [
            {'transaction_date': '2025-05-23',
             'description': 'QUALITY INNS JASPER TN', 'amount': '-93.99'},
        ],
    })
    assert request.bank_name == 'Choice Privileges'
    assert request.statement_total == 140.45
    assert request.transactions[0].amount == -93.99


def test_from_http_refuses_a_boolean_as_an_amount():
    """JSON true is not a number, and bool is an int subclass in Python."""
    with pytest.raises(ValueError):
        StatementStoreRequest.from_http({
            'image_path': '/x.jpg', 'bank_name': 'B', 'account_last4': '1234',
            'transactions': [{'transaction_date': '2025-05-23',
                              'description': 'X', 'amount': True}],
        })


def test_breakup_request_requires_an_image_path():
    with pytest.raises(ValidationError):
        StatementBreakupRequest.from_http({'image_path': '   '})


def test_breakup_request_defaults_to_auto_engine():
    request = StatementBreakupRequest.from_http({'image_path': '/x.jpg'})
    assert request.engine == 'auto'


def test_breakup_request_accepts_the_two_operator_engines():
    for engine in ('gemini-only', 'haiku-only'):
        request = StatementBreakupRequest.from_http(
            {'image_path': '/x.jpg', 'engine': engine})
        assert request.engine == engine


def test_breakup_request_rejects_an_unknown_engine():
    # Refused here, with a clear 400, rather than reaching
    # parse_statement_scan.py's --engine flag as a cryptic argparse failure.
    with pytest.raises(ValidationError):
        StatementBreakupRequest.from_http(
            {'image_path': '/x.jpg', 'engine': 'chatgpt-oauth'})


# --- the service: the recorder only fires on a real store --------------------

class RecordingRecorder(NullStatementIntakeRecorder):
    def __init__(self):
        self.records = []

    def record(self, request, response):
        self.records.append((request, response))


class StubStore(IStatementStore):
    def __init__(self, response):
        self._response = response

    def store(self, request):
        return self._response


def test_service_records_the_intake_only_when_the_store_succeeded():
    recorder = RecordingRecorder()
    service = StatementBreakupService(
        PreflightStatementExtractor(FakePreflight(_ok_preflight())),
        StubStore(StatementStoreResponse(ok=False, error='store failed')),
        recorder)
    assert service.store(_store_request()).ok is False
    assert recorder.records == []

    service = StatementBreakupService(
        PreflightStatementExtractor(FakePreflight(_ok_preflight())),
        StubStore(StatementStoreResponse(ok=True, stored=2)),
        recorder)
    assert service.store(_store_request()).ok is True
    assert len(recorder.records) == 1


def test_breakup_response_is_json_serializable_for_the_form():
    response = PreflightStatementExtractor(
        FakePreflight(_ok_preflight())).extract(
            StatementBreakupRequest(image_path='/staged/window_scan.jpg'))
    payload = json.loads(json.dumps(response.to_http()))
    assert len(payload['transactions']) == 6
    assert payload['transactions'][0]['transaction_date'] == '2025-05-23'
