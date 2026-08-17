"""The three field rules every hand-entered expense obeys, in one place.

Non-empty merchant/description, ISO transaction date, positive amount --
originally written inside ``manual_entry.ManualReceiptEntry`` and then needed
verbatim by the Edit Expense path (``expense_edit_model.ExpenseEdit``).
Duplicating three validators across two models is exactly the "duplicated
behavior" smell, so both models now inherit them from here and there is one
definition of what a valid expense field looks like.

Deliberately *not* a full expense: this base says nothing about where the
document lives, which row is being edited, or which org owns it. Subclasses
add the fields their own boundary needs (see rule 4, keep agreements small).
"""

from __future__ import annotations

from datetime import date

from pydantic import field_validator

from contracts import StrictModel


class ExpenseFieldRules(StrictModel):
    """Merchant/date/amount with the validation the finance DB requires."""

    merchant_name: str
    transaction_date: str
    total_amount: float

    @field_validator('merchant_name')
    @classmethod
    def _merchant_non_empty(cls, value: str) -> str:
        cleaned = ' '.join(value.split())
        if not cleaned:
            raise ValueError('merchant_name is required')
        return cleaned

    @field_validator('transaction_date')
    @classmethod
    def _date_is_iso(cls, value: str) -> str:
        """Validate, and normalise to canonical yyyy-mm-dd.

        ``date.fromisoformat`` also accepts ISO *basic* format ("20260815"),
        which used to be stored verbatim. Two spellings of one day then compare
        unequal as strings, so describe_changes reported a date edit that
        changed nothing. Round-tripping through ``date`` gives one spelling.
        """
        return date.fromisoformat(value).isoformat()

    @field_validator('total_amount')
    @classmethod
    def _amount_is_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError('total_amount must be positive')
        return value
