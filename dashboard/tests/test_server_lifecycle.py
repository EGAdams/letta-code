"""The two Server Management clocks, tested against their owning module.

These used to live in `tests/test_server.py` and drive `server.*`. They are
repointed here deliberately: `server.py` re-exports these names, and a
re-export is a second binding -- a test that patched `server.X` would isolate
nothing, because the moved function closes over `monitoring.server_lifecycle`'s
own global. Patching the owning module is the only patch that reaches the code.

The one exception is the shared registries: `_starting_servers` and
`_server_down_since` are imported into `server.py` *by identity*, so mutating
either object through either module touches the same dict. `TestSharedRegistry`
pins that, because the moment someone rebinds one of them the four `server.py`
restart handlers and this module would start keeping separate books.
"""

import threading
from datetime import timedelta

import pytest
from pydantic import ValidationError

import server
from monitoring import server_lifecycle as lifecycle


@pytest.fixture(autouse=True)
def _clean_clocks():
    with lifecycle._starting_lock:
        lifecycle._starting_servers.clear()
    with lifecycle._server_down_lock:
        lifecycle._server_down_since.clear()
    yield
    with lifecycle._starting_lock:
        lifecycle._starting_servers.clear()
    with lifecycle._server_down_lock:
        lifecycle._server_down_since.clear()


class TestStartingWindow:
    def test_mark_then_is_starting(self):
        assert lifecycle.is_server_starting('executor') is False
        lifecycle.mark_server_starting('executor')
        assert lifecycle.is_server_starting('executor') is True

    def test_clear_flips_it_back_immediately(self):
        lifecycle.mark_server_starting('executor')
        lifecycle.clear_server_starting('executor')
        assert lifecycle.is_server_starting('executor') is False

    def test_clear_is_safe_for_a_key_never_marked(self):
        lifecycle.clear_server_starting('never-started')

    def test_expires_after_the_window_and_evicts(self):
        lifecycle.mark_server_starting('executor')
        with lifecycle._starting_lock:
            lifecycle._starting_servers['executor'] -= timedelta(
                seconds=lifecycle.STARTING_WINDOW_SECONDS + 1)
        assert lifecycle.is_server_starting('executor') is False
        with lifecycle._starting_lock:
            assert 'executor' not in lifecycle._starting_servers

    def test_just_inside_the_window_still_counts(self):
        lifecycle.mark_server_starting('executor')
        with lifecycle._starting_lock:
            lifecycle._starting_servers['executor'] -= timedelta(
                seconds=lifecycle.STARTING_WINDOW_SECONDS - 5)
        assert lifecycle.is_server_starting('executor') is True


class TestDownDuration:
    def test_clears_on_up_and_accumulates(self, monkeypatch):
        t = [1000.0]
        monkeypatch.setattr(lifecycle.time, 'time', lambda: t[0])
        assert lifecycle.track_down_duration('dur-test', 'down') == (0, False)
        t[0] = 1000.0 + 30
        dur, stale = lifecycle.track_down_duration('dur-test', 'down')
        assert dur == 30 and stale is False
        t[0] = 1000.0 + lifecycle.SERVER_STALE_DOWN_SECONDS + 1
        dur, stale = lifecycle.track_down_duration('dur-test', 'concern')
        assert stale is True
        assert lifecycle.track_down_duration('dur-test', 'up') == (0, False)

    def test_starting_does_not_start_a_clock(self, monkeypatch):
        t = [1000.0]
        monkeypatch.setattr(lifecycle.time, 'time', lambda: t[0])
        assert lifecycle.track_down_duration('boot', 'starting') == (0, False)
        t[0] = 1000.0 + 900
        # Still no clock: 'starting' is transient, not an outage.
        assert lifecycle.track_down_duration('boot', 'starting') == (0, False)

    def test_a_clock_already_running_survives_a_starting_tick(self, monkeypatch):
        """A Restart click mid-outage must not reset the 'down for' counter --
        otherwise a server nobody can fix reads as freshly broken every time
        someone tries the button, and never escalates to stale."""
        t = [1000.0]
        monkeypatch.setattr(lifecycle.time, 'time', lambda: t[0])
        lifecycle.track_down_duration('stuck', 'down')
        t[0] = 1000.0 + 300
        dur, _ = lifecycle.track_down_duration('stuck', 'starting')
        assert dur == 300

    def test_keys_are_independent(self, monkeypatch):
        t = [1000.0]
        monkeypatch.setattr(lifecycle.time, 'time', lambda: t[0])
        lifecycle.track_down_duration('a', 'down')
        t[0] = 1000.0 + 60
        lifecycle.track_down_duration('b', 'down')
        t[0] = 1000.0 + 90
        assert lifecycle.track_down_duration('a', 'down')[0] == 90
        assert lifecycle.track_down_duration('b', 'down')[0] == 30

    @pytest.mark.parametrize('status', ['up', 'concern', 'starting', 'down'])
    def test_every_status_the_classifier_produces_is_accepted(self, status):
        lifecycle.track_down_duration('vocab', status)

    def test_an_unknown_status_raises_instead_of_starting_a_stale_clock(self):
        """The whole point of validating: 'Up' or a fifth state added to
        compute_server_status would otherwise fall through to the down branch
        and escalate a healthy server as stale ten minutes later, with nothing
        in the UI to explain it."""
        for bogus in ('Up', 'healthy', 'ok', '', None):
            with pytest.raises(ValidationError):
                lifecycle.track_down_duration('bogus', bogus)
            assert 'bogus' not in lifecycle._server_down_since


class TestServerStatusVocabulary:
    def test_matches_what_compute_server_status_can_return(self):
        """`ServerStatus` is only worth validating against if it is the same
        four words `compute_server_status` actually emits."""
        produced = set()
        produced.add(server.compute_server_status({'ok': True, 'text': 'x'}))
        produced.add(server.compute_server_status({'ok': True, 'text': 'x', 'concern': True}))
        produced.add(server.compute_server_status({'ok': False, 'text': 'x'}, starting=True))
        produced.add(server.compute_server_status({'ok': False, 'text': 'x'}, restartable=True))
        produced.add(server.compute_server_status({'ok': False, 'text': 'x'}))
        assert produced == {'up', 'concern', 'starting', 'down'}
        for status in produced:
            lifecycle.track_down_duration('vocab-live', status)


class TestSharedRegistry:
    def test_server_reexports_the_starting_registry_by_identity(self):
        """tests/test_server.py's `_clear_starting()` resets the registry
        through `server`; if this were a rebind it would clear a second, empty
        dict and leave real marks behind for the next test to trip over."""
        assert server._starting_servers is lifecycle._starting_servers
        assert server._starting_lock is lifecycle._starting_lock

    def test_the_down_clock_registry_is_not_re_exported(self):
        """Nothing outside this module touches it, and a dead re-export is
        how the patch-target trap gets set for the next person."""
        assert not hasattr(server, '_server_down_since')
        assert not hasattr(server, '_server_down_lock')
        assert not hasattr(server, 'SERVER_STALE_DOWN_SECONDS')

    def test_a_mark_through_server_is_visible_to_the_module(self):
        """`mark_server_starting` stays on server.py because six restart paths
        there call it. `clear_server_starting` had exactly one caller — GET
        /api/server-health — so round 12 pointed that route at this module and
        the re-export left with it."""
        server.mark_server_starting('executor')
        assert lifecycle.is_server_starting('executor') is True
        assert not hasattr(server, 'clear_server_starting')
        lifecycle.clear_server_starting('executor')
        assert lifecycle.is_server_starting('executor') is False

    def test_restart_handlers_still_open_the_window(self, monkeypatch):
        """`_restart_user_unit` is one of six call sites in server.py that mark
        a server starting; if the import ever became a copy this would pass in
        server.py and fail here."""
        monkeypatch.setattr(server.subprocess, 'run',
                            lambda *a, **k: type('R', (), {'returncode': 0, 'stdout': '', 'stderr': ''})())
        server._restart_user_unit('dashboard', 'dashboard-server.service')
        assert lifecycle.is_server_starting('dashboard') is True


class TestThreadSafety:
    def test_concurrent_marks_and_reads_do_not_corrupt_the_registry(self):
        """Restart handlers run on request threads while the health poller
        reads on its own; both take the same lock."""
        keys = [f'srv{i}' for i in range(20)]
        errors = []

        def churn():
            try:
                for _ in range(50):
                    for k in keys:
                        lifecycle.mark_server_starting(k)
                        lifecycle.is_server_starting(k)
                        lifecycle.track_down_duration(k, 'down')
                        lifecycle.clear_server_starting(k)
            except Exception as exc:  # pragma: no cover - only on a real race
                errors.append(exc)

        threads = [threading.Thread(target=churn) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert not errors
        assert all(lifecycle.is_server_starting(k) is False for k in keys)
