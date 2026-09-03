"""Browser-facing serialization for stored expense records."""
from __future__ import annotations

from typing import Sequence

from finance.expense_edit_model import ExpenseRecord


def records_as_json(records: Sequence[ExpenseRecord]) -> list[dict]:
    """Records -> the snake_case JSON the browser's reader expects."""
    return [
        {
            'id': record.id,
            'transaction_date': record.transaction_date,
            'total_amount': record.total_amount,
            'description': record.description,
            'id_light': record.id_light,
            'category_name': record.category_name,
        }
        for record in records
    ]
