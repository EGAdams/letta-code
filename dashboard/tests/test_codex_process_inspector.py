"""ProcProcessInspector against a real process.

Spawns a copy of `bash` renamed to `codex` (Linux sets `/proc/pid/comm` from
the exec'd file's basename, which is exactly how the real Codex CLI's vendor
binary ends up with `comm == 'codex'`) holding a file descriptor open on a
fake rollout file, and confirms the inspector both finds it as a Codex group
and matches it to the exact open file via /proc/<pid>/fd -- not by cwd,
which the 2026-09-07 incident showed is ambiguous with multiple sessions in
the same directory.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time

import pytest

from health.codex_process_inspector import ProcProcessInspector
from health.codex_watchdog_contracts import AUTONOMOUS_FLAG

pytestmark = pytest.mark.skipif(
    not os.path.exists('/bin/bash') or os.name != 'posix',
    reason='needs a POSIX shell to exec under a renamed binary')


@pytest.fixture
def fake_codex_process(tmp_path):
    fake_bin = tmp_path / 'codex'
    shutil.copy('/bin/bash', fake_bin)
    fake_bin.chmod(0o755)

    sessions_root = tmp_path / 'sessions'
    sessions_root.mkdir()
    session_file = sessions_root / 'rollout-fake.jsonl'
    session_file.write_text('{}\n')

    # `sleep 30 & wait` rather than a bare tail `sleep 30`: bash tail-call
    # optimizes a lone final command by exec-replacing itself, which would
    # swap our renamed `codex` process image (and its comm) out for `sleep`.
    # Backgrounding forces a real fork, so the `codex`-named bash process
    # (and the fd it opened) stays alive as the one we captured the pid of.
    proc = subprocess.Popen(
        [str(fake_bin), '-c', 'exec 3< "$1"; sleep 30 & wait',
         '_', str(session_file)],
        cwd=str(tmp_path), start_new_session=True,
    )
    try:
        for _ in range(50):
            if os.path.exists(f'/proc/{proc.pid}/fd'):
                break
            time.sleep(0.05)
        yield proc, str(session_file), str(sessions_root) + os.sep
    finally:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)


def test_finds_the_process_and_its_exact_open_session_file(fake_codex_process):
    proc, session_file, sessions_root = fake_codex_process
    inspector = ProcProcessInspector(sessions_root=sessions_root)

    deadline = time.time() + 3
    match = None
    while time.time() < deadline and match is None:
        groups = inspector.running_groups()
        match = next((g for g in groups if proc.pid in g.pids), None)
        if match is None:
            time.sleep(0.1)

    assert match is not None, 'inspector did not find the fake codex process'
    assert match.session_path == session_file
    assert not match.autonomous  # no --dangerously-bypass flag on this fake


def test_reports_the_autonomous_flag_when_present(tmp_path):
    fake_bin = tmp_path / 'codex'
    shutil.copy('/bin/bash', fake_bin)
    fake_bin.chmod(0o755)

    proc = subprocess.Popen(
        [str(fake_bin), '-c',
         f'echo {AUTONOMOUS_FLAG} >/dev/null; sleep 30 & wait'],
        cwd=str(tmp_path), start_new_session=True,
    )
    try:
        inspector = ProcProcessInspector(sessions_root=str(tmp_path) + os.sep)
        deadline = time.time() + 3
        match = None
        while time.time() < deadline and match is None:
            groups = inspector.running_groups()
            match = next((g for g in groups if proc.pid in g.pids), None)
            if match is None:
                time.sleep(0.1)
        assert match is not None
        assert AUTONOMOUS_FLAG in match.cmd
        assert match.autonomous
    finally:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)
