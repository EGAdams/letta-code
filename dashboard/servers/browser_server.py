"""Lifecycle boundary for the remote ChatGPT browser server."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
import subprocess
import time
import urllib.request

from contracts import StrictModel


class BrowserServerStartResult(StrictModel):
    """Result returned to the Server Management restart boundary."""

    ok: bool
    text: str


class IBrowserServerLifecycle(ABC):
    """Start and verify the browser server without exposing SSH to callers."""

    @abstractmethod
    def restart(self) -> BrowserServerStartResult:
        """Ensure the managed browser server is running."""


class SshBrowserServerLifecycle(IBrowserServerLifecycle):
    """Control the browser server's enabled user unit over SSH."""

    def __init__(
        self,
        *,
        remote_host: str,
        health_url: str,
        health_opener: Callable = urllib.request.urlopen,
        command_runner: Callable = subprocess.run,
        sleeper: Callable[[float], None] = time.sleep,
        mark_starting: Callable[[str], None] = lambda _key: None,
        log_restart: Callable[[str], None] = lambda _line: None,
        verify_attempts: int = 6,
    ) -> None:
        self._remote_host = remote_host
        self._health_url = health_url
        self._health_opener = health_opener
        self._command_runner = command_runner
        self._sleeper = sleeper
        self._mark_starting = mark_starting
        self._log_restart = log_restart
        self._verify_attempts = verify_attempts

    def _is_healthy(self) -> bool:
        try:
            response = self._health_opener(self._health_url, timeout=3)
            try:
                return 200 <= getattr(response, 'status', 200) < 400
            finally:
                response.close()
        except (OSError, TimeoutError):
            return False

    def restart(self) -> BrowserServerStartResult:
        if self._is_healthy():
            return BrowserServerStartResult(
                ok=True,
                text=f'browser_server already running at {self._health_url}',
            )

        unit = 'browser-server.service'
        command = [
            'ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes',
            self._remote_host, 'systemctl', '--user', 'restart', unit,
        ]
        self._log_restart(
            f'browser-server: restarting {unit} on {self._remote_host}')
        try:
            result = self._command_runner(
                command,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return BrowserServerStartResult(
                ok=False,
                text=f'Could not restart {unit}: {exc}',
            )

        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()[:300]
            return BrowserServerStartResult(
                ok=False,
                text=f'systemctl restart {unit} failed: {detail}',
            )

        self._mark_starting('browser-server')
        for _attempt in range(self._verify_attempts):
            self._sleeper(1)
            if self._is_healthy():
                return BrowserServerStartResult(
                    ok=True,
                    text=(f'Restarted enabled {unit} on {self._remote_host}; '
                          'Chrome launches lazily on the first relay message.'),
                )

        return BrowserServerStartResult(
            ok=False,
            text=(f'{unit} restarted but {self._health_url} did not become '
                  'healthy.'),
        )
