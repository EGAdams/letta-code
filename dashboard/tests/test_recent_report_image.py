import json
from pathlib import Path

from finance.recent_report_image import RecentReportImageSynchronizer


def _service(tmp_path, rows, pointer):
    written = []
    updated = []
    service = RecentReportImageSynchronizer(
        read_pointer=lambda: pointer,
        write_pointer=lambda data: written.append(data) or True,
        fetch_rows=lambda ids: [row for row in rows if row['id'] in ids],
        update_references=lambda ids, new_path, old_path='': updated.append((list(ids), new_path, old_path)),
        archive_root=str(tmp_path),
    )
    service.updated = updated
    return service, written


def test_amount_change_renames_image_to_sum_of_document_rows(tmp_path):
    # Set up canonical directory structure
    july_dir = tmp_path / '2025' / 'july' / 'july_14'
    july_dir.mkdir(parents=True)
    old = july_dir / 'meijer_07_14_25_29_48.jpg'
    old.write_bytes(b'image')
    pointer = {'intake': {'expense_ids': [1, 2], 'archive_paths': [str(old)]}}
    rows = [
        {'id': 1, 'vendor_key': 'meijer', 'date': '2025-07-14', 'amount': '-20.00'},
        {'id': 2, 'vendor_key': 'meijer', 'date': '2025-07-14', 'amount': '-11.25'},
    ]
    service, written = _service(tmp_path, rows, pointer)

    result = service.synchronize(1)

    expected = july_dir / 'meijer_07_14_25_31_25.jpg'
    assert result == {'renamed': True, 'path': str(expected)}
    assert expected.read_bytes() == b'image'
    assert not old.exists()
    assert written[0]['intake']['archive_paths'] == [str(expected)]
    assert service.updated == [([1, 2], str(expected), str(old))]


def test_delete_recalculates_total_from_remaining_rows(tmp_path):
    july_dir = tmp_path / '2025' / 'july' / 'july_14'
    july_dir.mkdir(parents=True)
    old = july_dir / 'meijer_07_14_25_31_25.jpg'
    old.write_bytes(b'image')
    pointer = {'intake': {'expense_ids': [1, 2], 'archive_paths': [str(old)]}}
    rows = [
        {'id': 1, 'vendor_key': 'meijer', 'date': '2025-07-14', 'amount': '20.00'},
        {'id': 2, 'vendor_key': 'meijer', 'date': '2025-07-14', 'amount': '11.25'},
    ]
    service, _ = _service(tmp_path, rows, pointer)

    result = service.synchronize(2, deleted=True)

    assert Path(result['path']).name == 'meijer_07_14_25_20_00.jpg'


def test_row_vendor_and_date_used_for_canonical_name(tmp_path):
    """Row data (not parameters) determines the canonical filename."""
    july_dir = tmp_path / '2025' / 'july' / 'july_14'
    july_dir.mkdir(parents=True)
    old = july_dir / 'old_07_14_25_29_48.jpg'
    old.write_bytes(b'image')
    pointer = {'intake': {'expense_ids': [1], 'archive_paths': [str(old)]}}
    rows = [{'id': 1, 'vendor_key': 'old', 'date': '2025-07-14', 'amount': '29.48'}]
    service, _ = _service(tmp_path, rows, pointer)

    # Parameters are ignored when row data is present
    result = service.synchronize(
        1, vendor_key='meijer', transaction_date='2025-07-15')

    # Should use row vendor_key='old' and date='2025-07-14', not parameters
    assert Path(result['path']).name == 'old_07_14_25_29_48.jpg'


def test_vendor_correction_via_row_update(tmp_path):
    """When row vendor_key is updated, filename reflects the change."""
    april_dir = tmp_path / '2025' / 'april' / 'april_19'
    april_dir.mkdir(parents=True)
    old = april_dir / 'lasagna_parmesan_potato_04_19_25_58_35.jpg'
    old.write_bytes(b'image')
    pointer = {'intake': {'expense_ids': [2259], 'archive_paths': [str(old)]}}
    # Row now has corrected vendor_key
    rows = [{'id': 2259, 'vendor_key': 'gordon_food_service_store', 'date': '2025-04-19',
             'amount': '58.35'}]
    service, _ = _service(tmp_path, rows, pointer)

    result = service.synchronize(2259)

    assert Path(result['path']).name == (
        'gordon_food_service_store_04_19_25_58_35.jpg')


def test_adding_line_item_updates_only_aggregate_amount(tmp_path):
    """Adding a second line item updates total, vendor/date from row data."""
    jan_dir = tmp_path / '2025' / 'january' / 'january_16'
    jan_dir.mkdir(parents=True)
    old = jan_dir / 'meijer_01_16_25_2_99.jpg'
    old.write_bytes(b'image')
    pointer = {'intake': {'expense_ids': [1, 2], 'archive_paths': [str(old)]}}
    rows = [
        {'id': 1, 'vendor_key': 'meijer', 'date': '2025-01-16', 'amount': '2.99'},
        {'id': 2, 'vendor_key': 'meijer', 'date': '2025-01-16', 'amount': '2.99'},
    ]
    service, _ = _service(tmp_path, rows, pointer)

    # Parameters ignored when row data present
    result = service.synchronize(
        2, vendor_key='sprite', transaction_date='2025-01-17')

    # Uses row vendor_key='meijer' and date='2025-01-16', not parameters
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
    july_dir = tmp_path / '2025' / 'july' / 'july_14'
    july_dir.mkdir(parents=True)
    old = july_dir / 'meijer_07_14_25_29_48.jpg'
    old.write_bytes(b'image')
    pointer = {'intake': {'expense_ids': [1], 'archive_paths': [str(old)]}}
    service, written = _service(tmp_path, [], pointer)

    assert service.synchronize(99) == {'renamed': False}
    assert old.exists()
    assert written == []


def test_date_change_moves_image_to_canonical_month_directory(tmp_path):
    """When row date changes, image moves to new month/day directory."""
    july_dir = tmp_path / '2025' / 'july' / 'july_14'
    july_dir.mkdir(parents=True)
    old = july_dir / 'meijer_07_14_25_29_48.jpg'
    old.write_bytes(b'image')
    pointer = {'intake': {'expense_ids': [1], 'archive_paths': [str(old)]}}
    # Row has updated date
    rows = [{'id': 1, 'vendor_key': 'meijer', 'date': '2025-08-19', 'amount': '29.48'}]
    service, written = _service(tmp_path, rows, pointer)

    result = service.synchronize(1)

    aug_dir = tmp_path / '2025' / 'august' / 'august_19'
    expected = aug_dir / 'meijer_08_19_25_29_48.jpg'
    assert result['renamed']
    assert result['path'] == str(expected)
    assert expected.read_bytes() == b'image'
    assert not old.exists()
    assert service.updated == [([1], str(expected), str(old))]


def test_collision_fails_closed_without_overwrite(tmp_path):
    """Collision with existing file fails without overwriting."""
    july_dir = tmp_path / '2025' / 'july' / 'july_14'
    july_dir.mkdir(parents=True)
    old = july_dir / 'meijer_07_14_25_29_48.jpg'
    old.write_bytes(b'old_image')
    existing = july_dir / 'meijer_07_14_25_31_25.jpg'
    existing.write_bytes(b'existing_image')
    pointer = {'intake': {'expense_ids': [1], 'archive_paths': [str(old)]}}
    rows = [{'id': 1, 'vendor_key': 'meijer', 'date': '2025-07-14', 'amount': '31.25'}]
    service, _ = _service(tmp_path, rows, pointer)

    result = service.synchronize(1)

    assert not result['renamed']
    assert 'already exists' in result['warning']
    assert old.read_bytes() == b'old_image'
    assert existing.read_bytes() == b'existing_image'


def test_rollback_on_reference_update_failure(tmp_path):
    """If update_references fails, file move is rolled back."""
    july_dir = tmp_path / '2025' / 'july' / 'july_14'
    july_dir.mkdir(parents=True)
    old = july_dir / 'meijer_07_14_25_29_48.jpg'
    old.write_bytes(b'image')
    pointer = {'intake': {'expense_ids': [1], 'archive_paths': [str(old)]}}
    rows = [{'id': 1, 'vendor_key': 'meijer', 'date': '2025-07-14', 'amount': '31.25'}]

    def failing_update(ids, new_path, old_path=''):
        raise RuntimeError('Database update failed')

    service = RecentReportImageSynchronizer(
        read_pointer=lambda: pointer,
        write_pointer=lambda data: True,
        fetch_rows=lambda ids: [row for row in rows if row['id'] in ids],
        update_references=failing_update,
        archive_root=str(tmp_path),
    )

    result = service.synchronize(1)

    assert not result['renamed']
    assert 'Failed to update references' in result['warning']
    assert old.read_bytes() == b'image'
    # New file should not exist after rollback
    new_path = july_dir / 'meijer_07_14_25_31_25.jpg'
    assert not new_path.exists()


def test_update_references_receives_old_path(tmp_path):
    """Verify update_references gets both new and old paths."""
    july_dir = tmp_path / '2025' / 'july' / 'july_14'
    july_dir.mkdir(parents=True)
    old = july_dir / 'meijer_07_14_25_29_48.jpg'
    old.write_bytes(b'image')
    pointer = {'intake': {'expense_ids': [1, 2], 'archive_paths': [str(old)]}}
    rows = [
        {'id': 1, 'vendor_key': 'meijer', 'date': '2025-07-14', 'amount': '20.00'},
        {'id': 2, 'vendor_key': 'meijer', 'date': '2025-07-14', 'amount': '11.25'},
    ]
    service, _ = _service(tmp_path, rows, pointer)

    service.synchronize(1)

    # Verify update_references was called with (ids, new_path, old_path)
    assert len(service.updated) == 1
    ids, new_path, old_path = service.updated[0]
    assert ids == [1, 2]
    assert old_path == str(old)
    assert new_path != old_path
    assert Path(new_path).name == 'meijer_07_14_25_31_25.jpg'


def test_edit_vendor_key_updates_filename(tmp_path):
    """Edit changing vendor_key updates filename and moves to canonical path."""
    aug_dir = tmp_path / '2025' / 'august' / 'august_19'
    aug_dir.mkdir(parents=True)
    old = aug_dir / 'meijer_08_19_25_19_08.jpg'
    old.write_bytes(b'receipt_image')
    pointer = {'intake': {'expense_ids': [2277], 'archive_paths': [str(old)]}}
    # Row has updated vendor_key after edit
    rows = [{'id': 2277, 'vendor_key': 'kroger', 'date': '2025-08-19', 'amount': '20.22'}]
    service, written = _service(tmp_path, rows, pointer)

    result = service.synchronize(2277)

    expected = aug_dir / 'kroger_08_19_25_20_22.jpg'
    assert result['renamed']
    assert result['path'] == str(expected)
    assert expected.read_bytes() == b'receipt_image'
    assert not old.exists()
    assert service.updated == [([2277], str(expected), str(old))]


def test_edit_date_updates_filename_and_directory(tmp_path):
    """Edit changing date updates filename and moves to new month directory."""
    aug_dir = tmp_path / '2025' / 'august' / 'august_19'
    aug_dir.mkdir(parents=True)
    old = aug_dir / 'meijer_08_19_25_19_08.jpg'
    old.write_bytes(b'receipt_image')
    pointer = {'intake': {'expense_ids': [2277], 'archive_paths': [str(old)]}}
    # Row has updated date after edit
    rows = [{'id': 2277, 'vendor_key': 'meijer', 'date': '2025-09-01', 'amount': '19.08'}]
    service, written = _service(tmp_path, rows, pointer)

    result = service.synchronize(2277)

    sep_dir = tmp_path / '2025' / 'september' / 'september_01'
    expected = sep_dir / 'meijer_09_01_25_19_08.jpg'
    assert result['renamed']
    assert result['path'] == str(expected)
    assert expected.read_bytes() == b'receipt_image'
    assert not old.exists()
    assert service.updated == [([2277], str(expected), str(old))]


def test_edit_amount_updates_filename_only(tmp_path):
    """Edit changing amount updates filename in same directory."""
    aug_dir = tmp_path / '2025' / 'august' / 'august_19'
    aug_dir.mkdir(parents=True)
    old = aug_dir / 'meijer_08_19_25_19_08.jpg'
    old.write_bytes(b'receipt_image')
    pointer = {'intake': {'expense_ids': [2277], 'archive_paths': [str(old)]}}
    # Row has updated amount after edit
    rows = [{'id': 2277, 'vendor_key': 'meijer', 'date': '2025-08-19', 'amount': '20.22'}]
    service, written = _service(tmp_path, rows, pointer)

    result = service.synchronize(2277)

    expected = aug_dir / 'meijer_08_19_25_20_22.jpg'
    assert result['renamed']
    assert result['path'] == str(expected)
    assert expected.read_bytes() == b'receipt_image'
    assert not old.exists()
    assert service.updated == [([2277], str(expected), str(old))]


def test_add_tax_updates_amount_in_filename(tmp_path):
    """Add 6% handler updates amount, keeping vendor and date unchanged."""
    aug_dir = tmp_path / '2025' / 'august' / 'august_19'
    aug_dir.mkdir(parents=True)
    old = aug_dir / 'meijer_08_19_25_19_08.jpg'
    old.write_bytes(b'receipt_image')
    pointer = {'intake': {'expense_ids': [2277], 'archive_paths': [str(old)]}}
    # Row amount increased by 6% (19.08 -> 20.22)
    rows = [{'id': 2277, 'vendor_key': 'meijer', 'date': '2025-08-19', 'amount': '20.22'}]
    service, written = _service(tmp_path, rows, pointer)

    result = service.synchronize(2277)

    expected = aug_dir / 'meijer_08_19_25_20_22.jpg'
    assert result['renamed']
    assert result['path'] == str(expected)
    assert expected.read_bytes() == b'receipt_image'
    assert not old.exists()
    # Verify vendor/date unchanged, only amount updated
    assert 'meijer' in str(expected)
    assert '08_19_25' in str(expected)


def test_edit_all_three_updates_filename_and_directory(tmp_path):
    """Edit changing vendor, date, and amount updates everything."""
    aug_dir = tmp_path / '2025' / 'august' / 'august_19'
    aug_dir.mkdir(parents=True)
    old = aug_dir / 'meijer_08_19_25_19_08.jpg'
    old.write_bytes(b'receipt_image')
    pointer = {'intake': {'expense_ids': [2277], 'archive_paths': [str(old)]}}
    # All fields changed
    rows = [{'id': 2277, 'vendor_key': 'kroger', 'date': '2025-09-01', 'amount': '25.50'}]
    service, written = _service(tmp_path, rows, pointer)

    result = service.synchronize(2277)

    sep_dir = tmp_path / '2025' / 'september' / 'september_01'
    expected = sep_dir / 'kroger_09_01_25_25_50.jpg'
    assert result['renamed']
    assert result['path'] == str(expected)
    assert expected.read_bytes() == b'receipt_image'
    assert not old.exists()
    assert service.updated == [([2277], str(expected), str(old))]
