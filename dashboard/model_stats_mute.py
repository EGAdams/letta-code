"""Per-source Model Stats warning silencer.

Lets EG mute a source's tab-blinking concern/down warning (e.g. R46's Codex
OAuth deliberately parked unused, so its quota-exhaustion warning is noise,
not a real problem) without hiding that source's actual usage data on its
detail card — muting only downgrades the *status* used for tab coloring.

Persisted as a flat {source_key: true} JSON file so a mute survives a
dashboard restart. Deliberately doesn't import MODEL_STAT_SOURCES from
server.py (which would be circular) — `source` is just whatever key the
caller already validated against that registry.
"""

from __future__ import annotations

import json
import os
import threading

from contracts import StrictModel

MODEL_STATS_MUTE_FILE = os.path.expanduser('~/.mazda/model_stats_muted.json')
_lock = threading.Lock()


class ModelStatsMuteRequest(StrictModel):
    """Body of POST /api/model-stats-mute."""

    source: str
    muted: bool


def _read() -> dict[str, bool]:
    try:
        with open(MODEL_STATS_MUTE_FILE, encoding='utf-8') as fh:
            data = json.load(fh)
        return {k: True for k, v in data.items() if v}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write(state: dict[str, bool]) -> None:
    os.makedirs(os.path.dirname(MODEL_STATS_MUTE_FILE), exist_ok=True)
    tmp = f'{MODEL_STATS_MUTE_FILE}.tmp.{os.getpid()}'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(state, fh)
    os.replace(tmp, MODEL_STATS_MUTE_FILE)


def is_muted(source: str) -> bool:
    return _read().get(source, False)


def set_muted(source: str, muted: bool) -> bool:
    """Set the mute flag for `source`; returns the resulting value."""
    with _lock:
        state = _read()
        if muted:
            state[source] = True
        else:
            state.pop(source, None)
        _write(state)
    return muted


def apply_mute_overlay(out: dict, source: str) -> dict:
    """Return a copy of a model_stats() payload with `muted` attached and,
    while muted, the tab-facing `status` downgraded to 'up' so it stops
    blinking — the real status/detail/windows underneath are untouched, so
    the detail card still shows what's actually going on."""
    view = dict(out)
    muted = is_muted(source)
    view['muted'] = muted
    if muted and view.get('status') in ('concern', 'down'):
        view['raw_status'] = view['status']
        view['status'] = 'up'
    return view
