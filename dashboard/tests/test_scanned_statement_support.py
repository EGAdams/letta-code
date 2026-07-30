import server
from supporting_document_slots import SUPPORTING_DOCUMENT_CATALOG


def test_catalog_exposes_scanned_statement_between_source_and_moms_ledger():
    assert [slot.kind for slot in SUPPORTING_DOCUMENT_CATALOG.slots()] == [
        "receipt",
        "source",
        "scanned_statement",
        "moms_ledger",
    ]


def test_scanned_statement_descriptor_uses_its_own_field(monkeypatch):
    monkeypatch.setattr(
        server,
        "_resolve_local_supporting_document",
        lambda reference, kind: reference if kind == "scanned_statement" else None,
    )
    row = {
        "receipt_url": "",
        "document_url": "",
        "scanned_statement_url": "/tmp/statement-scan.jpg",
        "moms_ledger": "",
    }
    descriptors = server._supporting_document_descriptors(row)
    scanned = next(d for d in descriptors if d["type"] == "scanned_statement")
    assert scanned == {
        "type": "scanned_statement",
        "label": "View Scanned Statement",
        "field": "scanned_statement_url",
        "available": True,
    }


def test_fold_event_includes_evidence_only_expense_ids():
    intake = {"expense_ids": [], "duplicate_expense_ids": []}
    server._fold_event_into_intake(
        intake,
        {
            "parsed": 3,
            "stored": 0,
            "scanned_statement_attached": [1366, 1390, 1434],
            "rolled_back_row_count": 0,
        },
    )
    assert intake["expense_ids"] == [1366, 1390, 1434]
    assert intake["rolled_back_row_count"] == 0


def test_step8_routes_scanned_statement_to_its_own_field():
    message = server.build_mazda_scan_message("/tmp/scan.jpg", "Freezer")
    assert "statement scanned from paper → scanned_statement_url" in message
    assert "MUST NEVER be stored in document_url" in message
    assert '"scanned_statement_attached"' in message
    assert '"outcome":"<EVIDENCE_ATTACHED' in message
