"""Usage history, the burn-rate bar, and the slow-leak detector.

Split out of server.py because none of it touches the server: the two
calculators are pure functions of a sample list, and the recorder owns one
file and one lock. What stays in server.py is the wiring -- the background
sampler needs a way to fetch a reading, and that is injected rather than
imported, because the reader imports this module and importing it back would
close the loop.

Rate metric (first version, deliberately simple): percentage-POINTS of the
source's PRIMARY quota window (windows[0]: the 5-hour window for Codex and
Claude, the daily request count for Antigravity) consumed per hour, measured
over the last RATE_WINDOW_MINUTES of snapshots. This borrows the SRE
"error-budget burn rate" idea (sre.google/workbook/alerting-on-slos): a quota
window spanning H hours replenishes at 100/H %-points per hour, so

    burn_multiple = observed %-points/hour ÷ (100 / window_hours)

burn 1.0x = spending exactly as fast as the window refills — sustainable
forever; anything above 1.0x will eventually max the account out. That makes
the numbers comparable across providers with different window sizes, and it
gives the thresholds real meaning instead of magic numbers:

  RATE_WARN_BURN_MULTIPLE (default 1.0)  — the bar blinks yellow when the
      last half-hour burned faster than the window replenishes. Interactive
      coding legitimately bursts past 1.0x, so expect blinks during heavy
      use; the point is "on pace to hit the cap", not "something is broken".
      Raise it (e.g. 1.5–2.0) if it blinks too often in practice.
  RATE_BAR_FULL_SCALE_MULTIPLE (default 2.0) — the bar renders 100% wide at
      this burn multiple, so HALF a bar always means "sustainable pace".

Leak detector (slow drain): the rate bar only sees the last 30 minutes, so a
slow drip can hide under bursty-but-legit use — the 2026-07-07 provider-probe
ping loop burned ~1.1x sustainable for HOURS and never looked dramatic in
any 30-minute slice. Following the SRE multiwindow pattern (short window
catches fast burns, long window catches slow ones), we also look back
LEAK_LOOKBACK_MINUTES, split the history into LEAK_BUCKET_MINUTES buckets,
and flag "slow token drain" when usage rose at least LEAK_MIN_RISE_PCT
%-points in LEAK_MIN_RISING_BUCKETS CONSECUTIVE buckets. A single burst
(one busy bucket, flat elsewhere) does NOT flag. This first version cannot
know whether a task *should* be running, so a genuine 2-hour work session
will also flag — acceptable for an early-warning light; tune below.

History comes from two feeds through the same recording point
(_attach_usage_metrics, called on every model-stats cache miss): the UI's
120s poll while the tab is open, plus _model_usage_sample_loop in the
background so the 2h lookback exists even when nobody is watching. Snapshots
persist to MODEL_USAGE_HISTORY_FILE so a dashboard restart doesn't blind the
leak detector. Known first-version quirks (documented, not bugs): a rolling
window's used_percent can FALL as old usage ages out — negative deltas clamp
to 0; an Adam<->mom token swap jumps the percentage discontinuously and may
cause one false warning cycle.

"""

from __future__ import annotations

import json
import os
import threading
import time

from pydantic import BaseModel, ConfigDict

from model_stats.sources import MODEL_STAT_SOURCES



class UsageRate(BaseModel):
    """The burn-rate bar: how fast this window is being spent, and whether
    that pace is sustainable.

    Two disjoint shapes share one model. Before there are enough snapshots
    there is no rate at all, only a reason -- and the frontend must not draw a
    0%-wide bar for that case, which is what a defaulted numeric field would
    have produced. `available` is the discriminator; everything else stays
    None until it is True.
    """

    model_config = ConfigDict(extra='forbid')

    available: bool
    reason: str | None = None
    pct_per_hour: float | None = None
    burn_multiple: float | None = None
    sustainable_pct_per_hour: float | None = None
    bar_percent: int | None = None
    warn: bool | None = None
    warn_at_multiple: float | None = None
    window_minutes: int | None = None
    #: Which quota window the rate was measured against. Attached by the
    #: caller after the fact, so it is absent from the pure result.
    window_label: str | None = None

    def to_payload(self) -> dict:
        """Only the keys this shape actually carries, so an unavailable rate
        stays the two-key object the frontend already expects."""
        return self.model_dump(exclude_none=True)


class LeakVerdict(BaseModel):
    """The slow-drain verdict, with the evidence behind it.

    The counts are not decoration: `consecutive_rising` vs
    `needed_consecutive` is what makes a false positive diagnosable rather
    than mysterious, and both are printed on every fetch.
    """

    model_config = ConfigDict(extra='forbid')

    suspected: bool
    rising_buckets: int
    consecutive_rising: int
    buckets_evaluated: int
    needed_consecutive: int
    total_rise_pct: float
    #: Empty unless suspected -- the frontend shows the banner iff this is set.
    text: str = ''

    def to_payload(self) -> dict:
        return self.model_dump()

def _env_float(name, default):
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


MODEL_USAGE_SAMPLE_INTERVAL = _env_int('MODEL_USAGE_SAMPLE_INTERVAL', 300)         # s between background snapshots
RATE_WINDOW_MINUTES = _env_int('MODEL_RATE_WINDOW_MINUTES', 30)                    # rate looks at the last N minutes
RATE_MIN_SPAN_MINUTES = _env_int('MODEL_RATE_MIN_SPAN_MINUTES', 5)                 # need >= this span before showing a rate
RATE_WARN_BURN_MULTIPLE = _env_float('MODEL_RATE_WARN_BURN_MULTIPLE', 1.0)         # blink yellow above this burn multiple
RATE_BAR_FULL_SCALE_MULTIPLE = _env_float('MODEL_RATE_BAR_FULL_SCALE', 2.0)        # bar is 100% wide at this burn multiple
LEAK_BUCKET_MINUTES = _env_int('MODEL_LEAK_BUCKET_MINUTES', 30)
LEAK_LOOKBACK_MINUTES = _env_int('MODEL_LEAK_LOOKBACK_MINUTES', 120)
LEAK_MIN_RISE_PCT = _env_float('MODEL_LEAK_MIN_RISE_PCT', 0.5)                     # a bucket "rises" if it gains >= this
LEAK_MIN_RISING_BUCKETS = _env_int('MODEL_LEAK_MIN_RISING_BUCKETS', 3)             # consecutive rising buckets => leak
MODEL_USAGE_HISTORY_FILE = os.environ.get('MODEL_USAGE_HISTORY_FILE', '/tmp/model_usage_history.json')
MODEL_USAGE_HISTORY_KEEP_MINUTES = LEAK_LOOKBACK_MINUTES + 60                      # prune margin past the lookback

# windows[0] label → hours that quota window spans (drives the replenish rate).
# Unknown labels fall back to 5h, the most common primary window.
_WINDOW_HOURS = {'5-hour': 5.0, 'weekly': 168.0, 'daily requests': 24.0}
_DEFAULT_WINDOW_HOURS = 5.0

_usage_history_lock = threading.Lock()
_usage_history = None   # source_key → [[ts, pct], ...]; lazy-loaded from disk


def _load_usage_history():
    try:
        with open(MODEL_USAGE_HISTORY_FILE) as f:
            data = json.load(f)
        return {k: [list(map(float, s)) for s in v] for k, v in data.items()}
    except Exception:
        return {}


def _record_usage_sample(source_key, pct, now=None):
    """Append one (timestamp, used_percent) snapshot for a source, prune history
    older than the leak lookback (+margin), persist best-effort, and return a
    copy of the source's samples for the pure calculators below."""
    global _usage_history
    now = now if now is not None else time.time()
    with _usage_history_lock:
        if _usage_history is None:
            _usage_history = _load_usage_history()
        samples = _usage_history.setdefault(source_key, [])
        samples.append([now, float(pct)])
        cutoff = now - MODEL_USAGE_HISTORY_KEEP_MINUTES * 60
        while samples and samples[0][0] < cutoff:
            samples.pop(0)
        try:
            with open(MODEL_USAGE_HISTORY_FILE, 'w') as f:
                json.dump(_usage_history, f)
        except Exception:
            pass   # persistence is a nicety; in-memory history still works
        return [tuple(s) for s in samples]


def compute_usage_rate(samples, window_hours, now=None,
                       window_minutes=None, warn_multiple=None, full_scale=None):
    """Pure: %-points/hour consumed over the last window_minutes of samples,
    plus the burn multiple vs the window's replenish rate (see section comment
    for the math). Thresholds are parameters so tests don't depend on env."""
    now = now if now is not None else time.time()
    window_minutes = window_minutes if window_minutes is not None else RATE_WINDOW_MINUTES
    warn_multiple = warn_multiple if warn_multiple is not None else RATE_WARN_BURN_MULTIPLE
    full_scale = full_scale if full_scale is not None else RATE_BAR_FULL_SCALE_MULTIPLE
    recent = [s for s in samples if s[0] >= now - window_minutes * 60]
    if len(recent) < 2 or recent[-1][0] - recent[0][0] < RATE_MIN_SPAN_MINUTES * 60:
        return UsageRate(
            available=False,
            reason=f'gathering data (need ≥{RATE_MIN_SPAN_MINUTES} min of snapshots)',
        ).to_payload()
    span_hours = (recent[-1][0] - recent[0][0]) / 3600.0
    # Rolling windows decay: used_percent can drop as old usage ages out, which
    # is not "negative spending" — clamp to 0 instead of showing it.
    pct_per_hour = max(0.0, recent[-1][1] - recent[0][1]) / span_hours
    sustainable = 100.0 / window_hours          # replenish rate of this window
    burn = pct_per_hour / sustainable
    return UsageRate(
        available=True,
        pct_per_hour=round(pct_per_hour, 1),
        burn_multiple=round(burn, 2),
        sustainable_pct_per_hour=round(sustainable, 1),
        bar_percent=round(min(100.0, 100.0 * burn / full_scale)),
        warn=burn >= warn_multiple,
        warn_at_multiple=warn_multiple,
        window_minutes=window_minutes,
    ).to_payload()


def detect_slow_leak(samples, now=None, bucket_minutes=None, lookback_minutes=None,
                     min_rise_pct=None, min_rising_buckets=None):
    """Pure: flag a slow, steady token drain — usage rising in several
    CONSECUTIVE buckets across the long lookback, the pattern a background
    drip leaves and a single legitimate burst does not (see section comment)."""
    now = now if now is not None else time.time()
    bucket_minutes = bucket_minutes if bucket_minutes is not None else LEAK_BUCKET_MINUTES
    lookback_minutes = lookback_minutes if lookback_minutes is not None else LEAK_LOOKBACK_MINUTES
    min_rise_pct = min_rise_pct if min_rise_pct is not None else LEAK_MIN_RISE_PCT
    min_rising_buckets = min_rising_buckets if min_rising_buckets is not None else LEAK_MIN_RISING_BUCKETS
    n_buckets = max(1, lookback_minutes // bucket_minutes)
    longest_run = run = 0
    rising = evaluated = 0
    for i in range(n_buckets):                      # oldest bucket first
        end = now - (n_buckets - 1 - i) * bucket_minutes * 60
        start = end - bucket_minutes * 60
        inside = [s for s in samples if start <= s[0] < end]
        if len(inside) < 2:
            run = 0                                 # a data gap breaks "consecutive"
            continue
        evaluated += 1
        if inside[-1][1] - inside[0][1] >= min_rise_pct:
            rising += 1
            run += 1
            longest_run = max(longest_run, run)
        else:
            run = 0
    suspected = longest_run >= min_rising_buckets
    in_window = [s for s in samples if s[0] >= now - lookback_minutes * 60]
    total_rise = round(in_window[-1][1] - in_window[0][1], 1) if len(in_window) >= 2 else 0.0
    hours = lookback_minutes / 60
    return LeakVerdict(
        suspected=suspected,
        rising_buckets=rising,
        consecutive_rising=longest_run,
        buckets_evaluated=evaluated,
        needed_consecutive=min_rising_buckets,
        total_rise_pct=total_rise,
        text=(f'Slow token drain — +{total_rise}% over last {hours:g}h '
              f'({longest_run} consecutive rising {bucket_minutes}-min windows)')
             if suspected else '',
    ).to_payload()


def _attach_usage_metrics(source_key, out):
    """Record a snapshot and attach 'rate' + 'leak' to a model-stats payload.
    Runs on every cache-miss fetch (UI poll or background sampler — the 120s
    stats cache dedupes). Also logs one debug line per fetch with the raw
    value, computed rate, thresholds, and leak verdict so the math can be
    checked against /tmp/dashboard_8765.log."""
    windows = out.get('windows') or []
    if out.get('ok') is False or not windows:
        return
    primary = windows[0]
    pct = primary.get('used_percent')
    if pct is None:
        return
    now = time.time()
    samples = _record_usage_sample(source_key, float(pct), now)
    window_hours = _WINDOW_HOURS.get(primary.get('label'), _DEFAULT_WINDOW_HOURS)
    rate = compute_usage_rate(samples, window_hours, now)
    rate['window_label'] = primary.get('label')
    leak = detect_slow_leak(samples, now)
    out['rate'] = rate
    out['leak'] = leak
    # Early warning propagates to the sub-nav tab color (yellow), never
    # overriding a real 'down'/'concern' from the quota itself.
    if (rate.get('warn') or leak['suspected']) and out.get('status') == 'up':
        out['status'] = 'concern'
    print(f"[model-usage] {source_key} pct={pct} samples={len(samples)} "
          f"rate={rate.get('pct_per_hour')}%/hr burn={rate.get('burn_multiple')}x "
          f"(warn≥{RATE_WARN_BURN_MULTIPLE}x → {rate.get('warn')}) "
          f"leak: {leak['consecutive_rising']}/{leak['needed_consecutive']} consecutive rising, "
          f"+{leak['total_rise_pct']}% over {LEAK_LOOKBACK_MINUTES}m → {leak['suspected']}")

def _model_usage_sample_loop(fetch_stats):
    """Background snapshotter: fetch every source on a fixed cadence so usage
    history keeps flowing while nobody has the Model Stats tab open — without
    it the leak detector would only have data from moments someone watched.
    model_stats() itself records the snapshot; its cache dedupes with the UI.

    `fetch_stats` is injected: the reader that produces a reading imports this
    module for _attach_usage_metrics, so importing it back from here would be
    a cycle. server.py wires the real one at its composition root."""
    while True:
        for key in MODEL_STAT_SOURCES:
            try:
                fetch_stats(key)
            except Exception:
                pass
        time.sleep(MODEL_USAGE_SAMPLE_INTERVAL)
