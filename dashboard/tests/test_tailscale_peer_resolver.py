"""Tests for monitoring/tailscale_peer_resolver.py.

This module exists to fix a specific incident (2026-09-15): a Tailscale
node-key reset re-registers a machine under a new IP, and anything with that
IP pinned in config goes stale. These tests pin down the resolution rule
(prefer online, then most-recently-seen) and the fail-safe fallback.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from monitoring import tailscale_peer_resolver as resolver


def _status_json(peers):
    return json.dumps({'Peer': {str(i): p for i, p in enumerate(peers)}})


def _run(monkeypatch, stdout):
    fake = MagicMock(return_value=MagicMock(stdout=stdout))
    monkeypatch.setattr(resolver.subprocess, 'run', fake)
    return fake


def test_tailscale_cli_falls_back_to_windows_host_client(monkeypatch):
    def which(name):
        return '/mnt/c/Program Files/Tailscale/tailscale.exe' if name == 'tailscale.exe' else None
    monkeypatch.setattr(resolver.shutil, 'which', which)
    assert resolver.tailscale_cli() == '/mnt/c/Program Files/Tailscale/tailscale.exe'


def test_tailscale_cli_falls_back_to_the_interop_path_systemd_cannot_see(monkeypatch):
    """A systemd user unit has a Linux-only PATH, so shutil.which finds nothing
    even though the Windows binary is runnable."""
    monkeypatch.setattr(resolver.shutil, 'which', lambda name: None)
    monkeypatch.setattr(resolver.os.path, 'isfile',
                        lambda p: p == '/mnt/c/Program Files/Tailscale/tailscale.exe')
    assert resolver.tailscale_cli() == '/mnt/c/Program Files/Tailscale/tailscale.exe'


def test_resolves_the_online_windows_peer_by_hostname(monkeypatch):
    _run(monkeypatch, _status_json([
        {'OS': 'windows', 'HostName': 'DESKTOP-SHDBATI', 'Online': True,
         'LastSeen': '2026-09-15T00:00:00Z', 'TailscaleIPs': ['100.96.120.127', 'fd7a::1']},
    ]))
    assert resolver.resolve_peer_ip('DESKTOP-SHDBATI') == '100.96.120.127'


def test_ignores_a_different_os_with_the_same_hostname(monkeypatch):
    """The WSL (linux) side of the same physical box shares the Windows
    hostname -- matching on hostname alone would pick the wrong peer."""
    _run(monkeypatch, _status_json([
        {'OS': 'linux', 'HostName': 'DESKTOP-SHDBATI', 'Online': True,
         'LastSeen': '2026-09-15T00:00:00Z', 'TailscaleIPs': ['100.80.49.10']},
    ]))
    assert resolver.resolve_peer_ip('DESKTOP-SHDBATI', fallback='fallback-ip') == 'fallback-ip'


def test_prefers_the_online_match_over_a_stale_offline_one(monkeypatch):
    """An old dead node (pre-reset) can linger in the peer list next to its
    replacement -- online must win regardless of list order."""
    _run(monkeypatch, _status_json([
        {'OS': 'windows', 'HostName': 'DESKTOP-SHDBATI', 'Online': True,
         'LastSeen': '2026-09-15T00:00:00Z', 'TailscaleIPs': ['100.96.120.127']},
        {'OS': 'windows', 'HostName': 'DESKTOP-SHDBATI', 'Online': False,
         'LastSeen': '2026-09-14T00:00:00Z', 'TailscaleIPs': ['100.69.80.89']},
    ]))
    assert resolver.resolve_peer_ip('DESKTOP-SHDBATI') == '100.96.120.127'


def test_falls_back_to_most_recently_seen_when_all_matches_are_offline(monkeypatch):
    _run(monkeypatch, _status_json([
        {'OS': 'windows', 'HostName': 'DESKTOP-SHDBATI', 'Online': False,
         'LastSeen': '2026-09-14T00:00:00Z', 'TailscaleIPs': ['100.69.80.89']},
        {'OS': 'windows', 'HostName': 'DESKTOP-SHDBATI', 'Online': False,
         'LastSeen': '2026-09-15T00:00:00Z', 'TailscaleIPs': ['100.96.120.127']},
    ]))
    assert resolver.resolve_peer_ip('DESKTOP-SHDBATI') == '100.96.120.127'


def test_returns_fallback_when_no_peer_matches(monkeypatch):
    _run(monkeypatch, _status_json([]))
    assert resolver.resolve_peer_ip('DESKTOP-SHDBATI', fallback='last-known') == 'last-known'


def test_returns_fallback_when_the_cli_call_fails(monkeypatch):
    def boom(*a, **kw):
        raise OSError('no tailscale binary')
    monkeypatch.setattr(resolver.subprocess, 'run', boom)
    assert resolver.resolve_peer_ip('DESKTOP-SHDBATI', fallback='last-known') == 'last-known'


def test_returns_fallback_on_unparseable_json(monkeypatch):
    _run(monkeypatch, 'not json')
    assert resolver.resolve_peer_ip('DESKTOP-SHDBATI', fallback='last-known') == 'last-known'


def test_returns_none_with_no_fallback_and_no_match(monkeypatch):
    _run(monkeypatch, _status_json([]))
    assert resolver.resolve_peer_ip('DESKTOP-SHDBATI') is None
