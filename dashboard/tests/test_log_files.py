"""Log files read as a health signal, tested against their owning module.

Repointed from `tests/test_server.py` for the same reason as
`test_server_lifecycle.py`: `server.tail_lines` and friends are re-exports, so
patching them on `server` would not reach the moved code.

`server_log_rows` is the interesting one. It takes `health_reader`,
`status_kind` and `starting_window` as arguments rather than importing them,
so these tests hand it fakes and never touch a real probe, a real socket or the
live `SERVERS` registry. `TestServerWiring` then checks the thin `server.py`
wrapper passes the real three through -- the injection is only honest if the
production wiring is also covered.
"""

import os
import time

import pytest

import server
from monitoring import log_files, server_lifecycle as lifecycle


def _never_probed(cfg):
    """A health_reader for log-only servers: nothing to ping."""
    return None


def _kind(cfg, health):
    return 'up' if (health or {}).get('ok') else 'down'


def _rows(cfg, q='', health_reader=_never_probed, status_kind=_kind):
    return log_files.server_log_rows(
        cfg, q, health_reader=health_reader, status_kind=status_kind,
        starting_window=lifecycle)


class TestFormatAge:
    @pytest.mark.parametrize('seconds,expected', [
        (0, '0s'), (42, '42s'), (59, '59s'),
        (60, '1m'), (299, '4m'), (3599, '59m'),
        (3600, '1h'), (86399, '23h'),
        (86400, '1d'), (86400 * 9, '9d'),
    ])
    def test_boundaries(self, seconds, expected):
        assert log_files.format_age(seconds) == expected

    def test_truncates_rather_than_rounds(self):
        """'1h' for 119 minutes is deliberate — the string is a glance, and
        rounding up would report a server down longer than it has been."""
        assert log_files.format_age(119 * 60) == '1h'


class TestTailLines:
    def test_returns_trailing_lines_with_absolute_start(self, tmp_path):
        p = tmp_path / 'app.log'
        p.write_text('\n'.join(f'line {i}' for i in range(10)) + '\n')
        start, lines = log_files.tail_lines(str(p), 3)
        assert lines == ['line 7', 'line 8', 'line 9']
        assert start == 7  # absolute index of the first returned line

    def test_short_file_starts_at_zero(self, tmp_path):
        p = tmp_path / 'app.log'
        p.write_text('only\n')
        assert log_files.tail_lines(str(p), 300) == (0, ['only'])

    def test_missing_file_returns_none(self):
        assert log_files.tail_lines('/no/such/file.log', 5) is None

    def test_a_directory_returns_none_rather_than_raising(self, tmp_path):
        """The detail panel must render a row saying "not found", never 500."""
        assert log_files.tail_lines(str(tmp_path), 5) is None

    def test_undecodable_bytes_do_not_raise(self, tmp_path):
        p = tmp_path / 'app.log'
        p.write_bytes(b'good\n\xff\xfe bad bytes\n')
        start, lines = log_files.tail_lines(str(p), 5)
        assert start == 0 and len(lines) == 2


class TestTrimLogCache:
    def test_trims_to_the_last_n_lines(self, tmp_path):
        p = tmp_path / 'cache.log'
        p.write_text('\n'.join(str(i) for i in range(100)) + '\n')
        log_files.trim_log_cache(str(p), 10)
        assert p.read_text().splitlines() == [str(i) for i in range(90, 100)]

    def test_leaves_a_short_file_alone(self, tmp_path):
        p = tmp_path / 'cache.log'
        p.write_text('a\nb\n')
        log_files.trim_log_cache(str(p), 10)
        assert p.read_text() == 'a\nb\n'

    def test_missing_file_is_a_no_op(self, tmp_path):
        log_files.trim_log_cache(str(tmp_path / 'absent.log'), 10)


class TestLogActivityHealth:
    def test_none_when_the_server_has_a_real_probe(self, tmp_path):
        cfg = {'health_url': 'http://x/', 'log_file': str(tmp_path / 'a.log')}
        assert log_files.log_activity_health(cfg) is None

    def test_none_when_there_is_no_log_file_either(self):
        assert log_files.log_activity_health({'key': 'x'}) is None

    def test_recent_write_reads_as_up(self, tmp_path):
        p = tmp_path / 'a.log'
        p.write_text('beat\n')
        h = log_files.log_activity_health({'log_file': str(p)})
        assert h['ok'] is True and 'log active' in h['text']

    def test_stale_write_reads_as_down_with_the_age(self, tmp_path):
        p = tmp_path / 'a.log'
        p.write_text('beat\n')
        old = time.time() - (log_files.LOG_ACTIVITY_WINDOW + 3600)
        os.utime(p, (old, old))
        h = log_files.log_activity_health({'log_file': str(p)})
        assert h['ok'] is False
        assert 'no recent log activity' in h['text'] and '1h ago' in h['text']

    def test_missing_log_file_reads_as_down(self, tmp_path):
        h = log_files.log_activity_health({'log_file': str(tmp_path / 'absent.log')})
        assert h == {'ok': False, 'text': 'no log file found'}

    def test_answers_the_same_contract_as_a_real_probe(self, tmp_path):
        """A log-mtime guess stands in for a health check, so the caller must
        not be able to tell them apart: same ProbeResult keys, nothing extra."""
        p = tmp_path / 'a.log'
        p.write_text('beat\n')
        for cfg in ({'log_file': str(p)}, {'log_file': str(tmp_path / 'absent.log')}):
            h = log_files.log_activity_health(cfg)
            assert set(h) == {'ok', 'text'}
            assert isinstance(h['ok'], bool) and h['text']


class TestServerLogRows:
    def test_tails_the_file_with_stable_ascending_seq(self, tmp_path):
        p = tmp_path / 'app.log'
        p.write_text('alpha\nbeta\ngamma\n')
        out = _rows({'key': 'x', 'name': 'X', 'log_file': str(p)})
        assert [r['text'] for r in out['rows']] == ['alpha', 'beta', 'gamma']
        seqs = [r['seq'] for r in out['rows']]
        assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)

    def test_repeated_identical_lines_keep_distinct_keys(self, tmp_path):
        """seq is the client's row key — duplicate log lines must not collide."""
        p = tmp_path / 'app.log'
        p.write_text('same\nsame\nsame\n')
        out = _rows({'key': 'x', 'name': 'X', 'log_file': str(p)})
        assert [r['seq'] for r in out['rows']] == [0, 1, 2]

    def test_filters_case_insensitively_without_renumbering(self, tmp_path):
        p = tmp_path / 'app.log'
        p.write_text('starting up\nERROR: boom\nall good\nminor error here\n')
        out = _rows({'key': 'x', 'name': 'X', 'log_file': str(p)}, q='error')
        assert [r['text'] for r in out['rows']] == ['ERROR: boom', 'minor error here']
        # Filtered rows keep their absolute line numbers, so a re-poll dedupes.
        assert [r['seq'] for r in out['rows']] == [1, 3]

    def test_missing_file_reports_a_row(self, tmp_path):
        out = _rows({'key': 'x', 'name': 'X', 'log_file': str(tmp_path / 'absent.log')})
        assert len(out['rows']) == 1
        assert 'not found' in out['rows'][0]['text']

    def test_no_log_file_and_no_probe_says_so(self):
        out = _rows({'key': 'x', 'name': 'X'})
        assert out['rows'] == []
        assert out['status'] == {'ok': False,
                                 'text': 'no log file or health check configured'}

    def test_an_ok_probe_wins_and_closes_the_starting_window(self, tmp_path):
        lifecycle.mark_server_starting('x')
        out = _rows({'key': 'x', 'name': 'X'},
                    health_reader=lambda cfg: {'ok': True, 'text': 'HTTP 200'})
        assert out['status']['ok'] is True
        assert out['status']['kind'] == 'up'
        assert lifecycle.is_server_starting('x') is False

    def test_starting_beats_a_failing_probe(self, tmp_path):
        lifecycle.mark_server_starting('x')
        try:
            out = _rows({'key': 'x', 'name': 'X'},
                        health_reader=lambda cfg: {'ok': False, 'text': 'refused'})
            assert out['status']['kind'] == 'starting'
            assert 'STARTING' in out['status']['text']
        finally:
            lifecycle.clear_server_starting('x')

    def test_a_failing_probe_outside_the_window_is_classified(self, tmp_path):
        lifecycle.clear_server_starting('x')
        out = _rows({'key': 'x', 'name': 'X'},
                    health_reader=lambda cfg: {'ok': False, 'text': 'refused'})
        assert out['status']['ok'] is False
        assert out['status']['kind'] == 'down'
        assert out['status']['text'] == 'refused'

    def test_the_probe_result_is_copied_not_mutated(self, tmp_path):
        """'kind' is added for the panel; writing it into the cached health
        dict would leak a display concern into the health cache."""
        health = {'ok': False, 'text': 'refused'}
        _rows({'key': 'x', 'name': 'X'}, health_reader=lambda cfg: health)
        assert health == {'ok': False, 'text': 'refused'}

    def test_falls_back_to_log_activity_when_there_is_no_probe(self, tmp_path):
        p = tmp_path / 'a.log'
        p.write_text('beat\n')
        out = _rows({'key': 'x', 'name': 'X', 'log_file': str(p)})
        assert out['status']['ok'] is True
        assert 'log active' in out['status']['text']
        assert out['status']['kind'] == 'up'


class TestServerWiring:
    def test_wrapper_passes_the_real_collaborators(self, tmp_path, monkeypatch):
        """The injection is only honest if server.py wires the real three. The
        wrapper resolves them at call time, so patching them on `server` — the
        way the rest of tests/test_server.py does — still reaches the code."""
        seen = {}
        p = tmp_path / 'app.log'
        p.write_text('one\n')

        def fake_health(cfg):
            seen['health'] = cfg
            return {'ok': False, 'text': 'refused'}

        def fake_kind(cfg, health):
            seen['kind'] = (cfg, health)
            return 'down'

        monkeypatch.setattr(server, 'cached_server_health', fake_health)
        monkeypatch.setattr(server, 'server_status_kind', fake_kind)
        out = server.server_log_rows({'key': 'x', 'name': 'X', 'log_file': str(p)})
        assert seen['health']['key'] == 'x'
        assert seen['kind'][1] == {'ok': False, 'text': 'refused'}
        assert out['status']['kind'] == 'down'
        assert [r['text'] for r in out['rows']] == ['one']

    def test_only_the_still_called_names_are_pulled_back_into_server(self):
        """server.py imports back exactly what it or a `srv.` route calls:
        `log_activity_health` (GET /api/server-health) and `_trim_log_cache`
        (the Letta remote-log pull). The rest is read from here, so a stale
        re-export cannot drift away from the real definition."""
        assert server.log_activity_health is log_files.log_activity_health
        assert server._trim_log_cache is log_files.trim_log_cache
        for gone in ('tail_lines', '_format_age', 'SERVER_LOG_TAIL',
                     'LOG_ACTIVITY_WINDOW'):
            assert not hasattr(server, gone), f'{gone} re-export is dead weight'
