#!/usr/bin/env python3
"""Operator-run Playwright process for ROL Finance -> Reports.

It repairs only deterministic category precedents above the 90% threshold.
Anything else remains selected behind an explicit OK or YES/NO blocker dialog.
Chromium stays open after the process exits.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from detached_playwright_browser import launch_detached_browser
from report_repair.api import DashboardApi
from report_repair.navigator import ReportsNavigator
from report_repair.workflow import ReportRepairWorkflow

DEFAULT_DASHBOARD = "http://100.102.209.100:8765"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dashboard-url", default=os.getenv("ROL_DASHBOARD_URL", DEFAULT_DASHBOARD)
    )
    parser.add_argument(
        "--finance-root", default=os.getenv("ROL_FINANCES_ROOT", "/home/adamsl/rol_finances")
    )
    parser.add_argument("--confidence", type=float, default=0.90)
    parser.add_argument("--max-repairs", type=int, default=100)
    parser.add_argument("--browser-executable")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument(
        "--skip-yellow-months", action="store_true",
        help=(
            "Pass over yellow month tabs (newest scanned expense still "
            "uncategorized) without stopping, so red/missing report tabs "
            "later in the year still get repaired. Never skips a report "
            "tab itself, only the month-level yellow signal."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if not 0 < args.confidence <= 1:
        raise SystemExit("--confidence must be between 0 and 1")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "Install browser dependencies: .venv/bin/pip install -r requirements-dev.txt"
        ) from exc

    manager = sync_playwright().start()
    process = None
    try:
        process, profile, browser = launch_detached_browser(
            manager, args.browser_executable, args.headless
        )
        page = browser.contexts[0].pages[0]
        api = DashboardApi(page)
        navigator = ReportsNavigator(page, args.dashboard_url, api)
        print(f"Browser PID {process.pid}; profile {profile}", flush=True)
        return ReportRepairWorkflow(
            api,
            navigator,
            page,
            finance_root=args.finance_root,
            confidence_threshold=args.confidence,
            skip_yellow_months=args.skip_yellow_months,
        ).run(args.max_repairs)
    finally:
        manager.stop()


if __name__ == "__main__":
    raise SystemExit(main())
