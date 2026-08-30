"""Synchronize stored expense edits into static finance report rows."""

from abc import ABC, abstractmethod
from html import escape
from pathlib import Path
import re

from finance.expense_edit_model import ExpenseRecord


class IExpenseReportSynchronizer(ABC):
    @abstractmethod
    def synchronize(self, before: ExpenseRecord, after: ExpenseRecord) -> int:
        """Return the number of report rows rewritten."""


class StaticExpenseReportSynchronizer(IExpenseReportSynchronizer):
    """Rewrite matching ``report.html`` rows without changing statement files."""

    _ROW = re.compile(r"<tr\b[^>]*data-date=\"[^\"]+\"[^>]*>.*?</tr>", re.DOTALL)

    def __init__(self, reports_root: str | Path):
        self._root = Path(reports_root)

    @staticmethod
    def _amount(value: float) -> str:
        return f"{abs(float(value)):.2f}"

    def _matches(self, row: str, before: ExpenseRecord) -> bool:
        expense_id = re.search(r'data-expense-id="([^"]*)"', row)
        if expense_id and expense_id.group(1) == str(before.id):
            return True
        date = re.search(r'data-date="([^"]*)"', row)
        amount = re.search(r'data-signed-amount="-?([^"]*)"', row)
        description = re.search(r'data-description="([^"]*)"', row)
        return bool(
            date and date.group(1) == before.transaction_date
            and amount and amount.group(1) == self._amount(before.total_amount)
            and description and description.group(1).strip() == before.description.strip()
        )

    def _rewrite(self, row: str, after: ExpenseRecord) -> str:
        amount = self._amount(after.total_amount)
        description = escape(after.description, quote=True)
        replacements = {
            'data-expense-id': str(after.id),
            'data-description': description,
            'data-signed-amount': f'-{amount}',
            'data-date': after.transaction_date,
        }
        for name, value in replacements.items():
            row = re.sub(fr'{name}="[^"]*"', f'{name}="{value}"', row, count=1)
        cells = re.findall(r'<td[^>]*>.*?</td>', row, re.DOTALL)
        if len(cells) >= 3:
            new_cells = [f'<td>{escape(after.description)}</td>',
                         f'<td class="number">-{amount}</td>',
                         f'<td>{after.transaction_date}</td>']
            for old, new in zip(cells[:3], new_cells):
                row = row.replace(old, new, 1)
        return row

    def synchronize(self, before: ExpenseRecord, after: ExpenseRecord) -> int:
        changed = 0
        for path in self._root.rglob('report.html'):
            original = path.read_text(encoding='utf-8')
            updated, count = self._ROW.subn(
                lambda match: self._rewrite(match.group(0), after)
                if self._matches(match.group(0), before) else match.group(0),
                original,
            )
            if count and updated != original:
                path.write_text(updated, encoding='utf-8')
                changed += sum(1 for old, new in zip(
                    self._ROW.findall(original), self._ROW.findall(updated)) if old != new)
        return changed
