"""JsonFileWatchdogActionStore: round-trip, idempotent-free append, and the
fail-soft contract shared with `claude_sdk_usage_store.py` -- a corrupt or
missing file must read back as empty, never raise."""

from __future__ import annotations

import json

from health.codex_watchdog_contracts import WatchdogAction
from health.codex_watchdog_store import JsonFileWatchdogActionStore


def _action(pgid=1, timestamp=1.0, action='terminate_quota'):
    return WatchdogAction(timestamp=timestamp, action=action, pgid=pgid,
                           cmd='node bin/codex', reason='test')


def test_round_trips_through_disk(tmp_path):
    path = str(tmp_path / 'actions.json')
    store = JsonFileWatchdogActionStore(path)

    store.record(_action(pgid=1))
    store.record(_action(pgid=2))

    reloaded = JsonFileWatchdogActionStore(path)
    recent = reloaded.recent()
    assert [a.pgid for a in recent] == [1, 2]


def test_recent_respects_limit(tmp_path):
    store = JsonFileWatchdogActionStore(str(tmp_path / 'actions.json'))
    for i in range(5):
        store.record(_action(pgid=i))

    assert [a.pgid for a in store.recent(limit=2)] == [3, 4]


def test_missing_file_reads_as_empty(tmp_path):
    store = JsonFileWatchdogActionStore(str(tmp_path / 'nope.json'))
    assert store.recent() == []


def test_corrupt_file_reads_as_empty_not_an_exception(tmp_path):
    path = tmp_path / 'actions.json'
    path.write_text('{not valid json')
    store = JsonFileWatchdogActionStore(str(path))
    assert store.recent() == []


def test_unknown_shaped_rows_are_skipped_not_fatal(tmp_path):
    path = tmp_path / 'actions.json'
    path.write_text(json.dumps({'actions': [{'garbage': True}]}))
    store = JsonFileWatchdogActionStore(str(path))
    assert store.recent() == []
