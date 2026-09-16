from finance.add_expense_page import build_add_expense_html


def test_page_names_itself_add_expense_not_recent_report():
    html = build_add_expense_html()
    assert '<title>Add Expense</title>' in html
    assert '<div class="title-bar-text">Add Expense</div>' in html
    assert 'Recent Report' not in html


def test_manual_entry_mount_point_is_in_add_expense_mode():
    html = build_add_expense_html()
    assert 'data-add-expense-mode="true"' in html
    assert 'id="manual-entry-root"' in html


def test_verified_transactions_table_starts_empty_with_its_own_note():
    html = build_add_expense_html()
    assert 'id="verified-transactions"' in html
    assert 'Expenses saved here will appear in this table.' in html


def test_omits_scan_only_document_metadata():
    html = build_add_expense_html()
    # No archive-evidence line, no working panel, no scanner key stamped.
    assert 'Archived Scan Image' not in html
    assert 'data-scanner-key=""' in html
