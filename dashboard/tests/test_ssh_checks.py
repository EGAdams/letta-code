"""Tests for monitoring/ssh_checks.py, pointed at the owning module.

Every monkeypatch here targets `ssh_checks`, never `server`. The poll loop and
the probes close over this module's globals; patching the re-export on `server`
would leave the real function running while the test read a fake -- the trap
that has bitten five rounds of this refactor.
"""
from __future__ import annotations

import subprocess
import threading

import pytest

import server
from monitoring import ssh_checks


def _cfg(**over):
    base = {'key': '__test_ssh_conn', 'name': 'Test Conn', 'host': '0.0.0.0', 'user': 'nobody'}
    base.update(over)
    return base


@pytest.fixture(autouse=True)
def _clean_caches():
    """Never leave a fake verdict where the next test (or a poll thread) reads it."""
    yield
    with ssh_checks._ssh_health_lock:
        ssh_checks._ssh_health_cache.pop('__test_ssh_conn', None)
    with ssh_checks._ssh_log_lock:
        ssh_checks._ssh_log_cache.pop('__test_ssh_conn', None)


# ── The roster ───────────────────────────────────────────────────────────────

def test_get_ssh_connection_finds_a_key_and_returns_none_for_a_stranger():
    assert ssh_checks.get_ssh_connection('win11')['name'] == 'Win11 (Lettabot/Dashboard)'
    assert ssh_checks.get_ssh_connection('no-such-box') is None


def test_every_roster_entry_has_the_fields_both_routes_render():
    for cfg in ssh_checks.SSH_CONNECTIONS:
        assert cfg['key'] and cfg['name'], cfg
        assert isinstance(cfg.get('note', ''), str), cfg


def test_roster_keys_are_unique():
    keys = [c['key'] for c in ssh_checks.SSH_CONNECTIONS]
    assert len(keys) == len(set(keys))


def test_peer_only_entries_are_checked_by_tailscale_not_ssh():
    """A phone and a Chromebook run no sshd. If either lost its 'check' key it
    would be probed with ssh and sit red forever, which reads as an outage."""
    for key in ('android-phone', 'chromebook-a13'):
        assert ssh_checks.get_ssh_connection(key)['check'] == 'tailscale'


def test_the_derp_relayed_box_keeps_its_own_generous_timeout():
    """100.80.49.10 is reached over a DERP relay measured at up to 43s. The
    default 8s would flip it down twice in a row -- i.e. genuinely down."""
    cfg = ssh_checks.get_ssh_connection('win10-wsl-letta')
    assert cfg['timeout'] > ssh_checks.SSH_CONNECT_TIMEOUT * 4


# ── ssh_test: the identity fallback chain ────────────────────────────────────

@pytest.mark.parametrize('identity_key', ['identity_files', 'identity_file'])
def test_ssh_test_uses_configured_identity_file(monkeypatch, tmp_path, identity_key):
    identity = tmp_path / 'id_ed25519'
    identity.write_text('key')
    cfg_value = (str(identity),) if identity_key == 'identity_files' else str(identity)
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, 'CONNECTED\nTESTBOX\n', '')
    monkeypatch.setattr(ssh_checks.subprocess, 'run', fake_run)

    result = ssh_checks.ssh_test({**_cfg(), identity_key: cfg_value}, timeout=5)
    assert result['ok'] is True and 'TESTBOX' in result['text']
    assert calls[0][:6] == [
        'ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
        '-o']
    assert '-i' in calls[0] and str(identity) in calls[0]
    assert 'IdentitiesOnly=yes' in calls[0]


def test_ssh_test_falls_through_a_dead_preferred_key_to_a_working_one(monkeypatch, tmp_path):
    """A key can exist on disk and no longer be authorized. Stopping at the
    first file that exists wedges on it forever -- ssh_gateway.py's
    ConfiguredIdentityStrategy still does exactly that, which is why nothing
    imports it."""
    dead = tmp_path / 'dead'
    dead.write_text('revoked')
    live = tmp_path / 'live'
    live.write_text('good')
    tried = []

    def fake_run(cmd, **kw):
        identity = cmd[cmd.index('-i') + 1]
        tried.append(identity)
        if identity == str(dead):
            return subprocess.CompletedProcess(cmd, 255, '', 'Permission denied (publickey).')
        return subprocess.CompletedProcess(cmd, 0, 'CONNECTED\nTESTBOX\n', '')
    monkeypatch.setattr(ssh_checks.subprocess, 'run', fake_run)

    result = ssh_checks.ssh_test({**_cfg(), 'identity_files': (str(dead), str(live))}, timeout=5)
    assert result['ok'] is True
    assert tried == [str(dead), str(live)]


def test_ssh_test_reports_the_last_failure_when_every_identity_fails(monkeypatch, tmp_path):
    dead = tmp_path / 'dead'
    dead.write_text('revoked')
    monkeypatch.setattr(ssh_checks.subprocess, 'run', lambda cmd, **kw: subprocess.CompletedProcess(
        cmd, 255, '', 'Permission denied (publickey).'))
    result = ssh_checks.ssh_test({**_cfg(), 'identity_files': (str(dead),)}, timeout=5)
    assert result['ok'] is False
    assert 'Permission denied' in result['text']


def test_ssh_test_without_any_identity_file_runs_a_plain_probe(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, 'CONNECTED\nTESTBOX\n', '')
    monkeypatch.setattr(ssh_checks.subprocess, 'run', fake_run)
    assert ssh_checks.ssh_test(_cfg(), timeout=5)['ok'] is True
    assert '-i' not in calls[0]


def test_ssh_test_reports_a_timeout_as_a_failure_not_an_exception(monkeypatch):
    def boom(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd='ssh', timeout=5)
    monkeypatch.setattr(ssh_checks.subprocess, 'run', boom)
    result = ssh_checks.ssh_test(_cfg(), timeout=5)
    assert result['ok'] is False and 'timed out' in result['text']


def test_ssh_test_requires_the_CONNECTED_sentinel(monkeypatch):
    """rc 0 is not enough: a login shell that prints a banner and exits cleanly
    would otherwise read as a healthy round trip."""
    monkeypatch.setattr(ssh_checks.subprocess, 'run', lambda cmd, **kw: subprocess.CompletedProcess(
        cmd, 0, 'Welcome to Ubuntu\n', ''))
    assert ssh_checks.ssh_test(_cfg(), timeout=5)['ok'] is False


def test_ssh_test_truncates_a_long_error_to_one_line(monkeypatch):
    monkeypatch.setattr(ssh_checks.subprocess, 'run', lambda cmd, **kw: subprocess.CompletedProcess(
        cmd, 255, '', 'x' * 500))
    assert len(ssh_checks.ssh_test(_cfg(), timeout=5)['text']) == 160


# ── tailscale_test ───────────────────────────────────────────────────────────

def test_tailscale_cli_falls_back_to_windows_host_client(monkeypatch):
    def which(name):
        return '/mnt/c/Program Files/Tailscale/tailscale.exe' if name == 'tailscale.exe' else None
    monkeypatch.setattr(ssh_checks.shutil, 'which', which)
    assert ssh_checks._tailscale_cli() == '/mnt/c/Program Files/Tailscale/tailscale.exe'


def test_tailscale_cli_falls_back_to_the_interop_path_systemd_cannot_see(monkeypatch):
    """A systemd user unit has a Linux-only PATH, so shutil.which finds nothing
    even though the Windows binary is runnable."""
    monkeypatch.setattr(ssh_checks.shutil, 'which', lambda name: None)
    monkeypatch.setattr(ssh_checks.os.path, 'isfile',
                        lambda p: p == '/mnt/c/Program Files/Tailscale/tailscale.exe')
    assert ssh_checks._tailscale_cli() == '/mnt/c/Program Files/Tailscale/tailscale.exe'


def test_tailscale_test_accepts_ping_when_status_is_stale_offline(monkeypatch):
    monkeypatch.setattr(ssh_checks, '_tailscale_cli', lambda: 'tailscale')
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if cmd[:2] == ['tailscale', 'status']:
            return subprocess.CompletedProcess(cmd, 0, '100.111.161.7 phone user android offline\n', '')
        return subprocess.CompletedProcess(cmd, 0, 'pong from phone via DERP(ord)\n', '')
    monkeypatch.setattr(ssh_checks.subprocess, 'run', fake_run)

    result = ssh_checks.tailscale_test({'host': '100.111.161.7'}, timeout=5)
    assert result['ok'] is True
    assert result['text'].startswith('reachable by tailscale ping')
    assert any(cmd[:2] == ['tailscale', 'ping'] for cmd in calls)


def test_tailscale_test_reports_down_when_status_and_ping_fail(monkeypatch):
    monkeypatch.setattr(ssh_checks, '_tailscale_cli', lambda: 'tailscale')

    def fake_run(cmd, **kw):
        if cmd[:2] == ['tailscale', 'status']:
            return subprocess.CompletedProcess(cmd, 0, '100.111.161.7 phone user android offline\n', '')
        return subprocess.CompletedProcess(cmd, 1, '', 'no matching peer\n')
    monkeypatch.setattr(ssh_checks.subprocess, 'run', fake_run)

    result = ssh_checks.tailscale_test({'host': '100.111.161.7'}, timeout=5)
    assert result['ok'] is False
    assert 'offline' in result['text']


def test_tailscale_test_takes_an_online_status_without_pinging(monkeypatch):
    monkeypatch.setattr(ssh_checks, '_tailscale_cli', lambda: 'tailscale')
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, '100.82.55.63 octopus user android -\n', '')
    monkeypatch.setattr(ssh_checks.subprocess, 'run', fake_run)

    assert ssh_checks.tailscale_test({'host': '100.82.55.63'}, timeout=5)['ok'] is True
    assert all(cmd[:2] != ['tailscale', 'ping'] for cmd in calls)


def test_tailscale_test_says_so_when_the_peer_is_not_in_status_at_all(monkeypatch):
    monkeypatch.setattr(ssh_checks, '_tailscale_cli', lambda: 'tailscale')

    def fake_run(cmd, **kw):
        if cmd[:2] == ['tailscale', 'status']:
            return subprocess.CompletedProcess(cmd, 0, '100.0.0.1 other user linux -\n', '')
        return subprocess.CompletedProcess(cmd, 1, '', 'no route\n')
    monkeypatch.setattr(ssh_checks.subprocess, 'run', fake_run)

    result = ssh_checks.tailscale_test({'host': '100.82.55.63'}, timeout=5)
    assert result['ok'] is False
    assert 'not found in tailscale status' in result['text']


# ── connection_test: the dispatch ────────────────────────────────────────────

def test_connection_test_dispatches_on_the_check_key(monkeypatch):
    monkeypatch.setattr(ssh_checks, 'ssh_test', lambda cfg, timeout=None: {'ok': True, 'text': 'ssh'})
    monkeypatch.setattr(ssh_checks, 'tailscale_test', lambda cfg, timeout=None: {'ok': True, 'text': 'ts'})
    assert ssh_checks.connection_test(_cfg())['text'] == 'ssh'
    assert ssh_checks.connection_test(_cfg(check='tailscale'))['text'] == 'ts'


def test_connection_test_prefers_the_entrys_own_timeout(monkeypatch):
    seen = []
    monkeypatch.setattr(ssh_checks, 'ssh_test',
                        lambda cfg, timeout=None: seen.append(timeout) or {'ok': True, 'text': ''})
    ssh_checks.connection_test(_cfg(timeout=55))
    ssh_checks.connection_test(_cfg())
    ssh_checks.connection_test(_cfg(timeout=55), timeout=3)
    assert seen == [55, ssh_checks.SSH_CONNECT_TIMEOUT, 3]


# ── The debounce ─────────────────────────────────────────────────────────────

def test_one_slow_probe_does_not_flip_a_healthy_connection_to_down(monkeypatch):
    cfg = _cfg()
    monkeypatch.setattr(ssh_checks, 'SSH_CONNECTIONS', [cfg])

    monkeypatch.setattr(ssh_checks, 'connection_test',
                        lambda c, timeout=None: {'ok': True, 'text': 'CONNECTED'})
    ssh_checks._poll_all_ssh_once()
    assert ssh_checks.cached_ssh_health(cfg)['ok'] is True

    monkeypatch.setattr(ssh_checks, 'connection_test',
                        lambda c, timeout=None: {'ok': False, 'text': 'timed out'})
    ssh_checks._poll_all_ssh_once()
    assert ssh_checks.cached_ssh_health(cfg)['ok'] is True, \
        'one failure must not flip a healthy connection to down'
    ssh_checks._poll_all_ssh_once()
    assert ssh_checks.cached_ssh_health(cfg)['ok'] is False, \
        'second consecutive failure should flip to down'


def test_health_recovers_immediately_on_success(monkeypatch):
    cfg = _cfg()
    monkeypatch.setattr(ssh_checks, 'SSH_CONNECTIONS', [cfg])
    monkeypatch.setattr(ssh_checks, 'connection_test',
                        lambda c, timeout=None: {'ok': False, 'text': 'timed out'})
    ssh_checks._poll_all_ssh_once()
    ssh_checks._poll_all_ssh_once()
    assert ssh_checks.cached_ssh_health(cfg)['ok'] is False

    monkeypatch.setattr(ssh_checks, 'connection_test',
                        lambda c, timeout=None: {'ok': True, 'text': 'CONNECTED'})
    ssh_checks._poll_all_ssh_once()
    assert ssh_checks.cached_ssh_health(cfg)['ok'] is True, \
        'a single success must clear the fail count immediately'


def test_the_first_failure_is_published_when_nothing_is_cached_yet(monkeypatch):
    """A box that is already down when the dashboard boots has no previous
    result to protect, so the threshold must not hide the first answer."""
    cfg = _cfg()
    monkeypatch.setattr(ssh_checks, 'SSH_CONNECTIONS', [cfg])
    monkeypatch.setattr(ssh_checks, 'connection_test',
                        lambda c, timeout=None: {'ok': False, 'text': 'no route to host'})
    ssh_checks._poll_all_ssh_once()
    assert ssh_checks.cached_ssh_health(cfg)['ok'] is False


def test_cached_ssh_health_probes_synchronously_before_the_loop_has_run(monkeypatch):
    cfg = _cfg()
    calls = []
    monkeypatch.setattr(ssh_checks, 'connection_test',
                        lambda c, timeout=None: calls.append(c) or {'ok': True, 'text': 'CONNECTED'})
    assert ssh_checks.cached_ssh_health(cfg)['ok'] is True
    assert len(calls) == 1
    ssh_checks.cached_ssh_health(cfg)
    assert len(calls) == 1, 'the synchronous fallback must populate the cache, not repeat'


def test_a_concurrent_poll_and_read_never_yields_a_torn_entry(monkeypatch):
    cfg = _cfg()
    monkeypatch.setattr(ssh_checks, 'SSH_CONNECTIONS', [cfg])
    flip = {'ok': True}

    def probe(c, timeout=None):
        flip['ok'] = not flip['ok']
        return {'ok': flip['ok'], 'text': 'CONNECTED' if flip['ok'] else 'timed out'}
    monkeypatch.setattr(ssh_checks, 'connection_test', probe)

    seen = []
    stop = threading.Event()

    def reader():
        while not stop.is_set():
            entry = ssh_checks.cached_ssh_health(cfg)
            seen.append(set(entry))

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    for _ in range(50):
        ssh_checks._poll_all_ssh_once()
    stop.set()
    t.join(timeout=5)
    assert seen and all(shape == {'ok', 'text'} for shape in seen)


# ── The log tail ─────────────────────────────────────────────────────────────

def test_the_log_tail_is_bounded_and_seq_numbers_keep_rising():
    for i in range(ssh_checks.SSH_LOG_TAIL + 10):
        ssh_checks._record_ssh_log('__test_ssh_conn', f'line {i}')
    rows = ssh_checks.connection_log_rows('__test_ssh_conn')
    assert len(rows) == ssh_checks.SSH_LOG_TAIL
    assert [r['seq'] for r in rows] == sorted(r['seq'] for r in rows)
    assert rows[-1]['text'] == f'line {ssh_checks.SSH_LOG_TAIL + 9}'


def test_connection_log_rows_returns_a_copy_not_the_live_deque():
    """The poll thread appends while a route renders. Handing out the deque
    itself makes that an occasional mutation-during-iteration 500."""
    ssh_checks._record_ssh_log('__test_ssh_conn', 'first')
    rows = ssh_checks.connection_log_rows('__test_ssh_conn')
    ssh_checks._record_ssh_log('__test_ssh_conn', 'second')
    assert len(rows) == 1
    assert isinstance(rows, list)


def test_connection_log_rows_is_empty_for_an_unpolled_key():
    assert ssh_checks.connection_log_rows('__never_polled') == []


def test_the_poll_loop_journals_one_line_per_connection(monkeypatch):
    cfg = _cfg()
    monkeypatch.setattr(ssh_checks, 'SSH_CONNECTIONS', [cfg])
    monkeypatch.setattr(ssh_checks, 'connection_test',
                        lambda c, timeout=None: {'ok': False, 'text': 'timed out'})
    ssh_checks._poll_all_ssh_once()
    rows = ssh_checks.connection_log_rows(cfg['key'])
    assert len(rows) == 1
    assert 'FAIL' in rows[0]['text'] and 'timed out' in rows[0]['text']


# ── run_manual_test: the Test button ─────────────────────────────────────────

def test_run_manual_test_publishes_its_answer_without_waiting_for_the_threshold(monkeypatch):
    """A human pressing Test is asking "is it back yet". Debouncing that would
    mean pressing it twice."""
    cfg = _cfg()
    monkeypatch.setattr(ssh_checks, 'connection_test',
                        lambda c, timeout=None: {'ok': False, 'text': 'no route to host'})
    result = ssh_checks.run_manual_test(cfg)
    assert result['ok'] is False
    assert ssh_checks.cached_ssh_health(cfg)['ok'] is False


def test_run_manual_test_marks_its_log_line_as_manual(monkeypatch):
    cfg = _cfg()
    monkeypatch.setattr(ssh_checks, 'connection_test',
                        lambda c, timeout=None: {'ok': True, 'text': 'CONNECTED — box'})
    ssh_checks.run_manual_test(cfg)
    rows = ssh_checks.connection_log_rows(cfg['key'])
    assert rows[-1]['text'].endswith('(manual test)')
    assert 'OK' in rows[-1]['text']


def test_a_manual_success_clears_a_previously_failed_cache(monkeypatch):
    cfg = _cfg()
    monkeypatch.setattr(ssh_checks, 'SSH_CONNECTIONS', [cfg])
    monkeypatch.setattr(ssh_checks, 'connection_test',
                        lambda c, timeout=None: {'ok': False, 'text': 'timed out'})
    ssh_checks._poll_all_ssh_once()
    ssh_checks._poll_all_ssh_once()
    assert ssh_checks.cached_ssh_health(cfg)['ok'] is False

    monkeypatch.setattr(ssh_checks, 'connection_test',
                        lambda c, timeout=None: {'ok': True, 'text': 'CONNECTED'})
    ssh_checks.run_manual_test(cfg)
    assert ssh_checks.cached_ssh_health(cfg)['ok'] is True


# ── What server.py re-exports, and what it must not ──────────────────────────

@pytest.mark.parametrize('name', [
    'SSH_CONNECTIONS', 'SSH_HEALTH_POLL_INTERVAL', '_ssh_poll_loop',
    'cached_ssh_health', 'connection_log_rows', 'get_ssh_connection',
])
def test_server_re_exports_the_owning_modules_object(name):
    assert getattr(server, name) is getattr(ssh_checks, name)


def test_server_re_exports_run_manual_test_under_its_route_facing_name():
    assert server.run_manual_ssh_test is ssh_checks.run_manual_test


@pytest.mark.parametrize('name', [
    'SSH_CONNECT_TIMEOUT', 'SSH_HEALTH_FAIL_THRESHOLD', 'SSH_LOG_TAIL',
    '_ssh_health_cache', '_ssh_health_lock', '_ssh_log_cache', '_ssh_log_lock',
    '_ssh_test_once', '_tailscale_cli', '_tailscale_ping_test', '_record_ssh_log',
    '_poll_all_ssh_once', 'ssh_test', 'tailscale_test', 'connection_test',
])
def test_dead_re_exports_are_gone_from_server(name):
    """Nothing calls these through `server` any more. Asserting their absence is
    what stops a future round quietly re-adding a second binding."""
    assert not hasattr(server, name), f'server.{name} is a dead re-export'
