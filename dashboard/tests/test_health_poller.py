"""health/poller.py -- the debounced background health cache."""

import pytest

from health.poller import HealthCacheEntry, HealthPoller, HEALTH_FAIL_THRESHOLD


def _cfg(key='svc', **extra):
    return {'key': key, 'health_url': 'http://x/', **extra}


class TestHealthCacheEntry:
    def test_defaults(self):
        entry = HealthCacheEntry()
        assert entry.fails == 0
        assert entry.result is None

    def test_rejects_unknown_fields(self):
        with pytest.raises(Exception):
            HealthCacheEntry(bogus=True)


class TestPollAllOnce:
    def test_skips_servers_with_no_check_configured(self):
        poller = HealthPoller()
        calls = []
        poller.poll_all_once([{'key': 'no-checks'}], lambda cfg, timeout=None: calls.append(cfg))
        assert calls == []
        assert poller.cached({'key': 'no-checks'}, lambda cfg, timeout=None: {}) is None

    def test_success_resets_fail_count(self):
        poller = HealthPoller()
        poller.poll_all_once([_cfg()], lambda cfg, timeout=None: {'ok': False})
        poller.poll_all_once([_cfg()], lambda cfg, timeout=None: {'ok': False})
        poller.poll_all_once([_cfg()], lambda cfg, timeout=None: {'ok': True, 'text': 'up'})
        assert poller.cached(_cfg(), lambda cfg, timeout=None: {'ok': True}) == {'ok': True, 'text': 'up'}

    def test_isolated_failure_keeps_last_good_result(self):
        poller = HealthPoller()
        poller.poll_all_once([_cfg()], lambda cfg, timeout=None: {'ok': True, 'text': 'up'})
        poller.poll_all_once([_cfg()], lambda cfg, timeout=None: {'ok': False, 'text': 'blip'})
        # One failure is below HEALTH_FAIL_THRESHOLD -- the LED should not flip.
        assert poller.cached(_cfg(), lambda cfg, timeout=None: {}) == {'ok': True, 'text': 'up'}

    def test_result_flips_after_threshold_consecutive_failures(self):
        poller = HealthPoller()
        poller.poll_all_once([_cfg()], lambda cfg, timeout=None: {'ok': True, 'text': 'up'})
        for _ in range(HEALTH_FAIL_THRESHOLD):
            poller.poll_all_once([_cfg()], lambda cfg, timeout=None: {'ok': False, 'text': 'down'})
        assert poller.cached(_cfg(), lambda cfg, timeout=None: {}) == {'ok': False, 'text': 'down'}


class TestCached:
    def test_probes_synchronously_on_first_access(self):
        poller = HealthPoller()
        result = poller.cached(_cfg(), lambda cfg, timeout=None: {'ok': True, 'text': 'up'})
        assert result == {'ok': True, 'text': 'up'}

    def test_second_access_does_not_reprobe(self):
        poller = HealthPoller()
        calls = []

        def health(cfg, timeout=None):
            calls.append(1)
            return {'ok': True, 'text': 'up'}

        poller.cached(_cfg(), health)
        poller.cached(_cfg(), health)
        assert len(calls) == 1

    def test_returns_none_for_config_without_any_check(self):
        poller = HealthPoller()
        assert poller.cached({'key': 'bare'}, lambda cfg, timeout=None: {}) is None


class TestThePatchTargetTrap:
    """server.py's cached_server_health/_poll_all_health_once/_health_poll_loop
    are thin composition-root wrappers around a module-level HealthPoller
    instance. Patching server.SERVERS or server.server_health only works
    because _health_poll_loop resolves both through a lambda at call time --
    an eagerly-bound reference would freeze whichever object existed when the
    background thread started, and a test replacing server.SERVERS afterward
    would silently stop being honoured.
    """

    def test_poll_loop_re_resolves_servers_getter_each_call(self):
        poller = HealthPoller()
        calls = []
        boxed = {'servers': [_cfg('a')]}

        def health(cfg, timeout=None):
            calls.append(cfg['key'])
            return {'ok': True}

        poller.poll_all_once(boxed['servers'], health)
        boxed['servers'] = [_cfg('b')]
        poller.poll_all_once(boxed['servers'], health)

        assert calls == ['a', 'b']
