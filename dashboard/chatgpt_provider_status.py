"""DTOs (Pydantic, per contracts.StrictModel) + pure translation for the
"which ChatGPT Plus account is the live provider row on" panel.

Split out along the same seam as codex_sync_status.py: this module owns data
shape + pure functions; chatgpt_provider_accounts.py owns the strategies that
actually touch the network/SSH. server.py's route handlers stay thin dispatch.
"""

from __future__ import annotations

import base64
import json
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


def decode_email(creds: Optional[dict]) -> Optional[str]:
    """Best-effort decode of the profile email out of a provider-row creds
    dict's access_token JWT. Never raises — an undecodable token just shows
    as 'unknown' rather than a 500."""
    if not creds:
        return None
    try:
        payload_b64 = creds['access_token'].split('.')[1]
        payload_b64 += '=' * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get('https://api.openai.com/profile', {}).get('email')
    except Exception:
        return None


def chatgpt_provider_account_status(active_creds: Optional[dict]) -> ChatGptProviderAccountStatus:
    return ChatGptProviderAccountStatus(
        active_email=decode_email(active_creds),
        sources=provider_account_options(),
    )
