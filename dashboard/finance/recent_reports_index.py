"""Indexing existing report.html files across all months, newest-first.

Backs both the month tab's red/broken state and the dashboard's "New Records"
section (the most recently touched documents, needs-attention ones first).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    reports_months: dict
    reports_url_prefix: str
    rol_reports_base_dir: Callable
    rol_finance_reports_for_month: Callable
    classify_report_status: Callable


def month_broken_report_label(deps: Collaborators, month_key):
    """Label of the first report in this month whose file is missing or fails
    verification, or None if every report card is healthy. Backs the month
    tab's red state: the uncategorized-expense signal in fetch_month_status
    says nothing about whether the month's report.html files are correct, so
    a month with all-green expenses could still hide a red report tab."""
    base_dir = deps.rol_reports_base_dir(month_key)
    for r in deps.rol_finance_reports_for_month(month_key):
        report_file = os.path.join(base_dir, r['dir'], 'report.html')
        status = (
            deps.classify_report_status(report_file)
            if os.path.isfile(report_file) else 'missing')
        if status in ('missing', 'fail'):
            return r['label']
    return None


def rol_finance_recent_reports(deps: Collaborators, limit=5):
    """Gather every existing report.html across all months, newest-first, with
    the most recently processed shown as 'latest' and the top `limit` entries
    (needs-attention reports — status 'review'/'fail' — sorted ahead of clean
    'pass' ones, each bucket newest-first) returned as 'items'. Backs the
    dashboard's "New Records" section so a human sees the documents most
    likely to need a look first, not just whatever was touched most recently."""
    candidates = []
    for month_key in deps.reports_months:
        base_dir = deps.rol_reports_base_dir(month_key)
        for r in deps.rol_finance_reports_for_month(month_key):
            report_file = os.path.join(base_dir, r['dir'], 'report.html')
            try:
                mtime = os.path.getmtime(report_file)
            except OSError:
                continue
            status = deps.classify_report_status(report_file)
            candidates.append({
                'key': r['key'],
                'label': r['label'],
                'month_key': month_key,
                'status': status,
                'needs_attention': status in ('review', 'fail'),
                'mtime': mtime,
                'url': f'{deps.reports_url_prefix}/{month_key}/{r["dir"]}/report.html',
            })
    latest = max(candidates, key=lambda c: c['mtime']) if candidates else None
    items = sorted(
        candidates,
        key=lambda c: (0 if c['needs_attention'] else 1, -c['mtime']),
    )[:limit]
    return {'latest': latest, 'items': items}
