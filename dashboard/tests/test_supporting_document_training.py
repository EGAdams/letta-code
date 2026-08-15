from pathlib import Path

import server


ROOT = Path(__file__).parents[2]


def test_dispatch_teaches_field_mapping_and_preservation_for_every_branch():
    message = server.build_mazda_scan_message(
        "/scans/support.jpg", "Window Scanner",
        {"ok": False, "doc_kind": "unknown", "confidence": 0},
    )

    assert "Receipt → receipt_url" in message
    assert "downloaded from the bank → document_url" in message
    assert "statement scanned from paper → scanned_statement_url" in message
    assert "Mom’s ledger → moms_ledger" in message
    assert "MUST NEVER be stored in document_url" in message
    assert "preserve the other three document fields" in message
    assert "View Receipt" in message
    assert "View Source Document" in message
    assert "View Scanned Statement" in message
    assert "View Mom’s Ledger" in message
    assert "fallback is only for repairing legacy rows" in message
    assert "If duplicate → STILL run STEP 4 exactly once" in message
    assert "rename the scan" in message
    assert "receipt_archive_path" in message
    assert '"archive_paths":[' in message


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
    assert "duplicate-safe save is what files the" in instructions
    assert "transient `incoming_scans` reference is not durable evidence" in instructions


def test_trainer_grades_the_red_box_without_blaming_mazda_for_it():
    instructions = (
        ROOT / "dashboard/trainer/mazda_trainer_instructions.md"
    ).read_text()

    assert "THE RED BOX IS PART OF THE CONTRACT TOO" in instructions
    assert "document_annotation.py" in instructions
    assert "/supporting-document/<expense_id>/receipt" in instructions
    assert "/supporting-document/<expense_id>/source" in instructions
    assert "include every child ID" in instructions
    assert "STEP 8 reports only the" in instructions
    assert "preserve every visible line date" in instructions
    assert "Grade every returned child's date" in instructions
    assert "opened without highlight" in instructions
    # The box is dashboard code, so coaching Mazda about it would teach her to
    # "fix" a defect she cannot cause by editing rows that are already correct.
    assert "never suggest re-storing or" in instructions
    assert "file it as a dashboard defect" in instructions


def test_trainer_runner_enforces_red_box_results_before_publishing_status():
    runner = (
        ROOT / "dashboard/trainer/run_mazda_trainer.mjs"
    ).read_text()

    assert 'from "./red-box-gate.ts"' in runner
    assert "collectExpenseIds" in runner
    assert "auditRedBoxesForRun" in runner
    assert "applyRedBoxAuditToReport" in runner
    assert "await enforceDeterministicRedBoxGate(args);" in runner
    assert runner.index("await enforceDeterministicRedBoxGate(args);") < runner.index(
        "await notifyDashboardStatus(args);"
    )


def test_trainer_claude_attempt_has_an_enforceable_deadline():
    """claude-code-sdk-ts@0.3.3 stores .withTimeout() and never reads it, so only
    .withSignal() can stop a stuck `claude` child. Without a real deadline a hung
    session parks the watchdog forever: no retry, no codex fallback, no emergency
    report, no /api/intake-status — the intake silently stays unverified."""
    runner = (
        ROOT / "dashboard/trainer/run_mazda_trainer.mjs"
    ).read_text()

    assert 'from "./claude-attempt.ts"' in runner
    claude_attempt = runner[runner.index("async function runClaudeAttempt"):
                            runner.index("async function runCodexAttempt")]
    assert "runWithAbortTimeout" in claude_attempt
    assert ".withSignal(signal)" in claude_attempt
    # .withTimeout() alone is not a deadline. Dropping it entirely (as the
    # runner does) satisfies that; keeping it is only allowed alongside the
    # signal. What must never happen is .withTimeout() as the sole guard.
    if ".withTimeout(" in claude_attempt:
        assert ".withSignal(signal)" in claude_attempt


def test_developer_manual_contains_four_field_contract():
    manual = (ROOT / "notes_plans_handoffs/mazda_dev_status.html").read_text()

    assert "receipt_url" in manual
    assert "document_url" in manual
    assert "scanned_statement_url" in manual
    assert "moms_ledger" in manual
    assert "supporting-document" in manual.lower()
    assert "repeated incoming scan" in manual
    assert "Set Category evidence visibility" in manual
    assert "View Source Document" in manual
    assert "report directory only to keep legacy records usable" in manual
