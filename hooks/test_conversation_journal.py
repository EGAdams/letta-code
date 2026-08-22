import json
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from conversation_journal import build_record, update_journal


def test_build_record_keeps_id_and_redacts_preview():
    record = build_record(
        {
            "event_type": "UserPromptSubmit",
            "conversation_id": "conv-test",
            "agent_id": "agent-test",
            "prompt": "Please use api_key=super-secret and remember this thread",
        },
        datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    assert record == {
        "conversation_id": "conv-test",
        "agent_id": "agent-test",
        "event_type": "UserPromptSubmit",
        "last_seen_at": "2026-01-02T00:00:00+00:00",
        "prompt_preview": "Please use api_key=[REDACTED] and remember this thread",
    }


def test_update_journal_deduplicates_conversation(tmp_path):
    path = tmp_path / "conversation-journal.jsonl"
    update_journal(path, {"conversation_id": "conv-test", "event_type": "SessionStart"})
    update_journal(path, {"conversation_id": "conv-test", "event_type": "UserPromptSubmit"})
    update_journal(path, {"conversation_id": "conv-other", "event_type": "SessionStart"})

    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows == [
        {"conversation_id": "conv-test", "event_type": "UserPromptSubmit"},
        {"conversation_id": "conv-other", "event_type": "SessionStart"},
    ]


def test_build_record_ignores_missing_id():
    assert build_record({"event_type": "SessionStart"}) is None
