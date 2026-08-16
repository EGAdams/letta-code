import os

import pytest

import server
from document_annotation import AnnotationResult


def test_matching_expense_supports_receipt_only_finance_schema():
    """A missing optional dashboard column cannot prevent red-box preparation."""
    queries = []

    class Cursor:
        def execute(self, sql, params=None):
            queries.append((sql, params))

        def fetchall(self):
            if len(queries) == 1:
                return [
                    {"Field": name}
                    for name in ("id", "description", "receipt_url", "expense_date", "amount")
                ]
            return [{
                "id": 1120,
                "description": "MEIJER STORE #020 GRAND RAPIDS MI",
                "receipt_url": "/receipts/meijer_12_29_24_53_06.jpg",
                "expense_date": "2024-12-29",
                "amount": "53.06",
                "id_light": None,
                "document_url": None,
                "scanned_statement_url": None,
                "moms_ledger": None,
                "notes": None,
            }]

    chosen = server._matching_expense(
        Cursor(), "", "", "meijer", "MEIJER STORE #020 GRAND RAPIDS MI", 1120
    )

    assert chosen["id"] == 1120
    assert chosen["receipt_url"].endswith("53_06.jpg")
    select_sql = queries[1][0]
    assert "NULL AS `id_light`" in select_sql
    assert "NULL AS `document_url`" in select_sql


def test_lookup_exposes_all_three_document_fields(monkeypatch):
    row = {
        "id": 42,
        "expense_date": "2025-01-02",
        "amount": "12.34",
        "id_light": "shop_01_02_25_12_34",
        "description": "Shop",
        "notes": "",
        "receipt_url": "receipt.jpg",
        "document_url": "statement.pdf",
        "moms_ledger": "ledger.jpg",
    }
    monkeypatch.setattr(server, "_lookup_expense_row", lambda *args, **kwargs: row)
    monkeypatch.setattr(
        server,
        "_supporting_document_descriptors",
        lambda chosen, report_path="": [
            {"type": "receipt", "label": "View Receipt", "available": True},
            {"type": "source", "label": "View Source Document", "available": True},
            {"type": "moms_ledger", "label": "View Mom’s Ledger", "available": True},
        ],
    )

    result = server.lookup_supporting_documents(
        "2025-01-02", "-12.34", "shop", "Shop", "", 42
    )

    assert result["receipt_url"] == "receipt.jpg"
    assert result["document_url"] == "statement.pdf"
    assert result["moms_ledger"] == "ledger.jpg"
    assert [item["type"] for item in result["documents"]] == [
        "receipt",
        "source",
        "moms_ledger",
    ]


def test_lookup_accepts_browser_string_expense_id(monkeypatch):
    row = {
        "id": 2048,
        "expense_date": "2025-04-12",
        "amount": "78.60",
        "description": "Priority Health",
        "receipt_url": "receipt.jpg",
        "document_url": "",
        "scanned_statement_url": "",
        "moms_ledger": "",
    }
    seen = []
    monkeypatch.setattr(
        server,
        "_lookup_expense_row",
        lambda *args, **kwargs: seen.append(args[-1]) or row,
    )
    monkeypatch.setattr(server, "_supporting_document_descriptors", lambda *args: [])

    result = server.lookup_supporting_documents(
        "2025-04-12", "78.60", "priority_health", "Priority Health", "", "2048"
    )

    assert result["ok"] is True
    assert result["expense_id"] == 2048
    assert seen == [2048]


def test_lookup_treats_empty_browser_expense_id_as_missing(monkeypatch):
    monkeypatch.setattr(server, "_lookup_expense_row", lambda *args: None)

    result = server.lookup_supporting_documents(
        "2025-04-12", "78.60", "priority_health", "Priority Health", "", ""
    )

    assert result == {
        "ok": False,
        "expense_id": None,
        "receipt_url": None,
        "document_url": None,
        "scanned_statement_url": None,
        "moms_ledger": None,
        "notes": "",
        "documents": [],
        "error": "No matching expense in DB.",
    }


def test_picker_has_two_rows_and_no_receipt_fallback():
    _css, html, _click_css = server._receipt_only_picker_assets()
    assert 'class="cp-document-actions"' in html
    assert 'class="cp-dialog-actions"' in html
    assert html.index("Ask Mazda") < html.index("Undo Last Action")
    assert html.index("Undo Last Action") < html.index("Close this Dialog")
    assert "Close this Dialog" in html
    assert 'class="cp-undo-action"' in html
    assert '"/api/undo-recategorize-expense"' in html
    assert '"rolFinanceCategoryUndoToken"' in html
    assert "document_url || metadata.receipt_url" not in html
    assert "moms_ledger || metadata.receipt_url" not in html
    descriptors = server._supporting_document_descriptors(
        {
            "receipt_url": "",
            "document_url": "",
            "scanned_statement_url": "",
            "moms_ledger": "",
        }
    )
    assert [item["label"] for item in descriptors] == [
        "View Receipt",
        "View Source Document",
        "View Scanned Statement",
        "View Mom’s Ledger",
    ]


def test_unusable_document_references_are_not_available():
    for value in (None, "", "   ", "null", "undefined", "#"):
        assert server._usable_document_reference(value) is False


def test_verified_report_refreshes_picker_without_rewriting_rows(tmp_path):
    report = tmp_path / "report.html"
    report.write_text(
        '<html><body><table><tr class="cat-personal" '
        'data-vendor-key="shop"></tr></table></body></html>'
    )

    html = server._report_html_with_current_picker(report)

    assert 'class="cat-personal"' in html
    assert 'class="cp-document-actions"' in html


def test_verified_report_current_picker_css_overrides_legacy_footer_styles(tmp_path):
    report = tmp_path / "report.html"
    report.write_text(
        "<html><head><style>/* ROL category picker */"
        "#rol-category-picker .cp-foot { display:flex; }"
        "</style></head><body>"
        "<style>#rol-category-picker .cp-actions { gap:26px; }</style>"
        '<table><tr data-vendor-key="shop" '
        'onclick="openCategoryPicker(this)"></tr></table>'
        "</body></html>"
    )

    html = server._report_html_with_current_picker(report)

    assert html.rfind(".cp-document-actions") > html.rfind(".cp-actions")
    current_footer = html.rfind(
        "#rol-category-picker .cp-foot { display:flex; "
        "flex-direction:column"
    )
    assert current_footer > html.rfind(".cp-actions")
    assert html.index('class="cp-document-actions"') < html.index(
        'class="cp-dialog-actions"'
    )


def test_set_category_picker_uses_windows_xp_dialog_chrome():
    _css, html, _click_css = server._receipt_only_picker_assets()

    assert 'class="cp-titlebar"' in html
    assert 'class="cp-titlebar-close"' in html
    assert 'aria-label="Close Set Category dialog"' in html
    assert "font-family:Tahoma" in html
    assert "linear-gradient(90deg,#0058ee 0%,#3b8cf5 72%,#0054e3 100%)" in html
    assert "background:#ece9d8" in html
    assert "border-radius:0" in html
    assert "titlebarClose.addEventListener(\"click\", close)" in html


def test_generated_html_report_is_not_a_source_document(
    tmp_path, monkeypatch
):
    report = tmp_path / "report.html"
    report.write_text("<html><body>Verified Transactions</body></html>")
    monkeypatch.setattr(
        server,
        "_resolve_local_supporting_document",
        lambda reference, kind: str(report) if kind == "source" else None,
    )

    documents = server._supporting_document_descriptors(
        {
            "receipt_url": "",
            "document_url": str(report),
            "moms_ledger": "",
        }
    )

    assert documents[1] == {
        "type": "source",
        "label": "View Source Document",
        "field": "document_url",
        "available": False,
    }


def test_source_document_is_unavailable_when_it_resolves_to_same_file_as_receipt(
    tmp_path, monkeypatch
):
    receipt = tmp_path / "receipts" / "tikun_03_18_25_300_00.jpg"
    receipt.parent.mkdir(parents=True)
    receipt.write_bytes(b"\xff\xd8\xff")
    relative_receipt = os.path.relpath(receipt, server.READABLE_DOCS_BASE)

    def _resolve(reference, kind):
        if not reference:
            return None
        raw = str(reference).split("#", 1)[0]
        if raw == str(receipt) or raw == relative_receipt:
            return str(receipt)
        return None

    monkeypatch.setattr(server, "_resolve_local_supporting_document", _resolve)

    documents = server._supporting_document_descriptors(
        {
            "receipt_url": relative_receipt,
            "document_url": str(receipt),
            "moms_ledger": "",
        },
        "/scanner_report.html?scanner=freezer",
    )

    assert documents[0]["available"] is True
    assert documents[1] == {
        "type": "source",
        "label": "View Source Document",
        "field": "document_url",
        "available": False,
    }


@pytest.mark.parametrize(
    ("receipt_url", "document_url"),
    [
        ("/receipts/tikun.jpg", "/receipts/tikun.jpg#page=2"),
        ("receipt:/receipts/tikun.jpg", "/receipts/tikun.jpg"),
        ({"source_document_id": "abc"}, {"id": "abc"}),
    ],
)
def test_source_document_is_unavailable_for_equivalent_targets(receipt_url, document_url, monkeypatch):
    monkeypatch.setattr(
        server,
        "_resolve_local_supporting_document",
        lambda reference, kind: "/tmp/shared.pdf" if reference and kind in {"receipt", "source"} else None,
    )

    documents = server._supporting_document_descriptors(
        {
            "receipt_url": receipt_url,
            "document_url": document_url,
            "moms_ledger": "",
        },
        "/scanner_report.html?scanner=freezer",
    )

    assert documents[0]["available"] is True
    assert documents[1]["available"] is False


def test_report_statement_is_available_when_document_url_is_missing(
    tmp_path, monkeypatch
):
    statement = tmp_path / "statement.pdf"
    statement.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        server, "_source_document_path", lambda report_path: str(statement)
    )
    monkeypatch.setattr(
        server,
        "_resolve_local_supporting_document",
        lambda reference, kind: str(statement) if kind == "source" else None,
    )

    documents = server._supporting_document_descriptors(
        {
            "receipt_url": "",
            "document_url": "",
            "moms_ledger": "",
        },
        "/rol_finances_reports/jan-2025/statement/report.html",
    )

    assert documents[1] == {
        "type": "source",
        "label": "View Source Document",
        "field": "document_url",
        "available": True,
    }


def test_source_document_is_unavailable_when_it_only_repeats_receipt(
    monkeypatch,
):
    receipt = "/receipts/tikun_03_18_25_300_00.jpg"
    monkeypatch.setattr(
        server,
        "_resolve_local_supporting_document",
        lambda reference, kind: receipt if kind == "receipt" and reference == receipt else None,
    )

    documents = server._supporting_document_descriptors(
        {
            "receipt_url": receipt,
            "document_url": receipt,
            "moms_ledger": "",
        },
        "/scanner_report.html?scanner=freezer",
    )

    assert documents[0]["available"] is True
    assert documents[1] == {
        "type": "source",
        "label": "View Source Document",
        "field": "document_url",
        "available": False,
    }


def test_source_document_falls_back_to_matching_report_in_another_month(
    tmp_path, monkeypatch
):
    reports = tmp_path / "bank_statements"
    january = reports / "january" / "same_statement"
    february = reports / "february" / "same_statement"
    january.mkdir(parents=True)
    february.mkdir(parents=True)
    statement = january / "same_statement.pdf"
    statement.write_bytes(b"%PDF-1.4\n")
    (january / "report.html").write_text("<html></html>")
    (february / "report.html").write_text("<html></html>")
    monkeypatch.setattr(server, "ROL_FINANCES_REPORTS_PARENT", str(reports))
    monkeypatch.setattr(
        server,
        "ROL_FINANCES_REPORTS_MONTHS",
        {"jan-2025": "january", "feb-2025": "february"},
    )

    result = server._source_document_path(
        "/rol_finances_reports/feb-2025/same_statement/report.html"
    )

    assert result == str(statement)


def test_report_statement_fallback_can_be_opened_and_viewed(
    tmp_path, monkeypatch
):
    statement = tmp_path / "statement.pdf"
    statement.write_bytes(b"%PDF-1.4\n")
    row = {
        "id": 658,
        "expense_date": "2025-01-15",
        "amount": "100.00",
        "id_light": "check_11024",
        "description": "Check 11024",
        "receipt_url": None,
        "document_url": None,
        "moms_ledger": None,
    }
    report_path = (
        "/rol_finances_reports/jan-2025/"
        "non_profit_rol_Statement_december_january_6285/report.html"
    )
    monkeypatch.setattr(
        server, "_lookup_expense_row", lambda *args, **kwargs: row
    )
    monkeypatch.setattr(
        server, "_source_document_path", lambda value: str(statement)
    )
    monkeypatch.setattr(
        server,
        "_resolve_local_supporting_document",
        lambda reference, kind: str(statement),
    )
    monkeypatch.setattr(
        server,
        "_prepare_supporting_document_view",
        lambda chosen, path, document_type="": AnnotationResult(
            str(statement), False
        ),
    )

    opened = server.open_supporting_document(
        "2025-01-15",
        "-100.00",
        "check_11024",
        "source",
        "Check 11024",
        658,
        report_path,
    )
    viewed = server._supporting_document_view_for_expense(
        658, "source", report_path
    )

    assert opened["ok"] is True
    assert opened["url"] == (
        "/supporting-document/658/source?report_path="
        "%2Frol_finances_reports%2Fjan-2025%2F"
        "non_profit_rol_Statement_december_january_6285%2Freport.html"
    )
    assert viewed == str(statement)


def test_generated_html_report_cannot_be_opened_as_source_document(
    tmp_path, monkeypatch
):
    report = tmp_path / "report.html"
    report.write_text("<html><body>Verified Transactions</body></html>")
    monkeypatch.setattr(
        server,
        "_lookup_expense_row",
        lambda *args, **kwargs: {
            "id": 42,
            "receipt_url": None,
            "document_url": str(report),
            "moms_ledger": None,
        },
    )
    monkeypatch.setattr(
        server,
        "_resolve_local_supporting_document",
        lambda reference, kind: str(report),
    )

    result = server.open_supporting_document(
        "2025-01-02", "-12.34", "shop", "source", expense_id=42
    )

    assert result["ok"] is False
    assert "PDF, image, or Excel workbook" in result["error"]


def test_open_document_uses_annotation_service_and_reports_highlight(
    tmp_path, monkeypatch
):
    statement = tmp_path / "statement.pdf"
    statement.write_bytes(b"%PDF-1.4\n")
    annotated = tmp_path / "annotated.pdf"
    annotated.write_bytes(b"%PDF-1.4\n")
    row = {
        "id": 477,
        "expense_date": "2025-01-13",
        "amount": "25.00",
        "id_light": "right_to_life_01_13_25_25_00",
        "description": "Right to Life",
        "receipt_url": None,
        "document_url": str(statement),
        "moms_ledger": None,
    }
    monkeypatch.setattr(
        server, "_lookup_expense_row", lambda *args, **kwargs: row
    )
    monkeypatch.setattr(
        server,
        "_resolve_local_supporting_document",
        lambda reference, kind: str(statement),
    )
    monkeypatch.setattr(
        server,
        "_prepare_supporting_document_view",
        lambda chosen, path, document_type="": AnnotationResult(
            str(annotated), True, page=3
        ),
    )

    result = server.open_supporting_document(
        "2025-01-13", "-25.00", "right_to_life", "source", expense_id=477
    )

    assert result["ok"] is True
    assert result["highlighted"] is True
    assert result["url"] == "/supporting-document/477/source#page=3"


def test_local_pdf_source_preserves_page_fragment(tmp_path, monkeypatch):
    statement = tmp_path / "statement.pdf"
    statement.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        server,
        "_lookup_expense_row",
        lambda *args, **kwargs: {
            "id": 477,
            "receipt_url": None,
            "document_url": f"{statement}#page=2",
            "moms_ledger": None,
        },
    )
    monkeypatch.setattr(
        server,
        "_resolve_local_supporting_document",
        lambda reference, kind: str(statement),
    )

    result = server.open_supporting_document(
        "2025-01-13", "-25.00", "right_to_life", "source", expense_id=477
    )

    assert result["ok"] is True
    assert result["url"] == "/supporting-document/477/source#page=2"


def test_stable_supporting_document_url_resolves_current_database_path(
    tmp_path, monkeypatch
):
    statement = tmp_path / "statement.pdf"
    statement.write_bytes(b"%PDF-1.4\n")
    row = {
        "id": 477,
        "receipt_url": None,
        "document_url": f"{statement}#page=1",
        "moms_ledger": None,
    }
    monkeypatch.setattr(
        server, "_lookup_expense_row", lambda *args, **kwargs: row
    )
    monkeypatch.setattr(
        server,
        "_resolve_local_supporting_document",
        lambda reference, kind: str(statement),
    )

    first = server._supporting_document_path_for_expense(477, "source")
    second = server._supporting_document_path_for_expense(477, "source")

    assert first == str(statement)
    assert second == str(statement)


def _resolve_if_on_disk(monkeypatch):
    """Stand in for the allowed-roots resolver: any real file resolves."""
    monkeypatch.setattr(
        server,
        "_resolve_local_supporting_document",
        lambda reference, kind: (
            str(reference)
            if reference and os.path.isfile(str(reference).split("#", 1)[0])
            else None
        ),
    )


def test_scanner_report_offers_its_own_scan_when_stored_path_is_gone(
    tmp_path, monkeypatch
):
    """A paper scan is not a downloaded source document, even if it remains staged."""
    scan = tmp_path / "scan_freezer_1785370278642285445_af131e077dc3.jpg"
    scan.write_bytes(b"\xff\xd8\xff")
    deleted = tmp_path / "scan_freezer_deleted_by_git_add.jpg"
    monkeypatch.setattr(
        server,
        "get_scanner_intake",
        lambda key: {"image_path": str(scan), "doc_kind": "statement"}
        if key == "freezer" else None,
    )
    _resolve_if_on_disk(monkeypatch)

    row = {"receipt_url": "", "document_url": str(deleted), "moms_ledger": ""}
    report_path = "/scanner_report.html?scanner=freezer"

    assert server._source_document_reference(row, report_path) == ""
    documents = server._supporting_document_descriptors(row, report_path)
    assert documents[1]["available"] is False


def test_scanner_report_never_borrows_the_other_scanner_or_a_reused_output(
    tmp_path, monkeypatch
):
    """The fallback is intake-scoped, and only the immutable staged path counts.

    The scanner's own output file (scan_freezer.jpg) is overwritten by the next
    scan, so offering it would show a different document under the label
    "View Source Document" — the legacy-document_url bug all over again.
    """
    window_scan = tmp_path / "window_scan_1785370237366238893_a1c87d8f3be6.jpg"
    window_scan.write_bytes(b"\xff\xd8\xff")
    reusable_output = tmp_path / "scan_freezer.jpg"
    reusable_output.write_bytes(b"\xff\xd8\xff")
    intakes = {
        "window": {"image_path": str(window_scan)},
        "freezer": {},  # dispatched before staging existed: no immutable path
    }
    monkeypatch.setattr(server, "get_scanner_intake", intakes.get)
    _resolve_if_on_disk(monkeypatch)

    row = {"receipt_url": "", "document_url": "", "moms_ledger": ""}

    assert server._source_document_reference(
        row, "/scanner_report.html?scanner=window") == ""
    assert server._source_document_reference(
        row, "/scanner_report.html?scanner=freezer") == ""
    assert server._supporting_document_descriptors(
        row, "/scanner_report.html?scanner=freezer")[1]["available"] is False


def test_recent_report_intake_mode_offers_the_dispatched_scan(
    tmp_path, monkeypatch
):
    scan = tmp_path / "window_scan_1785370237366238893_a1c87d8f3be6.jpg"
    scan.write_bytes(b"\xff\xd8\xff")
    monkeypatch.setattr(
        server,
        "resolve_recent_report",
        lambda: {"mode": "intake", "intake": {"image_path": str(scan)}},
    )
    _resolve_if_on_disk(monkeypatch)

    row = {"receipt_url": "", "document_url": "", "moms_ledger": ""}

    assert server._source_document_reference(
        row, server.RECENT_REPORT_PATH) == ""


def test_scanned_statement_never_appears_as_downloaded_source(
    tmp_path, monkeypatch
):
    scan = tmp_path / "fubo_statement_scan.jpg"
    scan.write_bytes(b"\xff\xd8\xff")
    monkeypatch.setattr(
        server,
        "_resolve_local_supporting_document",
        lambda reference, kind: str(scan)
        if reference and kind in {"source", "scanned_statement"} else None,
    )

    documents = server._supporting_document_descriptors(
        {
            "receipt_url": "",
            "document_url": str(scan),
            "scanned_statement_url": str(scan),
            "moms_ledger": "",
        },
        "/scanner_report.html?scanner=freezer",
    )

    assert documents[1]["available"] is False
    assert documents[2]["available"] is True


def test_last_freezer_scan_appears_only_as_scanned_statement(
    tmp_path, monkeypatch
):
    scan = tmp_path / "last_freezer_scan.jpg"
    scan.write_bytes(b"\xff\xd8\xff")
    monkeypatch.setattr(
        server,
        "get_scanner_intake",
        lambda key: {"image_path": str(scan), "doc_kind": None}
        if key == "freezer" else None,
    )
    _resolve_if_on_disk(monkeypatch)

    row = {
        "receipt_url": "",
        "document_url": "",
        "scanned_statement_url": "",
        "moms_ledger": "",
    }
    documents = server._supporting_document_descriptors(
        row, "/scanner_report.html?scanner=freezer"
    )

    assert documents[1]["available"] is False
    assert documents[2]["available"] is True


def test_stored_document_url_still_wins_while_it_resolves(tmp_path, monkeypatch):
    stored = tmp_path / "statement.pdf"
    stored.write_bytes(b"%PDF-1.4\n")
    scan = tmp_path / "scan_freezer_1785370278642285445_af131e077dc3.jpg"
    scan.write_bytes(b"\xff\xd8\xff")
    monkeypatch.setattr(
        server, "get_scanner_intake", lambda key: {"image_path": str(scan)}
    )
    _resolve_if_on_disk(monkeypatch)

    row = {"receipt_url": "", "document_url": str(stored), "moms_ledger": ""}

    assert server._source_document_reference(
        row, "/scanner_report.html?scanner=freezer") == str(stored)


def test_picker_reports_the_page_query_so_a_scanner_can_be_identified():
    """/scanner_report.html is one path for two scanners."""
    _css, html, _click_css = server._receipt_only_picker_assets()

    assert "report_path: location.pathname + location.search" in html


def test_last_freezer_scan_keeps_source_pdf_and_scanned_statement_separate(
    tmp_path, monkeypatch,
):
    """The Diners Club freezer intake has two different supporting documents.

    The downloaded statement is the Source Document; the photograph Mazda
    archived from paper is the Scanned Statement. A missing ``document_url``
    must not make the source viewer borrow ``scanned_statement_url`` (or make
    the scanned-statement slot disappear).
    """
    source_pdf = (
        "/home/adamsl/rol_finances/readable_documents/bank_statements/"
        "january/diners_0587_whole_year_2025/diners_0587_year_2025.pdf"
    )
    scanned_statement = tmp_path / "diners_club_0587_april_22__may_30.jpg"
    scanned_statement.write_bytes(b"\xff\xd8\xff")
    report_path = (
        "/rol_finances_reports/jan-2025/"
        "diners_0587_whole_year_2025/report.html"
    )
    row = {
        "id": 2000,
        "expense_date": "2025-05-30",
        "amount": "95.00",
        "id_light": "diners_club_0587_05_30_25_95_00",
        "description": "ANNUAL FEE Diners Club | x-0587",
        "receipt_url": None,
        "document_url": None,
        "scanned_statement_url": str(scanned_statement),
        "moms_ledger": None,
    }
    monkeypatch.setattr(
        server, "_lookup_expense_row", lambda *args, **kwargs: row
    )
    monkeypatch.setattr(
        server,
        "_supporting_document_roots",
        lambda: [str(tmp_path), server.READABLE_DOCS_BASE],
    )

    result = server.lookup_supporting_documents(
        "2025-05-30",
        "-95.00",
        "diners_club_0587",
        row["description"],
        report_path,
        2000,
    )

    assert result["ok"] is True
    assert result["document_url"] is None
    assert result["scanned_statement_url"] == str(scanned_statement)
    source = next(item for item in result["documents"] if item["type"] == "source")
    scanned = next(
        item for item in result["documents"]
        if item["type"] == "scanned_statement"
    )
    assert source["available"] is True
    assert scanned["available"] is True
    assert server._source_document_reference(row, report_path) == source_pdf
    assert server._source_document_reference(row, report_path) != str(scanned_statement)


def test_scanner_row_offers_source_document_matched_from_an_existing_report(
    tmp_path, monkeypatch,
):
    """A receipt scanned on the Freezer can still have a real downloaded source.

    Gardner Clinic 05/12/25 was scanned as a receipt (View Receipt covers the
    jpg), but that same transaction already has a row in an existing month
    report backed by a real downloaded statement (the credit-card xlsx). The
    synthetic scanner page has no report.html of its own, so
    _report_source_document_reference always returns '' for it — the dialog
    must still find the statement via the same (date, amount) match that
    already powers the page's "Associated PDF" header field, rather than
    silently dropping a document that plainly exists.
    """
    reports = tmp_path / "bank_statements"
    february = reports / "february" / "platinum_year"
    february.mkdir(parents=True)
    statement = february / "platinum_year.xlsx"
    statement.write_bytes(b"PK\x03\x04")
    (february / "report.html").write_text(
        '<table><tbody>'
        '<tr class="cat-x" data-vendor-key="the_gardner_clinic">'
        '<td>THE GARDNER CLINIC</td><td class="number">117.00</td>'
        '<td>2025-05-12</td></tr>'
        '</tbody></table>'
    )
    monkeypatch.setattr(server, "ROL_FINANCES_REPORTS_PARENT", str(reports))
    monkeypatch.setattr(
        server, "ROL_FINANCES_REPORTS_MONTHS",
        # The default-month entry must point at a *different* (empty) dir —
        # otherwise the same report.html is reachable under two month keys
        # and _find_matching_report_row sees it as an ambiguous double match.
        {server.ROL_FINANCES_REPORTS_DEFAULT_MONTH: "january", "feb-2025": "february"})
    monkeypatch.setattr(
        server, "ROL_FINANCE_REPORTS",
        [{"key": "platinum-year", "label": "Platinum Year", "dir": "platinum_year"}])
    monkeypatch.setattr(server, "get_scanner_intake", lambda key: {
        "image_path": "", "doc_kind": "receipt"} if key == "freezer" else None)
    monkeypatch.setattr(server, "resolve_recent_report", lambda: {})
    _resolve_if_on_disk(monkeypatch)

    row = {
        "id": 2160,
        "expense_date": "2025-05-12",
        "amount": "117.00",
        "receipt_url": "gardner_clinic_05_12_25_117_00.jpg",
        "document_url": None,
        "scanned_statement_url": None,
        "moms_ledger": None,
    }

    assert server._source_document_reference(
        row, "/scanner_report.html?scanner=freezer") == str(statement)
    documents = server._supporting_document_descriptors(
        row, "/scanner_report.html?scanner=freezer")
    source = next(item for item in documents if item["type"] == "source")
    assert source["available"] is True


def test_empty_source_does_not_borrow_same_freezer_scan_from_report_fallback(
    tmp_path, monkeypatch,
):
    """A scanner JPG must appear only as View Scanned Statement.

    This is the exact regression found while testing the Diners Club row: the
    row had no downloaded ``document_url``, but the report fallback resolved to
    the same JPG supplied by the scanner intake. The source button must be
    omitted rather than opening the same image a second time.
    """
    scan = tmp_path / "diners_club_0587_freezer_scan.jpg"
    scan.write_bytes(b"\xff\xd8\xff")
    monkeypatch.setattr(
        server,
        "_report_source_document_reference",
        lambda report_path: str(scan),
    )
    monkeypatch.setattr(
        server,
        "_report_scanned_statement_reference",
        lambda report_path: str(scan),
    )
    _resolve_if_on_disk(monkeypatch)

    row = {
        "receipt_url": "",
        "document_url": "",
        "scanned_statement_url": "",
        "moms_ledger": "",
    }
    documents = server._supporting_document_descriptors(
        row, "/scanner_report.html?scanner=freezer"
    )

    source = next(item for item in documents if item["type"] == "source")
    scanned = next(
        item for item in documents if item["type"] == "scanned_statement"
    )
    assert source["available"] is False
    assert scanned["available"] is True
    assert server._source_document_reference(
        row, "/scanner_report.html?scanner=freezer"
    ) == ""


def test_source_and_archived_scan_copies_are_same_underlying_document(
    tmp_path, monkeypatch,
):
    """Separate staged/archive paths with identical bytes expose one action."""
    staged = tmp_path / "incoming" / "scan_freezer.jpg"
    archived = tmp_path / "scanned_statements" / "diners.jpg"
    staged.parent.mkdir()
    archived.parent.mkdir()
    staged.write_bytes(b"same paper document")
    archived.write_bytes(staged.read_bytes())

    def resolve(reference, _kind):
        if reference == str(staged):
            return str(staged)
        if reference == str(archived):
            return str(archived)
        return None

    monkeypatch.setattr(server, "_resolve_local_supporting_document", resolve)
    monkeypatch.setattr(
        server,
        "_report_source_document_reference",
        lambda _report_path: str(staged),
    )
    monkeypatch.setattr(
        server,
        "_report_scanned_statement_reference",
        lambda _report_path: str(archived),
    )

    row = {
        "receipt_url": "",
        "document_url": "",
        "scanned_statement_url": str(archived),
        "moms_ledger": "",
    }
    documents = server._supporting_document_descriptors(
        row, "/scanner_report.html?scanner=freezer"
    )

    assert next(item for item in documents if item["type"] == "source")["available"] is False
    assert next(item for item in documents if item["type"] == "scanned_statement")["available"] is True


def test_scan_attached_to_a_duplicate_row_still_offers_view_receipt(
    tmp_path, monkeypatch
):
    """A receipt that duplicated an existing statement line keeps its button.

    Mazda attaches the scan itself as the row's receipt_url, so the reference
    is the intake staging path — the receipt was never filed into the receipts
    tree and the receipt index cannot see it.
    """
    staging = tmp_path / "incoming_scans"
    staging.mkdir()
    scan = staging / "window_scan_1785375180579246760_bf6820fdd860.jpg"
    scan.write_bytes(b"\xff\xd8\xff")
    monkeypatch.setattr(server, "_resolve_receipt_url_path", lambda ref: None)
    monkeypatch.setattr(
        server, "_supporting_document_roots", lambda: [str(staging)]
    )

    assert server._resolve_local_supporting_document(
        str(scan), "receipt") == str(scan)

    row = {
        "receipt_url": str(scan),
        "document_url": "",
        "moms_ledger": "",
    }
    receipt = server._supporting_document_descriptors(
        row, "/scanner_report.html?scanner=window")[0]

    assert receipt["label"] == "View Receipt"
    assert receipt["available"] is True


def test_a_receipt_reference_outside_the_allowed_roots_stays_unavailable(
    tmp_path, monkeypatch
):
    stray = tmp_path / "elsewhere" / "scan.jpg"
    stray.parent.mkdir()
    stray.write_bytes(b"\xff\xd8\xff")
    monkeypatch.setattr(server, "_resolve_receipt_url_path", lambda ref: None)
    monkeypatch.setattr(
        server, "_supporting_document_roots", lambda: [str(tmp_path / "roots")]
    )

    assert server._resolve_local_supporting_document(
        str(stray), "receipt") is None


def test_interactive_open_queues_annotation_without_waiting(
    tmp_path, monkeypatch
):
    statement = tmp_path / "statement.jpg"
    statement.write_bytes(b"image")
    row = {
        "id": 478,
        "expense_date": "2025-01-13",
        "amount": "25.00",
        "id_light": "shop_01_13_25_25_00",
        "description": "Shop",
        "receipt_url": None,
        "document_url": str(statement),
        "moms_ledger": None,
    }
    monkeypatch.setattr(server, "_lookup_expense_row", lambda *a, **kw: row)
    monkeypatch.setattr(
        server, "_resolve_local_supporting_document", lambda ref, kind: str(statement)
    )
    monkeypatch.setattr(
        server, "_background_annotation_result", lambda *a, **kw: None
    )

    result = server.open_supporting_document(
        "2025-01-13", "-25.00", "shop", "source",
        expense_id=478, wait_for_highlight=False,
    )

    assert result["ok"] is True
    assert result["url"] == "/supporting-document/478/source"
    assert result["highlighted"] is False
    assert result["highlight_pending"] is True


def test_viewer_serves_original_while_background_annotation_is_pending(
    tmp_path, monkeypatch
):
    statement = tmp_path / "statement.jpg"
    statement.write_bytes(b"image")
    row = {"id": 479, "document_url": str(statement)}
    monkeypatch.setattr(server, "_lookup_expense_row", lambda *a, **kw: row)
    monkeypatch.setattr(
        server, "_resolve_local_supporting_document", lambda ref, kind: str(statement)
    )
    monkeypatch.setattr(
        server, "_background_annotation_result", lambda *a, **kw: None
    )

    viewed = server._supporting_document_view_for_expense(479, "source")

    assert viewed == str(statement)


def test_receipt_scan_never_offers_itself_as_a_source_document(tmp_path, monkeypatch):
    """A receipt/invoice scan has no separate source document.

    The scan image already appears as "View Receipt"; offering it again under
    "View Source Document" is a redundant, misleading duplicate button — that
    label is reserved for a genuine downloaded/scanned statement covering
    several transactions, distinct from any one row's own receipt.
    """
    scan = tmp_path / "scan_freezer_1785370278642285445_af131e077dc3.jpg"
    scan.write_bytes(b"\xff\xd8\xff")
    monkeypatch.setattr(
        server,
        "get_scanner_intake",
        lambda key: {"image_path": str(scan), "doc_kind": "receipt"},
    )
    _resolve_if_on_disk(monkeypatch)

    row = {"receipt_url": "", "document_url": "", "moms_ledger": ""}
    report_path = "/scanner_report.html?scanner=freezer"

    assert server._source_document_reference(row, report_path) == ""
    documents = server._supporting_document_descriptors(row, report_path)
    assert documents[1]["available"] is False
