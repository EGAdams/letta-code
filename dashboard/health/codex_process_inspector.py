"""Finds running Codex CLI process groups by reading /proc directly.

No `ps` text-parsing: `comm` and `cmdline` are exact, and the fd table is the
only reliable way to prove which rollout file a process actually has open --
matching by cwd would have blamed the wrong session in the 2026-09-07
incident, where three autonomous sessions shared one cwd.
"""

from __future__ import annotations

import os
import subprocess
from typing import Dict, List, Optional

from health.codex_watchdog_contracts import CodexProcessGroup, ICodexProcessInspector

DEFAULT_SESSIONS_ROOT = os.path.expanduser('~/.codex/sessions/')


def _read_bytes(path: str) -> bytes:
    try:
        with open(path, 'rb') as handle:
            return handle.read()
    except OSError:
        return b''


def _cmdline_parts(pid: int) -> List[bytes]:
    raw = _read_bytes(f'/proc/{pid}/cmdline')
    return [part for part in raw.split(b'\x00') if part]


def _is_codex_process(pid: int) -> bool:
    comm = _read_bytes(f'/proc/{pid}/comm').strip()
    if comm == b'codex':
        return True
    return any(part == b'codex' or part.endswith(b'/codex')
               for part in _cmdline_parts(pid))


def _state_and_elapsed(pid: int) -> tuple:
    try:
        result = subprocess.run(
            ['ps', '-o', 'stat=,etimes=', '-p', str(pid)],
            capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return 'unknown', 0.0
    line = result.stdout.strip()
    if not line:
        return 'unknown', 0.0
    parts = line.split()
    stat = parts[0] if parts else 'unknown'
    try:
        elapsed = float(parts[1]) if len(parts) > 1 else 0.0
    except ValueError:
        elapsed = 0.0
    return stat, elapsed


def _find_open_session_file(pids: List[int], sessions_root: str) -> Optional[str]:
    for pid in pids:
        fd_dir = f'/proc/{pid}/fd'
        try:
            names = os.listdir(fd_dir)
        except OSError:
            continue
        for name in names:
            try:
                target = os.readlink(f'{fd_dir}/{name}')
            except OSError:
                continue
            if target.startswith(sessions_root) and target.endswith('.jsonl'):
                return target
    return None


class ProcProcessInspector(ICodexProcessInspector):
    """Real implementation: /proc plus one `ps` call per group for state."""

    def __init__(self, sessions_root: str = DEFAULT_SESSIONS_ROOT) -> None:
        self._sessions_root = sessions_root

    def running_groups(self) -> List[CodexProcessGroup]:
        by_pgid: Dict[int, List[int]] = {}
        for entry in os.listdir('/proc'):
            if not entry.isdigit():
                continue
            pid = int(entry)
            if not _is_codex_process(pid):
                continue
            try:
                pgid = os.getpgid(pid)
            except ProcessLookupError:
                continue
            by_pgid.setdefault(pgid, []).append(pid)

        groups: List[CodexProcessGroup] = []
        for pgid, pids in by_pgid.items():
            lead_pid = pgid if pgid in pids else pids[0]
            cmd = b' '.join(_cmdline_parts(lead_pid)).decode(
                'utf-8', errors='replace')
            try:
                cwd = os.readlink(f'/proc/{lead_pid}/cwd')
            except OSError:
                cwd = ''
            state, elapsed = _state_and_elapsed(lead_pid)
            session_path = _find_open_session_file(pids, self._sessions_root)
            groups.append(CodexProcessGroup(
                pgid=pgid,
                pids=sorted(pids),
                cmd=cmd,
                cwd=cwd,
                state=state,
                elapsed_seconds=elapsed,
                session_path=session_path,
            ))
        return groups
