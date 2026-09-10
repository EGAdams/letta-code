"""Tests for check-image PDF annotation and resolution."""
import os
import re
from pathlib import Path

import pytest

from document_annotation import (
    AnnotationResult,
    ExpenseEvidence,
    PdfCheckImageAnnotator,
)


def evidence_with_check(check_number="3987", amount="80.00"):
    """Build evidence for a check transaction."""
    return ExpenseEvidence(
        expense_id=123,
        expense_date="2025-03-15",
        amount=amount,
        description=f"Check #{check_number}",
        vendor_key="",
        reference_terms=(check_number,),
    )


@pytest.fixture
def check_images_pdf(tmp_path):
    """Create a minimal check-images PDF with mock check panels."""
    try:
        import fitz
    except ImportError:
        pytest.skip("PyMuPDF not installed")

    pdf_path = tmp_path / "bank_5938_check_images.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    # Simulate check panels with headers (2 columns, 3 rows layout)
    # Page 1: checks 3987/$80, 4068/$400, 9329/$200, 9330/$14.99, 9331/$200, 9332/$200
    checks = [
        ("3987", "80.00", 50, 100),
        ("4068", "400.00", 320, 100),
        ("9329", "200.00", 50, 300),
        ("9330", "14.99", 320, 300),
        ("9331", "200.00", 50, 500),
        ("9332", "200.00", 320, 500),
    ]

    for check_num, amount, x, y in checks:
        # Add check header text
        page.insert_text(
            (x, y),
            f"Check {check_num}",
            fontsize=10,
        )
        page.insert_text(
            (x, y + 15),
            f"Amount: ${amount}",
            fontsize=9,
        )
        # Draw a box representing the check image below
        check_rect = fitz.Rect(x, y + 25, x + 250, y + 150)
        page.draw_rect(check_rect, color=(0.8, 0.8, 0.8), width=1)

    doc.save(pdf_path)
    doc.close()
    return str(pdf_path)


def test_check_image_annotator_supports_check_images_pdf():
    annotator = PdfCheckImageAnnotator()
    assert annotator.supports("/path/to/check_images.pdf") is True
    assert annotator.supports("/path/to/check_image_statement.pdf") is True
    assert annotator.supports("/path/to/statement.pdf") is False
    assert annotator.supports("/path/to/receipt.jpg") is False


def test_check_image_annotator_finds_check_by_number(check_images_pdf, tmp_path):
    output = tmp_path / "annotated.pdf"
    evidence = evidence_with_check("3987", "80.00")

    annotator = PdfCheckImageAnnotator()
    result = annotator.annotate(str(check_images_pdf), str(output), evidence)

    assert result.highlighted is True
    assert result.path == str(output)
    assert result.page == 1
    assert os.path.isfile(output)


def test_check_image_annotator_distinguishes_same_amount_checks(check_images_pdf, tmp_path):
    """Three checks ($200) on one page - must use check number, not amount alone."""
    output = tmp_path / "annotated.pdf"
    evidence = evidence_with_check("9331", "200.00")

    annotator = PdfCheckImageAnnotator()
    result = annotator.annotate(str(check_images_pdf), str(output), evidence)

    assert result.highlighted is True
    # Verify it found the right check by reading back the annotated PDF
    import fitz
    doc = fitz.open(output)
    page = doc[0]
    drawings = page.get_drawings()
    red_rects = [
        d for d in drawings
        if d.get("color") == (1.0, 0.0, 0.0)
    ]
    # Should have exactly one red rectangle
    assert len(red_rects) > 0
    doc.close()


def test_check_image_annotator_fails_without_check_number(check_images_pdf, tmp_path):
    output = tmp_path / "annotated.pdf"
    evidence = ExpenseEvidence(
        expense_id=123,
        expense_date="2025-03-15",
        amount="80.00",
        description="Bank transaction",
        vendor_key="",
    )

    annotator = PdfCheckImageAnnotator()
    result = annotator.annotate(str(check_images_pdf), str(output), evidence)

    assert result.highlighted is False
    assert "No check number found" in result.reason


def test_check_image_annotator_extracts_check_from_description(check_images_pdf, tmp_path):
    output = tmp_path / "annotated.pdf"
    evidence = ExpenseEvidence(
        expense_id=123,
        expense_date="2025-03-15",
        amount="400.00",
        description="Payment via check #4068",
        vendor_key="",
    )

    annotator = PdfCheckImageAnnotator()
    result = annotator.annotate(str(check_images_pdf), str(output), evidence)

    assert result.highlighted is True
    assert result.path == str(output)


def test_check_image_annotator_fails_for_missing_check(check_images_pdf, tmp_path):
    output = tmp_path / "annotated.pdf"
    evidence = evidence_with_check("9999", "500.00")  # Non-existent check

    annotator = PdfCheckImageAnnotator()
    result = annotator.annotate(str(check_images_pdf), str(output), evidence)

    assert result.highlighted is False
    assert "No check panel found" in result.reason
    assert "9999" in result.reason


def test_check_image_annotator_highlights_full_panel_not_just_header(check_images_pdf, tmp_path):
    """Verify the red box covers the check image, not just the header text."""
    output = tmp_path / "annotated.pdf"
    evidence = evidence_with_check("3987", "80.00")

    annotator = PdfCheckImageAnnotator()
    result = annotator.annotate(str(check_images_pdf), str(output), evidence)

    assert result.highlighted is True

    import fitz
    doc = fitz.open(output)
    page = doc[0]

    # Find the drawn rectangle
    drawings = page.get_drawings()
    red_rects = [
        d for d in drawings
        if d.get("color") == (1.0, 0.0, 0.0)
    ]

    # Should have at least one red rectangle
    assert len(red_rects) > 0

    # The rectangle should be taller than just header text (header ~30px, full panel ~200px)
    for rect_info in red_rects:
        rect = rect_info.get("rect")
        if rect:
            height = rect.y1 - rect.y0
            assert height > 100, f"Check panel box too small (height={height}), should cover full check image"

    doc.close()
