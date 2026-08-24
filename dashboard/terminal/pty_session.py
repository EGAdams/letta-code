"""A login shell in a pty, and getting rid of it afterwards.

The spawning half is short. The reaping half is the reason this is its own
module: letta-code detaches into its own process group and reparents to init,
so a process-group kill misses it entirely and the browser tab closes over a
still-running agent. What it cannot escape without calling setsid() -- which it
does not -- is the pty's *session*, so teardown walks /proc looking for the
session id and kills by that instead.

Every closed terminal tab that left a bun process burning CPU on this box came
from getting that distinction wrong.
"""

from __future__ import annotations

import fcntl
import os
import pty
import signal
import struct
import termios
import time

def _terminal_spawn_shell(cols, rows, letta_agent_id):
    """pty.fork() a login shell sized cols×rows; returns (child_pid, master_fd).

    When letta_agent_id is set the command to open that agent is typed into the
    pty so it shows up in the terminal and runs as soon as bash is up.
    """
    pid, master_fd = pty.fork()
    if pid == 0:  # child
        env = dict(os.environ)
        env['TERM'] = 'xterm-256color'
        env['COLORTERM'] = 'truecolor'
        os.chdir(os.path.expanduser('~'))
        os.execvpe('bash', ['bash', '-l'], env)
    # Native byte order, not '!': TIOCSWINSZ takes a C `struct winsize`, so
    # big-endian packing byte-swaps every field (80x24 arrives as 20480x6144).
    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
    if letta_agent_id:
        os.write(master_fd, f'letta --agent {letta_agent_id}\n'.encode())
    return pid, master_fd


def _session_pids(sid):
    """PIDs whose session id == sid (read from /proc/<pid>/stat field 6).

    letta-code detaches into its own process group and reparents to init, so a
    process-group kill misses it — but it can't leave the pty's *session*
    without setsid(), which it doesn't call. Reaping by session catches it.
    """
    pids = []
    for entry in os.listdir('/proc'):
        if not entry.isdigit():
            continue
        try:
            with open(f'/proc/{entry}/stat', 'rb') as f:
                fields = f.read().rsplit(b')', 1)[1].split()
            # after the ')' the fields are: state ppid pgrp session ...
            if int(fields[3]) == sid:
                pids.append(int(entry))
        except (OSError, ValueError, IndexError):
            continue
    return pids


def _terminal_reap(pid):
    """Tear down the shell and every process in its pty session.

    pty.fork() made `pid` the session leader (sid == pid). We SIGHUP the whole
    session, then SIGKILL any survivor, so detached children (bun/letta) die too.
    """
    for sig, grace in ((signal.SIGHUP, 1.0), (signal.SIGKILL, 0.5)):
        for target in _session_pids(pid) or [pid]:
            try:
                os.kill(target, sig)
            except (ProcessLookupError, PermissionError):
                pass
        deadline = time.time() + grace
        while time.time() < deadline:
            try:
                done, _status = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                done = pid  # already reaped by someone else
            if done:
                break
            time.sleep(0.05)
