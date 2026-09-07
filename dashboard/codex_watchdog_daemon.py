#!/usr/bin/env python3
"""Standalone daemon: stops runaway local Codex CLI sessions before they burn
through the account's quota unattended.

Run on any box that might launch `codex --dangerously-bypass-approvals-and-sandbox`
outside of a person's watched terminal -- see codex-watchdog.service. Not a
dashboard route or a server.py background thread: the box serving the
dashboard is not necessarily the box running Codex (see dashboard/CLAUDE.md,
"Which machine is live"), and this has to run wherever Codex actually runs.

    python3 codex_watchdog_daemon.py                 # run forever
    python3 codex_watchdog_daemon.py --once           # one poll, for a manual check
    python3 codex_watchdog_daemon.py --kill-percent 85 --max-concurrent 2
"""

from __future__ import annotations

import argparse
import sys
import time

from health.codex_process_controller import OsProcessController
from health.codex_process_inspector import ProcProcessInspector
from health.codex_session_reader import RolloutFileSessionReader
from health.codex_watchdog import CodexWatchdog
from health.codex_watchdog_contracts import (
    KILL_PRIMARY_PERCENT,
    MAX_CONCURRENT_AUTONOMOUS,
    POLL_INTERVAL_SECONDS,
    STOPPED_REAP_SECONDS,
    WARN_PRIMARY_PERCENT,
)
from health.codex_watchdog_store import default_store


def _log(line: str) -> None:
    print(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {line}', flush=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kill-percent', type=float, default=KILL_PRIMARY_PERCENT,
                         help='Terminate at this primary (5h) quota %% (default %(default)s)')
    parser.add_argument('--warn-percent', type=float, default=WARN_PRIMARY_PERCENT,
                         help='Log-only warning threshold (default %(default)s)')
    parser.add_argument('--max-concurrent', type=int, default=MAX_CONCURRENT_AUTONOMOUS,
                         help='Max simultaneous autonomous sessions (default %(default)s)')
    parser.add_argument('--stopped-reap-seconds', type=float, default=STOPPED_REAP_SECONDS,
                         help='Kill a Ctrl-Z-stopped session after this long (default %(default)s)')
    parser.add_argument('--poll-interval-seconds', type=float, default=POLL_INTERVAL_SECONDS,
                         help='Seconds between checks (default %(default)s)')
    parser.add_argument('--once', action='store_true',
                         help='Run a single poll and exit, for a manual check.')
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    watchdog = CodexWatchdog(
        inspector=ProcProcessInspector(),
        reader=RolloutFileSessionReader(),
        controller=OsProcessController(),
        store=default_store(),
        log=_log,
        kill_percent=args.kill_percent,
        warn_percent=args.warn_percent,
        max_concurrent=args.max_concurrent,
        stopped_reap_seconds=args.stopped_reap_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
    )

    if args.once:
        decisions = watchdog.poll_once()
        _log(f'{len(decisions)} decision(s) made')
        return 0

    watchdog.run_forever()
    return 0


if __name__ == '__main__':
    sys.exit(main())
