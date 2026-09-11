"""Codex moms-token sync status — dual-account fallback for Mazda's
categorizer.

~/.codex/auth.json is EG's primary (W11) account; ~/.codex-moms/auth.json is
a periodically-refreshed cache of mom's (R46) account, used as a fallback
only when the primary errors (see server_tools/sync_moms_codex_token.sh).

This module owns the DTOs (Pydantic, per contracts.StrictModel) and the pure
translation of "two auth.json files + a script" into the payload the Model
Stats sync panel renders, so server.py's route handlers stay thin dispatch,
not business logic.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import time
from typing import Literal, Optional, Sequence

from codex_sync_sources import SYNC_SOURCES
from contracts import StrictModel

CODEX_MOMS_SYNC_INTERVAL_SECONDS = 4 * 3600  # keep in sync with
# ~/.config/systemd/user/codex-moms-token-sync.timer's OnUnitActiveSec
CODEX_PRIMARY_AUTH_JSON = os.path.expanduser('~/.codex/auth.json')
CODEX_MOMS_AUTH_JSON = os.path.expanduser('~/.codex-moms/auth.json')
CODEX_MOMS_SYNC_TIMER = 'codex-moms-token-sync.timer'
CODEX_MOMS_LAST_SOURCE_FILE = os.path.expanduser('~/.codex-moms/.last_sync_source')

# The timer only pulls every 4h, which let the fallback slot sit stale/wrong
# for weeks (2026-09-11 incident: r46-codex silently held EG's own account).
# Every status check now also self-heals the collapse on the spot, throttled
# by this cooldown so a page left open doesn't SSH to R46 on every poll.
CODEX_AUTO_RECOVER_COOLDOWN_SECONDS = 300
REAUTH_MESSAGE = 'Token not synced. Try authenticating again.'
_last_auto_recover_attempt_epoch: Optional[float] = None


class CodexTokenSlot(StrictModel):
    """One local auth.json slot and the account currently occupying it."""

    key: str
    label: str
    email: Optional[str] = None


class CodexSyncStatus(StrictModel):
    """Countdown + current-account-per-slot payload for the Model Stats
    'codex sync' panel."""

    interval_seconds: int
    last_sync_epoch: Optional[float] = None
    next_sync_epoch: Optional[float] = None
    seconds_remaining: Optional[float] = None
    slots: Sequence[CodexTokenSlot] = ()
    ran: bool = False
    ok: Optional[bool] = None
    output: Optional[str] = None
    source: Optional[str] = None
    sync_enabled: bool = True
    toggle_error: Optional[str] = None
    needs_reauth: bool = False
    reauth_message: Optional[str] = None


def _codex_auth_email(path: str) -> Optional[str]:
    """Decode the ChatGPT-OAuth JWT's profile email out of a codex auth.json.
    Returns None (never raises) if the file is missing or unreadable — the
    sync panel shows 'unknown' rather than a 500."""
    try:
        with open(path, encoding='utf-8') as fh:
            tokens = json.load(fh).get('tokens', {})
        access_token = tokens.get('access_token', '')
        payload_b64 = access_token.split('.')[1]
        payload_b64 += '=' * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get('https://api.openai.com/profile', {}).get('email')
    except Exception:
        return None


def _codex_token_slots() -> tuple[CodexTokenSlot, CodexTokenSlot]:
    return (
        CodexTokenSlot(
            key='w11-codex',
            label='W11 Codex OAuth (primary)',
            email=_codex_auth_email(CODEX_PRIMARY_AUTH_JSON),
        ),
        CodexTokenSlot(
            key='r46-codex',
            label='R46 Codex OAuth (fallback cache)',
            email=_codex_auth_email(CODEX_MOMS_AUTH_JSON),
        ),
    )


def _last_recorded_source() -> Optional[str]:
    """Which source last successfully filled the fallback slot. Used to tell
    a deliberate 'Copy from W11' collapse (leave it alone) apart from the
    slot merely having gone stale/wrong (self-heal it) — both look identical
    as 'w11 email == r46 email'."""
    try:
        with open(CODEX_MOMS_LAST_SOURCE_FILE, encoding='utf-8') as fh:
            return fh.read().strip() or None
    except Exception:
        return None


def _record_last_source(source: str) -> None:
    try:
        os.makedirs(os.path.dirname(CODEX_MOMS_LAST_SOURCE_FILE), exist_ok=True)
        with open(CODEX_MOMS_LAST_SOURCE_FILE, 'w', encoding='utf-8') as fh:
            fh.write(source)
    except Exception:
        pass  # advisory only — worst case a future auto-recover fights a deliberate w11 copy


def _slots_collapsed(slots: tuple[CodexTokenSlot, CodexTokenSlot]) -> bool:
    w11, r46 = slots
    return bool(w11.email) and w11.email == r46.email


def _auto_recover(slots: tuple[CodexTokenSlot, CodexTokenSlot]) -> tuple[tuple[CodexTokenSlot, CodexTokenSlot], bool, Optional[str]]:
    """Called on every status read. If the fallback slot has collapsed onto
    the primary account and that wasn't a deliberate 'Copy from W11' click,
    try an R46 pull right away instead of waiting for the 4h timer. Returns
    (possibly-refreshed slots, needs_reauth, reauth_message)."""
    global _last_auto_recover_attempt_epoch
    if not _slots_collapsed(slots):
        return slots, False, None
    if _last_recorded_source() == 'w11':
        return slots, False, None  # deliberate collapse — not our problem to fix
    now = time.time()
    if (
        _last_auto_recover_attempt_epoch is not None
        and now - _last_auto_recover_attempt_epoch < CODEX_AUTO_RECOVER_COOLDOWN_SECONDS
    ):
        return slots, True, REAUTH_MESSAGE  # already tried recently and it's still collapsed
    _last_auto_recover_attempt_epoch = now
    strategy = SYNC_SOURCES.get('r46')
    ok, _output = strategy.sync() if strategy else (False, 'no r46 sync source')
    if ok:
        _record_last_source('r46')
    new_slots = _codex_token_slots()
    if _slots_collapsed(new_slots) and _last_recorded_source() != 'w11':
        return new_slots, True, REAUTH_MESSAGE
    return new_slots, False, None


def codex_sync_timer_enabled() -> bool:
    """Whether the automatic 4h pull is armed. Checked live via systemctl
    rather than cached, so a change made outside the dashboard (a terminal
    `systemctl --user disable`) is reflected immediately."""
    try:
        result = subprocess.run(
            ['systemctl', '--user', 'is-enabled', CODEX_MOMS_SYNC_TIMER],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() == 'enabled'
    except Exception:
        return True  # fail toward "assume it's on" rather than hiding a live timer


def set_codex_sync_timer_enabled(enabled: bool) -> tuple[bool, str]:
    """Enable+start or disable+stop the automatic-pull timer. `--now` so the
    dashboard toggle takes effect immediately, not just on next boot."""
    verb = 'enable' if enabled else 'disable'
    try:
        result = subprocess.run(
            ['systemctl', '--user', verb, '--now', CODEX_MOMS_SYNC_TIMER],
            capture_output=True, text=True, timeout=10,
        )
        ok = result.returncode == 0
        output = (result.stdout or '') + (result.stderr or '') or f'{verb}d {CODEX_MOMS_SYNC_TIMER}'
        return ok, output
    except Exception as exc:
        return False, str(exc)


def codex_sync_status() -> CodexSyncStatus:
    """last_sync is the fallback cache file's mtime (the sync script only
    replaces it on a verified-good fetch, so mtime IS last successful
    sync)."""
    last_sync = (
        os.path.getmtime(CODEX_MOMS_AUTH_JSON)
        if os.path.isfile(CODEX_MOMS_AUTH_JSON)
        else None
    )
    next_sync = (
        last_sync + CODEX_MOMS_SYNC_INTERVAL_SECONDS if last_sync else None
    )
    seconds_remaining = max(0.0, next_sync - time.time()) if next_sync else None
    slots, needs_reauth, reauth_message = _auto_recover(_codex_token_slots())
    return CodexSyncStatus(
        interval_seconds=CODEX_MOMS_SYNC_INTERVAL_SECONDS,
        last_sync_epoch=last_sync,
        next_sync_epoch=next_sync,
        seconds_remaining=seconds_remaining,
        slots=slots,
        sync_enabled=codex_sync_timer_enabled(),
        needs_reauth=needs_reauth,
        reauth_message=reauth_message,
    )


class CodexSyncRequest(StrictModel):
    """Body of POST /api/codex-sync-now — which source refills the fallback
    slot. Fails closed (Pydantic rejects anything outside the two known
    sources) rather than silently defaulting to a guess."""

    source: Literal['r46', 'w11'] = 'r46'


class CodexSyncToggleRequest(StrictModel):
    """Body of POST /api/codex-sync-toggle."""

    enabled: bool


def toggle_codex_sync(enabled: bool) -> CodexSyncStatus:
    """Flip the automatic-pull timer on/off and return the resulting status.
    Manual 'Sync from R46'/'Copy from W11' buttons stay usable either way —
    disabling only stops the unattended 4h pull, not the operator's ability
    to trigger one on demand. `toggle_error` (not `ran`/`ok`/`output`, which
    are the manual-sync-result fields) carries a failure so the panel can
    report it without misreporting it as a failed token sync."""
    ok, output = set_codex_sync_timer_enabled(enabled)
    status = codex_sync_status()
    return status.model_copy(update={
        'toggle_error': None if ok else output.strip()[-2000:],
    })


def run_codex_sync_now(source: str = 'r46') -> CodexSyncStatus:
    """Manual trigger for a fallback-slot refill. Resets the countdown
    because a successful sync updates CODEX_MOMS_AUTH_JSON's mtime (a failed
    one leaves it untouched, so the panel keeps counting down to the next
    automatic attempt)."""
    strategy = SYNC_SOURCES.get(source)
    if strategy is None:
        ok, output = False, f'unknown sync source: {source!r}'
    else:
        ok, output = strategy.sync()
        if ok:
            _record_last_source(source)
    status = codex_sync_status()
    return status.model_copy(update={
        'ran': True,
        'ok': ok,
        'output': output.strip()[-2000:],
        'source': source,
    })
