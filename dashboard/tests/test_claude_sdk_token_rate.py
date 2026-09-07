"""Token-rate accumulation: idempotent per run, windowed, and fail-soft."""

import time

from health import claude_sdk_token_rate as rate
from health.claude_sdk_usage_contracts import RunUsageSample, usage_from_payload
from health.claude_sdk_usage_store import (
    InMemoryRunUsageStore,
    JsonFileRunUsageStore,
)

NOW = 1_700_000_000.0


def usage(input_tokens=100, output_tokens=50, cache_creation=1000, cache_read=2000):
    return {
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'cache_creation_input_tokens': cache_creation,
        'cache_read_input_tokens': cache_read,
        'server_tool_use': {'web_search_requests': 0},
    }


def activity(run_id='r1', status='complete', ended_at=NOW, tokens=None):
    return {
        'ok': True,
        'current_run': {
            'run_id': run_id,
            'status': status,
            'model': 'haiku',
            'ended_at': ended_at,
            'usage': tokens if tokens is not None else usage(),
        },
        'events': [],
    }


def service(store=None, now=NOW, source=None):
    return rate.ClaudeSdkTokenRateService(
        store or InMemoryRunUsageStore(clock=lambda: now),
        activity_source=source or (lambda: activity()),
        clock=lambda: now,
    )


def test_a_finished_run_is_counted_once_however_often_it_is_polled():
    store = InMemoryRunUsageStore(clock=lambda: NOW)
    svc = service(store)

    assert svc.ingest(activity()) == 1
    assert svc.ingest(activity()) == 0
    assert svc.ingest(activity()) == 0
    assert len(store.samples()) == 1


def test_a_running_run_is_not_counted_until_it_finishes():
    store = InMemoryRunUsageStore(clock=lambda: NOW)
    svc = service(store)

    assert svc.ingest(activity(status='running')) == 0
    assert svc.ingest(activity(status='complete')) == 1


def test_terminal_status_events_are_read_as_well_as_current_run():
    store = InMemoryRunUsageStore(clock=lambda: NOW)
    svc = service(store)
    payload = activity(run_id='live', status='running')
    payload['events'] = [{
        'seq': 4, 'timestamp': NOW - 10, 'run_id': 'earlier',
        'category': 'status', 'status': 'complete', 'usage': usage(),
    }]

    assert svc.ingest(payload) == 1
    assert [s.run_id for s in store.samples()] == ['earlier']


def test_windows_report_tokens_per_minute_and_flag_partial_coverage():
    store = InMemoryRunUsageStore(clock=lambda: NOW)
    store.record(RunUsageSample(run_id='a', ended_at=NOW - 30,
                                input_tokens=3000, output_tokens=0))
    svc = service(store, source=lambda: {'ok': True, 'current_run': None, 'events': []})

    payload = svc.rates()
    windows = {w.seconds: w for w in payload.windows}

    assert windows[60].total_tokens == 3000
    assert windows[60].tokens_per_minute == 3000.0
    assert windows[300].tokens_per_minute == 600.0
    # 30s of observed history cannot answer for an hour.
    assert windows[3600].complete is False


def test_the_rate_survives_an_unreachable_executor():
    store = InMemoryRunUsageStore(clock=lambda: NOW)
    store.record(RunUsageSample(run_id='a', ended_at=NOW - 30, output_tokens=600))
    svc = service(store, source=lambda: {
        'ok': False, 'current_run': None, 'events': [],
        'error': 'Claude SDK activity unavailable: offline',
    })

    payload = svc.rates()

    assert payload.ok is False
    assert 'offline' in payload.error
    assert payload.sample_count == 1
    assert {w.seconds: w.total_tokens for w in payload.windows}[60] == 600


def test_usage_without_any_tokens_is_not_a_sample():
    assert usage_from_payload('r', 'haiku', NOW, usage(0, 0, 0, 0)) is None
    assert usage_from_payload('', 'haiku', NOW, usage()) is None
    assert usage_from_payload('r', 'haiku', NOW, None) is None


def test_the_file_store_round_trips_and_drops_expired_samples(tmp_path):
    path = str(tmp_path / 'usage.json')
    store = JsonFileRunUsageStore(path, clock=lambda: NOW)

    assert store.record(RunUsageSample(run_id='fresh', ended_at=NOW - 60,
                                       output_tokens=10)) is True
    assert store.record(RunUsageSample(run_id='fresh', ended_at=NOW - 60,
                                       output_tokens=10)) is False
    store.record(RunUsageSample(run_id='ancient', ended_at=NOW - 40 * 3600,
                                output_tokens=10))

    reopened = JsonFileRunUsageStore(path, clock=lambda: NOW)
    assert [s.run_id for s in reopened.samples()] == ['fresh']


def test_a_corrupt_state_file_reads_as_no_history(tmp_path):
    path = tmp_path / 'usage.json'
    path.write_text('{not json')

    assert JsonFileRunUsageStore(str(path)).samples() == []


def test_the_sampler_keeps_running_after_a_failed_poll():
    calls = []

    def exploding():
        calls.append(1)
        raise OSError('executor down')

    svc = service(source=exploding)
    sampler = rate.TokenRateSampler(svc, interval=0.001)

    def stop_after_two():
        while len(calls) < 2:
            time.sleep(0.005)
        sampler.stop()

    import threading
    threading.Thread(target=stop_after_two, daemon=True).start()
    sampler.run_forever()

    assert len(calls) >= 2
