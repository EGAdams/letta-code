"""Contract tests for the column-tolerant `expenses` SELECT capability.

The live `expenses` table is narrower than this dashboard's own schema: rows
written by the finance tooling may lack `id_light`, `document_url`,
`scanned_statement_url`, `moms_ledger`, or the itemization columns. Selecting a
column that does not exist is a hard MySQL error, so every read has to ask the
table what it has first. This module owns that once.
"""

import pytest
from pydantic import ValidationError

from finance.expense_schema import (
    EXPENSE_TABLE,
    ExpenseSchema,
    InformationSchemaProbe,
    ShowColumnsProbe,
)


class RecordingCursor:
    """Cursor double that replays one canned result per execute()."""

    def __init__(self, rows):
        self._rows = list(rows)
        self.queries = []

    def execute(self, sql, params=None):
        self.queries.append((sql, params))

    def fetchall(self):
        return self._rows


class TestExpenseSchema:
    def test_reports_what_the_table_has(self):
        schema = ExpenseSchema(available=frozenset({'id', 'amount'}))
        assert schema.has('id') is True
        assert schema.has('moms_ledger') is False

    def test_is_a_strict_frozen_boundary_model(self):
        schema = ExpenseSchema(available=frozenset({'id'}))
        with pytest.raises(ValidationError):
            ExpenseSchema(available=frozenset({'id'}), extra_field='nope')
        with pytest.raises(ValidationError):
            ExpenseSchema(available=['id'])  # no implicit coercion
        with pytest.raises(ValidationError):
            schema.available = frozenset()  # frozen


class TestSelectClause:
    def test_required_columns_are_selected_plainly(self):
        schema = ExpenseSchema(available=frozenset({'id', 'amount'}))
        assert schema.select_clause(('id', 'amount'), ()) == 'id, amount'

    def test_a_missing_optional_column_becomes_a_null_placeholder(self):
        schema = ExpenseSchema(available=frozenset({'id', 'receipt_url'}))
        clause = schema.select_clause(('id',), ('receipt_url', 'moms_ledger'))
        assert clause == 'id, receipt_url, NULL AS moms_ledger'

    def test_identifiers_can_be_quoted_for_call_sites_that_need_it(self):
        schema = ExpenseSchema(available=frozenset({'id'}))
        clause = schema.select_clause(('id',), ('id_light',), quote='`')
        assert clause == '`id`, NULL AS `id_light`'

    def test_a_column_name_that_is_not_an_identifier_is_refused(self):
        schema = ExpenseSchema(available=frozenset({'id'}))
        with pytest.raises(ValueError):
            schema.select_clause(('id',), ('amount; DROP TABLE expenses',))


class TestProbeContract:
    """Both probes must report the same schema — only their SQL differs.

    Two exist because MySQL grants differ per deployment: `SHOW COLUMNS` needs
    a privilege on the table, `INFORMATION_SCHEMA` does not always agree.
    """

    CANDIDATES = ('id_light', 'document_url', 'moms_ledger')

    def test_show_columns_probe_reports_present_columns(self):
        cur = RecordingCursor([{'Field': 'id'}, {'Field': 'id_light'}])
        schema = ShowColumnsProbe().read(cur, self.CANDIDATES)
        assert schema.has('id_light') is True
        assert schema.has('document_url') is False
        assert cur.queries[0][0] == f'SHOW COLUMNS FROM `{EXPENSE_TABLE}`'

    def test_information_schema_probe_reports_present_columns(self):
        cur = RecordingCursor([{'COLUMN_NAME': 'id_light'}])
        schema = InformationSchemaProbe().read(cur, self.CANDIDATES)
        assert schema.has('id_light') is True
        assert schema.has('document_url') is False
        sql = cur.queries[0][0]
        assert "COLUMN_NAME IN ('id_light'" in sql
        assert 'INFORMATION_SCHEMA.COLUMNS' in sql

    @pytest.mark.parametrize(
        'probe,rows',
        [
            (ShowColumnsProbe(), [{'Field': 'id_light'}, {'Field': 'amount'}]),
            (InformationSchemaProbe(), [{'COLUMN_NAME': 'id_light'}]),
        ],
    )
    def test_every_probe_agrees_on_a_missing_column(self, probe, rows):
        schema = probe.read(RecordingCursor(rows), self.CANDIDATES)
        assert schema.has('id_light') is True
        assert schema.has('moms_ledger') is False

    @pytest.mark.parametrize(
        'probe', [ShowColumnsProbe(), InformationSchemaProbe()]
    )
    def test_every_probe_fails_closed_on_an_empty_table_report(self, probe):
        schema = probe.read(RecordingCursor([]), self.CANDIDATES)
        assert schema.has('id_light') is False

    def test_the_probe_refuses_a_candidate_that_is_not_an_identifier(self):
        with pytest.raises(ValueError):
            InformationSchemaProbe().read(RecordingCursor([]), ("x'; --",))
