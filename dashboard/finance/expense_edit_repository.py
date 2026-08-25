"""Behaviour behind the Edit Expense boundary: ports first, MySQL second.

Two ports, each deliberately narrow:

* ``ICategoryNamer`` — the only thing this module needs to know about the
  category taxonomy is "id -> label" and "label -> id". server.py owns the real
  taxonomy (``_reporting_category_for_id`` / ``_resolve_reporting_category``);
  passing the whole taxonomy in here would be a fat agreement for two lookups.
* ``IExpenseRecordRepository`` — search stored rows, apply one correction.

``MySqlExpenseRecordRepository`` is the one concrete implementation. It reads
through ``finance.expense_schema`` rather than naming optional columns
directly, because the live finance DB is not always as wide as this dashboard's
schema and a missing ``id_light`` must not fail the whole search.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, Sequence

from finance.expense_edit_model import (
    AMOUNT_MATCH_TOLERANCE,
    ExpenseEdit,
    ExpenseEditResult,
    ExpenseNotFound,
    ExpenseRecord,
    ExpenseSearchCriteria,
    describe_changes,
    linkage_warnings,
)
from finance.category_naming import ICategoryNamer
from finance.expense_schema import InformationSchemaProbe, IExpenseSchemaProbe
from finance.http_coercion import as_optional_float, as_optional_int

#: Columns the search reads only if the live table actually has them.
OPTIONAL_COLUMNS = ('id_light',)
#: Columns without which a row is not an expense at all.
REQUIRED_COLUMNS = ('id', 'expense_date', 'amount', 'description', 'category_id')


class IExpenseRecordRepository(ABC):
    """Port: find stored expenses and correct one."""

    @abstractmethod
    def search(self, criteria: ExpenseSearchCriteria) -> list[ExpenseRecord]:
        """Stored rows matching the criteria, newest first."""

    @abstractmethod
    def apply_edit(self, edit: ExpenseEdit) -> ExpenseEditResult:
        """Write one correction. Raises ExpenseNotFound for an unknown id."""


#: Escape character for LIKE patterns. Not backslash: under the
#: NO_BACKSLASH_ESCAPES sql_mode a backslash is not an escape at all, and this
#: has to behave the same either way.
LIKE_ESCAPE = '!'


def escape_like(text: str) -> str:
    """Neutralise LIKE's wildcards in a literal search term.

    `%` and `_` are pattern syntax, not text, so an unescaped search for "50%"
    became `%50%%` -- matching anything that merely starts with 50 -- and "a_b"
    matched "axb". Parameterising the value prevents injection but does nothing
    about this: the metacharacters are inside the bound string. The escape
    character itself has to be escaped first, or escaping would corrupt a
    merchant name that legitimately contains it.
    """
    out = text.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
    return out.replace('%', f'{LIKE_ESCAPE}%').replace('_', f'{LIKE_ESCAPE}_')


def _where_clauses(criteria: ExpenseSearchCriteria,
                   has_vendor_key: bool) -> tuple[list[str], list[Any]]:
    """Criteria -> (SQL fragments, bind params). Always parameterized.

    Split out as its own function so the query the search builds is testable
    without a database connection -- the part most likely to be got wrong is
    the part hardest to reach through a live cursor.
    """
    clauses: list[str] = []
    params: list[Any] = []
    if criteria.merchant:
        like = f'%{escape_like(criteria.merchant)}%'
        escape = f" ESCAPE '{LIKE_ESCAPE}'"
        if has_vendor_key:
            clauses.append(
                f'(description LIKE %s{escape} OR id_light LIKE %s{escape})')
            params += [like, like]
        else:
            clauses.append(f'description LIKE %s{escape}')
            params.append(like)
    if criteria.date_from:
        clauses.append('expense_date >= %s')
        params.append(criteria.date_from)
    if criteria.date_to:
        clauses.append('expense_date <= %s')
        params.append(criteria.date_to)
    if criteria.amount is not None:
        clauses.append('ABS(ABS(amount) - %s) < %s')
        params += [criteria.amount, AMOUNT_MATCH_TOLERANCE]
    return clauses, params


class MySqlExpenseRecordRepository(IExpenseRecordRepository):
    """The live `expenses` table.

    `connection_factory` is resolved per call (never cached) so a reconnect --
    or a test substituting a fake connection -- is honoured, matching how
    server.py's other repositories take `_rol_get_connection`.
    """

    def __init__(self, connection_factory: Callable[[], Any],
                 namer: ICategoryNamer,
                 schema_probe: Optional[IExpenseSchemaProbe] = None):
        self._connect = connection_factory
        self._namer = namer
        self._probe = schema_probe or InformationSchemaProbe()

    def _to_record(self, row: dict) -> ExpenseRecord:
        category_id = row.get('category_id')
        category_id = int(category_id) if category_id is not None else None
        return ExpenseRecord(
            id=int(row['id']),
            transaction_date=str(row['expense_date']),
            total_amount=abs(float(row['amount'])),
            description=(row.get('description') or '').strip(),
            id_light=(row.get('id_light') or '').strip(),
            category_id=category_id,
            category_name=self._namer.name_for(category_id),
        )

    def _select_clause(self, cur: Any) -> tuple[str, bool]:
        schema = self._probe.read(cur, OPTIONAL_COLUMNS)
        return (schema.select_clause(REQUIRED_COLUMNS, OPTIONAL_COLUMNS),
                schema.has('id_light'))

    def search(self, criteria: ExpenseSearchCriteria) -> list[ExpenseRecord]:
        with self._connect() as cnx:
            with cnx.cursor() as cur:
                select_sql, has_vendor_key = self._select_clause(cur)
                clauses, params = _where_clauses(criteria, has_vendor_key)
                cur.execute(
                    f'SELECT {select_sql} FROM expenses '
                    f'WHERE {" AND ".join(clauses)} '
                    'ORDER BY expense_date DESC, id DESC LIMIT %s',
                    tuple(params) + (criteria.limit,),
                )
                rows = cur.fetchall() or []
        return [self._to_record(row) for row in rows]

    def _read_one(self, cur: Any, expense_id: int) -> tuple[ExpenseRecord, bool]:
        """The row plus whether its stored amount is negative.

        ExpenseRecord carries the absolute amount -- that is what the operator
        types and what the form shows -- so the sign has to travel alongside
        it, or an edit would silently flip a credit into a debit.
        """
        select_sql, _ = self._select_clause(cur)
        cur.execute(f'SELECT {select_sql} FROM expenses WHERE id = %s',
                    (expense_id,))
        row = cur.fetchone()
        if not row:
            raise ExpenseNotFound(f'no expense with id {expense_id}')
        try:
            negative = float(row['amount']) < 0
        except (TypeError, ValueError, KeyError):
            negative = False
        return self._to_record(row), negative

    def apply_edit(self, edit: ExpenseEdit) -> ExpenseEditResult:
        with self._connect() as cnx:
            with cnx.cursor() as cur:
                before, was_negative = self._read_one(cur, edit.expense_id)
                changed = describe_changes(before, edit)
                if changed:
                    # Keep the row's original sign: an expense stored as
                    # -42.00 stays negative once its magnitude is corrected,
                    # so the report totals it exactly as it did before.
                    signed = -edit.total_amount if was_negative else edit.total_amount
                    cur.execute(
                        'UPDATE expenses SET description = %s, expense_date = %s, '
                        'amount = %s, category_id = %s WHERE id = %s',
                        (edit.merchant_name, edit.transaction_date, signed,
                         edit.category_id, edit.expense_id),
                    )
                    cnx.commit()
                after = ExpenseRecord(
                    id=before.id,
                    transaction_date=edit.transaction_date,
                    total_amount=edit.total_amount,
                    description=edit.merchant_name,
                    id_light=before.id_light,
                    category_id=edit.category_id,
                    category_name=self._namer.name_for(edit.category_id),
                )
        return ExpenseEditResult(
            record=after,
            changed_fields=changed,
            warnings=linkage_warnings(before, changed),
        )


def search_criteria_from_request(data: dict) -> ExpenseSearchCriteria:
    """Untrusted HTTP JSON -> criteria, coercing shape before strict Pydantic.

    ExpenseSearchCriteria is strict=True on purpose (a number arriving as a
    string is a client bug worth catching), so the coercion an HTTP body needs
    happens here, at the boundary, exactly as submit_manual_receipt_entry does
    for the insert path.
    """
    data = data or {}
    amount = as_optional_float(data.get('amount'), 'amount')
    limit = as_optional_int(data.get('limit') or None, 'limit')
    fields: dict[str, Any] = {
        'merchant': str(data.get('merchant') or ''),
        'date_from': _optional_text(data.get('date_from')),
        'date_to': _optional_text(data.get('date_to')),
        'amount': amount,
    }
    if limit is not None:
        fields['limit'] = limit
    return ExpenseSearchCriteria(**fields)


def _optional_text(value: Any) -> Optional[str]:
    text = str(value or '').strip()
    return text or None


def readable_validation_error(exc: Exception) -> str:
    """A Pydantic ValidationError as one sentence an operator can act on.

    ``str(ValidationError)`` is a multi-line dump ending in a docs URL. The
    messages these models raise ("enter a merchant, a date range, or an amount
    to search") are already written for a human, so surface those instead of
    the wrapper around them.
    """
    errors = getattr(exc, 'errors', None)
    if not callable(errors):
        return str(exc)
    messages = []
    for error in errors():
        message = str(error.get('msg') or '').strip()
        # Pydantic prefixes messages raised by a validator with "Value error, ".
        message = message.removeprefix('Value error, ')
        location = '.'.join(str(part) for part in error.get('loc') or ())
        if message:
            messages.append(f'{location}: {message}' if location else message)
    return '; '.join(messages) or str(exc)


def records_as_json(records: Sequence[ExpenseRecord]) -> list[dict]:
    """Records -> the snake_case JSON the browser's reader expects."""
    return [
        {
            'id': r.id,
            'transaction_date': r.transaction_date,
            'total_amount': r.total_amount,
            'description': r.description,
            'id_light': r.id_light,
            'category_name': r.category_name,
        }
        for r in records
    ]
