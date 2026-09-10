"""Integration tests for check-image supporting document workflow."""
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from supporting_document_slots import SUPPORTING_DOCUMENT_CATALOG


def test_check_image_slot_in_catalog():
    """Verify check_image slot is registered."""
    slot = SUPPORTING_DOCUMENT_CATALOG.slot_for_kind("check_image")
    assert slot is not None
    assert slot.kind == "check_image"
    assert slot.expense_field == "check_number"
    assert slot.label == "View Check Image"
    assert slot.falls_back_to_page_scan is False


def test_check_image_reference_resolution(monkeypatch, tmp_path):
    """Test _check_image_reference finds check-images PDF in report directory."""
    # Create mock report structure
    report_dir = tmp_path / "march_statement"
    report_dir.mkdir()
    report_html = report_dir / "report.html"
    report_html.write_text("<html>Report</html>")
    check_images = report_dir / "fifth_third_bank_5938_march_check_images.pdf"
    check_images.write_bytes(b"PDF")

    # Mock server functions
    import server

    def mock_split(path):
        if 'march_statement' in path:
            return str(tmp_path), 'march_statement/report.html'
        return str(tmp_path), path.lstrip('/')

    monkeypatch.setattr(server, '_split_report_url', mock_split)

    chosen = {'check_number': '3987', 'id': 123}
    report_path = '/rol_finances_reports/march/march_statement/report.html'

    result = server._check_image_reference(chosen, report_path)

    assert result
    assert 'check' in result.lower()
    assert 'image' in result.lower()
    assert result.endswith('.pdf')
    assert os.path.isfile(result)


def test_check_image_reference_extracts_from_description(monkeypatch, tmp_path):
    """Check number extracted from description when field is empty."""
    report_dir = tmp_path / "march_statement"
    report_dir.mkdir()
    check_images = report_dir / "bank_statement_check_images.pdf"
    check_images.write_bytes(b"PDF")

    import server

    def mock_split(path):
        return str(tmp_path), 'march_statement/report.html'

    monkeypatch.setattr(server, '_split_report_url', mock_split)

    chosen = {
        'check_number': '',
        'description': 'Payment via check #4068',
        'id': 123,
    }
    report_path = '/rol-finances/march_statement/report.html'

    result = server._check_image_reference(chosen, report_path)

    assert result
    assert os.path.isfile(result)


def test_check_image_reference_fails_without_check_number(monkeypatch, tmp_path):
    """No reference when check number missing."""
    report_dir = tmp_path / "march_statement"
    report_dir.mkdir()
    check_images = report_dir / "bank_check_images.pdf"
    check_images.write_bytes(b"PDF")

    import server

    def mock_split(path):
        return str(tmp_path), 'march_statement/report.html'

    monkeypatch.setattr(server, '_split_report_url', mock_split)

    chosen = {
        'check_number': '',
        'description': 'Bank transaction',
        'id': 123,
    }
    report_path = '/rol-finances/march_statement/report.html'

    result = server._check_image_reference(chosen, report_path)

    assert result == ''


def test_check_image_reference_fails_without_pdf(monkeypatch, tmp_path):
    """No reference when check-images PDF doesn't exist."""
    report_dir = tmp_path / "march_statement"
    report_dir.mkdir()
    # Create a non-matching file to ensure the search logic is correct
    (report_dir / "report.html").write_text("<html></html>")

    import server

    def mock_split(path):
        return str(tmp_path), 'march_statement/report.html'

    monkeypatch.setattr(server, '_split_report_url', mock_split)

    chosen = {'check_number': '3987', 'id': 123}
    report_path = '/rol-finances/march_statement/report.html'

    result = server._check_image_reference(chosen, report_path)

    assert result == ''


def test_expense_annotation_evidence_includes_check_reference_terms():
    """Check number passed as reference_terms for check_image documents."""
    import server

    chosen = {
        'id': 123,
        'expense_date': '2025-03-15',
        'amount': '80.00',
        'description': 'Check payment',
        'check_number': '3987',
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
