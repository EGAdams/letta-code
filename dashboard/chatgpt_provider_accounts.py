"""Strategies for installing a specific ChatGPT Plus account's token directly
into the LIVE chatgpt-plus-pro provider row on the Letta box — the token
Mazda's whole agent fleet actually spends against right now.

This is a different concern from codex_sync_sources.py: that module only
refills a local vision-fallback cache file (~/.codex-moms/auth.json). This
module answers "which account is the live LLM row on" and mirrors that
module's ABC-port shape (see IChatGptFallbackSyncSource) rather than
inventing new machinery.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone

CHATGPT_FAILOVER_HOST = 'adamsl@100.80.49.10'
CHATGPT_BACKUP_DIR = '/home/adamsl/letta-backups'
CHATGPT_STANDBY_FILE = f'{CHATGPT_BACKUP_DIR}/chatgpt_standby_token.json'
CODEX_PRIMARY_AUTH_JSON = os.path.expanduser('~/.codex/auth.json')
ROSEMARY46_HOST = 'adamsl@100.72.34.38'
ROSEMARY46_AUTH_JSON = '/home/adamsl/.codex/auth.json'
SSH_OPTS = ('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10')


def _jwt_exp(access_token: str) -> int:
    """Best-effort decode of a JWT's `exp` claim (no signature check)."""
    try:
        payload = access_token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get('exp', 0)
    except Exception:
        return 0


def auth_json_to_provider_row(data: dict) -> dict | None:
    """Transform a ~/.codex/auth.json bundle into the flat shape the
    chatgpt-plus-pro provider row's api_key_enc column expects. Returns None
    if `data` isn't a usable ChatGPT OAuth session."""
    tokens = data.get('tokens', {})
    access_token = tokens.get('access_token')
    if data.get('auth_mode') != 'chatgpt' or not access_token:
        return None
    return {
        'access_token': access_token,
        'refresh_token': tokens.get('refresh_token'),
        'account_id': tokens.get('account_id'),
        'expires_at': _jwt_exp(access_token),
    }


def install_provider_row(row: dict) -> tuple[bool, str]:
    """Push `row` into the live provider row on the Letta box. Backs up the
    displaced row both to a timestamped file and as the new standby (so
    auto-failover keeps ping-ponging between the two accounts afterward)."""
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    backup_path = f'{CHATGPT_BACKUP_DIR}/chatgpt_provider_row_displaced_{ts}.json'
    remote_row_path = f'/tmp/chatgpt_new_row_{ts}.json'
    local_tmp = f'/tmp/chatgpt_new_row_local_{ts}.json'
    try:
        with open(local_tmp, 'w', encoding='utf-8') as fh:
            json.dump(row, fh)
        scp = subprocess.run(['scp', *SSH_OPTS, local_tmp, f'{CHATGPT_FAILOVER_HOST}:{remote_row_path}'],
                              capture_output=True, text=True, timeout=30)
        if scp.returncode != 0:
            return False, f'scp of new token failed: {scp.stderr.strip()[:200]}'
    finally:
        try:
            os.remove(local_tmp)
        except OSError:
            pass

    remote_script = f'''set -euo pipefail
mkdir -p {CHATGPT_BACKUP_DIR}
docker exec letta-server psql -U letta -d letta -t -A -c "SET search_path TO letta; SELECT api_key_enc FROM providers WHERE name='chatgpt-plus-pro';" | grep -v '^SET$' > {backup_path}
python3 -c "import json; json.loads(open('{backup_path}').read())"
cp {backup_path} {CHATGPT_STANDBY_FILE}
python3 -c "import json; json.loads(open('{remote_row_path}').read())"
ROW=$(cat {remote_row_path})
docker exec letta-server psql -U letta -d letta -c "SET search_path TO letta; UPDATE providers SET api_key_enc='$ROW' WHERE name='chatgpt-plus-pro';"
rm -f {remote_row_path}
echo SET_OK
'''
    try:
        r = subprocess.run(['ssh', *SSH_OPTS, CHATGPT_FAILOVER_HOST, 'bash', '-s'],
                            input=remote_script, capture_output=True, text=True, timeout=60)
        out = ((r.stdout or '') + (r.stderr or '')).strip()
        return ('SET_OK' in out), (out[-300:] or f'install exited {r.returncode}')
    except Exception as e:
        return False, f'install failed: {e}'


class IChatGptProviderAccountSource(ABC):
    """Strategy: fetch a specific ChatGPT Plus account's current token and
    install it as the live provider row. Two interchangeable ways to answer
    "which account should the fleet spend against right now" — exactly the
    concern an ABC exists to isolate."""

    key: str
    label: str

    @abstractmethod
    def install(self) -> tuple[bool, str]:
        """Fetch this account's token and install it as the live provider row."""


class W11AccountSource(IChatGptProviderAccountSource):
    """EG's own account — local ~/.codex/auth.json on this (W11-slot) box."""

    key = 'w11'
    label = "EG's account (W11)"

    def install(self) -> tuple[bool, str]:
        try:
            with open(CODEX_PRIMARY_AUTH_JSON, encoding='utf-8') as fh:
                data = json.load(fh)
        except Exception as exc:
            return False, f'cannot read {CODEX_PRIMARY_AUTH_JSON}: {exc}'
        row = auth_json_to_provider_row(data)
        if row is None:
            return False, 'local auth.json is not a valid chatgpt OAuth session'
        if row['expires_at'] and row['expires_at'] < time.time():
            return False, "EG's local token is expired — re-run `codex login`"
        return install_provider_row(row)


class R46AccountSource(IChatGptProviderAccountSource):
    """Mom's account — fetched live over SSH from rosemary46 (R46 slot)."""

    key = 'r46'
    label = "Mom's account (R46)"

    def install(self) -> tuple[bool, str]:
        try:
            r = subprocess.run(['ssh', *SSH_OPTS, ROSEMARY46_HOST, 'cat', ROSEMARY46_AUTH_JSON],
                                capture_output=True, text=True, timeout=20)
            if r.returncode != 0 or not r.stdout.strip():
                return False, f'could not reach rosemary46: {r.stderr.strip()[:200]}'
            data = json.loads(r.stdout)
        except Exception as exc:
            return False, f'fetch from rosemary46 failed: {exc}'
        row = auth_json_to_provider_row(data)
        if row is None:
            return False, "rosemary46's auth.json is not a valid chatgpt OAuth session"
        if row['expires_at'] and row['expires_at'] < time.time():
            return False, "mom's rosemary46 token is expired"
        return install_provider_row(row)


PROVIDER_ACCOUNT_SOURCES: dict[str, IChatGptProviderAccountSource] = {
    'w11': W11AccountSource(),
    'r46': R46AccountSource(),
}
