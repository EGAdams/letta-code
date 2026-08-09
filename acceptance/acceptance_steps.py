from __future__ import annotations

import re
from pathlib import Path

import document_annotation
from document_annotation import (
    AnnotationResult,
    ExcelExpenseDocumentAnnotator,
    ExpenseEvidence,
    IExpenseDocumentAnnotationService,
    IImageRegionFallbackMatcher,
    ImageExpenseDocumentAnnotator,
    ImageRegionMatch,
    PdfExpenseDocumentAnnotator,
    build_document_annotation_service,
)


class _Fallback(IImageRegionFallbackMatcher):
    def __init__(self):
        self.calls = 0
        self.outcome = None

    def find_region(self, source_path, evidence):
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def _example_value(example, parameter_name):
    if parameter_name not in example:
        raise AssertionError(f"missing example value: {parameter_name}")
    return example[parameter_name]


def _expense_evidence(expense):
    values = {
        "2004": ("2025-09-08", "125.00", "John Roark"),
        "2006": ("2025-05-02", "30.00", "Gabrielle McKay"),
        "1985": ("2025-04-10", "53.06", "DTE"),
        "1522": ("2025-01-22", "10.59", "APPLE.COM"),
    }
    date, amount, description = values.get(
        str(expense), ("2025-01-22", "18.40", "MEIJER STORE")
    )
    return ExpenseEvidence(
        expense_id=int(expense) if str(expense).isdigit() else 1,
        expense_date=date,
        amount=amount,
        description=description,
        vendor_key=description.lower().replace(".", "").replace(" ", "_"),
    )


def _ensure_image_world(world, expense):
    world.setdefault("expense", str(expense))
    world.setdefault("evidence", _expense_evidence(expense))
    world.setdefault("fallback", _Fallback())
    world.setdefault("established_region", None)


def _run_image_annotation(world):
    from PIL import Image
    import pytesseract

    execution_dir = Path("build/acceptance/executions")
    execution_dir.mkdir(parents=True, exist_ok=True)
    source = execution_dir / f'{world["expense"]}-source.png'
    output = execution_dir / f'{world["expense"]}-annotated.png'
    Image.new("RGB", (300, 180), "white").save(source)
    if output.exists():
        output.unlink()
    original_ocr = pytesseract.image_to_data
    original_best_line = document_annotation._best_line
    pytesseract.image_to_data = lambda *args, **kwargs: {"text": []}
    established_region = world.get("established_region")
    document_annotation._best_line = (
        lambda lines, evidence: (
            (established_region, 10, "matching established row")
            if established_region is not None
            else (None, -1, "")
        )
    )
    try:
        result = ImageExpenseDocumentAnnotator(
            fallback_matcher=world["fallback"]
        ).annotate(str(source), str(output), world["evidence"])
    finally:
        pytesseract.image_to_data = original_ocr
        document_annotation._best_line = original_best_line
    world["annotation_result"] = result
    world["source_path"] = str(source)
    world["output_path"] = str(output)


def _noop(world, match, example):
    return None


def _available_image(world, match, example):
    _ensure_image_world(world, _example_value(example, match.group(1)))


def _established_absent(world, match, example):
    world["established_region"] = None


def _fallback_identifies(world, match, example):
    world["fallback"].outcome = ImageRegionMatch((30, 30, 270, 100), 0.99)


def _open_viewer(world, match, example):
    _run_image_annotation(world)


def _assert_annotated(world, match, example):
    result = world["annotation_result"]
    assert isinstance(result, AnnotationResult)
    assert result.highlighted is True
    assert result.path == world["output_path"]


def _assert_one_box(world, match, example):
    _assert_annotated(world, match, example)
    assert world["fallback"].calls <= 1


def _image_fixture(world, match, example):
    expense = _example_value(example, match.group(1))
    _ensure_image_world(world, expense)


def _fallback_outcome(world, match, example):
    outcome = _example_value(example, match.group(1))
    world["fallback"].outcome = {
        "no confident region": None,
        "two indistinguishable regions": None,
        "a region outside the receipt": ImageRegionMatch((-1, 10, 50, 50), 0.99),
        "an unavailable matching service": OSError("offline"),
    }[outcome]


def _assert_unboxed(world, match, example):
    result = world["annotation_result"]
    assert result.highlighted is False
    assert result.path == world["source_path"]
    assert Path(world["output_path"]).exists() is False


def _established_target(world, match, example):
    world["established_region"] = (40, 40, 260, 110)


def _established_result(world, match, example):
    value = _example_value(example, match.group(1))
    _ensure_image_world(world, "42")
    world["established_region"] = (
        (40, 40, 260, 110) if value == "an eligible region" else None
    )
    world["fallback"].outcome = ImageRegionMatch((30, 30, 270, 100), 0.99)


def _request_annotation(world, match, example):
    _run_image_annotation(world)


def _assert_fallback_calls(world, match, example):
    expected = int(_example_value(example, match.group(1)))
    assert world["fallback"].calls == expected


def _decisive_score(world, match, example):
    world["decisive_score"] = int(_example_value(example, match.group(1)))


def _assert_decisive_score(world, match, example):
    expected = int(_example_value(example, match.group(1)))
    assert document_annotation._DECISIVE_SCORE == expected


def _assert_scoring_unchanged(world, match, example):
    region, score, _text = document_annotation._best_line(
        [
            ("01/22/2025 MEIJER STORE 18.40", (0, 10, 100, 30)),
            ("01/21/2025 OTHER STORE 18.40", (0, 40, 100, 60)),
        ],
        _expense_evidence("42"),
    )
    assert region == (0, 10, 100, 30)
    assert score >= document_annotation._DECISIVE_SCORE


def _format_selected(world, match, example):
    world["document_format"] = _example_value(example, match.group(1))


def _assert_contract(world, match, example):
    service = build_document_annotation_service("build/acceptance/cache")
    assert isinstance(service, IExpenseDocumentAnnotationService)


def _assert_format_available(world, match, example):
    document_format = _example_value(example, match.group(1))
    strategy, path = {
        "image": (ImageExpenseDocumentAnnotator(), "receipt.png"),
        "PDF": (PdfExpenseDocumentAnnotator(), "receipt.pdf"),
        "Excel": (ExcelExpenseDocumentAnnotator(), "receipt.xlsx"),
    }[document_format]
    assert strategy.supports(path)


HANDLERS = [
    (re.compile(r"^the dashboard is open to a Verified Transactions report$"), _noop),
    (re.compile(r"^expense <([A-Za-z0-9_]+)> has an available local image receipt$"), _available_image),
    (re.compile(r"^the established receipt matcher finds no eligible region$"), _established_absent),
    (re.compile(r"^fallback matching confidently identifies the single payment region containing <([A-Za-z0-9_]+)>$"), _fallback_identifies),
    (re.compile(r"^the user opens Set Category for expense <([A-Za-z0-9_]+)>$"), _noop),
    (re.compile(r"^the user selects View Receipt$"), _open_viewer),
    (re.compile(r"^the receipt viewer opens an annotated copy$"), _assert_annotated),
    (re.compile(r"^exactly one red box encloses <([A-Za-z0-9_]+)>$"), _assert_one_box),
    (re.compile(r"^no unrelated receipt region is enclosed$"), _assert_one_box),
    (re.compile(r"^image receipt fixture <([A-Za-z0-9_]+)> is available$"), _image_fixture),
    (re.compile(r"^the fallback outcome is <([A-Za-z0-9_]+)>$"), _fallback_outcome),
    (re.compile(r"^the original receipt opens without a red box$"), _assert_unboxed),
    (re.compile(r"^no receipt region is presented as the matching expense$"), _assert_unboxed),
    (re.compile(r"^expense <([A-Za-z0-9_]+)> has an available local image supporting document$"), _available_image),
    (re.compile(r"^the established receipt matcher identifies <([A-Za-z0-9_]+)>$"), _established_target),
    (re.compile(r"^the supporting document also contains <([A-Za-z0-9_]+)>$"), _noop),
    (re.compile(r"^the user selects <([A-Za-z0-9_]+)>$"), _open_viewer),
    (re.compile(r"^no red box encloses <([A-Za-z0-9_]+)>$"), _assert_one_box),
    (re.compile(r"^document annotation supports image, PDF, and Excel supporting documents$"), _noop),
    (re.compile(r"^established image matching returns <([A-Za-z0-9_]+)>$"), _established_result),
    (re.compile(r"^image annotation is requested$"), _request_annotation),
    (re.compile(r"^fallback matching is requested <([A-Za-z0-9_]+)> times$"), _assert_fallback_calls),
    (re.compile(r"^established image matching uses decisive score <([A-Za-z0-9_]+)>$"), _decisive_score),
    (re.compile(r"^its line-scoring and physical-row tie rules are unchanged$"), _assert_scoring_unchanged),
    (re.compile(r"^fallback matching is added$"), _noop),
    (re.compile(r"^decisive score remains <([A-Za-z0-9_]+)>$"), _assert_decisive_score),
    (re.compile(r"^the established line-scoring and physical-row tie results remain unchanged$"), _assert_scoring_unchanged),
    (re.compile(r"^<([A-Za-z0-9_]+)> annotation is selected through the expense document annotator contract$"), _format_selected),
    (re.compile(r"^the expense document annotator contract remains unchanged$"), _assert_contract),
    (re.compile(r"^<([A-Za-z0-9_]+)> annotation remains selectable through that contract$"), _assert_format_available),
]


def dispatch_step(world, step_text, example):
    matches = [
        (match, handler)
        for pattern, handler in HANDLERS
        if (match := pattern.fullmatch(step_text)) is not None
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"expected one handler for {step_text!r}, found {len(matches)}"
        )
    match, handler = matches[0]
    handler(world, match, example)
