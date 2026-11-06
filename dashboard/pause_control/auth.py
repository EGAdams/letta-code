"""Narrow, authenticated gate for pause/resume/priority control requests.

Same shape as monitoring.worker_restart: one shared bearer token from the
environment, constant-time compared, local to this process. Pause/resume is
initiated by EG or ChatGPT through the dashboard (not by the worker calling
in), so this does not need scan_jobs.auth's per-client scopes -- a single
secret is the right size for one authorized caller class.
"""

from __future__ import annotations

import hmac
import os

TOKEN_ENV = 'PAUSE_CONTROL_TOKEN'


def configured() -> bool:
    return bool(os.environ.get(TOKEN_ENV))


def authorize(authorization_header: str | None) -> bool:
    expected = os.environ.get(TOKEN_ENV, '')
    if not expected:
        return False
    supplied = (authorization_header or '').removeprefix('Bearer ')
    return hmac.compare_digest(supplied, expected)


class EnvBearerAuthorizer:
    """IControlAuthorizer over this module's functions, for dependency injection."""

    def configured(self) -> bool:
        return configured()

    def authorize(self, authorization_header: str | None) -> bool:
        return authorize(authorization_header)
