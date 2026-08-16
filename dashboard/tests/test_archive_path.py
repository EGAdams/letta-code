"""Tests for finance/archive_path.py -- pure archive-destination naming.

Every expected value here is taken directly from parse_and_categorize.py's
real slugify()/_build_id_light()/move_receipt_to_month_day_dir() behavior
(confirmed against a real production save: kroger_08_15_26_12_34.jpg filed
under readable_documents/receipts/2026/august/august_15/), so a preview here
can never silently drift from where the file actually lands.
"""
from finance import archive_path


def test_slugify_matches_receipt_tool_exactly():
    assert archive_path.slugify_like_receipt_tool('Kroger') == 'kroger'
    assert archive_path.slugify_like_receipt_tool('7-Eleven / Speedway') == '7_eleven_speedway'
    assert archive_path.slugify_like_receipt_tool('  Extra   Spaces  ') == 'extra_spaces'
    assert archive_path.slugify_like_receipt_tool('') == ''


def test_build_id_light_matches_real_production_example():
    """kroger, 2026-08-15, 12.34 -> kroger_08_15_26_12_34 -- the exact
    id_light of expense id 2158 in the live database."""
    assert archive_path.build_id_light('Kroger', '2026-08-15', 12.34) == 'kroger_08_15_26_12_34'


def test_build_id_light_formats_amount_with_two_decimals():
    assert archive_path.build_id_light('Kroger', '2026-08-15', 5) == 'kroger_08_15_26_5_00'
    assert archive_path.build_id_light('Kroger', '2026-08-15', 5.1) == 'kroger_08_15_26_5_10'


def test_build_id_light_falls_back_to_receipt_for_an_unslugifiable_merchant():
    assert archive_path.build_id_light('***', '2026-08-15', 1.0) == 'receipt_08_15_26_1_00'


def test_preview_archive_path_matches_real_production_example():
    result = archive_path.preview_archive_path(
        '/staged/scan.jpg', 'Kroger', '2026-08-15', 12.34, archive_kind='receipt')
    assert result['path'] == (
        archive_path.ARCHIVE_ROOTS['receipt']
        + '/2026/august/august_15/kroger_08_15_26_12_34.jpg')
    assert result['is_real_destination'] is True


def test_preview_archive_path_uses_the_image_path_extension():
    result = archive_path.preview_archive_path(
        '/staged/scan.png', 'Kroger', '2026-08-15', 12.34)
    assert result['path'].endswith('.png')


def test_preview_archive_path_defaults_extension_when_image_path_has_none():
    result = archive_path.preview_archive_path('/staged/noext', 'Kroger', '2026-08-15', 12.34)
    assert result['path'].endswith('.jpg')


def test_preview_archive_path_scanned_document_is_not_a_real_destination():
    result = archive_path.preview_archive_path(
        '/staged/scan.jpg', 'Kroger', '2026-08-15', 12.34, archive_kind='scanned_document')
    assert result['is_real_destination'] is False
    assert 'scanned_documents' in result['path']


def test_preview_archive_path_day_and_month_are_zero_padded_and_lowercase():
    result = archive_path.preview_archive_path(
        '/staged/scan.jpg', 'Kroger', '2026-01-05', 1.0)
    assert '/january/january_05/' in result['path']


def test_preview_archive_path_custom_root_overrides_and_is_never_real():
    result = archive_path.preview_archive_path(
        '/staged/scan.jpg', 'Kroger', '2026-08-15', 12.34,
        archive_kind='receipt', custom_root='/some/other/place')
    assert result['path'].startswith('/some/other/place/2026/august/august_15/')
    assert result['is_real_destination'] is False
