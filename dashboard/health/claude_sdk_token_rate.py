"""How fast the Claude Code SDK is spending tokens.

The executor reports usage per run and forgets it; this turns that stream into
a rate. Two collaborators, both injected: an *activity source* (by default the
read-only proxy in ``claude_sdk_activity``) and an ``IRunUsageStore``.

Sampling, not pushing. The executor has no callback and no cumulative counter,
so something has to look. Two things do, and they share the same idempotent
``ingest``: every ``/api/claude-sdk-activity`` request the open dashboard makes
(free -- that panel already polls once a second), and a slow background sampler
for the hours nobody is watching. The executor keeps 400 events, so a 30s
sampler cannot miss a finished run in any realistic traffic.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional

from health import claude_sdk_activity
from health.claude_sdk_usage_contracts import (
    RATE_WINDOWS,
    CurrentRunUsage,
    IRunUsageStore,
    RateWindow,
    RunUsageSample,
    TokenRatePayload,
    usage_from_payload,
)
from health.claude_sdk_usage_store import default_store

#: How often the background sampler looks when no browser is polling.
SAMPLER_INTERVAL_SECONDS = 30.0


def _finished_runs(payload) -> List[RunUsageSample]:
    """Every finished run carrying usage in one activity payload.

    Reads both the ``current_run`` summary and the terminal status events in
    the buffer. They overlap constantly -- the store's run_id idempotency is
    what makes reading both safe, and reading both is what lets a run that
    finished between two polls still be counted.
    """
    if not isinstance(payload, dict):
        return []
    samples = []
    run = payload.get('current_run')
    if isinstance(run, dict) and run.get('status') != 'running':
        sample = usage_from_payload(
            run.get('run_id') or '', run.get('model') or 'unknown',
            run.get('ended_at') or run.get('started_at') or time.time(),
            run.get('usage'))
        if sample:
            samples.append(sample)
    for event in payload.get('events') or []:
        if not isinstance(event, dict) or event.get('category') != 'status':
            continue
        if event.get('status') == 'running':
            continue
        sample = usage_from_payload(
            event.get('run_id') or '', event.get('model') or 'unknown',
            event.get('timestamp') or time.time(), event.get('usage'))
        if sample:
            samples.append(sample)
    return samples


def _current_run(payload) -> Optional[CurrentRunUsage]:
    run = payload.get('current_run') if isinstance(payload, dict) else None
    if not isinstance(run, dict) or not run.get('run_id'):
        return None
    sample = usage_from_payload(run.get('run_id'), run.get('model') or 'unknown',
                                run.get('ended_at') or time.time(),
                                run.get('usage'))
    return CurrentRunUsage(
        run_id=str(run.get('run_id')),
        status=str(run.get('status') or 'unknown'),
        model=str(run.get('model') or 'unknown'),
        total_tokens=sample.total_tokens if sample else 0,
    )


class ClaudeSdkTokenRateService:
    """Ingest activity payloads; answer with windowed token rates."""

    def __init__(self, store: IRunUsageStore,
                 activity_source: Callable[[], dict] = claude_sdk_activity.activity_payload,
                 clock: Callable[[], float] = time.time):
        self._store = store
        self._activity = activity_source
        self._clock = clock
        self._watching_since: Optional[float] = None

    def ingest(self, payload) -> int:
        """Fold one activity payload in. Returns how many runs were new."""
        if isinstance(payload, dict) and payload.get('ok'):
            self._watching_since = self._watching_since or self._clock()
        return sum(1 for sample in _finished_runs(payload)
                   if self._store.record(sample))

    def sample(self) -> int:
        """Fetch the feed ourselves, then ingest it."""
        return self.ingest(self._activity())

    def rates(self, payload=None) -> TokenRatePayload:
        """The Server Management readout. Fetches the feed unless given one."""
        payload = self._activity() if payload is None else payload
        self.ingest(payload)
        now = self._clock()
        samples = self._store.samples()
        observed_since = min(
            [s.ended_at for s in samples] +
            ([self._watching_since] if self._watching_since else []),
            default=None)
        return TokenRatePayload(
            ok=bool(payload.get('ok')) if isinstance(payload, dict) else False,
            error=payload.get('error') if isinstance(payload, dict) else 'no payload',
            observed_since=observed_since,
            sample_count=len(samples),
            current_run=_current_run(payload),
            windows=[self._window(seconds, label, samples, now, observed_since)
                     for seconds, label in RATE_WINDOWS],
        )

    @staticmethod
    def _window(seconds: int, label: str, samples: List[RunUsageSample],
                now: float, observed_since: Optional[float]) -> RateWindow:
        cutoff = now - seconds
        inside = [s for s in samples if s.ended_at >= cutoff]
        total = sum(s.total_tokens for s in inside)
        return RateWindow(
            seconds=seconds,
            label=label,
            runs=len(inside),
            input_tokens=sum(s.input_tokens for s in inside),
            output_tokens=sum(s.output_tokens for s in inside),
            cache_tokens=sum(s.cache_tokens for s in inside),
            total_tokens=total,
            tokens_per_minute=round(total / (seconds / 60.0), 1),
            complete=observed_since is not None and (now - observed_since) >= seconds,
        )


class TokenRateSampler:
    """The background loop that keeps the history honest while nobody looks.

    Shaped as a plain ``run_forever`` rather than its own thread so it is one
    more ``BackgroundTask`` in ``startup_tasks()`` -- same lifecycle, same
    banner, same place to look as the other pollers. ``stop()`` exists for
    tests, which drive ``sample()`` directly and never start the loop.
    """

    def __init__(self, service: ClaudeSdkTokenRateService,
                 interval: float = SAMPLER_INTERVAL_SECONDS):
        self._service = service
        self._interval = interval
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run_forever(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self._service.sample()
            except Exception as exc:  # never kill the sampler over one bad poll
                print(f'[claude-sdk-token-rate] sample failed: {exc}', flush=True)


#: Live wiring. Imported by http_app/get_routes.py and started by server.py.
SERVICE = ClaudeSdkTokenRateService(default_store())
SAMPLER = TokenRateSampler(SERVICE)


def token_rate_payload() -> dict:
    """GET /api/claude-sdk-token-rate."""
    return SERVICE.rates().model_dump(mode='json')


def ingest_activity(payload) -> None:
    """Side-channel for /api/claude-sdk-activity: the poll is already paid for."""
    try:
        SERVICE.ingest(payload)
    except Exception as exc:
        print(f'[claude-sdk-token-rate] ingest failed: {exc}')
