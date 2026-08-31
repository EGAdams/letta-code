"""DTOs (Pydantic, per contracts.StrictModel) + pure translation for the
"which ChatGPT Plus account is the live provider row on" panel.

Split out along the same seam as codex_sync_status.py: this module owns data
shape + pure functions; chatgpt_provider_accounts.py owns the strategies that
actually touch the network/SSH. server.py's route handlers stay thin dispatch.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from typing import Literal, Optional, Sequence

from chatgpt_provider_accounts import PROVIDER_ACCOUNT_SOURCES
from contracts import StrictModel


class ChatGptProviderAccountOption(StrictModel):
    """One selectable account source, for rendering the swap buttons."""

    key: str
    label: str


class ChatGptProviderAccountStatus(StrictModel):
    """Current live-row account + the accounts it can be set to."""

    active_email: Optional[str] = None
    sources: Sequence[ChatGptProviderAccountOption] = ()
    ran: bool = False
    ok: Optional[bool] = None
    text: Optional[str] = None
    source: Optional[str] = None
    provider_token_state: Literal['valid', 'expired', 'stale', 'unavailable'] = 'unavailable'
    provider_expires_at: Optional[int] = None
    local_token_state: Literal['valid', 'expired', 'unavailable'] = 'unavailable'
    local_expires_at: Optional[int] = None
    sync_recommended: bool = False
    token_status_detail: str = ''
    incident_id: Optional[str] = None


class ChatGptProviderSwapRequest(StrictModel):
    """Body of POST /api/chatgpt-provider-account — which account to
    install as the live chatgpt-plus-pro provider row. Fails closed
    (Pydantic rejects anything outside the two known accounts)."""

    source: Literal['w11', 'r46']


def provider_account_options() -> tuple[ChatGptProviderAccountOption, ...]:
    return tuple(
        ChatGptProviderAccountOption(key=src.key, label=src.label)
        for src in PROVIDER_ACCOUNT_SOURCES.values()
    )


def decode_claims(creds: Optional[dict]) -> dict:
    """Best-effort decode of the profile email out of a provider-row creds
    dict's access_token JWT. Never raises — an undecodable token just shows
    as 'unknown' rather than a 500."""
    if not creds:
        return {}
    try:
        payload_b64 = creds['access_token'].split('.')[1]
        payload_b64 += '=' * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload
    except Exception:
        return {}


def decode_email(creds: Optional[dict]) -> Optional[str]:
    payload = decode_claims(creds)
    return payload.get('https://api.openai.com/profile', {}).get('email')


def chatgpt_provider_account_status(
    active_creds: Optional[dict], *, local_auth: Optional[dict] = None,
    probe: Optional[dict] = None, now: Optional[float] = None,
) -> ChatGptProviderAccountStatus:
    """Describe both credential copies without exposing either token.

    Exact token equality is deliberately not the contract: Codex may refresh
    its local access token while Letta's still-valid copy remains usable. A
    sync is recommended only when Letta's copy is expired/rejected and W11 has
    a valid replacement for the same account.
    """
    current_time = time.time() if now is None else now
    provider_claims = decode_claims(active_creds)
    provider_exp = provider_claims.get('exp') or (active_creds or {}).get('expires_at')
    provider_email = decode_email(active_creds)
    local_creds = (local_auth or {}).get('tokens') or local_auth or {}
    local_claims = decode_claims(local_creds)
    local_exp = local_claims.get('exp')
    local_email = decode_email(local_creds)

    if not active_creds:
        provider_state, detail = 'unavailable', 'Letta provider token is unavailable'
    elif provider_exp and provider_exp <= current_time:
        provider_state, detail = 'expired', 'Letta provider token expired'
    elif probe is not None and not probe.get('ok') and '401' in probe.get('text', ''):
        provider_state, detail = 'stale', 'Letta provider token was rejected (HTTP 401)'
    elif probe is not None and probe.get('ok'):
        provider_state, detail = 'valid', ''
    else:
        provider_state, detail = 'unavailable', (probe or {}).get('text', 'Token status unavailable')

    local_state = ('valid' if local_exp and local_exp > current_time else
                   'expired' if local_exp else 'unavailable')
    sync_recommended = (
        provider_state in ('expired', 'stale') and local_state == 'valid'
        and bool(provider_email) and provider_email == local_email)
    access_token = (active_creds or {}).get('access_token', '')
    incident_id = hashlib.sha256(access_token.encode()).hexdigest()[:16] if access_token else None
    return ChatGptProviderAccountStatus(
        active_email=provider_email,
        sources=provider_account_options(),
        provider_token_state=provider_state,
        provider_expires_at=provider_exp,
        local_token_state=local_state,
        local_expires_at=local_exp,
        sync_recommended=sync_recommended,
        token_status_detail=detail,
        incident_id=incident_id,
    )
