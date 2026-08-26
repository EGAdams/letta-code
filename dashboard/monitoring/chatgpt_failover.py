"""When the account the fleet is spending runs dry, move it to the other one.

Two ChatGPT Plus accounts exist. The Letta `chatgpt-plus-pro` provider row
holds one token; the other is parked in a standby file on the Letta box. This
module is the state machine that notices the active account has hit a rate
window, checks the parked one is actually usable, swaps the row, and re-probes
the token that came back -- so the fleet degrades to "the other account"
instead of "dead until the window resets".

Read top to bottom, it is one loop with one decision in the middle:

    poll_provider_once   -- read the live token, probe its usage endpoint
    failover_should_trigger -- is this a *rate limit*, and is the cooldown up?
    standby_has_headroom -- read the parked bundle, probe it, heal it if the
                            only thing wrong is an expired access token
    run_failover_swap    -- run the swap script on the Letta box
    (re-probe)           -- report the new token's real state, not the old one

Two distinctions here were paid for in downtime and are worth keeping:

  * A rate limit is the only thing worth swapping for. An auth or network
    failure would be inherited by the standby token, and the attempt burns the
    cooldown window (`failover_should_trigger`).
  * A *rejected* standby token is not a capped standby. Collapsing the two
    made a healable parked bundle look like "both accounts are exhausted"; on
    2026-08-19 the swap and the diagnosis were both unavailable because the
    standby's access token had simply expired (`standby_probe_verdict`).

`StandbyCredentials` is the typed boundary, and it guards exactly one field --
see its docstring. Everything downstream of a read is the model, not a dict,
so the guard cannot be switched off by an absent key.

What stays behind in `server.py` arrives in a `Collaborators` bundle built
fresh per sweep: the agent roster lookup and the two send-error writers, which
belong to Agent Management's cache, not here. `fetch_provider_oauth_creds`,
`probe_codex_usage`, `classify_failure` and the Letta box's ssh destination
are *imported* -- each already has its own module, and injecting them would be
ceremony.
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from health.failures import classify_failure
from hosts import LETTA_DOCKER_HOST
from monitoring.provider_usage import (
    PROVIDER_USAGE_PROBES,
    fetch_provider_oauth_creds,
    probe_codex_usage,
    shape_detail,
)


@dataclass(frozen=True)
class Collaborators:
    """What still lives in server.py. Build it per sweep, never at import."""
    provider_agent_ids: Callable[[str], list]
    record_send_error: Callable[[str, str], None]
    clear_send_error: Callable[[str], None]


#: The Letta box, where both the provider row and the standby file live. Third
#: independent copy of this destination until now -- it is `hosts.py`'s job.
CHATGPT_FAILOVER_HOST = LETTA_DOCKER_HOST
CHATGPT_FAILOVER_STANDBY_FILE = '/home/adamsl/letta-backups/chatgpt_standby_token.json'
CHATGPT_FAILOVER_SWAP_CMD = '/home/adamsl/server_tools/swap_chatgpt_provider_token.sh'
CHATGPT_FAILOVER_MIN_INTERVAL = int(os.environ.get('CHATGPT_FAILOVER_MIN_INTERVAL', '1800'))

CODEX_OAUTH_CLIENT_ID = 'app_EMoamEEZ73f0CkXaXp7hrann'
CODEX_LOCAL_AUTH = os.path.expanduser('~/.codex/auth.json')

#: seconds between sweeps; each probe is a free usage-API call (zero LLM tokens)
CHATGPT_PROVIDER_POLL_INTERVAL = 90

_SSH_OPTS = ('-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes')

#: Last swap time (cooldown) and the last thing auto-failover had to say.
#: Read through `last_failover_note()`; the Server Management tile shows it
#: instead of promising a Restart that cannot work.
_state = {'last_swap_ts': 0.0, 'last_note': ''}


def last_failover_note() -> str:
    """What auto-failover concluded on its most recent attempt, or ''."""
    return _state.get('last_note') or ''


# ── The parked bundle ────────────────────────────────────────────────────────

class StandbyCredentials(BaseModel):
    """The OAuth bundle parked on the Letta box, ready to become the live row.

    One required field, and it is `account_id`, because that field is what
    `codex_refresh_candidates` compares against this machine's own codex
    logins to decide whether a refresh token belongs to the standby account.
    The old guard read ``if account and tokens.get('account_id') != account``,
    so a bundle that had lost `account_id` -- an empty object, a truncated
    write, a hand-edited file -- did not fail: it silently *disabled* the
    guard, and `heal_standby_token` then wrote a completely different
    account's refresh token back into the standby file, destroying the only
    copy of the real one. Verified against the shipped code before this model
    existed::

        codex_refresh_candidates({}, [{'tokens': {'account_id': 'SOMEONE-ELSE',
                                                  'refresh_token': 'rt-not-ours'}}])
        -> ['rt-not-ours']

    Now the field is required, the comparison is unconditional, and a bundle
    that cannot be read is an error note rather than a confident wrong write.

    `access_token` is deliberately *not* required: a bundle holding only a
    refresh token is stale, not unusable, and healing it is precisely this
    module's job. `extra='allow'` because the swap script copies the provider
    row verbatim and the vendor may add keys.
    """
    model_config = ConfigDict(extra='allow')

    #: min_length=1 because '' is not a milder version of missing: it makes
    #: every real local login compare unequal, and the probe sends an empty
    #: ChatGPT-Account-Id header, so a healable standby reads as a dead one.
    account_id: str = Field(min_length=1)
    access_token: str = ''
    refresh_token: str | None = None
    expires_at: Any = None

    def as_creds(self) -> dict:
        """The plain dict the usage probe and the standby file expect."""
        return self.model_dump()


def read_standby_creds() -> tuple[StandbyCredentials | None, str | None]:
    """(creds, err) -- the OAuth bundle parked on the Letta box."""
    try:
        r = subprocess.run(['ssh', *_SSH_OPTS,
                            CHATGPT_FAILOVER_HOST, f'cat {CHATGPT_FAILOVER_STANDBY_FILE}'],
                           capture_output=True, text=True, timeout=20)
        if r.returncode != 0 or not r.stdout.strip():
            return None, 'standby token file missing/unreadable'
        raw = json.loads(r.stdout.strip())
    except Exception as e:
        return None, f'standby read failed: {e}'
    try:
        return StandbyCredentials.model_validate(raw), None
    except ValidationError as e:
        return None, f'standby bundle unreadable ({shape_detail(e)})'


def write_standby_creds(creds: StandbyCredentials) -> tuple[bool, str]:
    """Park a bundle back in the standby file on the Letta box (write-to-temp
    then rename, so the swap script never reads a half-written file)."""
    tmp = CHATGPT_FAILOVER_STANDBY_FILE + '.new'
    try:
        r = subprocess.run(['ssh', *_SSH_OPTS, CHATGPT_FAILOVER_HOST,
                            f'umask 077 && cat > {tmp} && mv {tmp} {CHATGPT_FAILOVER_STANDBY_FILE}'],
                           input=json.dumps(creds.as_creds()),
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return False, ((r.stderr or '').strip()[:120] or f'ssh exited {r.returncode}')
        return True, 'ok'
    except Exception as e:
        return False, str(e)


# ── Pure decisions ───────────────────────────────────────────────────────────

def failover_should_trigger(probe_text, now_ts, last_swap_ts, min_interval=None):
    """Pure gate: only a genuine rate-limit triggers failover (auth/network
    errors would just install a token with the same problem), and swaps are
    spaced at least min_interval apart so two capped accounts can't ping-pong."""
    if min_interval is None:
        min_interval = CHATGPT_FAILOVER_MIN_INTERVAL
    if not str(probe_text).startswith('llm_rate_limit'):
        return False
    return (now_ts - last_swap_ts) >= min_interval


def standby_probe_verdict(probe) -> Literal['headroom', 'limited', 'stale']:
    """Pure: what a standby probe result means for failover. A rate-limited
    standby is a real "both accounts are capped" answer; a *rejected* token is
    not -- it says the parked bundle went stale, which is fixable. Collapsing the
    two (the old code called any failure 'standby also limited') hid a dead
    safety net: on 2026-08-19 both the swap and the diagnosis were unavailable
    because the standby's access token had simply expired."""
    if probe['ok']:
        return 'headroom'
    return 'limited' if str(probe.get('text', '')).startswith('llm_rate_limit') else 'stale'


def codex_refresh_candidates(standby: StandbyCredentials,
                             auth_bundles: Iterable[dict]) -> list:
    """Pure: refresh tokens worth trying for the standby account, freshest
    first. Codex refresh tokens are single-use/rotating, so the standby file's
    own copy dies the moment anything else refreshes the SAME account -- which is
    exactly what this box's own codex login does every few days. Its
    ~/.codex/auth.json (and the backups the CLI leaves behind) is then the only
    place a live token for that account survives. `auth_bundles` is a list of
    parsed auth.json dicts; bundles for a different account are skipped so a
    heal can never park the wrong account's token as standby -- a comparison
    that is unconditional only because `StandbyCredentials` guarantees there is
    an account to compare against."""
    ordered = [standby.refresh_token]
    for data in auth_bundles:
        tokens = (data or {}).get('tokens') or {}
        if tokens.get('account_id') != standby.account_id:
            continue
        ordered.append(tokens.get('refresh_token'))
    seen, out = set(), []
    for rt in ordered:
        if rt and rt not in seen:
            seen.add(rt)
            out.append(rt)
    return out


# ── Healing a stale parked token ─────────────────────────────────────────────

def local_codex_bundles() -> list:
    """This box's own codex auth files -- live one first, then backups newest
    first (same self-heal source the Model Stats extractor walks)."""
    backups = sorted((p for p in glob.glob(CODEX_LOCAL_AUTH + '*') if p != CODEX_LOCAL_AUTH),
                     reverse=True)
    bundles = []
    for path in [CODEX_LOCAL_AUTH] + backups:
        try:
            with open(path) as f:
                bundles.append(json.load(f))
        except Exception:
            continue
    return bundles


def codex_refresh(refresh_token, timeout=25) -> dict:
    """Exchange a Codex refresh token for a fresh access token."""
    body = json.dumps({'grant_type': 'refresh_token', 'client_id': CODEX_OAUTH_CLIENT_ID,
                       'refresh_token': refresh_token, 'scope': 'openid profile email'}).encode()
    req = urllib.request.Request('https://auth.openai.com/oauth/token', data=body,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def heal_standby_token(creds: StandbyCredentials) -> tuple[StandbyCredentials | None, str]:
    """Refresh the parked standby bundle in place and write it back.
    Returns (creds, note); creds is None when no refresh token anywhere still
    works -- that account then needs an interactive `codex login`."""
    for rt in codex_refresh_candidates(creds, local_codex_bundles()):
        try:
            fresh = codex_refresh(rt)
        except Exception:
            continue
        update = {
            'access_token': fresh.get('access_token') or creds.access_token,
            'expires_at': str(int(time.time()) + int(fresh.get('expires_in', 3600))),
        }
        if fresh.get('refresh_token'):
            update['refresh_token'] = fresh['refresh_token']
        try:
            healed = StandbyCredentials.model_validate({**creds.as_creds(), **update})
        except ValidationError as e:
            return None, f'refresh response unusable ({shape_detail(e)})'
        ok, note = write_standby_creds(healed)
        if not ok:
            return None, f'standby token refreshed but write-back failed: {note}'
        print('[chatgpt-failover] standby token refreshed in place', flush=True)
        return healed, 'standby token refreshed'
    return None, ('standby token expired and no refresh token still works — '
                  'that account needs an interactive `codex login`')


def standby_has_headroom() -> tuple[bool, str]:
    """Read the standby token off the Letta box and probe its usage API.
    Returns (ok, note); ok=True only when the standby is NOT rate-limited. A
    standby whose access token has merely expired gets refreshed and re-probed
    first, so a stale parked bundle can't masquerade as a capped account and
    leave the fleet down while the other login still has quota."""
    creds, err = read_standby_creds()
    if err:
        return False, err
    probe = probe_codex_usage(creds.as_creds())
    if standby_probe_verdict(probe) == 'stale':
        healed, note = heal_standby_token(creds)
        if healed is None:
            return False, note
        probe = probe_codex_usage(healed.as_creds())
    verdict = standby_probe_verdict(probe)
    if verdict == 'headroom':
        return True, f"standby has headroom ({probe['text']})"
    if verdict == 'limited':
        return False, f"standby also limited ({probe['text'][:80]})"
    return False, f"standby token unusable after refresh ({probe['text'][:80]})"


# ── The swap, and the sweep that decides to make it ──────────────────────────

def run_failover_swap() -> tuple[bool, str]:
    """Execute the swap script on the Letta box. Returns (ok, note)."""
    try:
        r = subprocess.run(['ssh', *_SSH_OPTS,
                            CHATGPT_FAILOVER_HOST, CHATGPT_FAILOVER_SWAP_CMD],
                           capture_output=True, text=True, timeout=60)
        out = ((r.stdout or '') + (r.stderr or '')).strip()
        return ('SWAP_OK' in out), (out[-200:] or f'swap exited {r.returncode}')
    except Exception as e:
        return False, f'swap failed: {e}'


def maybe_failover(probe, provider_name):
    """Called when the active account's probe failed. On a successful swap,
    returns a fresh probe of the newly-installed token; otherwise None."""
    now = time.time()
    if not failover_should_trigger(probe.get('text', ''), now, _state['last_swap_ts']):
        return None
    ok, note = standby_has_headroom()
    if not ok:
        _state['last_note'] = note
        return None
    _state['last_swap_ts'] = now  # even a failed attempt starts the cooldown
    swapped, snote = run_failover_swap()
    _state['last_note'] = snote
    if not swapped:
        print(f'[chatgpt-failover] swap FAILED: {snote}', flush=True)
        return None
    print(f'[chatgpt-failover] provider token swapped to standby account — {note}', flush=True)
    try:
        creds, _ptype = fetch_provider_oauth_creds(provider_name)
        if creds:
            return probe_codex_usage(creds)
    except Exception:
        pass
    return None


def poll_provider_once(provider_name, *, deps: Collaborators) -> None:
    """One sweep: read the provider's OAuth token from the Letta API, ask the
    account's usage endpoint whether it's rate-limited (zero LLM tokens), and
    propagate ok/error to every tagged agent via the send-error registry."""
    affected = deps.provider_agent_ids(provider_name)
    if not affected:
        return
    try:
        creds, provider_type = fetch_provider_oauth_creds(provider_name)
    except Exception:
        return  # Letta API unreachable — that's Server Management's signal, not a quota fact
    probe_fn = PROVIDER_USAGE_PROBES.get(provider_type)
    if not creds or not probe_fn:
        return  # no token / unprobeable provider type — leave agent state alone
    probe = probe_fn(creds)
    if not probe['ok'] and provider_type == 'chatgpt_oauth':
        fresh = maybe_failover(probe, provider_name)
        if fresh is not None and fresh['ok']:
            probe = fresh
    for agent_id in affected:
        if probe['ok']:
            deps.clear_send_error(agent_id)
        else:
            _cls, label = classify_failure(probe['text'])
            deps.record_send_error(agent_id, f'{provider_name} {label} — {probe["text"]}')


def poll_loop(poll_once: Callable[[], Any],
              interval: float = CHATGPT_PROVIDER_POLL_INTERVAL) -> None:
    """Background daemon thread body: keep the provider probe fresh.

    Takes the sweep as a callable rather than a provider name so the caller's
    wrapper -- and therefore its `Collaborators` bundle -- is rebuilt on every
    iteration instead of being frozen when the thread started."""
    while True:
        try:
            poll_once()
        except Exception:
            pass
        time.sleep(interval)
