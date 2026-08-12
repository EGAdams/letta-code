"""Unit tests for the intake report page's wording and layout.

These used to be unreachable except through build_recent_intake_html, which
needs a pointer file, a scanner registry and a database. Splitting the page
into a model (what the intake means) and a page (how it looks) makes the two
failure modes that broke the Last Freezer/Window Scan tabs — an unnamed
document and a wall of '--' — directly testable.
"""

import intake_report_model as model
import intake_report_page as page


def test_document_type_label_reports_state_when_unclassified():
    assert model.document_type_label('statement', 'chase') == 'Chase Bank Statement'
    # Not 'Unknown' — that reads like a kind of document rather than the fact
    # that no classifier has named this one yet.
    assert model.document_type_label('unknown', None) == 'Not yet identified'
    assert model.document_type_label(None, None) == 'Not yet identified'


def test_display_document_name_never_leaks_the_directory():
    assert model.display_document_name(
        '/archive/2025/march/chase_6285.jpg', '/staged/scan_freezer.jpg'
    ) == 'chase_6285.jpg'
    # No archive copy yet (a stalled scan): still name the document.
    assert model.display_document_name(
        '', '/incoming_scans/scan_freezer_178653.jpg'
    ) == 'scan_freezer_178653.jpg'


def test_status_sentence_and_tone_by_outcome():
    stalled = {'status': 'stalled', 'status_detail': ''}
    assert 'STALLED' in model.status_sentence(
        stalled, [], status_detail='Lock cleared.')
    assert 'Lock cleared.' in model.status_sentence(
        stalled, [], status_detail='Lock cleared.')
    assert model.status_tone('stalled', None, []) == 'bad'
    assert model.status_tone('complete', 1.0, [{'id': 1}]) == 'ok'
    assert model.status_tone('complete', 1.0, []) == 'info'
    assert model.status_tone('processing', None, []) == 'working'


def test_empty_table_note_explains_which_kind_of_empty():
    assert 'stopped before any transactions' in model.empty_table_note(
        'stalled', None)
    assert 'still reading' in model.empty_table_note('processing', None)
    assert model.empty_table_note('complete', 1.0) == (
        'There is nothing to verify for this document.')


def test_presentation_rows_mark_a_duplicate_only_run():
    rows = [{'id': 7, 'cat_class': 'cat-x', 'vendor_key': 'v',
             'description': 'd', 'amount': '-1.00', 'date': '2025-06-01',
             'reporting_category': 'Uncategorized'}]
    assert model.presentation_rows(rows, set())[0]['duplicate'] is False
    assert model.presentation_rows(rows, {7})[0]['duplicate'] is True
    # Parsed something, stored nothing -> every row was seen before.
    assert model.presentation_rows(
        rows, set(), stored=0, parsed=3)[0]['duplicate'] is True


def test_document_meta_html_omits_fields_with_nothing_to_say():
    html = page.document_meta_html([
        ('Document Type', 'Chase Bank Statement'),
        ('Associated PDF', model.META_EMPTY),
        ('Associated Receipt', ''),
    ])
    assert 'Document Type: Chase Bank Statement' in html
    assert 'Associated PDF' not in html
    assert 'Associated Receipt' not in html
    # Nothing at all to report -> no empty block left behind.
    assert page.document_meta_html([('Associated PDF', '--')]) == ''


def test_transactions_table_always_renders_with_its_empty_note():
    html = page.transactions_table_html([], empty_note='Nothing here yet.')
    assert '<table id="verified-transactions"' in html
    assert 'Nothing here yet.' in html


def test_render_intake_report_places_the_banner_and_headline():
    html = page.render_intake_report(
        headline='scan_freezer.jpg',
        subtitle='Freezer Scanner — dispatched 2026-08-12 08:05',
        meta_fields=[('Document Type', 'Not yet identified')],
        status_text='Mazda Trainer reported STALLED.',
        status_tone='bad',
        table_html='<table id="verified-transactions"></table>',
    )
    assert 'Most Recent Document: scan_freezer.jpg' in html
    assert 'class="status-banner status-bad"' in html
    assert 'http-equiv="refresh"' not in html
    assert page.render_intake_report(
        headline='x', subtitle='', meta_fields=[], status_text='',
        status_tone='working', table_html='', auto_refresh=True,
    ).count('http-equiv="refresh"') == 1
