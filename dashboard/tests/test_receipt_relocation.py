"""Tests for finance/receipt_relocation.py's real filesystem implementation.

Uses tmp_path for real file I/O -- the one thing worth exercising for real
here is os.replace()'s actual behaviour (missing source, existing target),
not something a fake filesystem could silently get wrong.
"""
import os

from finance.receipt_relocation import (
    CanonicalReceiptDestinationPolicy,
    FilesystemReceiptFileRelocator,
    NullReceiptFileRelocator,
    replace_file_if_clear,
)


def _relocator(tmp_path):
    def resolve(receipt_url):
        candidate = tmp_path / receipt_url
        return str(candidate) if candidate.is_file() else None
    return FilesystemReceiptFileRelocator(resolve_path=resolve)


def test_renames_the_file_and_reports_the_new_basename(tmp_path):
    (tmp_path / 'kroger_08_15_26_12_34.jpg').write_bytes(b'x')
    result = _relocator(tmp_path).relocate(
        receipt_url='kroger_08_15_26_12_34.jpg',
        old_id_light='kroger_08_15_26_12_34',
        new_id_light='kroger_08_15_26_99_99')
    assert result.relocated
    assert result.new_receipt_url == 'kroger_08_15_26_99_99.jpg'
    assert not (tmp_path / 'kroger_08_15_26_12_34.jpg').exists()
    assert (tmp_path / 'kroger_08_15_26_99_99.jpg').exists()


def test_date_edit_refiles_receipt_into_the_canonical_day_folder(tmp_path):
    root = tmp_path / 'receipts'
    old = root / '2025' / 'august' / 'august_19' / 'at_t_08_19_25_80_24.jpg'
    old.parent.mkdir(parents=True)
    old.write_bytes(b'at&t')
    relocator = FilesystemReceiptFileRelocator(
        resolve_path=lambda _url: str(old),
        destination_policy=CanonicalReceiptDestinationPolicy(str(root)),
    )

    result = relocator.relocate(
        receipt_url=old.name,
        old_id_light='at_t_08_19_25_80_24',
        new_id_light='at_t_08_25_25_80_24',
    )

    expected = root / '2025' / 'august' / 'august_25' / 'at_t_08_25_25_80_24.jpg'
    assert result.relocated
    assert result.new_receipt_url == expected.name
    assert result.new_path == str(expected)
    assert expected.read_bytes() == b'at&t'
    assert not old.exists()


def test_same_id_light_is_a_silent_no_op(tmp_path):
    (tmp_path / 'kroger_08_15_26_12_34.jpg').write_bytes(b'x')
    result = _relocator(tmp_path).relocate(
        receipt_url='kroger_08_15_26_12_34.jpg',
        old_id_light='kroger_08_15_26_12_34',
        new_id_light='kroger_08_15_26_12_34')
    assert result == type(result)()


def test_missing_source_file_warns_instead_of_raising(tmp_path):
    result = _relocator(tmp_path).relocate(
        receipt_url='kroger_08_15_26_12_34.jpg',
        old_id_light='kroger_08_15_26_12_34',
        new_id_light='kroger_08_15_26_99_99')
    assert not result.relocated
    assert 'could not be found on disk' in result.warning


def test_existing_target_is_left_alone_and_warns(tmp_path):
    (tmp_path / 'kroger_08_15_26_12_34.jpg').write_bytes(b'old')
    (tmp_path / 'kroger_08_15_26_99_99.jpg').write_bytes(b'already here')
    result = _relocator(tmp_path).relocate(
        receipt_url='kroger_08_15_26_12_34.jpg',
        old_id_light='kroger_08_15_26_12_34',
        new_id_light='kroger_08_15_26_99_99')
    assert not result.relocated
    assert 'already exists' in result.warning
    assert (tmp_path / 'kroger_08_15_26_12_34.jpg').read_bytes() == b'old'


def test_replace_failure_is_reported_not_raised(tmp_path):
    (tmp_path / 'kroger_08_15_26_12_34.jpg').write_bytes(b'x')

    def _boom(_old, _new):
        raise OSError('disk is full')

    relocator = FilesystemReceiptFileRelocator(
        resolve_path=lambda url: str(tmp_path / url), replace=_boom)
    result = relocator.relocate(
        receipt_url='kroger_08_15_26_12_34.jpg',
        old_id_light='kroger_08_15_26_12_34',
        new_id_light='kroger_08_15_26_99_99')
    assert not result.relocated
    assert 'disk is full' in result.warning


def test_null_relocator_never_touches_a_file():
    result = NullReceiptFileRelocator().relocate(
        receipt_url='anything.jpg', old_id_light='a_01_01_26_1_00',
        new_id_light='a_01_01_26_2_00')
    assert result == type(result)()


# --------------------------------------------------------------------------
# replace_file_if_clear: the primitive both rename paths in this codebase
# share, so a fix to how a collision/vanished-source is handled applies to
# FilesystemReceiptFileRelocator and RecentReportImageSynchronizer alike.
# --------------------------------------------------------------------------

def test_replace_file_if_clear_moves_a_real_file(tmp_path):
    old = tmp_path / 'old.jpg'
    old.write_bytes(b'x')
    new = tmp_path / 'new.jpg'
    outcome = replace_file_if_clear(str(old), str(new))
    assert outcome.moved
    assert not old.exists() and new.exists()


def test_replace_file_if_clear_refuses_to_clobber_an_existing_target(tmp_path):
    old = tmp_path / 'old.jpg'
    old.write_bytes(b'old')
    new = tmp_path / 'new.jpg'
    new.write_bytes(b'already here')
    outcome = replace_file_if_clear(str(old), str(new))
    assert not outcome.moved
    assert outcome.reason == 'target_exists'
    assert old.read_bytes() == b'old' and new.read_bytes() == b'already here'


def test_replace_file_if_clear_treats_a_prior_identical_move_as_success(tmp_path):
    """If the source is already gone AND the target already exists, some
    other caller already made this exact move -- not a fault to report."""
    new = tmp_path / 'new.jpg'
    new.write_bytes(b'already moved here')
    outcome = replace_file_if_clear(str(tmp_path / 'old.jpg'), str(new))
    assert outcome.moved
    assert outcome.reason == 'missing_source'


def test_replace_file_if_clear_reports_a_genuinely_vanished_source(tmp_path):
    outcome = replace_file_if_clear(
        str(tmp_path / 'old.jpg'), str(tmp_path / 'new.jpg'))
    assert not outcome.moved
    assert outcome.reason == 'missing_source'


def test_replace_file_if_clear_reports_the_os_error_without_raising(tmp_path):
    old = tmp_path / 'old.jpg'
    old.write_bytes(b'x')

    def _boom(_old, _new):
        raise OSError('disk is full')

    outcome = replace_file_if_clear(str(old), str(tmp_path / 'new.jpg'), replace=_boom)
    assert not outcome.moved
    assert outcome.reason == 'error'
    assert 'disk is full' in outcome.detail
