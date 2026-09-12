"""Human verification starts when a person opens Set Category."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from finance.human_verification import (
    HumanVerificationRequest,
    HumanVerificationService,
    MySqlHumanVerificationRepository,
    decorate_verified_rows,
)
from finance.intake_report_model import presentation_rows
from finance.intake_report_page import transactions_table_html


class _Cursor:
    def __init__(self, row):
        self.row = row
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self.statements.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self, row):
        self.cursor_instance = _Cursor(row)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.cursor_instance


class _Repository:
    def __init__(self, found=True, verified_ids=()):
        self.found = found
        self.verified = set(verified_ids)
        self.marked = []

    def mark_verified(self, expense_id):
        self.marked.append(expense_id)
        return self.found

    def verified_ids(self, expense_ids):
        return self.verified.intersection(expense_ids)


def test_request_requires_a_strict_positive_expense_id():
    assert HumanVerificationRequest(expense_id=42).expense_id == 42
    for value in ("42", 0, -1, True, 4.2):
        with pytest.raises(ValidationError):
            HumanVerificationRequest(expense_id=value)


def test_mysql_repository_marks_the_existing_expense_once():
    connection = _Connection({"id": 42, "human_verified": 0})
    repository = MySqlHumanVerificationRepository(lambda: connection)

    assert repository.mark_verified(42) is True
    assert connection.cursor_instance.statements == [
        ("SELECT id, human_verified FROM expenses WHERE id=%s", (42,)),
        ("UPDATE expenses SET human_verified=1 WHERE id=%s", (42,)),
    ]


def test_mysql_repository_leaves_an_already_verified_expense_unchanged():
    connection = _Connection({"id": 42, "human_verified": 1})
    repository = MySqlHumanVerificationRepository(lambda: connection)

    assert repository.mark_verified(42) is True
    assert len(connection.cursor_instance.statements) == 1


def test_service_fails_closed_when_the_expense_does_not_exist():
    repository = _Repository(found=False)
    result = HumanVerificationService(repository).mark_verified(
        HumanVerificationRequest(expense_id=404)
    )

    assert result.ok is False
    assert result.human_verified is False
    assert repository.marked == [404]


def test_decorates_only_verified_rows_inside_verified_transactions():
    source = (
        '<table id="verified-transactions"><tbody>'
        '<tr class="cat-personal" data-expense-id="41"><td>A</td></tr>'
        '<tr class="cat-housing has-receipt" data-expense-id="42"><td>B</td></tr>'
        '</tbody></table>'
        '<table><tr data-expense-id="42"><td>Other table</td></tr></table>'
    )

    decorated = decorate_verified_rows(source, {42})

    assert 'class="cat-housing has-receipt human-verified"' in decorated
    assert 'data-expense-id="42" data-human-verified="true"' in decorated
    assert 'data-expense-id="41" data-human-verified' not in decorated
    assert '<table><tr data-expense-id="42"><td>Other table</td></tr></table>' in decorated


def test_report_decoration_is_idempotent():
    source = (
        '<table id="verified-transactions"><tbody>'
        '<tr class="cat-personal human-verified" data-expense-id="42" '
        'data-human-verified="true"><td>A</td></tr>'
        '</tbody></table>'
    )
    service = HumanVerificationService(_Repository(verified_ids={42}))

    assert service.decorate_report(source) == source


def test_dynamic_verified_transaction_row_renders_the_persisted_marker():
    rows = presentation_rows(
        [{
            "id": 42,
            "cat_class": "cat-personal",
            "description": "Reviewed expense",
            "human_verified": True,
        }],
        set(),
    )

    rendered = transactions_table_html(rows)

    assert 'class="cat-personal human-verified"' in rendered
    assert 'data-expense-id="42" data-human-verified="true"' in rendered
