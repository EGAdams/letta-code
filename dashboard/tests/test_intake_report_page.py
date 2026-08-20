"""Unit tests for the intake report page's wording and layout.

These used to be unreachable except through build_recent_intake_html, which
needs a pointer file, a scanner registry and a database. Splitting the page
into a model (what the intake means) and a page (how it looks) makes the two
failure modes that broke the Last Freezer/Window Scan tabs — an unnamed
document and a wall of '--' — directly testable.
"""

from finance import intake_report_model as model
from finance import intake_report_page as page


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


def test_status_sentence_and_tone_for_needs_human_review():
    """MAZDA_DECISION_MODE=human_only: distinct from a failure — Mazda's turn
    never started, it wasn't a crash — so it gets its own sentence/tone/empty
    note rather than falling into FAILED_STATUSES or the default 'still
    processing' branch (which would be actively misleading: Mazda is never
    coming back to report on this one)."""
    intake = {'status': 'needs_human_review', 'status_detail': ''}
    sentence = model.status_sentence(
        intake, [], status_detail='MAZDA_DECISION_MODE=human_only: ...')
    assert 'HUMAN-ONLY MODE' in sentence
    assert 'MAZDA_DECISION_MODE=human_only' in sentence
    assert model.status_tone('needs_human_review', None, []) == 'attention'
    assert 'human_only' in model.empty_table_note('needs_human_review', None)


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


def test_transactions_table_marks_category_text_for_picker_updates():
    html = page.transactions_table_html([
        {'id': 7, 'cat_class': 'cat-food', 'vendor_key': 'v',
         'description': 'd', 'amount': '-1.00', 'date': '2025-06-01',
         'reporting_category': 'Food', 'duplicate': False}
    ])

    assert 'class="category-cell" data-category-cell="true">Food</td>' in html


def test_render_intake_report_places_the_banner_and_omits_the_headline():
    html = page.render_intake_report(
        headline='scan_freezer.jpg',
        subtitle='Freezer Scanner — dispatched 2026-08-12 08:05',
        meta_fields=[('Document Type', 'Not yet identified')],
        status_text='Mazda Trainer reported STALLED.',
        status_tone='bad',
        table_html='<table id="verified-transactions"></table>',
    )
    assert 'Most Recent Document: scan_freezer.jpg' not in html
    assert 'class="status-banner status-bad"' in html
    assert 'http-equiv="refresh"' not in html
    assert page.render_intake_report(
        headline='x', subtitle='', meta_fields=[], status_text='',
        status_tone='working', table_html='', auto_refresh=True,
    ).count('http-equiv="refresh"') == 1


def test_manual_entry_form_html_carries_the_intake_reference():
    html = page.manual_entry_form_html(
        '/staged/scan_freezer.jpg', 'conv-abc123', 'freezer')
    assert 'id="manual-entry-root"' in html
    assert 'data-image-path="/staged/scan_freezer.jpg"' in html
    assert 'data-conversation-id="conv-abc123"' in html
    assert 'data-scanner-key="freezer"' in html
    assert 'src="/js/implementation/manual-entry-form.js"' in html


def test_manual_entry_form_html_scanner_key_defaults_blank_for_pdf_intakes():
    html = page.manual_entry_form_html('/staged/statement.pdf', 'conv-xyz')
    assert 'data-scanner-key=""' in html


def test_manual_entry_form_html_escapes_attribute_values():
    html = page.manual_entry_form_html('/staged/"onmouseover=alert(1).jpg', 'c')
    assert '"onmouseover=alert(1)' not in html


def test_render_intake_report_places_manual_entry_form_before_the_table():
    html = page.render_intake_report(
        headline='x', subtitle='', meta_fields=[], status_text='',
        status_tone='attention', table_html='<table id="verified-transactions"></table>',
        manual_entry_html='<div id="manual-entry-root"></div>',
    )
    assert html.index('manual-entry-root') < html.index('verified-transactions')


def test_expense_edit_panel_html_mounts_the_standalone_edit_dialog():
    html = page.expense_edit_panel_html()
    assert 'id="expense-edit-root"' in html
    assert 'src="/js/implementation/expense-edit-panel.js"' in html


def test_render_intake_report_places_the_edit_panel_before_the_table():
    html = page.render_intake_report(
        headline='x', subtitle='', meta_fields=[], status_text='',
        status_tone='ok', table_html='<table id="verified-transactions"></table>',
        expense_edit_html=page.expense_edit_panel_html(),
    )
    assert html.index('expense-edit-root') < html.index('verified-transactions')


def test_render_intake_report_can_show_the_edit_panel_without_the_entry_form():
    """The whole point of the split: a saved scan gets Edit Expense and no
    Save All."""
    html = page.render_intake_report(
        headline='x', subtitle='', meta_fields=[], status_text='',
        status_tone='ok', table_html='',
        expense_edit_html=page.expense_edit_panel_html(),
    )
    assert 'expense-edit-root' in html
    assert 'manual-entry-root' not in html


# ── The review dialog is mounted in both modes (2026-08-19) ────────────────
# It used to appear only on a needs_human_review intake — i.e. only while Mazda
# was switched off — so turning her back on took the review dialog away with
# her. These pin the mount point and the switch's starting position, because a
# switch that paints itself in the wrong position is worse than no switch: an
# operator who reads "Mazda Automatic" on a box where she is blocked will scan a
# stack of documents and wait for filing that never happens.

def test_manual_entry_mount_stamps_the_mode_it_was_rendered_in():
    from intake.mazda_mode import AUTOMATIC, SEMI_AUTOMATIC, state_for

    html = page.manual_entry_form_html(
        '/staged/x.jpg', 'conv-1', 'window',
        mazda_mode=state_for(AUTOMATIC, source='operator'))
    assert 'data-mazda-automatic="true"' in html
    assert 'data-mazda-mode-label="Mazda Automatic"' in html

    html = page.manual_entry_form_html(
        '/staged/x.jpg', 'conv-1', 'window',
        mazda_mode=state_for(SEMI_AUTOMATIC, source='default'))
    assert 'data-mazda-automatic="false"' in html
    assert 'data-mazda-mode-label="Mazda Semi-Automatic"' in html


def test_manual_entry_mount_without_a_mode_stamps_nothing():
    """None means "don't claim a position" — the form then asks
    /api/mazda-mode rather than guessing on the page's behalf."""
    html = page.manual_entry_form_html('/staged/x.jpg', 'conv-1', 'window')
    assert 'data-mazda-automatic' not in html
    assert 'manual-entry-root' in html


def test_render_intake_report_shows_the_entry_form_and_one_edit_button():
    """Both mount points render, but expense-edit-panel.js declines to mount
    when the entry form is present — the page must not grow a second Edit
    Expense button now that the form is unconditional."""
    html = page.render_intake_report(
        headline='x', subtitle='', meta_fields=[], status_text='',
        status_tone='ok', table_html='',
        manual_entry_html=page.manual_entry_form_html('/staged/x.jpg', '', 'window'),
        expense_edit_html=page.expense_edit_panel_html(),
    )
    assert 'manual-entry-root' in html
    assert 'expense-edit-root' in html
