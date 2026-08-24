"""The typed shapes behind the Model Stats card, and the seams they sit on.

Three things are pinned here, and they are worth separating.

*The models.* `ModelStatSource`, `UsageWindow`, `UsageRate` and `LeakVerdict`
replaced dicts that were assembled by hand in seven places. Pydantic's value
is only realised if the dumped payload is byte-identical to what those literals
produced, because the frontend reads the JSON positionally in places -- so
every model is compared against the exact dict the old code built, not against
a paraphrase of it.

*The absent-vs-zero distinction.* A window that could not be read and a window
at 0% are different facts drawn differently, and the same is true of a rate
with no history yet. Defaulting either to 0 would render a reassuring empty bar
over a reading nobody actually took. That is the failure these models exist to
prevent, so it gets its own tests.

*The patch-target trap.* server.py re-exports these modules' names, and a
re-export is a second binding. Patching `server.MODEL_USAGE_HISTORY_FILE`
isolates nothing while looking exactly like it does -- the readers close over
their own module global. The suite already had three fixtures doing precisely
that; they now target the owning module, and the tests at the bottom keep them
honest, because the cost of getting this wrong is a test run writing fake
percentages into the live leak detector, or hitting mom's real account.
"""
import json

import pytest
from pydantic import ValidationError

import server
from model_stats import last_good, reader, sources, usage_history, windows
from model_stats.sources import ModelStatSource
from model_stats.usage_history import LeakVerdict, UsageRate
from model_stats.windows import UsageWindow


class TestTheSourceRegistry:
    """The table that says which accounts exist and how to read each one."""

    def test_every_source_parses(self):
        assert set(sources.MODEL_STAT_SOURCES) == {
            'w11-codex', 'r46-codex', 'w11-claude', 'r46-claude', 'gemini'}

    def test_a_kind_the_reader_cannot_handle_is_rejected_at_import(self):
        """The reason the Literal is there.

        `_model_stats_uncached` matches on `kind` and falls off the end when it
        recognises none -- returning the bare skeleton, `ok: True`, no windows,
        no error. A card that says nothing at all is the worst outcome, and a
        typo used to be enough to produce one.
        """
        with pytest.raises(ValidationError):
            ModelStatSource(label='x', kind='antigravity')

    @pytest.mark.parametrize('kind', ['codex', 'claude', 'gemini'])
    def test_each_accepted_kind_has_a_branch_in_the_reader(self, kind):
        import inspect
        body = inspect.getsource(reader._model_stats_uncached)
        assert f"src.kind == '{kind}'" in body

    def test_a_misspelled_field_is_rejected_rather_than_ignored(self):
        """`extra='forbid'` is load-bearing: a source carrying `hostname`
        instead of `host` would silently be read on the wrong machine."""
        with pytest.raises(ValidationError):
            ModelStatSource(label='x', kind='codex', hostname='somewhere')

    def test_an_empty_label_is_rejected(self):
        with pytest.raises(ValidationError):
            ModelStatSource(label='', kind='codex')

    def test_a_source_cannot_be_mutated(self):
        """The registry is process-wide: a route that reassigned a host would
        change which machine every later reading measures."""
        with pytest.raises(ValidationError):
            sources.MODEL_STAT_SOURCES['w11-codex'].host = 'somewhere-else'

    def test_local_sources_have_no_host_and_remote_ones_do(self):
        by_key = sources.MODEL_STAT_SOURCES
        assert by_key['w11-codex'].host is None
        assert by_key['r46-codex'].host == sources.R46_SSH_HOST
        assert by_key['w11-claude'].host is None
        assert by_key['r46-claude'].host == sources.R46_SSH_HOST

    def test_the_registry_is_still_reachable_through_server(self):
        assert server.MODEL_STAT_SOURCES is sources.MODEL_STAT_SOURCES


class TestUsageWindowPayload:
    """A window's dict must be exactly what the frontend already receives."""

    def test_an_ordinary_window_dumps_the_four_keys_it_always_had(self):
        got = UsageWindow(label='5-hour', used_percent=47.0,
                          resets_at='2026-08-24T07:00:00+00:00',
                          resets_in='in 4h 13m').to_payload()
        assert got == {
            'label': '5-hour',
            'used_percent': 47.0,
            'resets_at': '2026-08-24T07:00:00+00:00',
            'resets_in': 'in 4h 13m',
        }

    def test_the_keys_come_out_in_the_order_the_card_expects(self):
        got = UsageWindow(label='weekly', used_percent=1.0).to_payload()
        assert list(got) == ['label', 'used_percent', 'resets_at', 'resets_in']

    def test_an_ordinary_window_carries_no_unavailable_key_at_all(self):
        """Not `unavailable: False` -- absent. The frontend treats the key's
        mere presence as meaningful, so defaulting it into every window would
        blank out every bar on the card."""
        got = UsageWindow(label='5-hour', used_percent=0.0).to_payload()
        assert 'unavailable' not in got and 'note' not in got

    def test_an_unavailable_window_explains_itself(self):
        got = UsageWindow(
            label='5-hour', unavailable=True,
            note='OpenAI paused the 5-hour cap 2026-07-12 (weekly-only, for now)',
        ).to_payload()
        assert got == {
            'label': '5-hour', 'used_percent': None, 'resets_at': None,
            'resets_in': None, 'unavailable': True,
            'note': 'OpenAI paused the 5-hour cap 2026-07-12 (weekly-only, for now)',
        }

    def test_zero_percent_and_unreadable_are_not_the_same_window(self):
        """The distinction the Optional exists for: one is a real reading of
        an idle account, the other is the absence of a reading."""
        at_zero = UsageWindow(label='weekly', used_percent=0.0).to_payload()
        unread = UsageWindow(label='weekly').to_payload()
        assert at_zero['used_percent'] == 0.0
        assert unread['used_percent'] is None

    def test_a_misspelled_field_is_rejected(self):
        with pytest.raises(ValidationError):
            UsageWindow(label='5-hour', used_pct=47.0)

    def test_a_window_survives_a_json_round_trip(self):
        """Windows are persisted by last_good and read back after a restart."""
        payload = UsageWindow(label='5-hour', used_percent=47.0,
                              resets_in='in 2h').to_payload()
        assert json.loads(json.dumps(payload)) == payload


class TestUsageRatePayload:
    def test_a_rate_with_no_history_is_exactly_two_keys(self):
        """A bar cannot be drawn from this, and a `bar_percent: 0` would have
        drawn one -- reading as 'nothing is being spent'."""
        got = UsageRate(available=False, reason='gathering data').to_payload()
        assert got == {'available': False, 'reason': 'gathering data'}

    def test_a_real_rate_dumps_the_eight_keys_the_bar_reads(self):
        got = UsageRate(
            available=True, pct_per_hour=55.7, burn_multiple=2.78,
            sustainable_pct_per_hour=20.0, bar_percent=100, warn=True,
            warn_at_multiple=1.0, window_minutes=30,
        ).to_payload()
        assert got == {
            'available': True, 'pct_per_hour': 55.7, 'burn_multiple': 2.78,
            'sustainable_pct_per_hour': 20.0, 'bar_percent': 100,
            'warn': True, 'warn_at_multiple': 1.0, 'window_minutes': 30,
        }

    def test_an_available_rate_carries_no_reason(self):
        got = UsageRate(available=True, pct_per_hour=1.0, burn_multiple=0.2,
                        sustainable_pct_per_hour=20.0, bar_percent=10,
                        warn=False, warn_at_multiple=1.0,
                        window_minutes=30).to_payload()
        assert 'reason' not in got

    def test_the_window_label_is_attached_after_the_fact(self):
        """compute_usage_rate is pure and does not know which window it
        measured; the caller names it. Absent until then."""
        pure = usage_history.compute_usage_rate(
            [(0, 1.0), (3600, 2.0)], 5.0, now=3600, window_minutes=120)
        assert 'window_label' not in pure


class TestLeakVerdictPayload:
    def test_a_quiet_verdict_still_carries_every_count(self):
        """The counts are the evidence. `consecutive_rising` against
        `needed_consecutive` is what makes a false positive diagnosable, and
        both are printed on every fetch."""
        got = LeakVerdict(suspected=False, rising_buckets=1,
                          consecutive_rising=1, buckets_evaluated=4,
                          needed_consecutive=3, total_rise_pct=1.0).to_payload()
        assert got == {
            'suspected': False, 'rising_buckets': 1, 'consecutive_rising': 1,
            'buckets_evaluated': 4, 'needed_consecutive': 3,
            'total_rise_pct': 1.0, 'text': '',
        }

    def test_a_quiet_verdict_has_empty_text_not_a_missing_key(self):
        """The frontend renders the banner iff `text` is truthy; dropping the
        key would be a KeyError in the template instead of no banner."""
        got = LeakVerdict(suspected=False, rising_buckets=0,
                          consecutive_rising=0, buckets_evaluated=0,
                          needed_consecutive=3, total_rise_pct=0.0).to_payload()
        assert got['text'] == ''


class TestTheCalculatorsStillReturnTheSameDicts:
    """Golden shapes: the models replaced literals, so the output must match.

    These call the real calculators rather than the models directly -- the risk
    of this refactor is a key renamed or dropped between the literal and the
    model, and only the calculator exercises that path.
    """

    def test_a_rate_that_cannot_be_computed(self):
        got = usage_history.compute_usage_rate([(0, 1.0)], 5.0, now=100)
        assert set(got) == {'available', 'reason'}
        assert got['available'] is False
        assert 'gathering data' in got['reason']

    def test_a_rate_that_can(self):
        # 10 %-points in one hour on a 5-hour window: sustainable is 20/hr,
        # so this is exactly half the replenish rate.
        samples = [(0, 10.0), (3600, 20.0)]
        got = usage_history.compute_usage_rate(
            samples, 5.0, now=3600, window_minutes=120,
            warn_multiple=1.0, full_scale=2.0)
        assert got == {
            'available': True, 'pct_per_hour': 10.0, 'burn_multiple': 0.5,
            'sustainable_pct_per_hour': 20.0, 'bar_percent': 25,
            'warn': False, 'warn_at_multiple': 1.0, 'window_minutes': 120,
        }

    def test_a_leak_verdict(self):
        got = usage_history.detect_slow_leak([(0, 1.0)], now=0)
        assert set(got) == {
            'suspected', 'rising_buckets', 'consecutive_rising',
            'buckets_evaluated', 'needed_consecutive', 'total_rise_pct', 'text'}

    def test_a_rolling_window_that_decayed_reports_zero_not_a_negative_rate(self):
        """Documented quirk, pinned: used_percent falls as old usage ages out.
        A negative %/hour would render as a bar going the wrong way."""
        got = usage_history.compute_usage_rate(
            [(0, 40.0), (3600, 10.0)], 5.0, now=3600, window_minutes=120)
        assert got['pct_per_hour'] == 0.0
        assert got['burn_multiple'] == 0.0


class TestTheSamplerIsWiredByInjection:
    """The reader imports usage_history; the sampler needs a reading back."""

    def test_the_loop_takes_the_fetch_rather_than_importing_it(self):
        import inspect
        sig = inspect.signature(usage_history._model_usage_sample_loop)
        assert list(sig.parameters) == ['fetch_stats']
        assert 'model_stats' not in inspect.getsource(usage_history).split('"""')[0]

    def test_the_composition_root_resolves_model_stats_at_call_time(self, monkeypatch):
        """The lambda is the point. Binding `model_stats` eagerly would freeze
        whichever function existed when server.py was imported, and a sampler
        thread started before a test's monkeypatch would keep calling the real
        one -- against mom's live account.
        """
        seen = []
        monkeypatch.setattr(server, 'model_stats', lambda key: seen.append(key))

        def stop_after_one_pass(_secs):
            raise _Stop()

        monkeypatch.setattr(usage_history.time, 'sleep', stop_after_one_pass)
        with pytest.raises(_Stop):
            server._model_usage_sample_loop()
        assert seen == list(sources.MODEL_STAT_SOURCES)

    def test_one_source_raising_does_not_stop_the_others(self, monkeypatch):
        """A sampler that died on a single unreachable host would blind the
        leak detector for every account, silently, until the next restart."""
        seen = []

        def flaky(key):
            seen.append(key)
            if key == 'w11-codex':
                raise RuntimeError('ssh: connect: no route to host')

        monkeypatch.setattr(server, 'model_stats', flaky)
        monkeypatch.setattr(usage_history.time, 'sleep',
                            lambda _s: (_ for _ in ()).throw(_Stop()))
        with pytest.raises(_Stop):
            server._model_usage_sample_loop()
        assert seen == list(sources.MODEL_STAT_SOURCES)


class _Stop(Exception):
    """Breaks the sampler's `while True` without waiting on a real sleep."""


class TestThePatchTargetTrap:
    """server.py re-exports these names; the readers do not read them there.

    Each of the three is a global some test needs to redirect. If a future
    change makes server.py the *owner* of one again, or a test patches the
    re-export, these fail -- which is the only warning anyone would get before
    a test run writes into the live history file or SSHes to mom's box.
    """

    @pytest.mark.parametrize('module, name', [
        (usage_history, 'MODEL_USAGE_HISTORY_FILE'),
        (usage_history, '_usage_history'),
        (last_good, 'MODEL_STATS_LAST_GOOD_FILE'),
        (reader, '_run_extractor'),
        (reader, '_model_stats_cache'),
    ])
    def test_the_global_lives_on_its_own_module(self, module, name):
        assert name in vars(module)

    def test_patching_the_history_path_on_server_does_not_redirect_writes(
            self, tmp_path, monkeypatch):
        """Demonstrates the trap rather than asserting it away.

        This is what three fixtures in test_server.py used to do. The write
        still lands on whatever `usage_history` points at -- here the isolated
        path the autouse fixture set, not the decoy.
        """
        decoy = tmp_path / 'decoy.json'
        monkeypatch.setattr(server, 'MODEL_USAGE_HISTORY_FILE', str(decoy))
        monkeypatch.setattr(usage_history, 'MODEL_USAGE_HISTORY_FILE',
                            str(tmp_path / 'real.json'))
        monkeypatch.setattr(usage_history, '_usage_history', {})
        usage_history._record_usage_sample('w11-codex', 5.0, now=1000)
        assert not decoy.exists()
        assert (tmp_path / 'real.json').exists()

    def test_patching_the_extractor_on_the_reader_does_reach_it(self, monkeypatch):
        """The other half: the target that works. Without this, the model-stats
        tests run the real extractor and read a live account."""
        monkeypatch.setattr(reader, '_run_extractor',
                            lambda *a, **k: {'error': 'stubbed'})
        reader._model_stats_cache.clear()
        out = server.model_stats('w11-codex')
        assert 'stubbed' in out['detail']


class TestServerReExports:
    @pytest.mark.parametrize('name, module', [
        ('model_stats', reader), ('compute_usage_rate', usage_history),
        ('detect_slow_leak', usage_history), ('_record_usage_sample', usage_history),
        ('_human_reset', windows), ('R46_SSH_HOST', sources),
        ('_save_model_stats_last_good', last_good),
    ])
    def test_the_historical_name_still_resolves(self, name, module):
        assert getattr(server, name) is getattr(module, name)
