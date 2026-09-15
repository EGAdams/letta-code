"""Resolve a Tailscale peer's current IPv4 by hostname, not by a pinned literal.

Why this exists: on 2026-09-15 the Windows side of the desktop-shdbati box got
stuck in Tailscale's `NoState` (never crashed, so Windows service-recovery
never fired) and the only fix that worked was wiping its local Tailscale state
and re-authenticating. That re-registers the *same physical machine* as a
brand new node under a brand new IP. Any config that pins that IP goes stale
the moment this happens again -- silently, until a status tile goes red or a
restart button SSHes into a dead address. This module replaces "pin the IP"
with "look the peer up by hostname each time", so a future node-key reset
self-heals instead of requiring a manual code fix and redeploy.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess


def tailscale_cli() -> str:
    """Return the available Tailscale CLI, including the WSL host fallback.

    A freshly migrated WSL distro may not have the Linux package installed
    even though the Windows host is connected to the same tailnet. WSL
    interop exposes that host client as ``tailscale.exe``.
    """
    discovered = shutil.which('tailscale') or shutil.which('tailscale.exe')
    if discovered:
        return discovered
    # systemd user units intentionally use a Linux-only PATH, so WSL interop
    # executables are not discoverable there even though they remain runnable.
    windows_cli = '/mnt/c/Program Files/Tailscale/tailscale.exe'
    if os.path.isfile(windows_cli):
        return windows_cli
    return 'tailscale'


def resolve_peer_ip(hostname: str, os_name: str = 'windows', fallback: str | None = None,
                     timeout: int = 5) -> str | None:
    """Return the current IPv4 tailnet address of the peer named `hostname`.

    Matches on Tailscale's own `HostName` field plus `os_name`, since a Tailscale
    device name (`desktop-shdbati-2`) changes across a node-key reset but the
    underlying Windows/Linux hostname does not. Prefers an online match; among
    several matches (e.g. an old dead node lingering next to its replacement),
    falls back to the most recently seen one rather than an arbitrary one.

    Returns `fallback` if the CLI is unavailable, the call fails, or no peer
    matches -- a transient lookup failure must never break the caller outright.
    """
    try:
        result = subprocess.run(
            [tailscale_cli(), 'status', '--json'],
            capture_output=True, text=True, timeout=timeout,
        )
        data = json.loads(result.stdout)
    except Exception:
        return fallback

    matches = []
    for peer in data.get('Peer', {}).values():
        if peer.get('OS') != os_name:
            continue
        if (peer.get('HostName') or '').upper() != hostname.upper():
            continue
        ipv4 = next((ip for ip in (peer.get('TailscaleIPs') or []) if '.' in ip), None)
        if ipv4:
            matches.append((bool(peer.get('Online')), peer.get('LastSeen') or '', ipv4))

    if not matches:
        return fallback

    matches.sort(key=lambda m: (m[0], m[1]), reverse=True)
    return matches[0][2]
