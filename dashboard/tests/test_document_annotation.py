from pathlib import Path

from document_annotation import (
    AnnotationResult,
    ExcelExpenseDocumentAnnotator,
    ExpenseDocumentAnnotationService,
    ExpenseEvidence,
    IExpenseDocumentAnnotator,
    IExpenseDocumentAnnotationService,
    PdfCheckNumberResolver,
    PdfExpenseDocumentAnnotator,
)


class FakeAnnotator(IExpenseDocumentAnnotator):
    def __init__(self):
        self.calls = 0

    def supports(self, source_path):
        return source_path.endswith(".fake")

    def annotate(self, source_path, output_path, evidence):
        self.calls += 1
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"highlighted")
        return AnnotationResult(output_path, True, page=2)


def evidence():
    return ExpenseEvidence(
        expense_id=42,
        expense_date="2025-01-22",
        amount="18.40",
        description="MEIJER STORE",
        vendor_key="meijer",
    )


def test_service_programs_to_interface_and_caches_annotated_copy(tmp_path):
    source = tmp_path / "statement.fake"
    source.write_bytes(b"original")
    annotator = FakeAnnotator()
    service: IExpenseDocumentAnnotationService = ExpenseDocumentAnnotationService(
        [annotator], str(tmp_path / "cache")
    )

    first = service.prepare(str(source), evidence())
    second = service.prepare(str(source), evidence())

    assert first.highlighted is True
    assert first.path != str(source)
    assert second.path == first.path
    assert annotator.calls == 1
    assert source.read_bytes() == b"original"


def test_service_fails_closed_for_an_unowned_format(tmp_path):
    source = tmp_path / "legacy.xls"
    source.write_bytes(b"original")
    service = ExpenseDocumentAnnotationService([], str(tmp_path / "cache"))

    result = service.prepare(str(source), evidence())

    assert result.highlighted is False
    assert result.path == str(source)
    assert "no annotation strategy" in result.reason


def test_pdf_strategy_boxes_the_matching_expense_line(tmp_path):
    import fitz

    source = tmp_path / "statement.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 100), "01/21/2025 OTHER STORE $18.40")
    page.insert_text((72, 130), "01/22/2025 MEIJER STORE $18.40")
    document.save(source)
    document.close()
    output = tmp_path / "annotated.pdf"

    result = PdfExpenseDocumentAnnotator().annotate(
        str(source), str(output), evidence()
    )

    assert result.highlighted is True
    assert result.page == 1
    assert output.exists()
    annotated = fitz.open(output)
    drawings = annotated[0].get_drawings()
    annotated.close()
    assert any(item.get("color") == (1.0, 0.0, 0.0) for item in drawings)


def test_pdf_strategy_boxes_only_the_matching_side_by_side_check(tmp_path):
    import fitz

    source = tmp_path / "checks.pdf"
    document = fitz.open()
    page = document.new_page()
    for x, number, amount in (
        (50, "11020", "100.00"),
        (245, "11021", "228.00"),
        (430, "11023", "25.00"),
    ):
        page.insert_text((x, 100), number)
        page.insert_text((x + 48, 100), "01/13")
        page.insert_text((x + 100, 100), amount)
    document.save(source)
    document.close()
    output = tmp_path / "annotated.pdf"
    target = ExpenseEvidence(
        expense_id=477,
        expense_date="2025-01-13",
        amount="25.00",
        description="Right to Life",
    )

    result = PdfExpenseDocumentAnnotator().annotate(
        str(source), str(output), target
    )

    assert result.highlighted is True
    annotated = fitz.open(output)
    red_rects = [
        item["rect"]
        for item in annotated[0].get_drawings()
        if item.get("color") == (1.0, 0.0, 0.0)
    ]
    annotated.close()
    assert len(red_rects) == 1
    assert red_rects[0].x0 > 400
    assert red_rects[0].width < 180


def test_pdf_reference_resolver_derives_check_number(tmp_path):
    import fitz

    source = tmp_path / "checks.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((400, 100), "11023")
    page.insert_text((455, 100), "01/13")
    page.insert_text((520, 100), "25.00")
    document.save(source)
    document.close()

    terms = PdfCheckNumberResolver().resolve(
        ExpenseEvidence(
            expense_id=477,
            expense_date="2025-01-13",
            amount="25.00",
            related_document_path=str(source),
        )
    )

    assert terms == ("11023",)


def test_image_strategy_boxes_the_matching_ocr_line(tmp_path):
    from PIL import Image, ImageDraw, ImageFont

    from document_annotation import ImageExpenseDocumentAnnotator

    source = tmp_path / "ledger.png"
    image = Image.new("RGB", (1000, 260), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34
    )
    draw.text((30, 35), "01/21/2025 OTHER STORE $18.40", fill="black", font=font)
    draw.text((30, 135), "01/22/2025 MEIJER STORE $18.40", fill="black", font=font)
    image.save(source)
    output = tmp_path / "annotated.png"

    result = ImageExpenseDocumentAnnotator().annotate(
        str(source), str(output), evidence()
    )

    assert result.highlighted is True
    assert output.exists()
    annotated = Image.open(output)
    # A pixel just outside the OCR text row should belong to the red rectangle.
    red_pixels = sum(
        1
        for red, green, blue in annotated.get_flattened_data()
        if red > 200 and green < 80 and blue < 80
    )
    annotated.close()
    assert red_pixels > 100


def test_excel_strategy_boxes_only_the_matching_row(tmp_path):
    from openpyxl import Workbook, load_workbook

    source = tmp_path / "ledger.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Date", "Description", "Amount"])
    sheet.append(["01/21/2025", "OTHER STORE", 18.40])
    sheet.append(["01/22/2025", "MEIJER STORE", 18.40])
    workbook.save(source)
    output = tmp_path / "annotated.xlsx"

    result = ExcelExpenseDocumentAnnotator().annotate(
        str(source), str(output), evidence()
    )

    assert result.highlighted is True
    highlighted = load_workbook(output)
    assert highlighted.active["A3"].border.left.color.rgb == "FFFF0000"
    assert highlighted.active["B3"].border.top.color.rgb == "FFFF0000"
    assert highlighted.active["C3"].border.right.color.rgb == "FFFF0000"
    assert highlighted.active["A2"].border.left.style is None
    highlighted.close()
