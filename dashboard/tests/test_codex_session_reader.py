"""RolloutFileSessionReader against real rollout-shaped JSONL files.

The fixture lines mirror the exact event actually seen in the 2026-09-07
incident's rollout log (`event_msg` / `token_count` / `rate_limits.primary`).
"""

from __future__ import annotations

import json

from health.codex_session_reader import RolloutFileSessionReader


def _token_count_line(percent, window_minutes=300):
    return json.dumps({
        'timestamp': '2026-09-07T15:03:24.053Z',
        'type': 'event_msg',
        'payload': {
            'type': 'token_count',
            'rate_limits': {
                'primary': {'used_percent': percent,
                            'window_minutes': window_minutes,
                            'resets_at': 1788806138},
                'secondary': {'used_percent': 15.0, 'window_minutes': 10080},
            },
        },
    })


def test_reads_the_last_token_count_event(tmp_path):
    path = tmp_path / 'rollout.jsonl'
    path.write_text('\n'.join([
        json.dumps({'type': 'session_meta', 'payload': {}}),
        _token_count_line(10.0),
        json.dumps({'type': 'event_msg', 'payload': {'type': 'other'}}),
        _token_count_line(97.0),
    ]) + '\n')

    sample = RolloutFileSessionReader().usage_for(str(path))

    assert sample is not None
    assert sample.primary_used_percent == 97.0
    assert sample.secondary_used_percent == 15.0
    assert sample.session_path == str(path)


def test_missing_file_returns_none():
    reader = RolloutFileSessionReader()
    assert reader.usage_for('/nonexistent/rollout.jsonl') is None


def test_file_with_no_token_count_event_returns_none(tmp_path):
    path = tmp_path / 'rollout.jsonl'
    path.write_text(json.dumps({'type': 'session_meta', 'payload': {}}) + '\n')

    assert RolloutFileSessionReader().usage_for(str(path)) is None


def test_tolerates_a_corrupt_line_and_still_finds_the_real_one(tmp_path):
    path = tmp_path / 'rollout.jsonl'
    path.write_text('\n'.join([
        _token_count_line(42.0),
        '{not json',
    ]) + '\n')

    sample = RolloutFileSessionReader().usage_for(str(path))
    assert sample is not None
    assert sample.primary_used_percent == 42.0


def test_only_tails_the_file_instead_of_reading_it_all(tmp_path, monkeypatch):
    from health import codex_session_reader

    monkeypatch.setattr(codex_session_reader, '_MAX_TAIL_BYTES', 200)
    path = tmp_path / 'rollout.jsonl'
    padding = json.dumps({'type': 'event_msg', 'payload': {'type': 'pad',
                                                             'x': 'y' * 500}})
    path.write_text('\n'.join([padding] * 50 + [_token_count_line(88.0)]) + '\n')

    sample = RolloutFileSessionReader().usage_for(str(path))
    assert sample is not None
    assert sample.primary_used_percent == 88.0
