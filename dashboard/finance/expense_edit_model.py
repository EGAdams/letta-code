"""Data shapes for the Recent Report page's "Edit Expense" button.

Save All only ever inserts. Once a row is stored there was no way to correct a
typo'd merchant, date, or amount from the dashboard -- the Set Category dialog
could change only the category. This module describes the search-then-edit
boundary: what an operator may search by, what one stored row looks like on the
way back, and what one correction looks like on the way in.

Pydantic describes the data; the behaviour lives behind the ABC ports in
``expense_edit_repository``. Nothing here touches a database or an HTTP
request, so every rule below is unit-testable without either.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import field_validator, model_validator

from contracts import StrictModel
from finance.expense_fields import ExpenseFieldRules

#: Never let a mistyped search sweep the whole expenses table into a response.
MAX_SEARCH_RESULTS = 100
DEFAULT_SEARCH_RESULTS = 25

#: Two amounts are "the same money" within half a cent -- the same tolerance
#: server.py's _resolve_duplicate_expense_ids uses to match a stored row.
AMOUNT_MATCH_TOLERANCE = 0.005


def _iso_or_none(value: Optional[str]) -> Optional[str]:
    text = (value or '').strip()
    if not text:
        return None
    date.fromisoformat(text)
    return text


class ExpenseSearchCriteria(StrictModel):
    """What the operator typed into the Edit Expense search row.

    Every field is optional on its own, but a search with *no* criterion is
    rejected rather than silently answered with "the newest 25 rows" -- an
    empty search is a mistake, not a request for everything.
    """

    merchant: str = ''
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    amount: Optional[float] = None
    limit: int = DEFAULT_SEARCH_RESULTS

    @field_validator('merchant')
    @classmethod
    def _trim_merchant(cls, value: str) -> str:
        return ' '.join(value.split())

    @field_validator('date_from', 'date_to')
    @classmethod
    def _dates_are_iso(cls, value: Optional[str]) -> Optional[str]:
        return _iso_or_none(value)

    @field_validator('amount')
    @classmethod
    def _amount_is_positive(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and value <= 0:
            raise ValueError('amount must be positive')
        return value

    @field_validator('limit')
    @classmethod
    def _limit_in_range(cls, value: int) -> int:
        return max(1, min(int(value), MAX_SEARCH_RESULTS))

    @model_validator(mode='after')
    def _at_least_one_criterion(self) -> 'ExpenseSearchCriteria':
        if not (self.merchant or self.date_from or self.date_to
                or self.amount is not None):
            raise ValueError(
                'enter a merchant, a date range, or an amount to search')
        if (self.date_from and self.date_to
                and self.date_from > self.date_to):
            raise ValueError('date_from must not be after date_to')
        return self


class ExpenseRecord(StrictModel):
    """One stored `expenses` row, as the edit dialog displays it.

    `category_name` is the *reporting* category label the Set Category dialog
    uses, resolved through the taxonomy rather than read from the row, so the
    dialog's category dropdown and this field speak the same vocabulary.
    """

    id: int
    transaction_date: str
    total_amount: float
    description: str = ''
    #: Transaction filing key from `expenses.id_light`. Not a reusable vendor
    #: key: it normally embeds the date and amount too, which is exactly why
    #: an amount/date edit has to recompute it (see receipt_relocation.py).
    id_light: str = ''
    #: Basename of the receipt image on disk, if this row owns one. Needed
    #: here (not just resolved ad hoc from server.py) so an edit can hand it
    #: to the relocator that renames the file to match a corrected date/amount.
    receipt_url: str = ''
    #: Usually a different document (a statement page, not the item receipt),
    #: but occasionally the same file as receipt_url for a single-image
    #: manual entry -- see relocate_receipt_for_edit's basename check.
    document_url: str = ''
    #: Absolute provenance path when the receipt image itself produced the row.
    source_file: str = ''
    category_id: Optional[int] = None
    category_name: str = ''


class ExpenseEdit(ExpenseFieldRules):
    """One correction to one stored row.

    Inherits the merchant/date/amount rules from ExpenseFieldRules, so an edit
    can never write a value a fresh manual entry would have been refused.
    """

    expense_id: int
    category_id: Optional[int] = None

    @field_validator('expense_id')
    @classmethod
    def _expense_id_is_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError('expense_id must be a positive row id')
        return value


class ExpenseEditResult(StrictModel):
    """What changed, plus anything the operator should know about it.

    `warnings` exists because an expense's `id_light` slug encodes the vendor,
    date, and amount that were true when the row was stored, and it is what
    links the row back to its receipt file on disk (see server.py's
    _resolve_expense_receipt_path). A date/amount edit makes the repository
    try to rename the file and rewrite id_light/receipt_url to match (see
    finance/receipt_relocation.py); `warnings` carries only the cases that
    relocation could not fix on its own -- no receipt file on record at all,
    the file missing from disk, or a naming collision -- so a silent mismatch
    never happens without the operator being told.
    """

    record: ExpenseRecord
    changed_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class ExpenseDeletion(StrictModel):
    """What a Delete removed, so the browser can say so and re-sync itself.

    The record is the row as it stood a moment before, not a bare id: the
    confirmation names the merchant ("Deleted Kroger"), and the Verified
    Transactions table has to drop the same row from the Prev/Next list the
    review dialog is walking. `line_item_ids` is normally empty -- it is only
    non-empty on a deployment with itemization, where deleting a parent takes
    its line items with it and the operator deserves to be told how many.
    """

    record: ExpenseRecord
    line_item_ids: tuple[int, ...] = ()


class ExpenseNotFound(LookupError):
    """No `expenses` row carries the id an edit named."""


def amount_changed(before: float, after: float) -> bool:
    """Whether two amounts differ by more than the half-cent tolerance."""
    return abs(abs(before) - abs(after)) >= AMOUNT_MATCH_TOLERANCE


def describe_changes(before: ExpenseRecord, edit: ExpenseEdit) -> tuple[str, ...]:
    """Which fields an edit actually alters, for the response and the log.

    Comparing before/after here (rather than blindly reporting every column in
    the UPDATE) is what lets the caller tell a real correction from a re-save
    of unchanged values.
    """
    changed = []
    if before.description != edit.merchant_name:
        changed.append('description')
    if before.transaction_date != edit.transaction_date:
        changed.append('expense_date')
    if amount_changed(before.total_amount, edit.total_amount):
        changed.append('amount')
    if before.category_id != edit.category_id:
        changed.append('category_id')
    return tuple(changed)


def linkage_warnings(before: ExpenseRecord,
                     changed_fields: tuple[str, ...]) -> tuple[str, ...]:
    """Warn when a date/amount edit drifts id_light and there is no receipt
    file on record for the repository to rename instead.

    Only the "nothing to rename" case: a row with a receipt_url takes the
    relocate-and-rewrite path in MySqlExpenseRecordRepository.apply_edit and
    reports its own outcome (success is silent; a real relocation failure --
    missing file, naming collision -- gets its own specific warning there).
    """
    if not before.id_light or before.receipt_url:
        return ()
    drifted = [f for f in ('expense_date', 'amount') if f in changed_fields]
    if not drifted:
        return ()
    return (
        f'This row\'s filing key ({before.id_light}) still encodes the old '
        f'{" and ".join(drifted)}. It has no receipt file on record to '
        'rename, so "View Receipt" may no longer match this row.',
    )
