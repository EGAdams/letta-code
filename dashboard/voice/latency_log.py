"""Durable sink for ConversationLatencyObserver's per-turn timing reports.

The browser (dashboard/js/abstract/conversation_latency_observer/) posts one
LatencyReport per conversational turn to /api/latency-log. This is the
durable sink the module's README flags as a follow-up, and the Phase 0
latency baseline the voice-communication plan needs before a Pipecat
go/no-go decision — see dashboard/js/plans/voice-communication/specs/.
"""

import json
import os
import threading
from datetime import datetime

LOG_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'voice_latency.json'))
_lock = threading.Lock()
_MAX_ENTRIES = 200


def _load():
    try:
        with open(LOG_FILE, 'r') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []


def append(report):
    """Append one LatencyReport dict, keeping only the most recent entries."""
    with _lock:
        rows = _load()
        rows.append({'received_at': datetime.now().isoformat(), **report})
        if len(rows) > _MAX_ENTRIES:
            rows = rows[-_MAX_ENTRIES:]
        with open(LOG_FILE, 'w') as f:
            json.dump(rows, f, indent=2)


def recent(limit=200):
    """Return up to `limit` most recent reports, newest last."""
    rows = _load()
    return rows[-limit:]
