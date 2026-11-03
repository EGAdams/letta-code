"""Who may use /api/scan-bridge/v1, and for what.

The dashboard listens on 0.0.0.0 with no auth of its own (EG: lock that down
later), so these routes carry their own gate, and the token is the real one:
WSL's localhost relay can make a forwarded request look like loopback, so
"came from 127.0.0.1" is a filter, not an identity.

clients.json (mode 0600, never committed) holds only token *hashes*:
  {"clients": [{"name": "agent-bridge-worker", "token_sha256": "<hex>",
                "scopes": ["scanner:start", "scanner:status", ...]}]}
It is re-read on each request, so rotating or revoking needs no restart.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
import stat
from pathlib import Path

from pydantic import Field

from contracts import StrictModel

SCOPES: tuple[str, ...] = ('scanner:start', 'scanner:status', 'scanner:list',
                           'scanner:document:read', 'scanner:verdict:read')


class AuthError(Exception):
    def __init__(self, code: str, message: str, http: int):
        super().__init__(message)
        self.code, self.http = code, http


class BridgeClient(StrictModel):
    name: str = Field(pattern=r'^[a-z0-9][a-z0-9_-]{0,39}$')
    token_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    scopes: tuple[str, ...]


class BridgeClients(StrictModel):
    clients: tuple[BridgeClient, ...]


def _is_loopback(client_ip: str) -> bool:
    try:
        address = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    mapped = getattr(address, 'ipv4_mapped', None)
    return (mapped or address).is_loopback


class TokenAuthorizer:
    def __init__(self, clients_file: Path):
        self._file = Path(clients_file)

    def authorize(self, client_ip: str, headers: dict[str, str], scope: str) -> str:
        if not _is_loopback(client_ip):
            raise AuthError('forbidden', 'scan bridge routes are local-only', 403)
        if headers.get('origin') or headers.get('sec-fetch-site'):
            raise AuthError('forbidden', 'browser requests are not accepted here', 403)
        auth = headers.get('authorization', '')
        if not auth.startswith('Bearer ') or len(auth) > 300:
            raise AuthError('unauthorized', 'missing bearer token', 401)
        presented = hashlib.sha256(auth[7:].strip().encode()).hexdigest()
        match = None
        for client in self._clients():
            if hmac.compare_digest(client.token_sha256, presented):
                match = client
        if match is None:
            raise AuthError('unauthorized', 'unknown token', 401)
        if scope not in match.scopes:
            raise AuthError('insufficient_scope', f'token lacks {scope}', 403)
        return match.name

    def _clients(self) -> tuple[BridgeClient, ...]:
        try:
            info = os.stat(self._file)
            if info.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
                raise AuthError('misconfigured', 'scan bridge client file must be mode 0600', 503)
            return BridgeClients.model_validate_json(self._file.read_text(encoding='utf-8')).clients
        except FileNotFoundError:
            raise AuthError('unauthorized', 'no scan bridge clients are provisioned', 401) from None
        except ValueError:
            raise AuthError('misconfigured', 'scan bridge client file is invalid', 503) from None
