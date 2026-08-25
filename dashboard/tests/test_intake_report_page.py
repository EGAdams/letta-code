"""Unit tests for the intake report page's wording and layout.

These used to be unreachable except through build_recent_intake_html, which
needs a pointer file, a scanner registry and a database. Splitting the page
into a model (what the intake means) and a page (how it looks) makes the two
failure modes that broke the Last Freezer/Window Scan tabs — an unnamed
document and a wall of '--' — directly testable.
"""

import json

from finance import intake_report_model as model
from finance import intake_report_page as page
from finance import vendor_lookup


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


def test_statement_source_description_recovers_the_cracker_barrel_text(tmp_path):
    artifact = tmp_path / 'scan.jpg.statement.json'
    artifact.write_text(json.dumps({
        'ok': True,
        'doc_kind': 'statement',
        'source_image': '/tmp/scan.jpg',
        'statement_count': 1,
        'statements': [{'transactions': [{
            'date': '2025-05-23',
            'description': 'CRACKER BARREL #428 CA CAVE CITY KY',
            'amount': -28.73,
            'transaction_kind': 'charge',
        }]}],
    }))
    rows = [{
        'id': 1391,
        'date': '2025-05-23',
        'amount': '28.730',
        'description': 'cracker_barrel',
    }]

    recovered = model.recover_statement_source_descriptions(artifact, rows)
    overlaid = model.apply_source_descriptions(rows, recovered)

    assert recovered == {1391: 'CRACKER BARREL #428 CA CAVE CITY KY'}
    assert overlaid[0]['description'] == 'CRACKER BARREL #428 CA CAVE CITY KY'


def test_canonical_vendor_key_is_separate_from_the_filing_key():
    rows = model.apply_canonical_vendor_keys([{
        'id': 1391,
        'description': 'CRACKER BARREL #428 CA CAVE CITY KY',
        'id_light': 'cracker_barrel_05_23_25_28_73',
        'vendor_key': '',
    }], lambda description: (
        'cracker_barrel' if description.startswith('CRACKER BARREL') else ''))
    assert rows[0]['vendor_key'] == 'cracker_barrel'
    assert rows[0]['id_light'] == 'cracker_barrel_05_23_25_28_73'


def test_statement_source_description_fails_closed_when_date_amount_is_ambiguous(
        tmp_path):
    artifact = tmp_path / 'scan.jpg.statement.json'
    artifact.write_text(json.dumps({
        'ok': True,
        'doc_kind': 'statement',
        'source_image': '/tmp/scan.jpg',
        'statement_count': 1,
        'statements': [{'transactions': [
            {'date': '2025-05-23', 'description': 'FIRST', 'amount': -28.73,
             'transaction_kind': 'charge'},
            {'date': '2025-05-23', 'description': 'SECOND', 'amount': -28.73,
             'transaction_kind': 'charge'},
        ]}],
    }))
    rows = [{
        'id': 1391,
        'date': '2025-05-23',
        'amount': '28.73',
        'description': 'DB FALLBACK',
    }]

    recovered = model.recover_statement_source_descriptions(artifact, rows)

    assert recovered == {}
    assert model.apply_source_descriptions(rows, recovered)[0]['description'] == 'DB FALLBACK'


def test_stored_findings_normalises_signed_amount_and_keeps_duplicates():
    rows = model.presentation_rows([
        {'id': 7, 'cat_class': 'cat-x', 'vendor_key': 'kum_go',
         'description': 'Kum & Go', 'amount': '-12.34', 'date': '2025-06-01',
         'reporting_category': 'Travel & Vehicle'},
        {'id': 8, 'cat_class': 'cat-y', 'vendor_key': 'meijer',
         'description': 'Meijer', 'amount': '-45.00', 'date': '2025-06-02',
         'reporting_category': 'Household'},
    ], duplicate_ids={8})
    findings = model.stored_findings(rows)
    # Duplicate-matched rows (id 8) still seed the dialog -- Prev/Next is how
    # an operator reaches and fixes a wrong date/amount that made Mazda match
    # it to an existing row in the first place. Save All's own dedup check
    # (parse_and_categorize.py --save) is what keeps an unedited resubmit safe.
    assert len(findings) == 2
    assert findings[0].merchant_name == 'Kum & Go'
    # No resolve_vendor injected -> known_vendor_key stays '' regardless of
    # the row's own (always-present, per-transaction) filing key.
    assert findings[0].known_vendor_key == ''
    # Stored amounts are signed (negative = expense); a finding always carries
    # the positive magnitude every manual/Mazda-Fill entry already uses.
    assert findings[0].total_amount == 12.34
    assert findings[1].merchant_name == 'Meijer'


def test_stored_findings_gives_unknown_vendor_a_separate_key_guess():
    rows = model.presentation_rows([{
        'id': 1391,
        'cat_class': 'cat-personal',
        'vendor_key': 'cracker_barrel_05_23_25_28_73',
        'description': 'CRACKER BARREL #428 CA CAVE CITY KY',
        'amount': '-28.73',
        'date': '2025-05-23',
        'reporting_category': 'Personal',
    }], duplicate_ids={1391})

    finding = model.stored_findings(
        rows,
        resolve_vendor=lambda _description: None,
        guess_vendor=lambda _description: 'cracker_barrel',
    )[0]

    assert finding.merchant_name == 'CRACKER BARREL #428 CA CAVE CITY KY'
    assert finding.known_vendor_key == ''
    assert finding.new_vendor_key == 'cracker_barrel'


def test_vendor_key_guess_trims_a_statement_store_number(monkeypatch):
    class _Lookup:
        def guess_vendor_key(self, _description):
            return 'cracker_barrel_428_ca_cave_city_ky'

    monkeypatch.setattr(vendor_lookup, 'vendor_category_lookup', lambda: _Lookup())
    assert vendor_lookup.guess_vendor_key(
        'CRACKER BARREL #428 CA CAVE CITY KY') == 'cracker_barrel'


def test_uncategorized_registered_key_is_still_a_new_vendor():
    rows = model.presentation_rows([{
        'id': 1391, 'cat_class': 'cat-personal',
        'vendor_key': 'filing_key',
        'description': 'CRACKER BARREL #428 CA CAVE CITY KY',
        'amount': '-28.73', 'date': '2025-05-23',
        'reporting_category': 'Personal',
    }], duplicate_ids={1391})
    finding = model.stored_findings(
        rows,
        resolve_vendor=lambda _description: 'cracker_barrel_428_ca_cave_city_ky',
        guess_vendor=lambda _description: 'cracker_barrel',
        vendor_is_known=lambda _key: False,
    )[0]
    assert finding.known_vendor_key == ''
    assert finding.new_vendor_key == 'cracker_barrel'


def test_stored_findings_carries_the_real_db_id_for_every_row():
    """EVERY row here already exists in the database (presentation_rows()
    only ever sees expenses actually queried back out of it) -- duplicate
    or not, Save All must never try to INSERT one of these again, so each
    finding needs its real id to route through an update instead."""
    rows = model.presentation_rows([
        {'id': 7, 'cat_class': 'cat-x', 'vendor_key': 'kum_go',
         'description': 'Kum & Go', 'amount': '-12.34', 'date': '2025-06-01',
         'reporting_category': 'Travel & Vehicle'},
    ], duplicate_ids=set())
    findings = model.stored_findings(rows)
    assert findings[0].expense_id == 7


def test_stored_findings_leaves_expense_id_none_for_a_row_with_no_real_id():
    rows = model.presentation_rows([
        {'id': None, 'cat_class': '', 'vendor_key': '',
         'description': 'Some Vendor', 'amount': '-9.00',
         'date': '2025-06-03', 'reporting_category': ''},
    ], duplicate_ids=set())
    assert model.stored_findings(rows)[0].expense_id is None


def test_stored_findings_fills_known_vendor_key_from_the_injected_resolver():
    """A stored row's own vendor_key is a per-transaction filing key (e.g.
    'cracker_barrel_05_23_25_28_73', built from merchant+date+amount) --
    never the reusable vendor the dialog's dropdown lists. known_vendor_key
    only comes from the injected resolver, which answers that different
    question."""
    rows = model.presentation_rows([
        {'id': 7, 'cat_class': 'cat-x',
         'vendor_key': 'cracker_barrel_05_23_25_28_73',
         'description': 'CRACKER BARREL #428 CA CAVE CITY ,KY',
         'amount': '-28.73', 'date': '2025-05-23',
         'reporting_category': 'Travel & Vehicle'},
    ], duplicate_ids={7})
    findings = model.stored_findings(
        rows, resolve_vendor=lambda description: 'cracker_barrel')
    assert findings[0].known_vendor_key == 'cracker_barrel'


def test_stored_findings_leaves_known_vendor_key_blank_when_resolver_finds_nothing():
    """No reusable vendor is a normal outcome (same as an uncategorized row)
    -- it must never fall back to the row's own per-transaction filing key,
    which is not a 'known vendor' and would misrepresent one as the other."""
    rows = model.presentation_rows([
        {'id': 7, 'cat_class': 'cat-x', 'vendor_key': 'raw_filing_key',
         'description': 'Some Vendor', 'amount': '-9.00',
         'date': '2025-05-23', 'reporting_category': ''},
    ], duplicate_ids={7})
    findings = model.stored_findings(rows, resolve_vendor=lambda _d: None)
    assert findings[0].known_vendor_key == ''


def test_stored_findings_drops_a_row_that_fails_expense_field_rules():
    """A blank description couldn't have been stored in the first place --
    the dialog degrades to blank-for-that-row instead of shipping the browser
    a finding it cannot render."""
    rows = model.presentation_rows([
        {'id': 9, 'cat_class': '', 'vendor_key': '', 'description': '',
         'amount': '-5.00', 'date': '2025-06-03', 'reporting_category': ''},
    ], duplicate_ids=set())
    assert model.stored_findings(rows) == []


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


def test_manual_entry_mount_stamps_stored_items_as_findings_json():
    """Mazda's own STEP 8 findings seed the review dialog instead of leaving
    it blank after an automatic scan (see intake_report_model.stored_findings)."""
    html = page.manual_entry_form_html(
        '/staged/x.jpg', 'conv-1', 'window',
        stored_items=[
            model.StoredFinding(merchant_name='DTE Energy', transaction_date='2026-08-01',
                                 total_amount=45.12, category_name='Utilities'),
            model.StoredFinding(merchant_name='Meijer', transaction_date='2026-08-02',
                                 total_amount=12.00, category_name=''),
        ])
    assert 'data-mazda-findings="' in html
    assert '&quot;merchant_name&quot;: &quot;DTE Energy&quot;' in html
    assert '&quot;merchant_name&quot;: &quot;Meijer&quot;' in html


def test_manual_entry_mount_without_stored_items_stamps_no_findings():
    html = page.manual_entry_form_html('/staged/x.jpg', 'conv-1', 'window')
    assert 'data-mazda-findings' not in html
    html = page.manual_entry_form_html(
        '/staged/x.jpg', 'conv-1', 'window', stored_items=[])
    assert 'data-mazda-findings' not in html


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
