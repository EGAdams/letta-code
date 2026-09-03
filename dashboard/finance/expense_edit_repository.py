"""Behaviour behind the Edit Expense boundary: ports first, MySQL second.

Two ports, each deliberately narrow:

* ``ICategoryNamer`` — the only thing this module needs to know about the
  category taxonomy is "id -> label" and "label -> id". server.py owns the real
  taxonomy (``_reporting_category_for_id`` / ``_resolve_reporting_category``);
  passing the whole taxonomy in here would be a fat agreement for two lookups.
* ``IExpenseRecordRepository`` — search stored rows, read one, correct one,
  remove one. Removal joined the port when the Verified Transactions table
  grew a Delete button: a row that was never an expense (a payment line, a
  misread) had no way off the page short of editing it into something
  harmless, which left a wrong row in the reports either way.

``MySqlExpenseRecordRepository`` is the one concrete implementation. It reads
through ``finance.expense_schema`` rather than naming optional columns
directly, because the live finance DB is not always as wide as this dashboard's
schema and a missing ``id_light`` must not fail the whole search.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from finance.expense_edit_model import (
    ExpenseDeletion,
    ExpenseEdit,
    ExpenseEditResult,
    ExpenseNotFound,
    ExpenseRecord,
    ExpenseSearchCriteria,
    describe_changes,
)
from finance.category_naming import ICategoryNamer
from finance.expense_receipt_sync import (
    ExpenseReceiptSynchronizer,
    IExpenseReceiptSynchronizer,
)
from finance.expense_record_serialization import records_as_json
from finance.expense_search import (
    escape_like,
    readable_validation_error,
    search_criteria_from_request,
    where_clauses,
)
from finance.expense_schema import InformationSchemaProbe, IExpenseSchemaProbe
from finance.receipt_relocation import IReceiptFileRelocator, NullReceiptFileRelocator

# Compatibility alias for older tests/callers; new code imports where_clauses.
_where_clauses = where_clauses

#: Columns the search reads only if the live table actually has them.
OPTIONAL_COLUMNS = ('id_light', 'receipt_url', 'document_url', 'source_file')
#: The itemization link, probed separately from the SELECT list because it is
#: never displayed -- a delete only needs to know whether this deployment can
#: have line items hanging off the row it is about to remove.
ITEMIZATION_COLUMN = 'parent_expense_id'
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

    @abstractmethod
    def read(self, expense_id: int) -> ExpenseRecord:
        """One stored row. Raises ExpenseNotFound for an unknown id."""

    @abstractmethod
    def delete(self, expense_id: int) -> ExpenseDeletion:
        """Remove one stored row (and its line items, where the deployment has
        them). Returns what was removed. Raises ExpenseNotFound."""


class MySqlExpenseRecordRepository(IExpenseRecordRepository):
    """The live `expenses` table.

    `connection_factory` is resolved per call (never cached) so a reconnect --
    or a test substituting a fake connection -- is honoured, matching how
    server.py's other repositories take `_rol_get_connection`.
    """

    def __init__(self, connection_factory: Callable[[], Any],
                 namer: ICategoryNamer,
                 schema_probe: Optional[IExpenseSchemaProbe] = None,
                 relocator: Optional[IReceiptFileRelocator] = None,
                 receipt_sync: Optional[IExpenseReceiptSynchronizer] = None):
        self._connect = connection_factory
        self._namer = namer
        self._probe = schema_probe or InformationSchemaProbe()
        self._receipt_sync = receipt_sync or ExpenseReceiptSynchronizer(
            relocator or NullReceiptFileRelocator())

    def _to_record(self, row: dict) -> ExpenseRecord:
        category_id = row.get('category_id')
        category_id = int(category_id) if category_id is not None else None
        return ExpenseRecord(
            id=int(row['id']),
            transaction_date=str(row['expense_date']),
            total_amount=abs(float(row['amount'])),
            description=(row.get('description') or '').strip(),
            id_light=(row.get('id_light') or '').strip(),
            receipt_url=(row.get('receipt_url') or '').strip(),
            document_url=(row.get('document_url') or '').strip(),
            source_file=(row.get('source_file') or '').strip(),
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
                clauses, params = where_clauses(criteria, has_vendor_key)
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
                references = self._receipt_sync.synchronize(before, edit, changed)
                if changed:
                    # Keep the row's original sign: an expense stored as
                    # -42.00 stays negative once its magnitude is corrected,
                    # so the report totals it exactly as it did before.
                    signed = -edit.total_amount if was_negative else edit.total_amount
                    schema = self._probe.read(cur, OPTIONAL_COLUMNS)
                    assignments = ['description = %s', 'expense_date = %s',
                                   'amount = %s', 'category_id = %s']
                    params = [edit.merchant_name, edit.transaction_date,
                              signed, edit.category_id]
                    for column, value in (
                        ('id_light', references.id_light),
                        ('receipt_url', references.receipt_url),
                        ('document_url', references.document_url),
                        ('source_file', references.source_file),
                    ):
                        if value and schema.has(column):
                            assignments.append(f'{column} = %s')
                            params.append(value)
                    params.append(edit.expense_id)
                    cur.execute(
                        f'UPDATE expenses SET {", ".join(assignments)} '
                        'WHERE id = %s',
                        tuple(params),
                    )
                    cnx.commit()
                after = ExpenseRecord(
                    id=before.id,
                    transaction_date=edit.transaction_date,
                    total_amount=edit.total_amount,
                    description=edit.merchant_name,
                    id_light=references.id_light or before.id_light,
                    receipt_url=references.receipt_url or before.receipt_url,
                    document_url=references.document_url or before.document_url,
                    source_file=references.source_file or before.source_file,
                    category_id=edit.category_id,
                    category_name=self._namer.name_for(edit.category_id),
                )
        return ExpenseEditResult(
            record=after,
            changed_fields=changed,
            warnings=references.warnings,
        )

    def read(self, expense_id: int) -> ExpenseRecord:
        with self._connect() as cnx:
            with cnx.cursor() as cur:
                record, _ = self._read_one(cur, expense_id)
        return record

    def _line_item_ids(self, cur: Any, expense_id: int) -> tuple[int, ...]:
        """The itemization rows filed under this expense, if this deployment
        has itemization at all.

        Probed rather than assumed for the same reason `id_light` is: a
        narrower finance DB has no `parent_expense_id`, and naming it in a
        DELETE would fail the whole statement on exactly the deployments that
        cannot have children to begin with.
        """
        schema = self._probe.read(cur, (ITEMIZATION_COLUMN,))
        if not schema.has(ITEMIZATION_COLUMN):
            return ()
        cur.execute(
            f'SELECT id FROM expenses WHERE {ITEMIZATION_COLUMN} = %s',
            (expense_id,))
        return tuple(int(row['id']) for row in (cur.fetchall() or []))

    def delete(self, expense_id: int) -> ExpenseDeletion:
        """Remove the row, and any line items filed under it, in one commit.

        Children go first and in the same transaction: half a delete leaves
        line items pointing at a parent that no longer exists, which reads as
        a data anomaly forever after and is invisible on every report that
        rolls children up into their parent.
        """
        with self._connect() as cnx:
            with cnx.cursor() as cur:
                record, _ = self._read_one(cur, expense_id)
                line_item_ids = self._line_item_ids(cur, expense_id)
                if line_item_ids:
                    placeholders = ','.join(['%s'] * len(line_item_ids))
                    cur.execute(
                        f'DELETE FROM expenses WHERE id IN ({placeholders})',
                        line_item_ids)
                cur.execute('DELETE FROM expenses WHERE id = %s', (expense_id,))
                cnx.commit()
        return ExpenseDeletion(record=record, line_item_ids=line_item_ids)
