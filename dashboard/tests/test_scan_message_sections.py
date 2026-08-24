"""The intake prompt, section by section.

`tests/test_server.py` already asserts a great deal about the *whole* message,
and those tests kept working unchanged through this split -- which is most of
the evidence that the split was faithful. What it could not do is reach a
single rule: to check how a bank name is quoted you had to build 18,000
characters of prompt and search them.

These tests exercise the sections directly. The failure mode they guard is the
one this prompt has always had: nothing raises. A dropped flag or a mangled
path produces a slightly different instruction, Mazda follows it, and a real
expense is filed against the wrong account.
"""

import json
import re

import pytest

import server
from intake import scan_message
from intake.scan_message import (
    MAZDA_RF_ENV_JSON,
    MAZDA_RF_VENV_PY,
    artifact_paths,
    blocks_for_unidentified,
    categorizer_input_for,
    facade_block_for_identified,
    finish_block_for,
    override_args_for,
    statement_only_message,
    steps_for_identified_statement,
    store_contract_for,
)

IDENTIFIED_RECEIPT = {
    'ok': True, 'doc_kind': 'receipt', 'vendor': 'goodwill_cascade',
    'confidence': 0.91, 'recommended_action': 'accept', 'routing_key': 'rk',
    'parsed': {'transaction_date': '2026-08-01', 'total_amount': '12.34',
               'merchant_name': 'Goodwill Cascade'},
}
IDENTIFIED_STATEMENT = {
    'ok': True, 'doc_kind': 'statement', 'vendor': 'chase', 'confidence': 0.99,
    'recommended_action': 'accept', 'parsed': {},
}
UNIDENTIFIED = {'ok': True, 'doc_kind': 'unknown', 'confidence': 0.0,
                'recommended_action': 'reject', 'parsed': None}


class TestOverrideArgs:
    """Bank identity flags. Half an identity files a statement to the wrong
    account, so both fields are required before either flag is emitted."""

    def test_both_fields_produce_both_flags(self):
        args = override_args_for({'bank_name': 'Chase', 'account_last4': '1234'})
        assert '--bank-name Chase' in args
        assert '--account-last4 1234' in args

    @pytest.mark.parametrize('preflight', [
        {'bank_name': 'Chase'},
        {'account_last4': '1234'},
        {'bank_name': 'Chase', 'account_last4': ''},
        {'bank_name': '', 'account_last4': '1234'},
        {},
    ])
    def test_a_partial_identity_emits_nothing(self, preflight):
        assert override_args_for(preflight) == ''

    def test_a_bank_name_with_spaces_is_quoted_as_one_argument(self):
        args = override_args_for(
            {'bank_name': 'Chase Bank', 'account_last4': '1234'})
        assert "--bank-name 'Chase Bank'" in args

    def test_an_apostrophe_in_a_bank_name_cannot_break_out_of_the_command(self):
        """shlex, not manual quoting: `O'Brien` would otherwise end the string."""
        args = override_args_for(
            {'bank_name': "O'Brien & Co", 'account_last4': '9999'})
        import shlex
        assert shlex.split(args) == [
            '--bank-name', "O'Brien & Co", '--account-last4', '9999']

    def test_the_workbook_source_is_declared_when_that_is_where_last4_came_from(self):
        args = override_args_for({'bank_name': 'Chase', 'account_last4': '1234',
                                  'last4_source': 'known_cards_workbook'})
        assert '--account-last4-source known_cards_workbook' in args

    @pytest.mark.parametrize('source', [None, '', 'statement_text', 'guess'])
    def test_any_other_source_is_not_declared(self, source):
        args = override_args_for({'bank_name': 'Chase', 'account_last4': '1234',
                                  'last4_source': source})
        assert '--account-last4-source' not in args

    def test_a_numeric_last4_survives_quoting(self):
        args = override_args_for({'bank_name': 'Chase', 'account_last4': 1234})
        assert '--account-last4 1234' in args


class TestArtifactPaths:
    """Paths are keyed to the scan so two concurrent intakes cannot collide."""

    def test_both_paths_carry_the_same_scan_token(self):
        receipt, statement = artifact_paths('/scans/a.jpg', {})
        token = re.search(r'mazda_receipt_([0-9a-f]+)\.json', receipt).group(1)
        assert f'mazda_statement_{token}.json' == statement.split('/')[-1]

    def test_the_token_is_twelve_hex_characters(self):
        receipt, _ = artifact_paths('/scans/a.jpg', {})
        assert re.fullmatch(r'/tmp/mazda_receipt_[0-9a-f]{12}\.json', receipt)

    def test_two_scans_in_flight_get_different_artifacts(self):
        """The collision this prevents: two scanners filing at once, the second
        parse overwriting the first scan's artifact before STEP 4 reads it."""
        first, _ = artifact_paths('/scans/window-001.jpg', {})
        second, _ = artifact_paths('/scans/freezer-001.jpg', {})
        assert first != second

    def test_the_same_scan_always_gets_the_same_artifact(self):
        assert artifact_paths('/scans/a.jpg', {}) == artifact_paths('/scans/a.jpg', {})

    def test_a_validated_payload_replaces_the_statement_path_only(self):
        receipt, statement = artifact_paths(
            '/scans/a.jpg', {'payload_path': '/tmp/validated.json'})
        assert statement == '/tmp/validated.json'
        assert receipt.startswith('/tmp/mazda_receipt_')

    @pytest.mark.parametrize('payload', [None, '', 0])
    def test_an_absent_payload_falls_back_to_the_derived_path(self, payload):
        _, statement = artifact_paths('/scans/a.jpg', {'payload_path': payload})
        assert statement.startswith('/tmp/mazda_statement_')


class TestStoreContract:
    def test_the_unidentified_path_demands_a_verified_parse_artifact(self):
        assert 'parse_artifact_verified=true' in store_contract_for(False)

    def test_the_identified_path_warns_the_artifact_may_be_unverified(self):
        """Its only parse happens during STEP 4, so the flag can be false --
        Mazda is told to check the values instead of trusting the flag."""
        contract = store_contract_for(True)
        assert 'parse_artifact_verified may be false' in contract
        assert 'Verify' in contract

    def test_the_two_contracts_differ(self):
        assert store_contract_for(True) != store_contract_for(False)


class TestFinishBlock:
    def test_the_report_is_built_next_to_the_scan(self):
        block = finish_block_for('/reports/2026-08/scan.jpg')
        assert '/reports/2026-08/report.html' in block

    def test_the_audit_runs_against_the_report_directory(self):
        block = finish_block_for('/reports/2026-08/scan.jpg')
        assert re.search(r'audit_statement_reports\.py\s+/reports/2026-08\b', block)

    def test_annotations_use_the_plural_flag_in_one_call(self):
        """Singular --expense-id or a per-ID loop was the observed failure; the
        block spells out the prohibition because Mazda kept reinventing it."""
        block = finish_block_for('/scans/a.jpg')
        assert '--expense-ids <IDS>' in block
        assert 'do not use singular --expense-id' in block
        assert 'shell substitution' in block
        assert 'per-ID calls' in block

    def test_annotations_cover_duplicates_as_well_as_stored_rows(self):
        """A duplicate row is an existing expense this scan is evidence for. If
        <IDS> carries only newly stored ids, the annotations never reach the
        rows the scan actually matched -- and nothing reports an error."""
        block = finish_block_for('/scans/a.jpg')
        assert 'every stored AND duplicate expense id' in block
        assert 'one comma-separated value' in block

    def test_it_names_the_scan_being_annotated(self):
        assert '--image /scans/a.jpg' in finish_block_for('/scans/a.jpg')

    def test_every_command_uses_the_venv_interpreter(self):
        block = finish_block_for('/scans/a.jpg')
        for line in block.splitlines():
            if '.py ' in line and 'python' in line:
                assert MAZDA_RF_VENV_PY in line


class TestFacadeBlocks:
    def test_the_identified_block_forbids_reclassifying(self):
        block = facade_block_for_identified(
            IDENTIFIED_RECEIPT, 'receipt', 'goodwill_cascade', 0.91,
            IDENTIFIED_RECEIPT['parsed'])
        assert 'IDENTIFIED this document' in block
        assert 'Do NOT re-run classify or parse' in block

    def test_the_summary_carries_only_the_fields_worth_showing(self):
        parsed = {'transaction_date': '2026-08-01', 'total_amount': '12.34',
                  'merchant_name': 'Goodwill', 'raw_ocr': 'x' * 5000}
        block = facade_block_for_identified(
            IDENTIFIED_RECEIPT, 'receipt', 'goodwill', 0.9, parsed)
        assert 'Goodwill' in block
        assert 'raw_ocr' not in block

    def test_an_absent_field_is_omitted_rather_than_shown_as_null(self):
        block = facade_block_for_identified(
            IDENTIFIED_RECEIPT, 'receipt', 'v', 0.9, {'merchant_name': 'M'})
        summary = re.search(r'parsed: (\{.*\})', block).group(1)
        assert json.loads(summary) == {'merchant_name': 'M'}

    def test_an_unserialisable_value_does_not_raise(self):
        import datetime
        block = facade_block_for_identified(
            IDENTIFIED_RECEIPT, 'receipt', 'v', 0.9,
            {'transaction_date': datetime.date(2026, 8, 1)})
        assert '2026-08-01' in block

    def test_the_unidentified_block_reports_the_facades_error_when_there_is_one(self):
        facade, fallback = blocks_for_unidentified(
            {'error': 'file not found'}, 'unknown', 0.0, '/scans/a.jpg', '/tmp/r.json')
        assert 'error: file not found' in facade
        assert 'STEP 0' in fallback

    def test_without_an_error_it_reports_what_the_facade_did_return(self):
        facade, _ = blocks_for_unidentified(
            {'ok': True}, 'unknown', 0.0, '/scans/a.jpg', '/tmp/r.json')
        assert "doc_kind='unknown'" in facade
        assert 'confidence: 0' not in facade or 'confidence=0' in facade

    def test_the_fallback_forbids_chaining_the_classifier_to_a_parser(self):
        """Chaining is what routed a statement into the receipt parser."""
        _, fallback = blocks_for_unidentified(
            UNIDENTIFIED, 'unknown', 0.0, '/scans/a.jpg', '/tmp/r.json')
        assert 'HARD ROUTING BARRIER' in fallback
        assert 'Never chain the classifier to a parser' in fallback

    def test_the_fallback_writes_the_parse_artifact_it_was_given(self):
        _, fallback = blocks_for_unidentified(
            UNIDENTIFIED, 'unknown', 0.0, '/scans/a.jpg', '/tmp/r-abc.json')
        assert '--write-parsed-json /tmp/r-abc.json' in fallback

    def test_the_fallback_sends_a_statement_away_before_parsing_it(self):
        _, fallback = blocks_for_unidentified(
            UNIDENTIFIED, 'unknown', 0.0, '/scans/a.jpg', '/tmp/r.json')
        assert 'STOP STEP 0 HERE' in fallback
        assert 'STATEMENT BRANCH S1' in fallback


class TestStatementSteps:
    def test_a_validated_payload_is_stored_without_parsing_again(self):
        steps = steps_for_identified_statement(
            '/scans/a.jpg', '/tmp/validated.json', '/tmp/validated.json', '')
        assert 'Do not run statement vision again' in steps
        assert 'parse_statement_scan.py' not in steps
        assert '-f /tmp/validated.json' in steps

    def test_without_a_payload_it_parses_first_then_stores(self):
        steps = steps_for_identified_statement(
            '/scans/a.jpg', '', '/tmp/derived.json', '')
        assert 'parse_statement_scan.py /scans/a.jpg -o /tmp/derived.json' in steps
        assert 'store_statement_transactions.py' in steps

    @pytest.mark.parametrize('payload', ['', '/tmp/validated.json'])
    def test_the_override_flags_reach_the_store_command_either_way(self, payload):
        steps = steps_for_identified_statement(
            '/scans/a.jpg', payload, payload or '/tmp/d.json',
            ' --bank-name Chase --account-last4 1234')
        store = [ln for ln in steps.splitlines()
                 if 'store_statement_transactions.py' in ln or '--bank-name' in ln]
        assert any('--bank-name Chase' in ln for ln in store)

    @pytest.mark.parametrize('payload', ['', '/tmp/validated.json'])
    def test_every_command_carries_the_executor_env(self, payload):
        steps = steps_for_identified_statement(
            '/scans/a.jpg', payload, '/tmp/d.json', '')
        assert MAZDA_RF_ENV_JSON in steps
        assert 'PYTHONPATH=/home/adamsl' not in steps


class TestStatementOnlyMessage:
    def message(self):
        return statement_only_message(
            '/scans/a.jpg', 'Freezer Scanner', 'chase', 0.99,
            steps_for_identified_statement('/scans/a.jpg', '', '/tmp/d.json', ''),
            finish_block_for('/scans/a.jpg'), 'conv-1', 1723.5)

    @pytest.mark.parametrize('absent', [
        'STEP 2', 'STEP 3', 'STEP 4', 'check_duplicates', 'categorizer_main.py',
        'parse_and_categorize.py',
    ])
    def test_the_receipt_pipeline_is_absent_not_merely_skipped(self, absent):
        """Omission, not instruction. "Skip STEPS 2-4" is a rule Mazda has been
        observed to disregard; text that was never sent cannot be followed."""
        assert absent not in self.message()

    def test_it_says_so_explicitly(self):
        assert 'STATEMENT-ONLY intake' in self.message()
        assert 'forbidden' in self.message()

    def test_it_still_records_judges_and_notifies(self):
        message = self.message()
        assert 'record_trace' in message
        assert 'judge_trace' in message
        assert '/api/expense-stored' in message

    def test_the_callback_carries_the_dispatch_identity(self):
        message = self.message()
        assert 'conversation_id="conv-1"' in message
        assert 'dispatched_at=1723.5' in message

    def test_a_missing_dispatch_identity_becomes_empty_and_zero(self):
        message = statement_only_message(
            '/scans/a.jpg', 'S', 'chase', 0.9, 'steps', 'finish', None, None)
        assert 'conversation_id=""' in message
        assert 'dispatched_at=0.0' in message

    def test_duplicates_do_not_end_the_run_early(self):
        assert 'Do not stop before steps 4-6' in self.message()

    def test_it_carries_the_supporting_document_contract(self):
        assert 'SUPPORTING-DOCUMENT STORAGE CONTRACT' in self.message()


class TestCategorizerInput:
    def test_an_identified_facade_prefills_the_input(self):
        line = categorizer_input_for(
            True, {'merchant_name': 'Goodwill Cascade'}, 'goodwill_cascade')
        payload = json.loads(re.search(r"printf '%s' '(\{.*?\})'", line).group(1))
        assert payload['description'] == 'Goodwill Cascade'
        assert payload['vendor_key'] == 'goodwill_cascade'

    def test_a_vendor_of_unknown_is_sent_as_null_not_as_the_word(self):
        line = categorizer_input_for(True, {'merchant_name': 'M'}, 'unknown')
        payload = json.loads(re.search(r"printf '%s' '(\{.*?\})'", line).group(1))
        assert payload['vendor_key'] is None

    def test_the_vendor_stands_in_when_the_parse_found_no_merchant(self):
        line = categorizer_input_for(True, {}, 'goodwill_cascade')
        payload = json.loads(re.search(r"printf '%s' '(\{.*?\})'", line).group(1))
        assert payload['description'] == 'goodwill_cascade'

    def test_the_unidentified_path_never_ships_the_literal_placeholder(self):
        """Handing over {"description":"unknown"} guarantees a categorizer miss
        and pushes the vendor onto the slow LLM-research path."""
        line = categorizer_input_for(False, {}, 'unknown')
        assert '"description": "unknown"' not in line
        assert 'NOT the literal word' in line

    def test_the_unidentified_path_points_at_the_step_0_results(self):
        line = categorizer_input_for(False, {}, 'unknown')
        assert 'STEP 0' in line
        assert '/tmp/mazda_cat_input.json' in line


class TestRouting:
    """Which branch a document takes -- the one decision in an otherwise
    straight-line builder."""

    @pytest.mark.parametrize('doc_kind', ['statement', 'bank_statement'])
    def test_an_identified_statement_gets_the_statement_only_dispatch(self, doc_kind):
        facade = dict(IDENTIFIED_STATEMENT, doc_kind=doc_kind)
        message = scan_message.build_scan_message('/scans/a.jpg', 'S', facade)
        assert 'STATEMENT-ONLY intake' in message
        assert 'STEP 2' not in message

    def test_an_unidentified_statement_still_gets_the_full_pipeline(self):
        """The facade did not classify it, so Mazda must classify it herself --
        the statement branch is inside the full message, reached via STEP 0."""
        message = scan_message.build_scan_message('/scans/a.jpg', 'S', UNIDENTIFIED)
        assert 'STATEMENT-ONLY intake' not in message
        assert 'STEP 0' in message
        assert 'STATEMENT BRANCH' in message

    def test_an_identified_receipt_gets_the_full_pipeline_without_step_0(self):
        message = scan_message.build_scan_message(
            '/scans/a.jpg', 'S', IDENTIFIED_RECEIPT)
        assert 'IDENTIFIED this document' in message
        assert 'STEP 0 — CLASSIFY' not in message
        assert 'STEP 4 — STORE' in message

    def test_an_identified_receipt_omits_the_parse_artifact_flag(self):
        """Its parse happens during STEP 4; there is no earlier artifact."""
        message = scan_message.build_scan_message(
            '/scans/a.jpg', 'S', IDENTIFIED_RECEIPT)
        assert '--parsed-json' not in message

    def test_no_facade_at_all_is_treated_as_unidentified(self):
        for facade in (None, {}):
            message = scan_message.build_scan_message('/scans/a.jpg', 'S', facade)
            assert 'STEP 0' in message

    def test_the_scanner_name_reaches_the_operator_facing_first_line(self):
        message = scan_message.build_scan_message(
            '/scans/a.jpg', 'Window Scanner', None)
        assert 'Window Scanner' in message.splitlines()[0]


class TestServerReExport:
    def test_server_still_exposes_the_historical_names(self):
        assert server.build_mazda_scan_message is scan_message.build_scan_message
        assert server.mazda_facade_identified is scan_message.facade_identified

    def test_the_constants_are_re_exported_too(self):
        assert server.MAZDA_RF_VENV_PY == MAZDA_RF_VENV_PY
        assert server.MAZDA_RF_ENV_JSON == MAZDA_RF_ENV_JSON

    def test_the_builder_no_longer_lives_in_server(self):
        assert (server.build_mazda_scan_message.__module__
                == 'intake.scan_message')
