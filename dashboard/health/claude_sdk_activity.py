"""Read-only proxy for the shared Claude SDK executor activity feed."""

from __future__ import annotations

import json
import urllib.request


FRITA_EXEC_ACTIVITY_URL = 'http://100.80.49.10:8799/claude_sdk_activity'


def activity_payload(timeout=None):
    """Return the executor feed, failing closed without launching any work."""
    try:
        request = urllib.request.Request(FRITA_EXEC_ACTIVITY_URL, method='GET')
        with urllib.request.urlopen(request, timeout=timeout or 6) as response:
            payload = json.loads(response.read(1_000_000).decode('utf-8'))
        if not isinstance(payload, dict) or not isinstance(payload.get('events'), list):
            raise ValueError('executor returned an invalid activity payload')
        return payload
    except Exception as exc:
        return {
            'ok': False,
            'current_run': None,
            'events': [],
            'error': f'Claude SDK activity unavailable: {exc}',
        }
