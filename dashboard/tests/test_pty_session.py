"""Spawning a shell in a pty, and — the hard part — getting rid of it.

The teardown is why this module exists. letta-code detaches into its own
process group and reparents to init, so killing the process group misses it
entirely: the browser tab closes, the panel disappears, and a bun process keeps
burning CPU on this box with nothing pointing at it. What it cannot escape
without calling setsid() — which it does not — is the pty's *session*, so the
reaper walks /proc looking for the session id instead.

These tests run against real processes rather than mocks wherever they safely
can, because the bug being guarded against is precisely one that a mock of
os.kill would not have caught: the wrong set of PIDs was being killed, very
successfully.
"""
import os
import signal
import struct
import time

import pytest

import server
from terminal import pty_session as ptys


class TestFindingASession:
    def test_this_process_is_found_in_its_own_session(self):
        sid = os.getsid(0)
        assert os.getpid() in ptys._session_pids(sid)

    def test_a_session_that_does_not_exist_yields_nothing(self):
        assert ptys._session_pids(0x7FFFFFF0) == []

    def test_a_process_that_exits_mid_scan_is_skipped_not_raised(self, monkeypatch):
        """/proc is a race by construction: a PID listed by listdir can be gone
        before its stat file is opened, and an unhandled FileNotFoundError
        there would take down the scan — which runs during teardown.

        Driven with a PID that genuinely does not exist rather than a patched
        `open`, so the real errno path is the one exercised.
        """
        real = ptys.os.listdir
        monkeypatch.setattr(ptys.os, 'listdir',
                            lambda p: ['4194303'] + real(p))
        assert os.getpid() in ptys._session_pids(os.getsid(0))

    def test_a_malformed_stat_line_is_skipped(self, monkeypatch):
        """A process name can contain ')' and spaces, which is why the parser
        splits on the LAST ')'. Anything it still cannot read is skipped."""
        monkeypatch.setattr(ptys.os, 'listdir', lambda p: ['1', 'self', 'x'])

        class Boom:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b'garbage with no paren'

        monkeypatch.setattr(ptys, 'open', lambda *a, **k: Boom(), raising=False)
        assert ptys._session_pids(1) == []

    def test_non_numeric_proc_entries_are_ignored(self, monkeypatch):
        """/proc holds 'self', 'meminfo', 'net' and friends beside the PIDs."""
        seen = []
        monkeypatch.setattr(ptys.os, 'listdir',
                            lambda p: ['self', 'meminfo', 'net', 'thread-self'])
        monkeypatch.setattr(ptys, 'open',
                            lambda *a, **k: seen.append(a) or (_ for _ in ()).throw(OSError()),
                            raising=False)
        assert ptys._session_pids(1) == []
        assert seen == []


class TestSpawningTheShell:
    def test_it_returns_a_live_child_and_a_readable_master(self):
        pid, fd = ptys._terminal_spawn_shell(80, 24, None)
        try:
            assert pid > 0 and fd > 2
            os.kill(pid, 0)              # raises if it is not there
        finally:
            ptys._terminal_reap(pid)
            os.close(fd)

    def test_the_child_leads_its_own_session(self):
        """The whole teardown strategy rests on sid == pid, which is what
        pty.fork() guarantees. If that stopped holding, the reaper would be
        looking up a session nobody is in."""
        pid, fd = ptys._terminal_spawn_shell(80, 24, None)
        try:
            assert os.getsid(pid) == pid
        finally:
            ptys._terminal_reap(pid)
            os.close(fd)

    def test_the_window_size_arrives_the_right_way_round(self):
        """TIOCSWINSZ takes a C struct winsize, so the pack must be native
        order. Packing big-endian byte-swaps every field and 80x24 arrives as
        20480x6144 — which the shell believes, and then wraps every line."""
        import fcntl
        import termios
        pid, fd = ptys._terminal_spawn_shell(100, 30, None)
        try:
            packed = fcntl.ioctl(fd, termios.TIOCGWINSZ, b'\0' * 8)
            rows, cols, _, _ = struct.unpack('HHHH', packed)
            assert (cols, rows) == (100, 30)
        finally:
            ptys._terminal_reap(pid)
            os.close(fd)

    def test_an_agent_id_is_typed_into_the_pty_so_it_is_visible(self):
        """Typed rather than exec'd on purpose: the operator sees the command
        that opened their session, and exiting letta drops back to bash."""
        pid, fd = ptys._terminal_spawn_shell(80, 24, 'agent-abc123')
        try:
            deadline = time.time() + 5
            seen = b''
            os.set_blocking(fd, False)
            while time.time() < deadline and b'agent-abc123' not in seen:
                try:
                    seen += os.read(fd, 4096)
                except (BlockingIOError, OSError):
                    time.sleep(0.05)
            assert b'letta --agent agent-abc123' in seen
        finally:
            ptys._terminal_reap(pid)
            os.close(fd)

    def test_no_agent_types_nothing(self, monkeypatch):
        written = []
        monkeypatch.setattr(ptys.pty, 'fork', lambda: (4242, 9))
        monkeypatch.setattr(ptys.fcntl, 'ioctl', lambda *a: None)
        monkeypatch.setattr(ptys.os, 'write', lambda fd, b: written.append(b))
        ptys._terminal_spawn_shell(80, 24, None)
        assert written == []


class TestReaping:
    def test_a_real_shell_is_gone_afterwards(self):
        pid, fd = ptys._terminal_spawn_shell(80, 24, None)
        ptys._terminal_reap(pid)
        os.close(fd)
        with pytest.raises(OSError):
            for _ in range(40):
                os.kill(pid, 0)
                time.sleep(0.05)

    def test_it_signals_the_whole_session_not_just_the_leader(self, monkeypatch):
        """The bug this exists to prevent: killing only `pid` leaves every
        detached child of the session running."""
        killed = []
        monkeypatch.setattr(ptys, '_session_pids', lambda sid: [111, 222, 333])
        monkeypatch.setattr(ptys.os, 'kill', lambda p, s: killed.append((p, s)))
        monkeypatch.setattr(ptys.os, 'waitpid', lambda p, f: (111, 0))
        ptys._terminal_reap(111)
        assert {p for p, _ in killed} == {111, 222, 333}

    def test_it_hangs_up_before_it_kills(self, monkeypatch):
        """SIGHUP first so a shell can run its exit traps; SIGKILL only for
        whatever ignored it."""
        killed = []
        monkeypatch.setattr(ptys, '_session_pids', lambda sid: [111])
        monkeypatch.setattr(ptys.os, 'kill', lambda p, s: killed.append(s))
        monkeypatch.setattr(ptys.os, 'waitpid', lambda p, f: (0, 0))
        monkeypatch.setattr(ptys.time, 'sleep', lambda s: None)
        monkeypatch.setattr(ptys.time, 'time', _clock())
        ptys._terminal_reap(111)
        assert killed[0] == signal.SIGHUP
        assert signal.SIGKILL in killed

    def test_an_empty_session_scan_still_targets_the_leader(self, monkeypatch):
        """If /proc gives nothing back — a permissions problem, a race — the
        fallback is the PID we already hold, not a silent no-op that leaks the
        shell."""
        killed = []
        monkeypatch.setattr(ptys, '_session_pids', lambda sid: [])
        monkeypatch.setattr(ptys.os, 'kill', lambda p, s: killed.append(p))
        monkeypatch.setattr(ptys.os, 'waitpid', lambda p, f: (999, 0))
        ptys._terminal_reap(999)
        assert 999 in killed

    def test_an_already_dead_process_is_not_an_error(self, monkeypatch):
        """The common case: the user typed `exit`, and teardown runs anyway."""
        monkeypatch.setattr(ptys, '_session_pids', lambda sid: [111])

        def gone(p, s):
            raise ProcessLookupError(p)

        monkeypatch.setattr(ptys.os, 'kill', gone)
        monkeypatch.setattr(ptys.os, 'waitpid', lambda p, f: (111, 0))
        ptys._terminal_reap(111)          # must not raise

    def test_a_process_owned_by_someone_else_is_skipped(self, monkeypatch):
        monkeypatch.setattr(ptys, '_session_pids', lambda sid: [1, 111])

        def denied(p, s):
            if p == 1:
                raise PermissionError(p)

        monkeypatch.setattr(ptys.os, 'kill', denied)
        monkeypatch.setattr(ptys.os, 'waitpid', lambda p, f: (111, 0))
        ptys._terminal_reap(111)          # must not raise

    def test_a_child_reaped_by_someone_else_ends_the_wait(self, monkeypatch):
        """SIGCHLD handling elsewhere in the process can beat us to waitpid.
        Treating that as 'still running' would burn the whole grace period."""
        monkeypatch.setattr(ptys, '_session_pids', lambda sid: [111])
        monkeypatch.setattr(ptys.os, 'kill', lambda p, s: None)

        def already(p, f):
            raise ChildProcessError(p)

        monkeypatch.setattr(ptys.os, 'waitpid', already)
        slept = []
        monkeypatch.setattr(ptys.time, 'sleep', lambda s: slept.append(s))
        ptys._terminal_reap(111)
        assert slept == []


def _clock():
    """A monotonic fake so the grace-period loops terminate instantly."""
    ticks = iter(range(0, 10_000))
    return lambda: next(ticks)


class TestServerReExports:
    @pytest.mark.parametrize('name', [
        '_terminal_spawn_shell', '_terminal_reap', '_session_pids'])
    def test_the_historical_name_still_resolves(self, name):
        assert getattr(server, name) is getattr(ptys, name)
