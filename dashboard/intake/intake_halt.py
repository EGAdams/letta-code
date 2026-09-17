"""The fail-loud intake-halt surface.

rol_finances' DashboardIntakeHaltNotifier POSTs here when an intake step
crashes (a fault, not a "no match"), so the pipeline HALTS instead of silently
inserting a duplicate. Unlike the document-vision halt (which self-clears when
a provider tier recovers), a code fault does not recover on its own — it stays
active until a human acknowledges it.

``halt_file`` is rebound by tests directly, so it arrives fresh per call via
``Collaborators`` rather than being read once at import time.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    halt_file: str
    lock: object


def record_intake_halt(deps: Collaborators, data):
    """Persist a fail-loud intake halt so the dashboard can raise the alert.

    Stores the single most recent halt as active; a human clears it via
    /api/intake-halt-ack. Kept as a discrete event (not merged) because each
    halt is a distinct fault to see."""
    event = data or {}
    record = {
        'active': True,
        'halted_at': time.time(),
        'step': str(event.get('step', '')),
        'cause': str(event.get('cause', '')),
        'exception_type': str(event.get('exception_type', '')),
        'document_path': str(event.get('document_path', '')),
        'repo_path': str(event.get('repo_path', '')),
        'metadata': event.get('metadata') if isinstance(event.get('metadata'), dict) else {},
    }
    with deps.lock:
        try:
            with open(deps.halt_file, 'w') as fh:
                json.dump(record, fh)
        except OSError as exc:
            return {'ok': False, 'error': str(exc)}
    return {'ok': True, 'active': True}


def read_intake_halt(deps: Collaborators):
    """Current intake-halt state for the front-end poller."""
    with deps.lock:
        try:
            with open(deps.halt_file) as fh:
                record = json.load(fh)
        except (OSError, ValueError):
            return {'ok': True, 'active': False}
    if not isinstance(record, dict) or not record.get('active'):
        return {'ok': True, 'active': False}
    return {'ok': True, 'active': True, 'event': record}


def acknowledge_intake_halt(deps: Collaborators):
    """Clear the active halt once a human has seen it (the alert's Acknowledge)."""
    with deps.lock:
        try:
            with open(deps.halt_file) as fh:
                record = json.load(fh)
        except (OSError, ValueError):
            return {'ok': True, 'active': False}
        if isinstance(record, dict):
            record['active'] = False
            try:
                with open(deps.halt_file, 'w') as fh:
                    json.dump(record, fh)
            except OSError as exc:
                return {'ok': False, 'error': str(exc)}
    return {'ok': True, 'active': False}
