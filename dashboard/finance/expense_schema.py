"""Column-tolerant reads of the live `expenses` table.

The finance database this dashboard reads is not always as wide as the
dashboard's own schema: a deployment may have no `id_light`, `document_url`,
`scanned_statement_url`, `moms_ledger`, or itemization columns at all. MySQL
fails the whole statement when a SELECT names a column that does not exist, so
a read must ask the table what it has and substitute NULL for the rest.

Every expense read shares that capability through this module instead of
hand-rolling its own probe and its own SELECT string.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Iterable, Sequence

from contracts import StrictModel

EXPENSE_TABLE = 'expenses'

_IDENTIFIER = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def _checked_identifier(name: str) -> str:
    """Guard the only values this module ever interpolates into SQL.

    Column names are internal constants, never user input, but they are
    inlined (a probe cannot parameterize an identifier list), so the guard
    keeps a future refactor from turning that into an injection point.
    """
    text = str(name)
    if not _IDENTIFIER.match(text):
        raise ValueError(f'not a SQL identifier: {name!r}')
    return text


class ExpenseSchema(StrictModel):
    """Which of the columns we care about this table actually has."""

    available: frozenset[str]

    def has(self, column: str) -> bool:
        return column in self.available

    def select_clause(
        self,
        required: Sequence[str],
        optional: Sequence[str],
        quote: str = '',
    ) -> str:
        """A SELECT list where every absent optional column reads as NULL.

        `required` columns are assumed to exist — without them the row is not
        an expense and failing loudly is correct.
        """
        parts = [f'{quote}{_checked_identifier(c)}{quote}' for c in required]
        for column in optional:
            name = f'{quote}{_checked_identifier(column)}{quote}'
            parts.append(name if self.has(column) else f'NULL AS {name}')
        return ', '.join(parts)


class IExpenseSchemaProbe(ABC):
    """Port: report which candidate columns the expenses table has."""

    @abstractmethod
    def read(self, cur: Any, candidates: Sequence[str]) -> ExpenseSchema:
        """Return the schema, failing closed (absent) on anything unreported."""


def _column_values(rows: Iterable[Any], key: str) -> set[str]:
    found: set[str] = set()
    for row in rows or ():
        value = row.get(key) if hasattr(row, 'get') else None
        if value:
            found.add(str(value))
    return found


class ShowColumnsProbe(IExpenseSchemaProbe):
    """`SHOW COLUMNS` — one round trip, reports the entire table."""

    def read(self, cur: Any, candidates: Sequence[str]) -> ExpenseSchema:
        for candidate in candidates:
            _checked_identifier(candidate)
        cur.execute(f'SHOW COLUMNS FROM `{EXPENSE_TABLE}`')
        return ExpenseSchema(
            available=frozenset(_column_values(cur.fetchall(), 'Field'))
        )


class InformationSchemaProbe(IExpenseSchemaProbe):
    """`INFORMATION_SCHEMA` — asks only about the columns in question.

    Preferred where `SHOW COLUMNS` is not granted, or where the caller wants
    the probe to name its own interest in the query log.
    """

    def read(self, cur: Any, candidates: Sequence[str]) -> ExpenseSchema:
        names = [_checked_identifier(c) for c in candidates]
        if not names:
            return ExpenseSchema(available=frozenset())
        in_list = ', '.join(f"'{name}'" for name in names)
        cur.execute(
            'SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS '
            'WHERE TABLE_SCHEMA = DATABASE() '
            f"AND TABLE_NAME = '{EXPENSE_TABLE}' "
            f'AND COLUMN_NAME IN ({in_list})'
        )
        return ExpenseSchema(
            available=frozenset(_column_values(cur.fetchall(), 'COLUMN_NAME'))
        )
