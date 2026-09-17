"""Probing a Server Management entry's health and reducing it to a tab status.

``server_status_kind`` is the shared 4-state classification
('up'|'concern'|'starting'|'down', or None when there's nothing to check) used
by BOTH the sidebar tab (/api/server-health) and the detail panel
(/api/server-logs) so the two never disagree.
"""

from __future__ import annotations

import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    health_checks: dict
    restartable_keys: object
    is_server_starting: Callable
    win10_docker_ok: Callable


def server_health(deps: Collaborators, cfg, timeout=None):
    """Ping a server's health_url or tcp_check. Returns {ok, text} (or None if neither set).

    A cfg may instead provide 'check': <name> referencing HEALTH_CHECKS for a
    custom, body-aware probe (e.g. verifying the SDK executor, not just HTTP up).

    tcp_check: (host, port) — used for MCP proxies and other non-HTTP servers that
    only need a TCP connection test (no HTTP response to parse)."""
    check = cfg.get('check')
    if check:
        fn = deps.health_checks.get(check)
        if fn is None:
            return {'ok': False, 'text': f'unknown check: {check}'}
        return fn(timeout=timeout)
    tcp = cfg.get('tcp_check')
    url = cfg.get('health_url')
    if not url and not tcp:
        return None
    if tcp:
        host, port = tcp
        try:
            s = socket.create_connection((host, port), timeout=timeout or 3)
            s.close()
            return {'ok': True, 'text': f'port {port} accepting connections'}
        except Exception as e:
            return {'ok': False, 'text': f'port {port} unreachable: {e}'}
    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=timeout or 4) as r:
            code = r.getcode()
            body = r.read(400).decode('utf-8', errors='replace').strip()
        snippet = (' — ' + body.replace('\n', ' ')[:160]) if body else ''
        return {'ok': 200 <= code < 400, 'text': f'HTTP {code}{snippet}'}
    except urllib.error.HTTPError as e:
        return {'ok': False, 'text': f'HTTP {e.code} {e.reason}'}
    except Exception as e:
        return {'ok': False, 'text': f'unreachable: {e}'}


def compute_server_status(health, *, starting=False, restartable=False,
                          host_unreachable=False, dependency_down=False):
    """Reduce a health result to a tab status: 'up' | 'concern' | 'starting' | 'down'.

    Yellow ('concern') is the "needs attention, but you can fix it here" state and
    covers the four cases the dashboard surfaces:
      1. reachable-but-degraded  — health ok but with a `concern` flag (e.g. the
         Frita executor is up on :8799 but a ghost shadows :8797);
      2. dependency needs a reboot — e.g. the Win10 dockerd is down;
      3. down-but-restartable-here — a restart handler exists and the host is
         reachable, so a Restart button can recover it;
      4. recently-restarted — the 'starting' grace window after a Restart.
    Red ('down') is reserved for genuinely-stuck servers: down with no restart
    path, a remote whose host we can't even reach (host_unreachable) to attempt
    a fix, or a health result flagged 'hard': True — a failure a restart click
    cannot fix by itself (e.g. a dead OAuth token that needs human re-auth). host_unreachable is derived from an actual host probe (e.g. the SSH/
    docker check), not from guessing at the health-text wording."""
    if health is not None and health.get('ok'):
        return 'concern' if health.get('concern') else 'up'
    if starting:
        return 'starting'
    if dependency_down:
        return 'concern'
    if restartable and not host_unreachable and not (health or {}).get('hard'):
        return 'concern'
    return 'down'


def server_status_kind(deps: Collaborators, cfg, health):
    """Shared 4-state classification ('up'|'concern'|'starting'|'down', or None
    when there's nothing to check) used by BOTH the sidebar tab
    (/api/server-health) and the detail panel (/api/server-logs) so the two never
    disagree. dependency_down/host_unreachable come from the cached Win10 docker
    probe for win10_docker servers."""
    if health is None:
        return None
    key = cfg['key']
    dependency_down = host_unreachable = False
    if cfg.get('win10_docker') and not health.get('ok'):
        d = deps.win10_docker_ok()
        dependency_down = (d is False)
        host_unreachable = (d is None)
    return compute_server_status(
        health,
        starting=deps.is_server_starting(key),
        restartable=key in deps.restartable_keys,
        host_unreachable=host_unreachable,
        dependency_down=dependency_down)
