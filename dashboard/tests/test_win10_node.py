"""Tests for monitoring/win10_node.py -- the Win10 box's health and recovery.

Pointed at the owning module, never at `server`. The code under test closes
over its own module globals, so `monkeypatch.setattr(server, 'X', ...)` would
isolate nothing here while looking exactly like it did.

Every probe in this module is an SSH or socket round trip, so nothing here is
allowed to touch the network: `subprocess.run`, `subprocess.Popen` and
`socket.create_connection` are replaced on the owning module in every test that
reaches them, and the caches are cleared by the autouse fixture below.
"""
import threading
import time

import pytest
from pydantic import ValidationError

import server
from monitoring import win10_node
from monitoring.win10_node import (
    Collaborators,
    Win10CacheEntry,
    container_status_for,
    ensure_win10_docker,
    win10_container_states,
    win10_docker_ok,
    win10_node_health,
)


@pytest.fixture(autouse=True)
def _clear_caches():
    """Each cache is process-wide, so a value left behind by one test silently
    answers the next one's probe without it ever running."""
    for cache in (win10_node._NODE_CACHE, win10_node._CONTAINERS_CACHE,
                  win10_node._DOCKER_CACHE):
        cache.invalidate()
    yield
    for cache in (win10_node._NODE_CACHE, win10_node._CONTAINERS_CACHE,
                  win10_node._DOCKER_CACHE):
        cache.invalidate()


def _deps(log=None):
    return Collaborators(log_restart=log or (lambda line: None),
                         restart_log_path='/dev/null')


class _Run:
    """Stand-in for a completed subprocess.run."""

    def __init__(self, stdout='', stderr=''):
        self.stdout = stdout
        self.stderr = stderr


def _counting_run(monkeypatch, result):
    """Replace subprocess.run on the owning module; return the call counter."""
    calls = []

    def fake_run(*a, **k):
        calls.append(a)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(win10_node.subprocess, 'run', fake_run)
    return calls


# ==========================================================================
# Win10CacheEntry -- why the caches are modelled at all
# ==========================================================================
class TestWin10CacheEntry:
    def test_an_entry_may_hold_none_as_a_value(self):
        """None is a legal answer from win10_docker_ok ('cannot tell'), so the
        entry has to be able to carry it. The old dict could store it but could
        never recognise it as stored."""
        entry = Win10CacheEntry(value=None, ts=100.0)

        assert entry.value is None
        assert entry.is_fresh(now=110.0, ttl=30)

    def test_freshness_is_exclusive_at_the_ttl(self):
        entry = Win10CacheEntry(value=True, ts=100.0)

        assert entry.is_fresh(now=129.9, ttl=30)
        assert not entry.is_fresh(now=130.0, ttl=30)

    def test_an_entry_is_frozen(self):
        """A reader must never see a new value stamped with an old timestamp,
        so entries are replaced whole rather than mutated field by field."""
        entry = Win10CacheEntry(value=True, ts=100.0)

        with pytest.raises(ValidationError):
            entry.value = False

    def test_an_unknown_field_is_refused(self):
        with pytest.raises(ValidationError):
            Win10CacheEntry(value=True, ts=1.0, stale=True)


# ==========================================================================
# The bug the model was built for: an "unknown" dockerd answer never cached
# ==========================================================================
class TestUnknownDockerAnswerCaches:
    def test_an_unknown_answer_is_served_from_cache(self, monkeypatch):
        """The regression this round fixes.

        win10_docker_ok is three-state, and None means "the SSH did not come
        back". The old freshness test was `value is not None and now - ts <
        TTL`, so an unknown answer was written to the cache and then never
        matched -- and every health poll paid another 8-second SSH timeout
        against a box that had just proved it was not answering. That is the
        one case the cache exists for.
        """
        calls = _counting_run(monkeypatch, OSError('ssh: connect timed out'))

        first = win10_docker_ok()
        second = win10_docker_ok()

        assert first is None and second is None
        assert len(calls) == 1, 'the unknown answer must be cached, not re-probed'

    @pytest.mark.parametrize(('stdout', 'expected'),
                             [('active\n', True), ('inactive\n', False)])
    def test_a_known_answer_is_also_cached(self, monkeypatch, stdout, expected):
        calls = _counting_run(monkeypatch, _Run(stdout=stdout))

        assert win10_docker_ok() is expected
        assert win10_docker_ok() is expected
        assert len(calls) == 1

    def test_the_cache_expires(self, monkeypatch):
        _counting_run(monkeypatch, _Run(stdout='active\n'))
        assert win10_docker_ok() is True

        calls = _counting_run(monkeypatch, _Run(stdout='inactive\n'))
        later = time.time() + win10_node.WIN10_DOCKER_CACHE_TTL + 1
        monkeypatch.setattr(win10_node.time, 'time', lambda: later)

        assert win10_docker_ok() is False
        assert len(calls) == 1


# ==========================================================================
# Node reachability
# ==========================================================================
class TestWin10NodeHealth:
    def test_a_reachable_node_is_ok(self, monkeypatch):
        closed = []
        monkeypatch.setattr(
            win10_node.socket, 'create_connection',
            lambda addr, timeout: type('S', (), {'close': lambda self: closed.append(True)})())

        health = win10_node_health()

        assert health['ok'] is True
        assert win10_node.WIN10_NODE_HOST in health['text']
        assert closed == [True], 'the probe socket must be closed'

    def test_an_unreachable_node_names_what_it_blocks(self, monkeypatch):
        """The whole point of this check is that six reds collapse into one, so
        the text has to say which dependents are symptoms of it."""
        monkeypatch.setattr(
            win10_node.socket, 'create_connection',
            lambda addr, timeout: (_ for _ in ()).throw(OSError('no route to host')))

        health = win10_node_health()

        assert health['ok'] is False
        assert 'OFFLINE' in health['text']
        for dependent in ('Letta', 'Frita SDK', 'Logger API'):
            assert dependent in health['text']
        assert 'no route to host' in health['text']

    def test_the_probe_is_cached(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            win10_node.socket, 'create_connection',
            lambda addr, timeout: calls.append(addr) or type('S', (), {'close': lambda self: None})())

        win10_node_health()
        win10_node_health()

        assert len(calls) == 1
        assert calls[0] == (win10_node.WIN10_NODE_HOST, 22)


# ==========================================================================
# Reviving the node
# ==========================================================================
class TestRestartWin10Node:
    def _fake_popen(self, monkeypatch):
        spawned = {}
        monkeypatch.setattr(win10_node.subprocess, 'Popen',
                            lambda cmd, **kw: spawned.update(cmd=cmd, kw=kw))
        return spawned

    def test_it_restarts_tailscaled_from_the_windows_side(self, monkeypatch, tmp_path):
        """The WSL node is unreachable by definition when this button is
        pressed, so the command has to go to the Windows host."""
        spawned = self._fake_popen(monkeypatch)
        log = tmp_path / 'restarts.log'

        result = win10_node.restart_win10_node(
            deps=Collaborators(log_restart=lambda line: None, restart_log_path=str(log)))

        assert result['ok'] is True
        assert spawned['cmd'][-2] == win10_node.WIN10_WINDOWS_HOST
        assert win10_node.WIN10_WSL_DISTRO in spawned['cmd'][-1]
        assert 'systemctl restart tailscaled' in spawned['cmd'][-1]
        assert spawned['kw']['start_new_session'] is True

    def test_it_journals_the_command_before_running_it(self, monkeypatch, tmp_path):
        self._fake_popen(monkeypatch)
        lines = []

        win10_node.restart_win10_node(
            deps=Collaborators(log_restart=lines.append,
                               restart_log_path=str(tmp_path / 'restarts.log')))

        assert len(lines) == 1
        assert lines[0].startswith('win10-node: ssh ')
        assert win10_node.WIN10_WINDOWS_HOST in lines[0]

    def test_it_marks_the_server_starting(self, monkeypatch, tmp_path):
        self._fake_popen(monkeypatch)
        marked = []
        monkeypatch.setattr(win10_node, 'mark_server_starting', marked.append)

        win10_node.restart_win10_node(
            deps=Collaborators(log_restart=lambda line: None,
                               restart_log_path=str(tmp_path / 'restarts.log')))

        assert marked == ['win10-node']

    def test_it_forces_a_fresh_probe_next_poll(self, monkeypatch, tmp_path):
        """A cached OFFLINE would otherwise keep the tab red for the whole TTL
        after the node came back."""
        self._fake_popen(monkeypatch)
        win10_node._NODE_CACHE.put({'ok': False, 'text': 'stale'})

        win10_node.restart_win10_node(
            deps=Collaborators(log_restart=lambda line: None,
                               restart_log_path=str(tmp_path / 'restarts.log')))

        assert win10_node._NODE_CACHE.hit() == (False, None)

    def test_a_spawn_failure_is_reported_not_raised(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            win10_node.subprocess, 'Popen',
            lambda *a, **k: (_ for _ in ()).throw(OSError('ssh missing')))

        result = win10_node.restart_win10_node(
            deps=Collaborators(log_restart=lambda line: None,
                               restart_log_path=str(tmp_path / 'restarts.log')))

        assert result['ok'] is False
        assert 'ssh missing' in result['text']


# ==========================================================================
# Container states -- Docker's own status string is the diagnosis
# ==========================================================================
class TestContainerStates:
    def test_it_parses_docker_ps(self, monkeypatch):
        _counting_run(monkeypatch, _Run(
            stdout='letta-server|Up 3 minutes\n'
                   'frita-executor|Restarting (1) 2 seconds ago\n'))

        states = win10_container_states()

        assert states['letta-server'] == 'Up 3 minutes'
        assert states['frita-executor'] == 'Restarting (1) 2 seconds ago'

    def test_the_format_template_survives_the_remote_shell(self, monkeypatch):
        """The regression that made Indicator #2 dead on arrival.

        ssh joins everything after the destination into one string and lets the
        remote login shell parse it again. Passed as separate argv words, the
        template came apart on the far side -- `|` became a pipe, `{{.Status}}`
        became a command -- so the probe exited 127 with no output, and an
        empty result is indistinguishable from "no containers".
        """
        calls = _counting_run(monkeypatch, _Run(stdout=''))

        win10_container_states()

        argv = calls[0][0]
        remote = argv[argv.index(win10_node.LETTA_DOCKER_HOST) + 1:]
        assert len(remote) == 1, 'the remote command must be one argument, not words'
        assert remote[0] == "docker ps -a --format '{{.Names}}|{{.Status}}'"

    def test_lines_without_a_separator_are_skipped(self, monkeypatch):
        _counting_run(monkeypatch, _Run(stdout='warning: something\nletta-memfs|Up 1 hour\n'))

        assert win10_container_states() == {'letta-memfs': 'Up 1 hour'}

    def test_a_failed_probe_is_cached_as_empty(self, monkeypatch):
        """An unreachable box is exactly when this must not be retried on every
        poll -- the failure mode is a 10s timeout, not a fast error."""
        calls = _counting_run(monkeypatch, OSError('unreachable'))

        assert win10_container_states() == {}
        assert win10_container_states() == {}
        assert len(calls) == 1

    def test_summaries_name_the_container_and_its_docker_status(self):
        states = {'letta-server': 'Exited (139) 54 minutes ago',
                  'letta-memfs': 'Up 2 minutes (healthy)'}

        summary = container_status_for('letta', states)

        assert 'letta-server: Exited (139) 54 minutes ago' in summary
        assert 'letta-memfs: Up 2 minutes (healthy)' in summary

    def test_a_non_docker_server_has_no_summary(self):
        assert container_status_for('dashboard', {'letta-server': 'Up'}) == ''

    def test_a_failed_probe_has_no_summary(self):
        assert container_status_for('letta', {}) == ''

    def test_containers_missing_from_the_probe_are_left_out(self):
        """docker ps -a only lists containers that exist; a never-created one
        must not render as a blank entry."""
        summary = container_status_for('letta', {'letta-server': 'Up 3 minutes'})

        assert summary == 'letta-server: Up 3 minutes'


# ==========================================================================
# Starting dockerd
# ==========================================================================
class TestEnsureWin10Docker:
    def test_it_clears_the_stale_pid_before_starting(self, monkeypatch):
        """The recurring failure (frita_executor_ghost_container, 2026-06-22)
        is dockerd dying on a stale /var/run/docker.pid, which `systemctl
        start` alone will not clear."""
        calls = _counting_run(monkeypatch, _Run(stdout='active\n'))

        result = ensure_win10_docker()

        script = calls[0][0][-1]
        assert 'rm -f /var/run/docker.pid' in script
        assert script.index('docker.pid') < script.index('systemctl start')
        assert result['ok'] is True

    def test_only_a_final_active_counts_as_success(self, monkeypatch):
        """The remote script prints its own progress, so the verdict is the
        last line -- `is-active` -- not whether 'active' appears anywhere."""
        _counting_run(monkeypatch, _Run(stdout='Job for docker.service failed\nfailed\n'))

        assert ensure_win10_docker()['ok'] is False

    def test_a_failure_is_reported_not_raised(self, monkeypatch):
        _counting_run(monkeypatch, OSError('boom'))

        result = ensure_win10_docker()

        assert result['ok'] is False
        assert 'ensure docker error: boom' in result['text']

    @pytest.mark.parametrize('outcome', [_Run(stdout='active\n'), OSError('boom')])
    def test_it_invalidates_the_docker_cache_either_way(self, monkeypatch, outcome):
        """We just tried to start dockerd, so any cached opinion about dockerd
        is stale whichever way it went. Without this, the now-cacheable unknown
        would pin a recovered box in host_unreachable for the rest of its TTL."""
        win10_node._DOCKER_CACHE.put(None)
        _counting_run(monkeypatch, outcome)

        ensure_win10_docker()

        assert win10_node._DOCKER_CACHE.hit() == (False, None)


# ==========================================================================
# The caches are independent
# ==========================================================================
class TestCachesAreIndependent:
    def test_each_probe_has_its_own_lock(self):
        """A slow `docker ps` must not hold up a cheap socket check."""
        locks = {id(c._lock) for c in (win10_node._NODE_CACHE,
                                       win10_node._CONTAINERS_CACHE,
                                       win10_node._DOCKER_CACHE)}

        assert len(locks) == 3

    def test_a_reader_never_sees_a_torn_entry(self):
        """Concurrent put/hit must never yield a value from one probe stamped
        with another's timestamp."""
        cache = win10_node._TtlCache(ttl=1000)
        seen = []

        def writer(value):
            for _ in range(200):
                cache.put(value)

        def reader():
            for _ in range(400):
                hit, value = cache.hit()
                if hit:
                    seen.append(value)

        threads = [threading.Thread(target=writer, args=('a',)),
                   threading.Thread(target=writer, args=('b',)),
                   threading.Thread(target=reader)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert set(seen) <= {'a', 'b'}


# ==========================================================================
# How server.py wires it
# ==========================================================================
class TestServerWiring:
    def test_the_wrapper_passes_the_real_collaborators(self):
        deps = server._win10_node_deps()

        assert deps.log_restart is server._log_restart
        assert deps.restart_log_path == server.RESTART_LOG

    def test_the_wrapper_resolves_the_log_at_call_time(self, monkeypatch):
        """The bundle is built per call, so replacing either name is honoured.
        Built at import instead, `monkeypatch.setattr(server, '_log_restart',
        ...)` would land on a name nothing calls any more."""
        sentinel = object()
        monkeypatch.setattr(server, '_log_restart', sentinel)
        monkeypatch.setattr(server, 'RESTART_LOG', '/tmp/somewhere-else.log')

        deps = server._win10_node_deps()

        assert deps.log_restart is sentinel
        assert deps.restart_log_path == '/tmp/somewhere-else.log'

    def test_the_node_check_is_registered_and_restartable(self):
        keys = {s['key'] for s in server.SERVERS}

        assert 'win10-node' in keys
        assert 'win10_node_health' in server.HEALTH_CHECKS
        assert 'win10-node' in server.RESTARTABLE_KEYS

    def test_the_registered_check_is_the_moved_one(self):
        assert server.HEALTH_CHECKS['win10_node_health'] is win10_node.win10_node_health

    def test_the_restart_handler_is_the_wrapper_not_the_bare_function(self):
        """The bare function needs a Collaborators bundle; dispatching straight
        to it would raise a TypeError on the one path nobody tests by hand."""
        assert server.RESTART_HANDLERS['win10-node'] is server.restart_win10_node

    def test_win10_hosted_servers_depend_on_the_node(self):
        dep = {s['key']: s.get('depends_on') for s in server.SERVERS}

        for key in ('letta', 'logger-api', 'frita-executor', 'dashboard-proxy'):
            assert dep.get(key) == 'win10-node', f'{key} should depend on win10-node'

    @pytest.mark.parametrize('name', [
        'WIN10_NODE_HOST', 'WIN10_WINDOWS_HOST', 'WIN10_WSL_DISTRO',
        'WIN10_NODE_CACHE_TTL', 'WIN10_CONTAINERS_CACHE_TTL', 'WIN10_DOCKER_CACHE_TTL',
        '_win10_node_cache', '_win10_node_lock',
        '_win10_containers_cache', '_win10_containers_lock',
        '_win10_docker_cache', '_win10_docker_lock',
    ])
    def test_server_does_not_re_export_the_moved_names(self, name):
        assert not hasattr(server, name), (
            f'server.{name} is a dead re-export -- a second binding a test can '
            f'patch while the real one keeps running')

    @pytest.mark.parametrize('name', [
        'WIN10_CONTAINERS', 'win10_node_health', 'win10_container_states',
        'container_status_for', 'win10_docker_ok', 'ensure_win10_docker',
    ])
    def test_the_names_http_app_and_the_registries_use_are_still_reachable(self, name):
        """http_app/get_routes.py reaches these through `srv`, so dropping one
        would break a route with the suite still green."""
        assert getattr(server, name) is getattr(win10_node, name)
