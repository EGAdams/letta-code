import server
from document_annotation import AnnotationResult


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
        {"receipt_url": "", "document_url": "", "moms_ledger": ""}
    )
    assert [item["label"] for item in descriptors] == [
        "View Receipt", "View Source Document", "View Mom’s Ledger"
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
