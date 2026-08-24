"""The shape of a quota window, and how a window is labelled and dated.

A "window" is one row of the Model Stats card: a used-percentage, when it
resets, and how long that is in words. Three providers produce them from three
unrelated payloads, so the shape is declared once here rather than assembled
ad-hoc in each branch of the reader.

`UsageWindow` is dumped back to a plain dict before it reaches the payload.
That is deliberate: the JSON the browser receives is unchanged, while the
construction sites gain a spelling check. A window that reaches the frontend
missing `resets_in`, or carrying `used_pct` instead of `used_percent`, renders
as a blank bar with no error anywhere -- which is exactly the failure this
model makes impossible.
"""

from __future__ import annotations

import time
from typing import Optional

from pydantic import BaseModel, ConfigDict


class UsageWindow(BaseModel):
    """One quota window on a Model Stats card.

    `used_percent` is Optional rather than defaulted to 0 because "we could not
    read this window" and "this window is at 0%" are different facts, and the
    frontend draws them differently. A window that is genuinely absent -- the
    5-hour cap OpenAI paused in 2026-07 -- sets `unavailable` and explains
    itself in `note` instead of quietly reading as an empty bar.
    """

    model_config = ConfigDict(extra='forbid')

    label: str
    used_percent: Optional[float] = None
    resets_at: Optional[object] = None
    resets_in: Optional[str] = None
    unavailable: bool = False
    note: Optional[str] = None

    def to_payload(self) -> dict:
        """The dict the card actually receives.

        `unavailable` and `note` are dropped when unset so an ordinary window
        serialises to exactly the four keys it always has -- the frontend
        treats the mere presence of `unavailable` as meaningful.
        """
        out = {
            'label': self.label,
            'used_percent': self.used_percent,
            'resets_at': self.resets_at,
            'resets_in': self.resets_in,
        }
        if self.unavailable:
            out['unavailable'] = True
        if self.note is not None:
            out['note'] = self.note
        return out


def _human_reset(when):
    """'in 3h 12m' / 'in 5d 2h' from a reset time (Unix epoch OR ISO-8601 string)."""
    if not when:
        return None
    if isinstance(when, str):
        try:
            from datetime import datetime
            when = datetime.fromisoformat(when.replace('Z', '+00:00')).timestamp()
        except Exception:
            return None
    secs = int(when - time.time())
    if secs <= 0:
        return 'now'
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f'in {d}d {h}h'
    if h:
        return f'in {h}h {m}m'
    return f'in {m}m'

# Codex rate-limit windows are labeled by their duration (limit_window_seconds),
# not by position in the payload, so a single-window response still labels correctly.
_CODEX_WINDOW_ORDER = {'5-hour': 0, 'weekly': 1}

def _codex_window_label(seconds):
    try:
        s = int(seconds or 0)
    except (TypeError, ValueError):
        s = 0
    if s <= 0:
        return 'usage'
    if s <= 6 * 3600:       # ~5-hour window (18000s), allow slack
        return '5-hour'
    if s <= 8 * 86400:      # ~weekly window (604800s)
        return 'weekly'
    days = round(s / 86400)
    return f'{days}-day'
