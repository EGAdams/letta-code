"""Reading a server's log file as a health signal, and as the detail panel.

Half the entries in `SERVERS` have no endpoint to ping. For those, the only
evidence the process is alive is that it is still writing to its log, so a file
mtime has to stand in for a health probe -- `log_activity_health` is that
substitution, and it answers with the same `ProbeResult` contract every real
probe answers with, so the caller cannot tell the two apart.

`server_log_rows` is the other half: the same file, tailed, plus whichever
status the panel should show above it. It takes its two health collaborators as
arguments instead of importing them, because `cached_server_health` and
`server_status_kind` live in server.py -- importing them would be a cycle, and
binding them at import time would quietly detach this module from
`monkeypatch.setattr(server, 'cached_server_health', ...)`, which is how the
existing tests drive it.
"""

from __future__ import annotations

import os
import time

from health.probe import probe

#: How recently a log-only server (no health_url) must have written to its log
#: to count as "appears running". Lettabot's heartbeat writes every ~5 minutes,
#: so 15 minutes tolerates a couple of missed cycles before flipping red.
LOG_ACTIVITY_WINDOW = 900

#: How many trailing log lines the detail panel exposes.
SERVER_LOG_TAIL = 300


def format_age(seconds):
    """Render a duration as a short human string: '42s', '5m', '3h', '2d'."""
    seconds = int(seconds)
    if seconds < 60:
        return f'{seconds}s'
    minutes = seconds // 60
    if minutes < 60:
        return f'{minutes}m'
    hours = minutes // 60
    if hours < 24:
        return f'{hours}h'
    return f'{hours // 24}d'


def log_activity_health(cfg):
    """Derive up/down for a log-only server from its log file's mtime.

    A server with no health_url can't be pinged — recent log writes are the
    only "is it alive" signal available. Returns a ProbeResult payload, or None
    if the server has a health_url (use server_health instead) or no log_file."""
    if cfg.get('health_url') or not cfg.get('log_file'):
        return None
    log_file = cfg['log_file']
    try:
        age = time.time() - os.path.getmtime(log_file)
    except OSError:
        return probe(False, 'no log file found')
    if age <= LOG_ACTIVITY_WINDOW:
        return probe(True, f'log active — last write {format_age(age)} ago')
    return probe(False, f'no recent log activity — last write {format_age(age)} ago')


def tail_lines(path, n):
    """Return up to the last n lines of a file as (start_lineno, [lines]).

    start_lineno is the absolute line number of the first returned line so the
    client can give each physical line a stable key (repeated identical lines
    stay distinct, and re-polled overlap dedupes correctly)."""
    try:
        with open(path, 'r', errors='replace') as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return None
    except Exception:
        return None
    start = max(0, len(lines) - n)
    return start, lines[start:]


def trim_log_cache(path, max_lines):
    """Rewrite a cache file to its last `max_lines` once it grows past that —
    keeps /tmp from filling up on a long-running dashboard process."""
    try:
        with open(path, 'r', errors='replace') as f:
            lines = f.read().splitlines()
    except OSError:
        return
    if len(lines) > max_lines:
        with open(path, 'w') as f:
            f.write('\n'.join(lines[-max_lines:]) + '\n')


def server_log_rows(cfg, q='', *, health_reader, status_kind,
                    starting_window):
    """Build {status, rows} for a server. rows carry a stable 'seq' line key.

    `health_reader(cfg)` is the cached active probe, `status_kind(cfg, health)`
    the shared 4-state classifier, and `starting_window` the
    `monitoring.server_lifecycle` module -- all injected so this stays free of
    the server registry.
    """
    out = {'rows': []}

    # A real "up" health check always wins — flip green the moment the server
    # actually answers, rather than waiting out the "starting" window below.
    # The detail panel's status must agree with the sidebar tab — both go through
    # status_kind so a down-but-restartable server reads the same yellow
    # "concern" in the panel as on the tab (not a bare red "Down").
    health = health_reader(cfg)
    if health is not None and health.get('ok'):
        starting_window.clear_server_starting(cfg['key'])
        out['status'] = dict(health)
        out['status']['kind'] = status_kind(cfg, health)
    elif starting_window.is_server_starting(cfg['key']):
        out['status'] = {'ok': False, 'kind': 'starting',
                         'text': 'STARTING... — server startup in progress'}
    elif health is not None:
        out['status'] = dict(health)
        out['status']['kind'] = status_kind(cfg, health)
    else:
        # No health_url to ping — fall back to "is it still writing logs?".
        log_health = log_activity_health(cfg)
        if log_health is not None:
            out['status'] = dict(log_health)
            out['status']['kind'] = status_kind(cfg, log_health)

    log_file = cfg.get('log_file')
    if log_file:
        tail = tail_lines(log_file, SERVER_LOG_TAIL)
        if tail is None:
            out.setdefault('status', {'ok': False, 'text': ''})
            out['rows'].append({'seq': 0, 'date': '', 'type': 'log',
                                'text': f'(log file not found: {log_file})'})
        else:
            start, lines = tail
            ql = q.lower()
            for i, line in enumerate(lines):
                if ql and ql not in line.lower():
                    continue
                out['rows'].append({'seq': start + i, 'date': '', 'type': 'log', 'text': line})
    elif 'status' not in out:
        out['status'] = {'ok': False, 'text': 'no log file or health check configured'}
    return out
