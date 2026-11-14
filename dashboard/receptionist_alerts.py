"""Failure alerts from every receptionist who sends work through the post office.

A task Toyota or Sydney sent to another agent that failed raises an alert on
her sidecar (agent_blocks' agent_comms/alerts.py). This gathers them for the
dashboard's ReceptionistFailureAlert, which shows, speaks and notifies each
one on whatever tab is open, and passes "Got it" back to the sidecar that
raised it.

Programmed against IAlertSource only: each profile module's BRIDGE, plus
the Star Trek Bridge gateway's own queue watch (gateway_alerts), which raises
its alerts from off this machine and so still has them after an outage, the
factory watchdog (factory_alerts), which watches the workers and both
supervisors on this machine and is itself watched by its heartbeat, and the
independent ADW task supervisor's own per-task problems (adw_task_alerts),
which were previously visible only on the Worker Activity page's table.
"""

from __future__ import annotations

from typing import Any, Protocol

import sydney_service
import cashy_service
import yolanda_service
import liz_service
import toyota_service
import gateway_alerts
import factory_alerts
import adw_task_alerts
from receptionist_sidecar import ReceptionistAlertAckRequest


class IAlertSource(Protocol):
    """The part of a sidecar this module uses; SidecarBridge and GatewayAlertSource both satisfy it."""

    name: str

    def alerts(self) -> dict[str, Any]: ...

    def acknowledge_alerts(self, ids: list[str] | None) -> dict[str, Any]: ...


def sources() -> dict[str, IAlertSource]:
    # A function, not a constant, so a test's rebind of BRIDGE is seen.
    return {'toyota': toyota_service.BRIDGE, 'sydney': sydney_service.BRIDGE,
            'cashy': cashy_service.BRIDGE, 'yolanda': yolanda_service.BRIDGE,
            'liz': liz_service.BRIDGE, 'bridge': gateway_alerts.from_environment(),
            'factory': factory_alerts.from_environment(),
            'adw_tasks': adw_task_alerts.from_environment()}


def collect(bridges: dict[str, IAlertSource] | None = None) -> dict[str, Any]:
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
                bridges: dict[str, IAlertSource] | None = None) -> dict[str, Any]:
    return (bridges or sources())[request.agent].acknowledge_alerts(request.ids)
