from pathlib import Path

import server


ROOT = Path(__file__).parents[2]


def test_dispatch_teaches_field_mapping_and_preservation_for_every_branch():
    message = server.build_mazda_scan_message(
        "/scans/support.jpg", "Window Scanner",
        {"ok": False, "doc_kind": "unknown", "confidence": 0},
    )

    assert "Receipt → receipt_url" in message
    assert "statement/source document → document_url" in message
    assert "Mom’s ledger → moms_ledger" in message
    assert "Never write a statement path into receipt_url" in message
    assert "preserve the other two document fields" in message
    assert "View Receipt" in message
    assert "View Source Document" in message
    assert "View Mom’s Ledger" in message
    assert "fallback is only for repairing legacy rows" in message


def test_trainer_grades_idempotency_conflicts_and_any_arrival_order():
    instructions = (
        ROOT / "dashboard/trainer/mazda_trainer_instructions.md"
    ).read_text()

    assert "SUPPORTING-DOCUMENT INVARIANTS" in instructions
    assert "statement first, receipt later" in instructions
    assert "receipt first, statement later" in instructions
    assert "same-type conflict" in instructions
    assert "already_attached" in instructions
    assert "NEEDS_DOCUMENT_VERIFICATION" in instructions
    assert "repeated incoming scan" in instructions
    assert "reclassify" in instructions
    assert "DIALOG VISIBILITY IS PART OF THE CONTRACT" in instructions
    assert "/api/supporting-documents" in instructions
    assert "Grade every returned `expense_id`" in instructions


def test_developer_manual_contains_three_field_contract():
    manual = (ROOT / "notes_plans_handoffs/mazda_dev_status.html").read_text()

    assert "receipt_url" in manual
    assert "document_url" in manual
    assert "moms_ledger" in manual
    assert "supporting-document" in manual.lower()
    assert "repeated incoming scan" in manual
    assert "Set Category evidence visibility" in manual
    assert "View Source Document" in manual
    assert "report directory only to keep legacy records usable" in manual
