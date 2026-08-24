"""Reading one account's token usage and turning it into a card.

Three providers, three unrelated payloads, one shape on the way out. The
branches in `_model_stats_uncached` are the only place that knows a Codex
`rate_limit` block from a Claude `five_hour` block from a Gemini request
count.

The part worth reading carefully is the failure path. A card with no usage on
it has to say *why* in terms the reader can act on, and the honest source of
that answer is the extractor, which is the only party that observed the
condition -- `condition` in the payload, not a pattern grepped out of the
error text. Inferring it from the text is how a logged-out host came to be
reported as a throttle: an unauthenticated request draws a 429 from
Anthropic's edge, and "429 is in the string" was the only evidence anyone
looked at.
"""

from __future__ import annotations

import time

from model_stats.extractors import (
    _CLAUDE_EXTRACT_PY,
    _CODEX_EXTRACT_PY,
    _GEMINI_FLASH_FILL_EXTRACT_PY,
    _run_extractor,
)
from model_stats.last_good import (
    _restore_model_stats_last_good,
    _save_model_stats_last_good,
)
from model_stats.sources import MODEL_STAT_SOURCES
from model_stats.usage_history import _attach_usage_metrics
from model_stats.windows import (
    _CODEX_WINDOW_ORDER,
    _codex_window_label,
    _human_reset,
    UsageWindow,
)

_model_stats_cache = {}   # key → (timestamp, result)
MODEL_STATS_CACHE_TTL = 120  # seconds – prevent 429s from rapid polling


def model_stats(source_key):
    """Build the Model Stats payload for one source: provider/model, usage windows
    (used_percent + reset), a tokens summary, and a status (up/concern/down) so the
    tab can go red at 100%."""
    cached = _model_stats_cache.get(source_key)
    if cached and time.time() - cached[0] < MODEL_STATS_CACHE_TTL:
        return cached[1]
    src = MODEL_STAT_SOURCES.get(source_key)
    if not src:
        return {'ok': False, 'error': f'unknown source {source_key}'}
    out = _model_stats_uncached(source_key, src)
    if src.kind == 'claude':
        if out.get('windows'):
            _save_model_stats_last_good(source_key, out)
        elif out.get('rate_limited'):
            _restore_model_stats_last_good(source_key, out)
    try:
        _attach_usage_metrics(source_key, out)   # rate-of-change bar + leak detector
    except Exception as e:
        print(f'[model-usage] {source_key} attach failed: {e}')
    _model_stats_cache[source_key] = (time.time(), out)
    return out


def _looks_rate_limited(err):
    t = str(err).lower()
    return ('429' in t or 'rate limit' in t or 'rate_limit' in t
            or 'too many requests' in t)


def _fill_rate_limited(out, d, err, severity='down'):
    """A provider-side 429 means the endpoint we polled is throttled. For
    Codex/Antigravity that endpoint IS the account's real quota meter, so a
    429 there really does mean 'you cannot use this provider right now'
    (severity='down', red). Claude's usage check hits a separate, much
    stricter usage-stats endpoint (api/oauth/usage) that throttles on its own
    schedule independent of the actual chat/completion API — repeated polling
    (e.g. manual diagnostics) can trip it while Claude itself works fine. That
    case passes severity='concern' (yellow) so the tile doesn't falsely claim
    the whole OAuth connection is dead. Surface the reset as an absolute
    epoch either way so the frontend can render a live countdown."""
    out['status'] = severity
    out['rate_limited'] = True
    retry_after = d.get('retry_after')
    if retry_after:
        until = (d.get('as_of') or time.time()) + retry_after
        out['rate_limited_until'] = until
        out['detail'] = f'RATE LIMITED ({err}) — resets {_human_reset(until)}'
    else:
        out['detail'] = f'RATE LIMITED ({err}) — reset time not reported'
    if severity == 'concern':
        out['detail'] = f'usage stats {out["detail"]} (Claude itself may still work — this only throttles quota reporting)'
    return out


def _looks_like_login_problem(err):
    t = str(err).lower()
    return 'expired' in t or 'token' in t or 'unauthor' in t or '401' in t


def _failure_condition(d, err):
    """Name the condition behind a usage-less extractor payload.

    The extractor is the only party that actually observes the condition, so it
    SHOULD name one in `condition`. Payloads that don't (the Codex extractor,
    older mocks) fall back to inferring it from the error text — which is how a
    logged-out host used to be mistaken for a throttle: an unauthenticated
    request gets a 429 from Anthropic's edge, and '429' in the string was the
    only evidence anyone looked at. New failure modes belong in the extractor,
    named, rather than as another pattern to grep for here."""
    return d.get('condition') or ('rate_limited' if _looks_rate_limited(err) else 'unknown')


def _fill_extractor_failure(out, src, d, rate_limit_severity='down', login_hint=''):
    """Explain, in terms the reader can act on, why a source reported no usage.

    Shared by every OAuth-backed source so a new condition is described once
    instead of once per provider. `rate_limit_severity` is the provider's own
    judgement of what a 429 means for it (see _fill_rate_limited)."""
    err = d.get('error') or 'no data'
    condition = _failure_condition(d, err)

    if condition == 'rate_limited':
        return _fill_rate_limited(out, d, err, severity=rate_limit_severity)

    if condition == 'logged_out':
        # Neither a quota problem nor self-healing: the credential file is
        # present but empty, and only an interactive login on that host
        # restores it. Red, and it names the command.
        out['status'] = 'down'
        out['logged_out'] = True
        where = src.host or 'this box'
        out['detail'] = f'LOGGED OUT — no OAuth token on {where}. Fix: {login_hint or "log in on that host"}.'
        return out

    out['status'] = 'concern'
    hint = f' — {login_hint}' if login_hint and _looks_like_login_problem(err) else ''
    out['detail'] = f'usage unavailable: {err}{hint}'
    return out


def _model_stats_uncached(source_key, src):
    out = {'ok': True, 'key': source_key, 'label': src.label, 'kind': src.kind,
           'windows': [], 'status': 'up', 'detail': ''}

    if src.kind == 'codex':
        d = _run_extractor(_CODEX_EXTRACT_PY, src.host, timeout=35)
        out['model'] = d.get('model')
        out['as_of'] = d.get('as_of')
        u = d.get('usage') or {}
        if d.get('error') or not u:
            return _fill_extractor_failure(out, src, d, rate_limit_severity='down',
                                           login_hint='run `codex login` there')
        rl = u.get('rate_limit') or {}
        out['detail'] = f'plan: {u.get("plan_type", "?")}'
        worst = 0.0
        # Label each window by its actual duration (limit_window_seconds), NOT by
        # position: Codex sometimes returns only the weekly window in
        # primary_window with secondary_window null, so the old positional
        # ('primary'→5-hour, 'secondary'→weekly) mapping mislabeled the weekly bar
        # as "5-hour" and dropped the weekly bar entirely.
        for wkey, fallback_label in (
                ('primary_window', '5-hour'),
                ('secondary_window', 'weekly')):
            w = rl.get(wkey)
            if not isinstance(w, dict):
                continue
            up = float(w.get('used_percent') or 0)
            worst = max(worst, up)
            seconds = w.get('limit_window_seconds')
            out['windows'].append(UsageWindow(
                # Current payloads identify windows by duration. Retain the
                # old positional labels only for legacy/mocked payloads that
                # omit it, instead of producing two generic "usage" rows.
                label=(_codex_window_label(seconds)
                       if seconds is not None else fallback_label),
                used_percent=round(up, 1),
                resets_at=w.get('reset_at'),
                resets_in=_human_reset(w.get('reset_at')),
            ).to_payload())
        # OpenAI temporarily removed the rolling 5-hour Codex cap on Plus/Pro/
        # Business tiers on 2026-07-12 (following the GPT-5.6 Sol launch), so
        # wham/usage now returns secondary_window: null — there's genuinely no
        # 5-hour data to show, not a bug on our end. Insert a placeholder row
        # for parity with the Claude card, which always shows both windows;
        # flip back to real data automatically once OpenAI restores the window.
        if not any(x['label'] == '5-hour' for x in out['windows']):
            out['windows'].append(UsageWindow(
                label='5-hour', unavailable=True,
                note='OpenAI paused the 5-hour cap 2026-07-12 (weekly-only, for now)',
            ).to_payload())
        out['windows'].sort(key=lambda x: _CODEX_WINDOW_ORDER.get(x['label'], 99))
        if rl.get('limit_reached') or worst >= 100:
            out['status'] = 'down'        # maxed → red, with reset shown
        elif worst >= 80:
            out['status'] = 'concern'     # getting close → yellow
        return out

    if src.kind == 'claude':
        d = _run_extractor(_CLAUDE_EXTRACT_PY, src.host, timeout=35)
        out['as_of'] = d.get('as_of')
        out['model'] = d.get('recent_model') or 'Claude subscription'
        u = d.get('usage') or {}
        if d.get('error') or not u:
            return _fill_extractor_failure(out, src, d, rate_limit_severity='concern',
                                           login_hint='run `claude` there and complete /login')
        worst = 0.0
        for key, label in (('five_hour', '5-hour'), ('seven_day', 'weekly')):
            w = u.get(key) or {}
            up = float(w.get('utilization') or 0)
            worst = max(worst, up)
            out['windows'].append(UsageWindow(
                label=label,
                used_percent=round(up, 1),
                resets_at=w.get('resets_at'),
                resets_in=_human_reset(w.get('resets_at')),
            ).to_payload())
        eu = u.get('extra_usage') or {}
        if eu.get('is_enabled'):
            out['detail'] = f'extra usage {round(eu.get("utilization", 0))}% of ${eu.get("monthly_limit")}'
        else:
            out['detail'] = 'subscription (5h + weekly)'
        if worst >= 100:
            out['status'] = 'down'
        elif worst >= 80:
            out['status'] = 'concern'
        return out

    if src.kind == 'gemini':
        # Tracks the Gemini API key ("Gemini Flash Fill" button's engine),
        # not Antigravity CLI -- see _GEMINI_FLASH_FILL_EXTRACT_PY's comment
        # for why those are different Google products.
        d = _run_extractor(_GEMINI_FLASH_FILL_EXTRACT_PY, src.host, timeout=15)
        out['model'] = 'gemini-2.5-flash (receipts)'
        if d.get('error') or not d.get('configured'):
            out['status'] = 'concern'
            out['detail'] = f'usage unavailable: {d.get("error", "no data")}'
            return out
        limit = d.get('limit') or 250
        used = d.get('used') or 0
        up = (100.0 * used / limit) if limit else 0.0
        out['windows'].append(UsageWindow(
            label='daily requests',
            used_percent=round(up, 1),
            resets_at=d.get('resets_at'),
            resets_in=_human_reset(d.get('resets_at')),
        ).to_payload())
        # Unlike Antigravity's real Google-reported tier/limit, this "limit" is
        # a locally-configured estimate (no usage-query endpoint exists for a
        # bare API key) -- said plainly here so it never reads as authoritative.
        out['detail'] = f'{used}/{limit} requests today (estimate, self-tracked)'
        if up >= 100:
            out['status'] = 'down'
        elif up >= 80:
            out['status'] = 'concern'
        return out

    return out
