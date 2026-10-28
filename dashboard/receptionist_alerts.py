"""Failure alerts from every receptionist who sends work through the post office.

A task Toyota or Sydney sent to another agent that failed raises an alert on
her sidecar (agent_blocks' agent_comms/alerts.py). This gathers them for the
dashboard's ReceptionistFailureAlert, which shows, speaks and notifies each
one on whatever tab is open, and passes "Got it" back to the sidecar that
raised it.

Programmed against IReceptionistSidecar only; the addresses are each
profile module's BRIDGE.
"""

from __future__ import annotations

from typing import Any

import sydney_service
import toyota_service
from receptionist_sidecar import IReceptionistSidecar, ReceptionistAlertAckRequest


def sources() -> dict[str, IReceptionistSidecar]:
    # A function, not a constant, so a test's rebind of BRIDGE is seen.
    return {'toyota': toyota_service.BRIDGE, 'sydney': sydney_service.BRIDGE}


def collect(bridges: dict[str, IReceptionistSidecar] | None = None) -> dict[str, Any]:
    """Every pending alert, each tagged with whose it is. Never raises.

    A sidecar that is down is left to Server Management; one that is up but
    cannot read its alerts is reported, because that is a silent failure too.
    """
    alerts, errors = [], []
    for agent, bridge in (bridges or sources()).items():
        state = bridge.alerts()
        for alert in state.get('alerts') or []:
            if isinstance(alert, dict) and alert.get('id'):
                alerts.append({**alert, 'agent': agent, 'name': bridge.name})
        if not state.get('ok') and state.get('reachable', True):
            errors.append({'agent': agent, 'name': bridge.name, 'error': state.get('error', 'unknown error')})
    return {'ok': True, 'alerts': alerts, 'errors': errors}


def acknowledge(request: ReceptionistAlertAckRequest,
                bridges: dict[str, IReceptionistSidecar] | None = None) -> dict[str, Any]:
    return (bridges or sources())[request.agent].acknowledge_alerts(request.ids)
