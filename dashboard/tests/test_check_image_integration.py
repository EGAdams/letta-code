"""Integration tests for check-image supporting document workflow.

The slot stores nothing on the expense row: a row qualifies when its
description names a check number, and the document is the statement's
companion ``<statement>_images.pdf`` beside the source PDF.
"""
import os

from supporting_document_slots import SUPPORTING_DOCUMENT_CATALOG


def _statement_with_check_images(monkeypatch, tmp_path, *, with_images=True):
    """A statement PDF the report resolves to, and its companion if asked."""
    import server

    statement = tmp_path / "fifth_third_bank_5938_march.pdf"
    statement.write_bytes(b"PDF")
    companion = tmp_path / "fifth_third_bank_5938_march_images.pdf"
    if with_images:
        companion.write_bytes(b"PDF")
    monkeypatch.setattr(
        server, '_source_document_path',
        lambda report_path, receipt_path=None: str(statement))
    return server, str(companion)


REPORT_PATH = '/rol_finances_reports/march/march_statement/report.html'


def test_check_image_slot_in_catalog():
    """Verify check_image slot is registered, once, with no stored field."""
    slot = SUPPORTING_DOCUMENT_CATALOG.slot_for_kind("check_image")
    assert slot is not None
    assert slot.kind == "check_image"
    assert slot.expense_field == ""
    assert slot.label == "View Check Image"
    assert slot.falls_back_to_page_scan is False
    kinds = [s.kind for s in SUPPORTING_DOCUMENT_CATALOG.slots()]
    assert kinds.count("check_image") == 1


def test_check_image_reference_resolution(monkeypatch, tmp_path):
    """A check row resolves to the statement's companion images PDF."""
    server, companion = _statement_with_check_images(monkeypatch, tmp_path)

    chosen = {'description': 'Check 3987', 'id': 123}

    result = server._slot_reference(chosen, 'check_image', REPORT_PATH)

    assert result == companion
    assert result.endswith('_images.pdf')
    assert os.path.isfile(result)


def test_check_image_reference_extracts_from_description(monkeypatch, tmp_path):
    """The check number is recognised inside a longer description."""
    server, companion = _statement_with_check_images(monkeypatch, tmp_path)

    chosen = {'description': 'Payment via check #4068', 'id': 123}

    result = server._slot_reference(chosen, 'check_image', REPORT_PATH)

    assert result == companion
    assert os.path.isfile(result)


def test_check_image_reference_fails_without_check_number(monkeypatch, tmp_path):
    """No reference when check number missing."""
    server, _ = _statement_with_check_images(monkeypatch, tmp_path)

    chosen = {'description': 'Bank transaction', 'id': 123}

    assert server._slot_reference(chosen, 'check_image', REPORT_PATH) == ''


def test_check_image_reference_fails_without_pdf(monkeypatch, tmp_path):
    """No reference when the companion images PDF doesn't exist."""
    server, _ = _statement_with_check_images(
        monkeypatch, tmp_path, with_images=False)

    chosen = {'description': 'Check 3987', 'id': 123}

    assert server._slot_reference(chosen, 'check_image', REPORT_PATH) == ''


def test_expense_annotation_evidence_includes_check_reference_terms():
    """Check number passed as reference_terms for check_image documents."""
    import server

    chosen = {
        'id': 123,
        'expense_date': '2025-03-15',
        'amount': '80.00',
        'description': 'Check 3987',
        'id_light': 'vendor',
    }

    evidence = server._expense_annotation_evidence(chosen, 'check_image')

    assert evidence.reference_terms == ('3987',)
    assert evidence.expense_id == 123
    assert evidence.amount == '80.00'


def test_expense_annotation_evidence_extracts_check_from_description():
    """Check number extracted from description for check_image evidence."""
    import server

    chosen = {
        'id': 123,
        'expense_date': '2025-03-15',
        'amount': '400.00',
        'description': 'Payment check #4068',
        'check_number': '',
        'id_light': 'vendor',
    }

    evidence = server._expense_annotation_evidence(chosen, 'check_image')

    assert evidence.reference_terms == ('4068',)
