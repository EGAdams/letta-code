"""Mapping a report URL to its file on disk, and finding which report.html
row backs a given (date, amount) or expense id.

``rol_reports_base_dir``, ``reports_url_prefix``, ``reports_months`` and
``reports`` (the report registry) are all read fresh via ``Collaborators``:
the registries are rebound wholesale by several tests to point at a tmp_path
fixture tree, so a snapshot taken at import time would keep resolving against
the real ~/rol_finances tree. ``find_matching_report_row`` routes internal
calls in ``document_association.py`` back through the server.py name (not
this module's own function) because tests monkeypatch it directly to drive
those callers without real report.html files on disk.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from typing import Callable
from urllib.parse import unquote

from finance.report_page import ReportRowMatch


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    reports_url_prefix: str
    reports_months: dict
    rol_reports_base_dir: Callable
    reports: list
    recent_report_path: str
    scanner_report_path: str
    receipt_only_report_path: str
    resolve_recent_report: Callable
    viewable_document_extensions: set
    supporting_document_annotation_cache: str
    render_excel_for_browser: Callable
    source_document_path: Callable


def split_report_url(deps: Collaborators, report_path):
    """Map '/rol_finances_reports/<month>/<rel>' -> (base_dir, rel), or None if
    malformed or the month key isn't recognized."""
    prefix = deps.reports_url_prefix + '/'
    if not report_path or not report_path.startswith(prefix):
        return None
    month_key, sep, rel = report_path[len(prefix):].partition('/')
    if not sep or month_key not in deps.reports_months:
        return None
    return deps.rol_reports_base_dir(month_key), rel


def report_file_for_url(deps: Collaborators, report_path):
    """Map a /rol_finances_reports/<month>/<dir>/report.html URL path to its file on disk."""
    split = split_report_url(deps, report_path)
    if not split:
        return None
    base, rel = split
    fp = os.path.abspath(os.path.join(base, rel))
    base = os.path.abspath(base)
    if os.path.commonpath([fp, base]) == base and os.path.isfile(fp):
        return fp
    return None


def iter_existing_report_files(deps: Collaborators):
    """Yield (url, file_path, label) for every report.html that actually exists on
    disk, across every month x report-dir combination. Mirrors the nested loop in
    _rol_finance_recent_reports but returns file paths instead of status info."""
    for month_key in deps.reports_months:
        base_dir = deps.rol_reports_base_dir(month_key)
        for r in deps.reports:
            report_file = os.path.join(base_dir, r['dir'], 'report.html')
            if os.path.isfile(report_file):
                url = f'{deps.reports_url_prefix}/{month_key}/{r["dir"]}/report.html'
                yield url, report_file, r['label']


def find_matching_report_row(deps: Collaborators, date_str, amount_str,
                             vendor_key='', expense_id=None):
    """Search every existing report.html's Verified-Transactions rows for the one
    matching (date, amount) — used by recategorize_expense when it is called with
    no report_path (the New Records dialog's case: it only knows the DB row, not
    which static report.html — if any — already carries a <tr> for the same
    transaction). Report-file vendor_keys are parsed from the bank statement and
    often diverge from the DB's id_light-derived vendor_key (e.g. 'kum_go_2608r'
    vs 'kum_go_2608r_walker'), so vendor_key is NOT required to match — only used
    to disambiguate when more than one row shares the same date+amount.

    Returns a ReportRowMatch for exactly one match, or None when zero or
    unresolvably-many rows matched (leaves report files alone in the
    ambiguous case rather than guessing wrong).
    """
    d = (date_str or '').strip()
    a = (amount_str or '').strip()
    eid = str(expense_id or '').strip()
    if not eid and (not d or not a):
        return None
    matches: list[ReportRowMatch] = []
    for url, file_path, label in iter_existing_report_files(deps):
        try:
            with open(file_path, encoding='utf-8', errors='replace') as f:
                html = f.read()
        except OSError:
            continue
        for m in re.finditer(r'<tr([^>]*)>(.*?)</tr>', html, re.S):
            open_tag, inner = m.group(1), m.group(2)
            vk_m = re.search(r'data-vendor-key="([^"]*)"', open_tag)
            if not vk_m:
                continue  # not a Verified-Transactions row (e.g. a summary table)
            if eid:
                if ('data-expense-id="%s"' % eid) not in open_tag:
                    continue
            elif ('>%s<' % d) not in inner or ('>%s<' % a) not in inner:
                continue
            matches.append(ReportRowMatch(
                report_path=url, label=label, row_vendor_key=vk_m.group(1),
            ))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1 and vendor_key:
        vk = vendor_key.strip()
        narrowed = [mch for mch in matches if mch.row_vendor_key and (
            vk.startswith(mch.row_vendor_key) or mch.row_vendor_key.startswith(vk))]
        if len(narrowed) == 1:
            return narrowed[0]
    return None


def resolve_report_path_alias(deps: Collaborators, report_path):
    """The Recent Report view serves a real report.html at /recent_report.html,
    so the picker dialog injected in that report posts
    report_path='/recent_report.html' (it uses location.pathname). Translate
    the alias to the underlying report URL so row recolor, receipt lookup and
    reprocess hit the actual file on disk.

    The dialog now posts location.search too (the scanner report needs it to say
    WHICH scanner), so every synthetic page is matched on its path alone and
    answers without its query string."""
    base = str(report_path or '').split('?', 1)[0]
    if base == deps.recent_report_path:
        recent = deps.resolve_recent_report()
        if recent and recent.get('mode') == 'report':
            return recent['url']
        # Intake mode (or nothing yet): no report.html backs the page — return
        # '' so recategorize does its search-every-report / DB-only fallback,
        # exactly like the New Records dialog.
        return ''
    if base == deps.scanner_report_path:
        # Scanner reports are always synthetic DB-backed pages. There is no
        # report.html to recolor, so an empty path intentionally selects
        # recategorize_expense's search/static-row-or-DB-only success path.
        return ''
    if base == deps.receipt_only_report_path:
        # Synthetic too, but its own code path keys off this exact constant.
        return base
    return report_path


def source_document_path(deps: Collaborators, report_path, receipt_path=None):
    """Resolve the original statement document represented by a report URL."""
    raw = unquote((report_path or '').split('?', 1)[0])
    report_file = None
    split = split_report_url(deps, raw)
    if split:
        base, rel = split
        candidate = os.path.abspath(os.path.join(base, rel))
        base = os.path.abspath(base)
        if os.path.commonpath([candidate, base]) == base:
            report_file = candidate
    if report_file:
        directory = os.path.dirname(report_file)

        def preferred_source(candidate_directory):
            preferred = []
            if not os.path.isdir(candidate_directory):
                return ''
            for name in os.listdir(candidate_directory):
                fp = os.path.join(candidate_directory, name)
                ext = os.path.splitext(name)[1].lower()
                if (os.path.isfile(fp)
                        and ext in deps.viewable_document_extensions):
                    preferred.append(fp)
            priority = {
                '.pdf': 0, '.xlsx': 1, '.xlsm': 2,
                '.jpg': 3, '.jpeg': 3, '.png': 3, '.webp': 3,
                '.tif': 3, '.tiff': 3, '.bmp': 3, '.gif': 3,
            }
            preferred.sort(
                key=lambda fp: (
                    priority.get(os.path.splitext(fp)[1].lower(), 99),
                    os.path.basename(fp).lower(),
                )
            )
            return preferred[0] if preferred else ''

        source = preferred_source(directory)
        if source:
            return source

        # A statement may be listed under more than one month while only one
        # canonical month directory contains the source file. Search the same
        # report directory across configured month roots before giving up.
        split = split_report_url(deps, raw)
        if split:
            _base, rel = split
            report_directory = os.path.dirname(rel)
            for month_key in deps.reports_months:
                candidate_directory = os.path.join(
                    deps.rol_reports_base_dir(month_key), report_directory)
                if os.path.abspath(candidate_directory) == os.path.abspath(directory):
                    continue
                source = preferred_source(candidate_directory)
                if source:
                    return source
        if os.path.isfile(report_file):
            return report_file
    return receipt_path or ''


def report_source_document_view(deps: Collaborators, report_path):
    """Return a browser-viewable copy of the document behind a report.

    Calls ``deps.source_document_path`` -- the server.py name -- rather than
    this module's own function, so a test's
    ``monkeypatch.setattr(server, '_source_document_path', ...)`` is still
    honoured.
    """
    source_path = deps.source_document_path(report_path)
    if not source_path or not os.path.isfile(source_path):
        return ''
    ext = os.path.splitext(source_path)[1].lower()
    if ext not in deps.viewable_document_extensions:
        return ''
    if ext in {'.xlsx', '.xlsm'}:
        cache_key = hashlib.sha256(source_path.encode('utf-8')).hexdigest()[:16]
        browser_path = os.path.join(
            deps.supporting_document_annotation_cache,
            f'{cache_key}-{os.path.basename(source_path)}.html',
        )
        return deps.render_excel_for_browser(source_path, browser_path)
    return source_path
