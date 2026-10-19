"""A stable optimistic-concurrency token over the stored edit record."""
import hashlib

from finance.expense_edit_model import ExpenseRecord


def record_version(record: ExpenseRecord) -> str:
    # Labels can change with a taxonomy refresh without altering this expense.
    return hashlib.sha256(record.model_dump_json(exclude={'category_name'}).encode()).hexdigest()
