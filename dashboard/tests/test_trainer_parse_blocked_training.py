"""Pins the Trainer curriculum for fail-closed parse evidence."""

from pathlib import Path


INSTRUCTIONS = (
    Path(__file__).parents[1] / "trainer" / "mazda_trainer_instructions.md"
).read_text(encoding="utf-8")


def test_parse_blocked_is_terminal_not_missing_downstream_work():
    assert "`parse_blocked:true`" in INSTRUCTIONS
    assert "Vendor resolution" in INSTRUCTIONS
    assert "NOT APPLICABLE" in INSTRUCTIONS
    assert "`NEEDS_REVIEW`, `failure_type=none`" in INSTRUCTIONS


def test_callback_identity_is_mandatory_even_when_nothing_was_stored():
    assert "including `stored:0`" in INSTRUCTIONS
    assert "`document_path` (or `receipt_url`)" in INSTRUCTIONS
    assert "`conversation_id`" in INSTRUCTIONS
    assert "`dispatched_at`" in INSTRUCTIONS
    assert "Uncorrelated callbacks" in INSTRUCTIONS


def test_report_separates_visible_print_from_trustworthy_parse_evidence():
    assert "human-visible print" in INSTRUCTIONS
    assert "machine-trustworthy evidence" in INSTRUCTIONS
    assert "do not claim all" in INSTRUCTIONS
    assert "arithmetic was unreadable" in INSTRUCTIONS

