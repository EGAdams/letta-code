"""Lifecycle object for the local Agent Blocks documentation server."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
import subprocess
import urllib.request

from contracts import StrictModel


class ServiceStartResult(StrictModel):
    """Result returned to the Server Management restart boundary."""

    ok: bool
    text: str


class AgentBlocksServer:
    """Request the independent user service; never own the SPA process."""

    def __init__(
        self,
        *,
        start_script: str | Path,
        startup_log: str | Path,
        health_url: str = 'http://localhost:8931/',
        health_opener: Callable = urllib.request.urlopen,
        launcher: Callable = subprocess.run,
        mark_starting: Callable[[str], None] = lambda _key: None,
    ) -> None:
        self._start_script = Path(start_script)
        self._startup_log = Path(startup_log)
        self._health_url = health_url
        self._health_opener = health_opener
        self._launcher = launcher
        self._mark_starting = mark_starting

    def is_running(self) -> bool:
        """Return whether the existing service answers successfully."""
        try:
            response = self._health_opener(self._health_url, timeout=2)
            try:
                return 200 <= getattr(response, 'status', 200) < 400
            finally:
                response.close()
        except (OSError, TimeoutError):
            return False

    def start(self) -> ServiceStartResult:
        """Idempotently request systemd startup outside the dashboard cgroup."""
        if self.is_running():
            return ServiceStartResult(
                ok=True,
                text='Agent Blocks Server is already running.',
            )
        if not self._start_script.is_file():
            return ServiceStartResult(
                ok=False,
                text=f'Start script not found: {self._start_script}',
            )

        try:
            with self._startup_log.open('a', encoding='utf-8') as log_file:
                timestamp = datetime.now().isoformat(timespec='seconds')
                log_file.write(f'\n--- launch requested {timestamp} ---\n')
                log_file.flush()
                self._launcher(
                    ['systemctl', '--user', 'start', '--no-block',
                     'agent-blocks-server.service'],
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=10,
                )
            self._mark_starting('agent-blocks')
            return ServiceStartResult(
                ok=True,
                text=(f'Requested agent-blocks-server.service — tailing '
                      f'{self._startup_log}'),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return ServiceStartResult(ok=False, text=str(exc))
