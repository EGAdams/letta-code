"""Reads the latest rate-limit sample from a Codex CLI rollout log.

Rollout files are append-only JSONL and can grow past several megabytes in
one session (the 2026-09-07 incident's was 6.7MB / 866 lines). Re-parsing
the whole file on every 60s poll would mean chewing through megabytes of
transcript just to read one number, so this seeks from the end instead and
only looks at the last `_MAX_TAIL_BYTES`.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from health.codex_watchdog_contracts import CodexUsageSample, ICodexSessionReader

#: Large enough to comfortably contain the last `token_count` event even
#: after a big tool-output turn; small enough to stay a cheap read.
_MAX_TAIL_BYTES = 4 * 1024 * 1024


def _tail_lines(path: str, max_bytes: int = _MAX_TAIL_BYTES):
    with open(path, 'rb') as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        read_from = max(0, size - max_bytes)
        handle.seek(read_from)
        data = handle.read()
    lines = data.split(b'\n')
    if read_from > 0:
        lines = lines[1:]  # the first line may be a truncated fragment
    return [line for line in lines if line.strip()]


def _sample_from_event(session_path: str, event: dict) -> Optional[CodexUsageSample]:
    if event.get('type') != 'event_msg':
        return None
    payload = event.get('payload')
    if not isinstance(payload, dict) or payload.get('type') != 'token_count':
        return None
    limits = payload.get('rate_limits')
    if not isinstance(limits, dict):
        return None
    primary = limits.get('primary') or {}
    secondary = limits.get('secondary') or {}
    if 'used_percent' not in primary:
        return None
    try:
        observed_at = os.path.getmtime(session_path)
    except OSError:
        observed_at = 0.0
    return CodexUsageSample(
        session_path=session_path,
        observed_at=observed_at,
        primary_used_percent=float(primary.get('used_percent', 0.0)),
        primary_window_minutes=int(primary.get('window_minutes', 300)),
        secondary_used_percent=float(secondary.get('used_percent', 0.0)),
        secondary_window_minutes=int(secondary.get('window_minutes', 10080)),
        resets_at=primary.get('resets_at'),
    )


class RolloutFileSessionReader(ICodexSessionReader):
    """Real implementation: tails one rollout `.jsonl` file."""

    def usage_for(self, session_path: str) -> Optional[CodexUsageSample]:
        try:
            lines = _tail_lines(session_path)
        except OSError:
            return None
        for raw in reversed(lines):
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            sample = _sample_from_event(session_path, event)
            if sample is not None:
                return sample
        return None
