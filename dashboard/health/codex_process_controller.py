"""Sends real signals to a Codex CLI process group."""

from __future__ import annotations

import os
import signal

from health.codex_watchdog_contracts import ICodexProcessController


class OsProcessController(ICodexProcessController):
    """Real implementation: `os.killpg`, swallowing an already-dead group."""

    def terminate(self, pgid: int) -> None:
        self._send(pgid, signal.SIGTERM)

    def force_kill(self, pgid: int) -> None:
        self._send(pgid, signal.SIGKILL)

    @staticmethod
    def _send(pgid: int, sig: int) -> None:
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError):
            pass
