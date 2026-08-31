from finance.expense_edit_model import ExpenseRecord
from finance.expense_report_sync import StaticExpenseReportSynchronizer


def record(**changes):
    values = dict(id=985, transaction_date='2025-04-14', total_amount=310,
                  description='WOODMEADOW DENTISTRYGRAND RAPIDS        MI',
                  id_light='woodmeadow_04_14_25_310_00', category_id=243,
                  category_name='Rosemary Benefits & Medical')
    values.update(changes)
    return ExpenseRecord(**values)


def test_syncs_report_only_row_by_previous_identity(tmp_path):
    report = tmp_path / 'statement' / 'report.html'
    report.parent.mkdir()
    report.write_text(
        '<table id="verified-transactions"><tbody>'
        '<tr data-expense-id="" data-description="WOODMEADOW DENTISTRYGRAND RAPIDS        MI" '
        'data-signed-amount="-310.00" data-date="2025-04-14">'
        '<td>WOODMEADOW DENTISTRYGRAND RAPIDS        MI</td>'
        '<td class="number">-310.00</td><td>2025-04-14</td></tr>'
        '</tbody></table>', encoding='utf-8')

    count = StaticExpenseReportSynchronizer(tmp_path).synchronize(
        record(), record(total_amount=145,
                         id_light='woodmeadow_04_14_25_145_00'))

    html = report.read_text(encoding='utf-8')
    assert count == 1
    assert 'data-expense-id="985"' in html
    assert 'data-signed-amount="-145.00"' in html
    assert '<td class="number">-145.00</td>' in html
    assert '310.00' not in html


def test_does_not_change_the_other_same_vendor_transaction(tmp_path):
    report = tmp_path / 'report.html'
    december = (
        '<tr data-expense-id="" data-description="WOODMEADOW DENTISTRYGRAND RAPIDS        MI" '
        'data-signed-amount="-192.00" data-date="2025-12-04">'
        '<td>WOODMEADOW DENTISTRYGRAND RAPIDS        MI</td>'
        '<td class="number">-192.00</td><td>2025-12-04</td></tr>')
    report.write_text(december, encoding='utf-8')
    assert StaticExpenseReportSynchronizer(tmp_path).synchronize(
        record(), record(total_amount=145)) == 0
    assert report.read_text(encoding='utf-8') == december
