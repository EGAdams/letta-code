from pathlib import Path

import pytest

from document_annotation import (
    AnnotationResult,
    CodexCliImageRegionFallbackMatcher,
    ExcelExpenseDocumentAnnotator,
    ExpenseDocumentAnnotationService,
    ExpenseEvidence,
    ImageExpenseDocumentAnnotator,
    ImageRegionMatch,
    IExpenseDocumentAnnotator,
    IExpenseDocumentAnnotationService,
    IImageRegionFallbackMatcher,
    PdfCheckNumberResolver,
    PdfExpenseDocumentAnnotator,
    render_excel_for_browser,
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


class FakeImageRegionFallbackMatcher(IImageRegionFallbackMatcher):
    def __init__(self, match):
        self.match = match
        self.calls = []

    def find_region(self, source_path, evidence):
        self.calls.append((source_path, evidence))
        return self.match


class UnavailableImageRegionFallbackMatcher(IImageRegionFallbackMatcher):
    def find_region(self, source_path, evidence):
        raise OSError("matching service offline")


def test_image_strategy_uses_confident_fallback_when_established_match_is_absent(
    tmp_path,
    monkeypatch,
):
    from PIL import Image
    import pytesseract

    source = tmp_path / "check.png"
    Image.new("RGB", (200, 120), "white").save(source)
    output = tmp_path / "annotated.png"
    fallback = FakeImageRegionFallbackMatcher(
        ImageRegionMatch(region=(20, 30, 180, 90), confidence=0.99)
    )
    monkeypatch.setattr(
        pytesseract,
        "image_to_data",
        lambda *args, **kwargs: {"text": []},
    )

    result = ImageExpenseDocumentAnnotator(
        fallback_matcher=fallback,
    ).annotate(str(source), str(output), evidence())

    assert fallback.calls == [(str(source), evidence())]
    assert result.highlighted is True
    assert result.path == str(output)
    annotated = Image.open(output)
    red_pixels = [
        (x, y)
        for y in range(annotated.height)
        for x in range(annotated.width)
        if annotated.getpixel((x, y))[0] > 200
        and annotated.getpixel((x, y))[1] < 80
        and annotated.getpixel((x, y))[2] < 80
    ]
    annotated.close()
    assert red_pixels
    assert min(x for x, _y in red_pixels) < 20
    assert max(x for x, _y in red_pixels) > 180
    assert min(y for _x, y in red_pixels) < 30
    assert max(y for _x, y in red_pixels) > 90


@pytest.mark.parametrize(
    "fallback_match",
    [
        None,
        ImageRegionMatch(region=(20, 30, 180, 90), confidence=0.5),
        ImageRegionMatch(region=(-1, 30, 180, 90), confidence=0.99),
    ],
)
def test_image_strategy_fails_closed_for_uncertain_fallback_results(
    tmp_path,
    monkeypatch,
    fallback_match,
):
    from PIL import Image
    import pytesseract

    source = tmp_path / "check.png"
    Image.new("RGB", (200, 120), "white").save(source)
    output = tmp_path / "annotated.png"
    monkeypatch.setattr(
        pytesseract,
        "image_to_data",
        lambda *args, **kwargs: {"text": []},
    )

    result = ImageExpenseDocumentAnnotator(
        fallback_matcher=FakeImageRegionFallbackMatcher(fallback_match),
    ).annotate(str(source), str(output), evidence())

    assert result.highlighted is False
    assert result.path == str(source)
    assert output.exists() is False


def test_image_strategy_fails_closed_when_fallback_service_is_unavailable(
    tmp_path,
    monkeypatch,
):
    from PIL import Image
    import pytesseract

    source = tmp_path / "check.png"
    Image.new("RGB", (200, 120), "white").save(source)
    output = tmp_path / "annotated.png"
    monkeypatch.setattr(
        pytesseract,
        "image_to_data",
        lambda *args, **kwargs: {"text": []},
    )

    result = ImageExpenseDocumentAnnotator(
        fallback_matcher=UnavailableImageRegionFallbackMatcher(),
    ).annotate(str(source), str(output), evidence())

    assert result.highlighted is False
    assert result.path == str(source)
    assert "unavailable" in result.reason.lower()
    assert output.exists() is False


def test_codex_fallback_requests_one_payment_region_in_original_pixels():
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))

        class Completed:
            returncode = 0
            stdout = (
                '{"confidence":0.98,"regions":['
                '{"left":100,"top":80,"right":900,"bottom":420}]}'
            )
            stderr = ""

        return Completed()

    target = ExpenseEvidence(
        expense_id=2004,
        expense_date="2025-09-08",
        amount="125.00",
        description="John Roark",
        vendor_key="john_roark",
    )

    match = CodexCliImageRegionFallbackMatcher(
        codex_path="/opt/codex",
        runner=runner,
    ).find_region("/receipts/check.jpg", target)

    assert match == ImageRegionMatch(
        region=(100.0, 80.0, 900.0, 420.0),
        confidence=0.98,
    )
    command, kwargs = calls[0]
    assert command[:2] == ["/opt/codex", "exec"]
    assert command[command.index("--image") + 1] == "/receipts/check.jpg"
    assert "125.00" in kwargs["input"]
    assert "John Roark" in kwargs["input"]
    assert "posting" in kwargs["input"].lower()
    assert kwargs["timeout"] > 0


def test_codex_fallback_rejects_multiple_candidate_regions():
    def runner(command, **kwargs):
        class Completed:
            returncode = 0
            stdout = (
                '{"confidence":0.99,"regions":['
                '{"left":10,"top":20,"right":100,"bottom":80},'
                '{"left":10,"top":100,"right":100,"bottom":160}]}'
            )
            stderr = ""

        return Completed()

    matcher = CodexCliImageRegionFallbackMatcher(
        codex_path="/opt/codex",
        runner=runner,
    )

    assert matcher.find_region("/receipts/check.jpg", evidence()) is None


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


def test_check_number_in_description_counts_as_reference_identity():
    from document_annotation import _best_line

    target = ExpenseEvidence(
        expense_id=1996,
        expense_date="2026-01-06",
        amount="303.00",
        description="Donation (Check # 1107)",
        vendor_key="childrens_vision_int_inc",
    )

    region, score, text = _best_line(
        [
            ("8/16/2023 1107 303.00 2,111.00", "target-row"),
            ("4/22/2025 1071 303.00 1,203.50", "other-row"),
        ],
        target,
    )

    assert region == "target-row"
    assert score >= 12
    assert "1107" in text


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
    fallback = FakeImageRegionFallbackMatcher(None)

    result = ImageExpenseDocumentAnnotator(fallback_matcher=fallback).annotate(
        str(source), str(output), evidence()
    )

    assert result.highlighted is True
    assert fallback.calls == []
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


def test_bill_summary_candidate_joins_amount_rows_to_the_dated_balance_row():
    from document_annotation import (
        ExpenseEvidence,
        _best_line,
        _bill_summary_windows,
    )

    target = ExpenseEvidence(
        expense_id=1985,
        expense_date="2025-04-10",
        amount="53.06",
        description="DTE",
        vendor_key="dte_04_10_25_53_06",
    )
    # Captured from Tesseract on the 2026-08-02 Freezer scan. The charge and
    # its date are printed on adjacent bill-summary rows, not one OCR line.
    lines = [
        ("Gas Commercial Heating 53.06", (200, 1953, 1306, 1992)),
        ("Total Current Charges 53.06", (180, 2004, 1307, 2041)),
        ("Account Balance as of April 10, 2025 = $216.79", (180, 2062, 1307, 2097)),
    ]

    candidates = lines + _bill_summary_windows(lines)
    region, score, text = _best_line(candidates, target)

    assert score >= 10
    assert "Gas Commercial Heating 53.06" in text
    assert "April 10, 2025" in text
    # Adjacent rows prove identity, but only the expense row is boxed.
    assert region == (200.0, 1953.0, 1306.0, 1992.0)


def test_illegible_amount_still_matches_on_date_plus_payee():
    from document_annotation import _best_line

    # What tesseract returns for a statement row EG has written across: the
    # date and payee survive, "10.59" comes back as "1.59".
    lines = [
        ("01/22/2025 MEIJER STORE 1.40", "row"),
        ("Statement period 01/01/2025 - 01/31/2025", "header"),
    ]

    region, score, text = _best_line(lines, evidence())

    assert region == "row"
    assert text == "01/22/2025 MEIJER STORE 1.40"
    # Held below the decisive band: identity alone never outranks a real
    # amount match, and never survives a tie.
    assert score < 10


def test_illegible_amount_match_needs_the_date_and_the_payee():
    from document_annotation import _best_line

    # Right payee, wrong date — this is a different month's Meijer charge.
    assert _best_line([("02/22/2025 MEIJER STORE", "row")], evidence())[0] is None
    # Right date, no payee overlap — a bare date is not identity.
    assert _best_line([("01/22/2025 balance forward", "row")], evidence())[0] is None


def test_illegible_amount_does_not_treat_a_bare_date_in_description_as_row_date():
    from document_annotation import _best_line

    target = ExpenseEvidence(
        expense_id=1679,
        expense_date="2025-03-05",
        amount="19.50",
        description="Edited Rosemary's 2/15 sermon",
    )
    lines = [
        ("3/25/2025 Edited Rosemary's 3/5 sermon 15.50", "wrong-row"),
        ("3/5/2025 Edited Rosemary's 2/15 sermon", "right-row"),
    ]

    assert _best_line(lines, target)[0] == "right-row"


def test_wrapped_invoice_row_matches_on_unique_description_when_date_and_amount_are_garbled():
    from document_annotation import _best_line, _wrapped_line_windows

    target = ExpenseEvidence(
        expense_id=1680,
        expense_date="2025-03-12",
        amount="18.00",
        description=(
            "Edited and uploaded the students and Rosemary's messages on "
            "Love Not the World and Loving the Family of God"
        ),
        vendor_key="jacob_menninga",
    )
    # Captured from Tesseract on the real Freezer scan. The target row wraps,
    # while OCR turns both 3/12/2025 and 18.00 into noise.
    spatial_lines = [
        (
            "Travel Edited and uploaded the-students and Rosemary's messages on a",
            (255.0, 1599.0, 2506.0, 1653.0),
        ),
        (
            "apap avzS Love Not the World and Loving the Family of God "
            "<2 saree —_ Sree?",
            (724.0, 1639.0, 2459.0, 1694.0),
        ),
        (
            "3/19/2025 Edited and uploaded Rosemary's sermon on the golden rule "
            "0.65 15.00 9.75",
            (725.0, 1777.0, 2131.0, 1816.0),
        ),
    ]

    candidates = spatial_lines + _wrapped_line_windows(spatial_lines)
    region, score, text = _best_line(candidates, target)

    assert region == (255.0, 1599.0, 2506.0, 1694.0)
    assert score == 9
    assert "students" in text
    assert "Love Not the World" in text


def test_description_only_fallback_rejects_short_or_repeated_descriptions():
    from document_annotation import _best_line

    short = ExpenseEvidence(
        expense_id=1,
        amount="18.00",
        description="Monthly subscription",
    )
    repeated = ExpenseEvidence(
        expense_id=2,
        amount="18.00",
        description=(
            "Edited and uploaded the students and Rosemary's messages on "
            "Love Not the World and Loving the Family of God"
        ),
    )

    assert _best_line([("Monthly subscription", "row")], short)[0] is None
    assert _best_line(
        [
            (repeated.description, "first-row"),
            (repeated.description, "second-row"),
        ],
        repeated,
    )[0] is None


def test_illegible_amount_match_rejects_two_rows_of_the_same_payee_and_date():
    from document_annotation import _best_line

    # Without a readable amount there is nothing left to tell these apart, so
    # the annotator must box neither rather than guess.
    lines = [
        ("01/22/2025 MEIJER STORE 1.40", "first"),
        ("01/22/2025 MEIJER STORE 8.40", "second"),
    ]

    assert _best_line(lines, evidence())[0] is None


def test_unique_amount_boxes_a_total_line_with_no_date_or_payee_on_it():
    from document_annotation import _best_line

    # AT&T-bill / single-item-receipt shape: the "Total due" line carries no
    # date or vendor text, so it can't clear the normal score-7 bar on its
    # own — but $171.17 appears nowhere else in the document, so there is no
    # rival row it could be confused with.
    target = ExpenseEvidence(
        expense_id=1975,
        expense_date="2025-03-01",
        amount="171.17",
        description="AT&T",
        vendor_key="at_t",
    )
    lines = [
        ("Bill date 03/01/25", "header"),
        ("Total due $171.17", "total-row"),
        ("Account charges $15.00", "line-1"),
    ]

    region, score, text = _best_line(lines, target)

    assert region == "total-row"
    assert score < 7


def test_repeated_amount_still_rejects_the_ambiguous_total_line():
    from document_annotation import _best_line

    # Same shape, but the amount is not unique in the document (it also
    # appears as an unrelated line item) — uniqueness can't rescue this one.
    target = ExpenseEvidence(
        expense_id=1975,
        expense_date="2025-03-01",
        amount="15.00",
        description="AT&T",
        vendor_key="at_t",
    )
    lines = [
        ("Bill date 03/01/25", "header"),
        ("Total due $15.00", "total-row"),
        ("Late fee $15.00", "other-row"),
    ]

    assert _best_line(lines, target)[0] is None


def test_repeated_total_restatement_boxes_the_bottom_most_line():
    from document_annotation import _best_line

    # Payment-slip shape (Dermatology Associates freezer scan, 2026-08-02):
    # a single total is printed twice — a labeled field, then a footer
    # confirmation — with no date or payee on either line. Both disjoint
    # regions carry the word "total", so this is the receipt restating its
    # one figure, not two coincidentally-equal line items; the bottom-most
    # restatement (closest to the signature/copy line) wins.
    target = ExpenseEvidence(
        expense_id=1980,
        expense_date="2025-04-08",
        amount="150.00",
        description="Dermatology Associates of West Michigan",
        vendor_key="dermatology_associates_of_west_michigan_dawm",
    )
    lines = [
        ("Total Amount 150.00", (30, 400, 300, 430)),
        ("Total $150.00", (30, 500, 260, 530)),
    ]

    region, score, text = _best_line(lines, target)

    assert region == (30, 500, 260, 530)
    assert score < 7


def test_image_strategy_boxes_the_amount_column_when_ocr_loses_it(tmp_path):
    from PIL import Image, ImageDraw, ImageFont

    from document_annotation import ImageExpenseDocumentAnnotator

    source = tmp_path / "statement.png"
    image = Image.new("RGB", (1400, 260), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34
    )
    draw.text((30, 35), "01/21/2025 OTHER STORE", fill="black", font=font)
    draw.text((1150, 35), "22.10", fill="black", font=font)
    draw.text((30, 135), "01/22/2025 MEIJER STORE", fill="black", font=font)
    # The amount column of the row we want, rendered unreadable the way EG's
    # pen does it on a real scan.
    draw.text((1150, 135), "18.40", fill="black", font=font)
    draw.line((1120, 175, 1360, 130), fill="black", width=9)
    draw.line((1120, 130, 1360, 175), fill="black", width=9)
    image.save(source)
    output = tmp_path / "annotated.png"

    result = ImageExpenseDocumentAnnotator().annotate(
        str(source), str(output), evidence()
    )

    assert result.highlighted is True
    annotated = Image.open(output)
    pixels = annotated.load()
    # The box must reach across the amount column, not stop at the payee text.
    red_columns = {
        x
        for x in range(annotated.width)
        for y in range(annotated.height)
        if pixels[x, y][0] > 200
        and pixels[x, y][1] < 80
        and pixels[x, y][2] < 80
    }
    annotated.close()
    assert red_columns
    assert max(red_columns) > 1200


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


def test_render_excel_for_browser_preserves_red_highlight(tmp_path):
    from openpyxl import Workbook

    source = tmp_path / 'annotated.xlsx'
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['Date', 'Description', 'Amount'])
    sheet.append(['01/21/2025', 'TRINITY HEALTH CORP-LIVONIA MI', 225.00])
    from openpyxl.styles import Border, Side
    red = Side(style='thick', color='FFFF0000')
    sheet['B2'].border = Border(left=red, right=red, top=red, bottom=red)
    workbook.save(source)
    output = tmp_path / 'view.html'

    render_excel_for_browser(str(source), str(output))

    html = output.read_text()
    assert 'TRINITY HEALTH CORP-LIVONIA MI' in html
    assert 'class=\'highlight\'' in html


def test_card_statement_row_identifies_by_bare_month_day_and_payee_head():
    """Card statements print the year once, in the billing-cycle header.

    Every transaction row opens with "MM/DD MM/DD", so requiring a printed
    calendar date made the identity-only path unreachable on scans of them —
    the Choice Privileges freezer scan of 2026-07-29 lost the box on two rows
    whose amount OCR could not read.
    """
    from document_annotation import _line_score

    roku = ExpenseEvidence(
        expense_id=1695,
        expense_date="2025-03-17",
        amount="7.99",
        description="THE ROKU CHANNEL 8162728107 DE",
        vendor_key="the_roku_channel",
    )
    radisson = ExpenseEvidence(
        expense_id=1476,
        expense_date="2025-03-15",
        amount="127.56",
        description="RADISSON HOTELS GRAND GRAND RAPIDS ,MI",
        vendor_key="radisson",
    )

    # OCR read the amount as "BF .99" and split the year off the row.
    assert _line_score(
        "03/17 03/1 7 210001500 15270212Q009MWRO6 THE ROKU CHANNEL "
        "8162728107 DE BF .99 | Lu=",
        roku,
    ) >= 7
    # OCR truncated the payee and dropped the amount column entirely.
    assert _line_score(
        "03/15 03/15 920001300 85369432BAS8HP1E3 RADISSON HO", radisson
    ) >= 7


def test_bare_month_day_needs_the_payee_head_not_its_city():
    from document_annotation import _line_score

    radisson = ExpenseEvidence(
        expense_id=1476,
        expense_date="2025-03-15",
        amount="127.56",
        description="RADISSON HOTELS GRAND GRAND RAPIDS ,MI",
        vendor_key="radisson",
    )

    # A different merchant in the same town, on the same day: "GRAND RAPIDS MI"
    # is shared by every row printed from that city and identifies nothing.
    assert _line_score(
        "03/15 03/15 000 SOME OTHER PLACE GRAND RAPIDS MI", radisson
    ) < 0
    # A bare M/D inside prose is not a transaction row either.
    assert _line_score(
        "your payment must be received by 03/15 to avoid a late fee", radisson
    ) < 0


def test_image_strategy_boxes_a_card_statement_row_without_a_printed_year(
    tmp_path,
):
    from PIL import Image, ImageDraw, ImageFont

    from document_annotation import ImageExpenseDocumentAnnotator

    source = tmp_path / "card_statement.png"
    image = Image.new("RGB", (1500, 320), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32
    )
    draw.text((30, 30), "Billing Cycle 02/20/2025 to 03/21/2025",
              fill="black", font=font)
    draw.text((30, 120), "03/15 03/15 920001300 RADISSON HOTELS GRAND",
              fill="black", font=font)
    draw.text((30, 210), "03/17 03/17 210001500 THE ROKU CHANNEL 8162728107",
              fill="black", font=font)
    # The amount column both rows lost to EG's pen.
    draw.text((1290, 210), "7.99", fill="black", font=font)
    draw.line((1270, 250, 1460, 205), fill="black", width=9)
    draw.line((1270, 205, 1460, 250), fill="black", width=9)
    image.save(source)
    output = tmp_path / "annotated.png"

    result = ImageExpenseDocumentAnnotator().annotate(
        str(source),
        str(output),
        ExpenseEvidence(
            expense_id=1695,
            expense_date="2025-03-17",
            amount="7.99",
            description="THE ROKU CHANNEL 8162728107 DE",
            vendor_key="the_roku_channel",
        ),
    )

    assert result.highlighted is True
    annotated = Image.open(output)
    pixels = annotated.load()
    red_rows = {
        y
        for y in range(annotated.height)
        for x in range(annotated.width)
        if pixels[x, y][0] > 200
        and pixels[x, y][1] < 80
        and pixels[x, y][2] < 80
    }
    annotated.close()
    assert red_rows
    # The box must sit on the ROKU row, not the RADISSON row above it.
    assert min(red_rows) > 150



def test_last_freezer_scan_boxes_annual_fee_row_2000(tmp_path):
    """The hard Last Freezer Scan row must be visibly boxed for verification."""
    from document_annotation import ImageExpenseDocumentAnnotator

    source = Path(
        "/home/adamsl/rol_finances/readable_documents/scanned_statements/"
        "2025/diners_club_0587_april_22__may_30.jpg"
    )
    assert source.exists()
    output = tmp_path / "diners-0587-2000-annotated.jpg"
    target = ExpenseEvidence(
        expense_id=2000,
        expense_date="2025-05-30",
        amount="95.00",
        description="ANNUAL FEE Diners Club | x-0587",
        vendor_key="diners_club_0587",
    )

    result = ImageExpenseDocumentAnnotator().annotate(
        str(source), str(output), target
    )

    assert result.highlighted is True
    assert output.read_bytes() != source.read_bytes()
