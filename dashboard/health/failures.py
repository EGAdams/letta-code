"""Naming the real failure behind an error string.

One pure function, in its own module because five unrelated health checks call
it and putting it beside any one of them would make the other four import that
one's dependencies.

Why it exists at all: the ChatGPT provider canary used to label an HTTP 404 as
"rate-limited", because 404 fell through to a generic branch and rate-limiting
was the guess. That sent diagnosis down the wrong path entirely -- somebody
waited for a quota window to reset while a route was simply missing. The
ordering below is deliberate; the specific conditions are tested before the
generic ones, and 'error' is the answer only when nothing matched.
"""

from __future__ import annotations

def classify_failure(text):
    """Map a raw error string to (class, human_label) so the dashboard reports the
    REAL failure mode instead of a generic/misleading one (today the ChatGPT
    provider canary labelled a 404 as 'rate-limited', which sent diagnosis down
    the wrong path). Used for provider + server errors."""
    t = (text or '').lower()
    if '429' in t or 'rate limit' in t or 'rate-limit' in t or 'rate_limit' in t or 'too many requests' in t or 'quota' in t:
        return ('rate_limit', 'rate-limited')
    if '401' in t or '403' in t or 'unauth' in t or 'forbidden' in t or 'invalid_api_key' in t or 'authentication' in t:
        return ('auth', 'auth error')
    if '404' in t or 'not found' in t:
        return ('not_found', 'provider error (404)')
    if 'timed out' in t or 'timeout' in t:
        return ('timeout', 'timeout')
    if 'connection refused' in t or 'refused' in t:
        return ('refused', 'connection refused')
    if 'unreachable' in t or 'no route' in t or 'name or service not known' in t:
        return ('unreachable', 'unreachable')
    return ('error', 'error')
