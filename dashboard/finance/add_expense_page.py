"""The Add Expense page: GET /add_expense.html.

Not tied to any document, scan, or intake record -- it is the Recent Report
dialog's shell and mounted widgets reused as-is (see intake_report_page.py),
minus the scan-only controls the manual entry form hides in add_expense_mode
(Image Path, Show Image..Mazda Automatic, File As, Will Be Filed As). The
Verified Transactions table starts empty; js/implementation/manual-entry-
form.js appends each newly-saved row live, so nothing here needs to be
recomputed after a save.
"""

from __future__ import annotations

from .intake_report_page import (
    manual_entry_form_html,
    render_intake_report,
    transactions_table_html,
)


def build_add_expense_html() -> str:
    return render_intake_report(
        window_title='Add Expense',
        headline='Add Expense',
        subtitle='',
        meta_fields=[],
        status_text='Enter an expense below. There is no scanned document on this page.',
        status_tone='ok',
        table_html=transactions_table_html(
            [], empty_note='Expenses saved here will appear in this table.'),
        manual_entry_html=manual_entry_form_html(
            image_path='', conversation_id='', add_expense_mode=True),
    )
