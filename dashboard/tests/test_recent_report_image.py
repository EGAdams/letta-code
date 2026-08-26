from pathlib import Path

from finance.recent_report_image import RecentReportImageSynchronizer


def _service(tmp_path, rows, pointer):
    written = []
    updated = []
    service = RecentReportImageSynchronizer(
        read_pointer=lambda: pointer,
        write_pointer=lambda data: written.append(data) or True,
        fetch_rows=lambda ids: [row for row in rows if row['id'] in ids],
        update_references=lambda ids, path: updated.append((list(ids), path)),
    )
    service.updated = updated
    return service, written


def test_amount_change_renames_image_to_sum_of_document_rows(tmp_path):
    old = tmp_path / 'meijer_07_14_25_29_48.jpg'
    old.write_bytes(b'image')
    pointer = {'intake': {'expense_ids': [1, 2], 'archive_paths': [str(old)]}}
    rows = [
        {'id': 1, 'vendor_key': 'meijer', 'date': '2025-07-14', 'amount': '-20.00'},
        {'id': 2, 'vendor_key': 'meijer', 'date': '2025-07-14', 'amount': '-11.25'},
    ]
    service, written = _service(tmp_path, rows, pointer)

    result = service.synchronize(1)

    expected = tmp_path / 'meijer_07_14_25_31_25.jpg'
    assert result == {'renamed': True, 'path': str(expected)}
    assert expected.read_bytes() == b'image'
    assert not old.exists()
    assert written[0]['intake']['archive_paths'] == [str(expected)]
    assert service.updated == [([1, 2], str(expected))]


def test_delete_recalculates_total_from_remaining_rows(tmp_path):
    old = tmp_path / 'meijer_07_14_25_31_25.jpg'
    old.write_bytes(b'image')
    pointer = {'intake': {'expense_ids': [1, 2], 'archive_paths': [str(old)]}}
    rows = [
        {'id': 1, 'vendor_key': 'meijer', 'date': '2025-07-14', 'amount': '20.00'},
        {'id': 2, 'vendor_key': 'meijer', 'date': '2025-07-14', 'amount': '11.25'},
    ]
    service, _ = _service(tmp_path, rows, pointer)

    result = service.synchronize(2, deleted=True)

    assert Path(result['path']).name == 'meijer_07_14_25_20_00.jpg'


def test_line_item_vendor_and_date_cannot_replace_receipt_identity(tmp_path):
    old = tmp_path / 'old_07_14_25_29_48.jpg'
    old.write_bytes(b'image')
    pointer = {'intake': {'expense_ids': [1], 'archive_paths': [str(old)]}}
    rows = [{'id': 1, 'vendor_key': 'old', 'date': '2025-07-14', 'amount': '29.48'}]
    service, _ = _service(tmp_path, rows, pointer)

    result = service.synchronize(
        1, vendor_key='meijer', transaction_date='2025-07-15')

    assert Path(result['path']).name == 'old_07_14_25_29_48.jpg'


def test_adding_sprite_to_meijer_changes_only_aggregate_amount(tmp_path):
    old = tmp_path / 'meijer_01_16_25_2_99.jpg'
    old.write_bytes(b'image')
    pointer = {'intake': {'expense_ids': [1, 2], 'archive_paths': [str(old)]}}
    rows = [
        {'id': 1, 'vendor_key': '', 'date': '2025-01-16', 'amount': '2.99'},
        {'id': 2, 'vendor_key': '', 'date': '2025-01-16', 'amount': '2.99'},
    ]
    service, _ = _service(tmp_path, rows, pointer)

    result = service.synchronize(
        2, vendor_key='sprite', transaction_date='2025-01-17')

    assert Path(result['path']).name == 'meijer_01_16_25_5_98.jpg'


def test_unrelated_expense_does_not_touch_the_image(tmp_path):
    old = tmp_path / 'meijer_07_14_25_29_48.jpg'
    old.write_bytes(b'image')
    pointer = {'intake': {'expense_ids': [1], 'archive_paths': [str(old)]}}
    service, written = _service(tmp_path, [], pointer)

    assert service.synchronize(99) == {'renamed': False}
    assert old.exists()
    assert written == []
