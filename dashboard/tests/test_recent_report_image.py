from pathlib import Path

from finance.receipt_relocation import CanonicalReceiptDestinationPolicy
from finance.recent_report_image import RecentReportImageSynchronizer


def _service(tmp_path, rows, pointer, destination_policy=None):
    written = []
    updated = []
    service = RecentReportImageSynchronizer(
        read_pointer=lambda: pointer,
        write_pointer=lambda data: written.append(data) or True,
        fetch_rows=lambda ids: [row for row in rows if row['id'] in ids],
        update_references=lambda ids, path: updated.append((list(ids), path)),
        destination_policy=destination_policy,
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


def test_explicit_vendor_correction_replaces_wrong_receipt_identity(tmp_path):
    old = tmp_path / 'lasagna_parmesan_potato_04_19_25_58_35.jpg'
    old.write_bytes(b'image')
    pointer = {'intake': {'expense_ids': [2259], 'archive_paths': [str(old)]}}
    rows = [{'id': 2259, 'vendor_key': '', 'date': '2025-04-19',
             'amount': '58.35'}]
    service, _ = _service(tmp_path, rows, pointer)

    result = service.synchronize(
        2259, vendor_key='gordon_food_service_store',
        transaction_date='2025-04-19', replace_identity=True)

    assert Path(result['path']).name == (
        'gordon_food_service_store_04_19_25_58_35.jpg')


def test_explicit_date_correction_refiles_image_and_pointer_to_new_day(tmp_path):
    root = tmp_path / 'receipts'
    old = root / '2025' / 'august' / 'august_19' / 'at_t_08_19_25_80_24.jpg'
    old.parent.mkdir(parents=True)
    old.write_bytes(b'at&t')
    pointer = {'intake': {'expense_ids': [2547], 'archive_paths': [str(old)]}}
    rows = [{'id': 2547, 'vendor_key': 'at_t', 'date': '2025-08-25',
             'amount': '80.24'}]
    service, written = _service(
        tmp_path, rows, pointer,
        CanonicalReceiptDestinationPolicy(str(root)),
    )

    result = service.synchronize(
        2547, vendor_key='at_t', transaction_date='2025-08-25',
        replace_identity=True,
    )

    expected = root / '2025' / 'august' / 'august_25' / 'at_t_08_25_25_80_24.jpg'
    assert result == {'renamed': True, 'path': str(expected)}
    assert expected.read_bytes() == b'at&t'
    assert not old.exists()
    assert written[0]['intake']['archive_paths'] == [str(expected)]
    assert service.updated == [([2547], str(expected))]


def test_repository_moved_image_seeds_missing_archive_pointer(tmp_path):
    moved = tmp_path / 'receipts' / '2025' / 'august' / 'august_25' / (
        'at_t_08_25_25_80_24.jpg')
    moved.parent.mkdir(parents=True)
    moved.write_bytes(b'at&t')
    pointer = {'intake': {'expense_ids': [2547], 'archive_paths': []}}
    rows = [{'id': 2547, 'vendor_key': 'at_t', 'date': '2025-08-25',
             'amount': '80.24', 'source_file': str(moved)}]
    service, written = _service(
        tmp_path, rows, pointer,
        CanonicalReceiptDestinationPolicy(str(tmp_path / 'receipts')),
    )

    result = service.synchronize(
        2547, vendor_key='at_t', transaction_date='2025-08-25',
        replace_identity=True,
    )

    assert result == {'renamed': False, 'path': str(moved)}
    assert written[0]['intake']['archive_paths'] == [str(moved)]
    assert service.updated == [([2547], str(moved))]


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


def test_a_rename_that_already_happened_elsewhere_is_not_an_error(tmp_path):
    """The exact race this class now shares replace_file_if_clear with
    finance/receipt_relocation.py to avoid: MySqlExpenseRecordRepository's own
    receipt relocation can rename the file first (off the row's receipt_url),
    so by the time this pointer-cache sync runs, old_path is already gone and
    new_path already holds the (correctly renamed) file. That must read as
    success, not a missing-file fault."""
    already_renamed = tmp_path / 'meijer_07_14_25_31_25.jpg'
    already_renamed.write_bytes(b'image')
    stale_pointer_path = tmp_path / 'meijer_07_14_25_29_48.jpg'
    pointer = {'intake': {'expense_ids': [1, 2],
                          'archive_paths': [str(stale_pointer_path)]}}
    rows = [
        {'id': 1, 'vendor_key': 'meijer', 'date': '2025-07-14', 'amount': '-20.00'},
        {'id': 2, 'vendor_key': 'meijer', 'date': '2025-07-14', 'amount': '-11.25'},
    ]
    service, written = _service(tmp_path, rows, pointer)

    result = service.synchronize(1)

    assert result == {'renamed': True, 'path': str(already_renamed)}
    assert already_renamed.exists()
    assert written[0]['intake']['archive_paths'] == [str(already_renamed)]


def test_unrelated_expense_does_not_touch_the_image(tmp_path):
    old = tmp_path / 'meijer_07_14_25_29_48.jpg'
    old.write_bytes(b'image')
    pointer = {'intake': {'expense_ids': [1], 'archive_paths': [str(old)]}}
    service, written = _service(tmp_path, [], pointer)

    assert service.synchronize(99) == {'renamed': False}
    assert old.exists()
    assert written == []
