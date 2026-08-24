"""Keeping the last real quota reading, so a throttle cannot erase the bars.

Claude's usage endpoint throttles on its own schedule, independently of
whether Claude itself works. When it does, the reading comes back with no
windows at all -- and a card that drops from "68% weekly" to an empty bar
reads as "your quota is fine", which is the opposite of the truth. So the
last reading that *did* have windows is written to disk and put back on the
error response, flagged `windows_stale` so the frontend can grey it.

Only the bars are persisted: labels, percentages and reset times. No tokens,
no account identifiers, nothing an extractor read out of a credential file.
"""

from __future__ import annotations

import json
import os
import threading
import time

from model_stats.usage_history import MODEL_USAGE_HISTORY_FILE

MODEL_STATS_LAST_GOOD_FILE = os.environ.get(
    'MODEL_STATS_LAST_GOOD_FILE', '/tmp/dashboard_model_stats_last_good.json')
_model_stats_last_good_lock = threading.Lock()


def _save_model_stats_last_good(source_key, out):
    """Persist non-secret quota bars so a transient stats 429 cannot erase them."""
    if not out.get('windows'):
        return
    with _model_stats_last_good_lock:
        try:
            data = {}
            if os.path.isfile(MODEL_STATS_LAST_GOOD_FILE):
                with open(MODEL_STATS_LAST_GOOD_FILE, encoding='utf-8') as fh:
                    data = json.load(fh)
            data[source_key] = {
                'windows': out['windows'],
                'model': out.get('model'),
                'as_of': out.get('as_of') or time.time(),
            }
            tmp = f'{MODEL_STATS_LAST_GOOD_FILE}.tmp.{os.getpid()}'
            with open(tmp, 'w', encoding='utf-8') as fh:
                json.dump(data, fh)
            os.replace(tmp, MODEL_STATS_LAST_GOOD_FILE)
        except Exception as exc:
            print(f'[model-stats] could not save last-good snapshot: {exc}')


def _restore_model_stats_last_good(source_key, out):
    """Add the last real quota bars to an otherwise bar-less error response."""
    if out.get('windows'):
        return out
    with _model_stats_last_good_lock:
        try:
            with open(MODEL_STATS_LAST_GOOD_FILE, encoding='utf-8') as fh:
                saved = (json.load(fh) or {}).get(source_key) or {}
        except (OSError, ValueError, TypeError):
            saved = {}
    if not saved.get('windows'):
        # Older dashboard versions persisted only the primary usage percentage
        # for burn-rate history. Use that real reading after an upgrade/restart
        # until the next successful live response seeds both quota windows.
        try:
            with open(MODEL_USAGE_HISTORY_FILE, encoding='utf-8') as fh:
                history = (json.load(fh) or {}).get(source_key) or []
            sampled_at, used_percent = history[-1]
            saved = {
                'as_of': sampled_at,
                'windows': [
                    {'label': '5-hour', 'used_percent': used_percent,
                     'resets_at': None, 'resets_in': None},
                    {'label': 'weekly', 'used_percent': None,
                     'resets_at': None, 'resets_in': None,
                     'unavailable': True,
                     'note': 'waiting for the next successful live reading'},
                ],
            }
        except (OSError, ValueError, TypeError, IndexError):
            return out
    out['windows'] = saved['windows']
    out['model'] = out.get('model') or saved.get('model')
    out['usage_as_of'] = saved.get('as_of')
    out['windows_stale'] = True
    return out
