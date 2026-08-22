#!/usr/bin/env python3
"""Record lightweight Letta conversation anchors from hook payloads.

This hook intentionally stores identifiers and short prompt previews only. The
conversation API/history remains the source of truth for reconstructing a
thread.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_PREVIEW = 240
DEFAULT_JOURNAL = Path.home() / ".letta" / "conversation-journal.jsonl"
_SECRET_PATTERN = re.compile(
    r"(?i)(api[_ -]?key|token|password|secret|authorization)\s*[:=]\s*[^\s,;]+"
)


def journal_path() -> Path:
    configured = os.environ.get("LETTA_CONVERSATION_JOURNAL")
    return Path(configured).expanduser() if configured else DEFAULT_JOURNAL


def sanitize_preview(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    value = _SECRET_PATTERN.sub(r"\1=[REDACTED]", value)
    value = " ".join(value.split())
    return value[:MAX_PREVIEW]


def build_record(payload: dict[str, Any], now: datetime | None = None) -> dict[str, Any] | None:
    conversation_id = payload.get("conversation_id")
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        return None
    timestamp = (now or datetime.now(timezone.utc)).isoformat()
    record: dict[str, Any] = {
        "conversation_id": conversation_id,
        "agent_id": payload.get("agent_id") if isinstance(payload.get("agent_id"), str) else None,
        "event_type": payload.get("event_type") if isinstance(payload.get("event_type"), str) else "unknown",
        "last_seen_at": timestamp,
    }
    preview = sanitize_preview(payload.get("prompt"))
    if preview:
        record["prompt_preview"] = preview
    return record


def update_journal(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    if path.exists():
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict) and isinstance(value.get("conversation_id"), str):
                    records.append(value)
        except OSError:
            return

    for existing in records:
        if existing.get("conversation_id") == record["conversation_id"]:
            existing.update(record)
            break
    else:
        records.append(record)

    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(
            "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in records),
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        if isinstance(payload, dict):
            record = build_record(payload)
            if record:
                update_journal(journal_path(), record)
    except (json.JSONDecodeError, OSError, TypeError):
        # Hooks must never block a conversation because journaling failed.
        pass


if __name__ == "__main__":
    main()
