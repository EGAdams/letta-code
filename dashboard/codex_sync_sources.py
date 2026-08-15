"""Strategies for refilling the r46-codex fallback slot (~/.codex-moms/auth.json).

Split out of codex_sync_status.py along the ABC-port/implementation seam
(that module keeps the Pydantic DTOs + pure status functions; this one owns
the "how do I actually get a new token into the fallback slot" behavior).
"""

from __future__ import annotations

import json
import os
import subprocess
from abc import ABC, abstractmethod

CODEX_PRIMARY_AUTH_JSON = os.path.expanduser('~/.codex/auth.json')
CODEX_MOMS_AUTH_JSON = os.path.expanduser('~/.codex-moms/auth.json')
CODEX_MOMS_SYNC_SCRIPT = os.path.expanduser('~/server_tools/sync_moms_codex_token.sh')


class ICodexFallbackSyncSource(ABC):
    """Strategy: how the r46-codex fallback slot gets refilled. Two
    interchangeable ways to answer "what account should the fallback slot
    hold" — swapping the source is exactly the concern of this ABC."""

    key: str

    @abstractmethod
    def sync(self) -> tuple[bool, str]:
        """Attempt the refill; returns (ok, output)."""


class R46ScriptSyncSource(ICodexFallbackSyncSource):
    """Default: pull mom's account over SSH, same code path the timer runs.
    Preserves the dual-account failover (see codex_token_slot_assignment_rule
    in memory) — this is the source that keeps primary and fallback on
    different accounts."""

    key = 'r46'

    def sync(self) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                ['bash', CODEX_MOMS_SYNC_SCRIPT],
                capture_output=True, text=True, timeout=30,
            )
            return result.returncode == 0, (result.stdout or '') + (result.stderr or '')
        except Exception as exc:
            return False, str(exc)


class PrimaryCopySyncSource(ICodexFallbackSyncSource):
    """Deliberately collapses the fallback slot onto EG's own (W11) account —
    only reachable via an explicit 'Copy from W11' click, never the default
    or the timer. This defeats the dual-account failover the R46 source
    exists to preserve, so it stays a conscious opt-in with its own button,
    not a parameter anyone could pass by accident."""

    key = 'w11'

    def sync(self) -> tuple[bool, str]:
        try:
            with open(CODEX_PRIMARY_AUTH_JSON, encoding='utf-8') as fh:
                data = json.load(fh)
            tokens = data.get('tokens', {})
            if data.get('auth_mode') != 'chatgpt' or not tokens.get('access_token'):
                return False, 'primary auth.json is not a valid chatgpt OAuth session'
            os.makedirs(os.path.dirname(CODEX_MOMS_AUTH_JSON), exist_ok=True)
            tmp = f'{CODEX_MOMS_AUTH_JSON}.tmp.{os.getpid()}'
            with open(tmp, 'w', encoding='utf-8') as fh:
                json.dump(data, fh)
            os.chmod(tmp, 0o600)
            os.replace(tmp, CODEX_MOMS_AUTH_JSON)
            return True, f'copied {CODEX_PRIMARY_AUTH_JSON} -> {CODEX_MOMS_AUTH_JSON}'
        except Exception as exc:
            return False, str(exc)


SYNC_SOURCES: dict[str, ICodexFallbackSyncSource] = {
    'r46': R46ScriptSyncSource(),
    'w11': PrimaryCopySyncSource(),
}
