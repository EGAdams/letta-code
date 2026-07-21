#!/usr/bin/env python3
"""
Dashboard SPA server.
Serves dashboard.html and proxies agent data from the Letta API.
Run: python3 server.py   (from /home/adamsl/letta-code/dashboard/)
Then open: http://localhost:8765/
"""
import json
import hashlib
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from collections import deque
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote, unquote

from voice.pipeline import build_pipeline, handle_voice_upload
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
LETTA_CODE_BUN = os.environ.get(
    'LETTA_CODE_BUN', os.path.expanduser('~/.bun/bin/bun'))

# Time this process started serving — used by /api/code-status to detect source
# files that changed on disk after the running process loaded them, so the
# dashboard can prompt for a restart of dashboard-server.service.
SERVER_START_TIME = time.time()

# Files/dirs whose mtimes are checked by /api/code-status. Only Python source
# is watched: HTML/CSS/JS are static files served fresh from disk on every
# request, so editing them takes effect immediately and a restart isn't
# needed. server.py and the modules it imports (voice/) are loaded into the
# running process at startup, so they need dashboard-server.service restarted
# for edits to take effect. Directories are walked recursively for .py files.
CODE_WATCH_PATHS = [
    os.path.join(HERE, 'server.py'),
    os.path.join(HERE, 'voice'),
]


def get_code_status():
    """Report whether any watched source file changed after this server started."""
    changed_files = []
    for watch_path in CODE_WATCH_PATHS:
        if os.path.isdir(watch_path):
            for root, _dirs, files in os.walk(watch_path):
                for fname in files:
                    if not fname.endswith('.py'):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        if os.path.getmtime(fpath) > SERVER_START_TIME:
                            changed_files.append(os.path.relpath(fpath, HERE))
                    except OSError:
                        continue
        elif os.path.isfile(watch_path):
            try:
                if os.path.getmtime(watch_path) > SERVER_START_TIME:
                    changed_files.append(os.path.relpath(watch_path, HERE))
            except OSError:
                continue
    return {
        'changed': len(changed_files) > 0,
        'changed_files': sorted(changed_files),
        'server_start': SERVER_START_TIME,
    }

# ROL Finance project plan lives outside the repo (its own project dir) — served
# directly under this fixed path since it isn't reachable via HERE/REPO_ROOT.
ROL_FINANCES_PLAN_PATH = '/rol_finances/tools/plan.html'
ROL_FINANCES_PLAN_FILE = os.path.expanduser('~/rol_finances/tools/plan.html')

# ROL Finance "Reports" sub-tab: one tab per source-document directory, each
# containing a generated report.html. Lives outside the repo, so reports are
# served under ROL_FINANCES_REPORTS_URL_PREFIX (path-traversal checked below).
# `check_images/` is intentionally excluded — still waiting on those files.
# Reports are grouped by month (the frontend's month tabs); each monthly `dir`
# is looked up under that month's own subfolder, so a document is "ready" for a
# given month independently of the others. All-year documents are intentionally
# shown only in January, which is the dashboard's special all-year view.
ROL_FINANCES_REPORTS_PARENT = os.path.expanduser(
    '~/rol_finances/readable_documents/bank_statements')
ROL_FINANCES_REPORTS_MONTHS = {
    'jan-2025': 'january',
    'feb-2025': 'february',
    'mar-2025': 'march',
    'apr-2025': 'april',
}
# Calendar date range (inclusive) each month tab covers. Used by
# /api/rol-finance-month-status to find that month's most-recently-scanned
# expense. Statements straddle month boundaries, but the tabs group by the
# calendar month they're filed under, so we key the range off that month.
ROL_FINANCES_MONTH_RANGES = {
    'jan-2025': ('2025-01-01', '2025-01-31'),
    'feb-2025': ('2025-02-01', '2025-02-28'),
    'mar-2025': ('2025-03-01', '2025-03-31'),
    'apr-2025': ('2025-04-01', '2025-04-30'),
}
ROL_FINANCES_REPORTS_DEFAULT_MONTH = 'jan-2025'
ROL_FINANCES_REPORTS_BASE = os.path.join(
    ROL_FINANCES_REPORTS_PARENT, ROL_FINANCES_REPORTS_MONTHS[ROL_FINANCES_REPORTS_DEFAULT_MONTH])
ROL_FINANCES_REPORTS_URL_PREFIX = '/rol_finances_reports'
ROL_FINANCE_REPORTS = [
    {'key': 'amex-61006',        'label': 'Amex 61006',         'dir': 'amex_personal_january_25'},
    {'key': 'fnbo-4851',         'label': 'FNBO 4851',          'dir': 'january_fnbo_2025_account_4851'},
    {'key': 'amex-personal-year','label': 'Amex Personal Year', 'dir': 'amex_personal_whole_2025', 'all_year': True},
    {'key': 'bank-5938-pdf1',    'label': 'Bank 5938 PDF 1',    'dir': 'december_january_personal_bank_statement'},
    {'key': 'bank-6285-pdf1',    'label': 'Bank 6285 PDF 1',    'dir': 'non_profit_rol_Statement_december_january_6285'},
    {'key': 'bank-6285-pdf2',    'label': 'Bank 6285 PDF 2',    'dir': 'business_january_february_6285'},
    {'key': 'jetblue-pdf1',      'label': 'Jet Blue PDF 1',     'dir': 'jet_blue__december_january_12_26_25_to_01_23_25'},
    {'key': 'jetblue-pdf2',      'label': 'Jet Blue PDF 2',     'dir': 'jet_blue_january_february_01_27_to_02_25_25'},
    {'key': 'platinum-year',     'label': 'Platinum Year',      'dir': 'platinum_business_credit_card_for_the_year', 'all_year': True},
    {'key': 'diners-club-0587',  'label': 'Diners Club 0587',   'dir': 'diners_club__january_25_statements-MONTHLY-0587'},
    {'key': 'diners-0587-year',  'label': 'Diners 0587 Year',   'dir': 'diners_0587_whole_year_2025', 'all_year': True},
    {'key': 'bank-3119-pdf',     'label': 'Bank 3119 PDF',      'dir': 'fifth_third_non_profit_3119'},
    {'key': 'choice-7580-year',  'label': 'Choice 7580 Year',   'dir': 'choice_7580_year', 'all_year': True},
]


def _rol_finance_reports_for_month(month_key):
    """Document cards for a month; all-year cards live only under January."""
    if month_key == ROL_FINANCES_REPORTS_DEFAULT_MONTH:
        return ROL_FINANCE_REPORTS
    return [r for r in ROL_FINANCE_REPORTS if not r.get('all_year')]

# ── ROL Finance: recategorize a Verified-Transactions row ─────────────────
# The category-picker dialog injected into each report.html (by
# rol_finances/tools/python_tasks/verification_lib/restructure_verified_transactions.py)
# POSTs to /api/recategorize-expense. We reuse the same DB access create_spreadsheet.py
# uses (app.db.get_connection from the rol_finances receipt_parsing_tools tree), so the
# next create_spreadsheet run sees the user's correction.
RECEIPT_PARSING_TOOLS = os.path.expanduser('~/rol_finances/receipt_parsing_tools')

# Reporting-category name → representative categories.id. Mirrors
# create_spreadsheet.py's REPORTING_CATEGORY_DB_MAP. "Uncategorized" clears category_id.
REPORTING_CATEGORY_DB_MAP = {
    'Church Facility': 100,
    'Church Utilities': 120,
    'Ministry and Worship': 150,
    'Office & Administration': 140,
    'Food & Hospitality': 130,
    'Gifts & Love Offerings': 190,
    # "Staff & Benefits" (240) split into Robert (RJ, 242) and Rosemary (RM, 243),
    # both "Priority Health" leaves under "Senior Pastors" (241).
    'Robert Benefits and Medical': 242,
    'Rosemary Benefits & Medical': 243,
    'Travel & Vehicle': 160,
    'Insurance, Taxes & Fees': 230,
    'Housing': 300,
    'Personal': 3,
    'Uncategorized': None,
}

# Reporting-category name → the cat-* CSS class baked into report.html rows.
# report.html is a STATIC file: its row color comes from this class, NOT from a
# live DB read, so a category change must rewrite this class on disk to survive a
# page refresh (the DB write alone is invisible to the static file).
REPORTING_CATEGORY_CLASS = {
    'Church Facility': 'cat-church-facility',
    'Church Utilities': 'cat-church-utilities',
    'Ministry and Worship': 'cat-ministry-and-worship',
    'Office & Administration': 'cat-office-and-administration',
    'Food & Hospitality': 'cat-food-and-hospitality',
    'Gifts & Love Offerings': 'cat-gifts-and-love-offerings',
    'Robert Benefits and Medical': 'cat-robert-benefits-and-medical',
    'Rosemary Benefits & Medical': 'cat-rosemary-benefits-and-medical',
    'Travel & Vehicle': 'cat-travel-and-vehicle',
    'Insurance, Taxes & Fees': 'cat-insurance-taxes-and-fees',
    'Housing': 'cat-housing',
    'Personal': 'cat-personal',
    'Uncategorized': 'cat-uncategorized',
}

# Reporting-category name → (background, font) hex, mirrors create_spreadsheet.py's
# REPORTING_CATEGORY_STYLES. Used to color the synthetic "Receipt Only" report rows
# (the static per-statement report.html files carry these as baked-in cat-* CSS).
REPORTING_CATEGORY_STYLE = {
    'Church Facility': ('#B8CCE4', '#000000'),
    'Church Utilities': ('#95B3D7', '#000000'),
    'Ministry and Worship': ('#DCE6F1', '#000000'),
    'Office & Administration': ('#4F81BD', '#FFFFFF'),
    'Food & Hospitality': ('#F4F199', '#000000'),
    'Gifts & Love Offerings': ('#A9D18E', '#000000'),
    'Robert Benefits and Medical': ('#CCC0DA', '#000000'),
    'Rosemary Benefits & Medical': ('#F4B6C2', '#000000'),
    'Travel & Vehicle': ('#F4B683', '#000000'),
    'Insurance, Taxes & Fees': ('#FCD5B4', '#000000'),
    'Housing': ('#DDD9C4', '#000000'),
    'Personal': ('#948A54', '#FFFFFF'),
    'Uncategorized': ('#BFBFBF', '#000000'),
}

# category_id → reporting bucket, walked up the ancestor chain. Duplicated from
# create_spreadsheet.py's REPORTING_CATEGORY_ANCESTOR_MAP (small + stable; importing
# create_spreadsheet pulls xlsxwriter which the server's system python lacks).
REPORTING_CATEGORY_ANCESTOR_MAP = {
    100: 'Church Facility', 110: 'Church Facility', 120: 'Church Utilities',
    130: 'Food & Hospitality', 140: 'Office & Administration',
    150: 'Ministry and Worship', 160: 'Travel & Vehicle',
    190: 'Gifts & Love Offerings', 230: 'Insurance, Taxes & Fees',
    240: 'Robert Benefits and Medical', 242: 'Robert Benefits and Medical',
    243: 'Rosemary Benefits & Medical', 300: 'Housing', 310: 'Housing',
    320: 'Housing', 330: 'Housing', 340: 'Housing', 350: 'Housing',
    358: 'Insurance, Taxes & Fees', 364: 'Uncategorized',
    400: 'Insurance, Taxes & Fees', 1: 'Uncategorized', 2: 'Housing', 3: 'Personal',
}

# URL of the synthetic "Receipt Only" report page (served by do_GET, listed as a tab
# by /api/rol-finance-reports). Not a file on disk — the page is built live from the DB.
RECEIPT_ONLY_REPORT_PATH = '/api/rol-finance-receipt-only-report'
VERIFICATION_LIB = os.path.expanduser(
    '~/rol_finances/tools/python_tasks/verification_lib')


def _classify_report_status(report_file):
    """Classify a report.html's overall verification status from its hero
    badge text: 'pass' (green, finished), 'review' (yellow, work in progress
    — e.g. "REVIEW NEEDED"), or 'fail' (red — explicit failure). Falls back to
    'review' when the badge can't be found/parsed, since an unparseable
    report still needs a human look rather than being silently green."""
    try:
        with open(report_file, 'r', encoding='utf-8', errors='replace') as f:
            html = f.read()
    except OSError:
        return 'fail'
    m = re.search(r'<div class="badge[^"]*">(.*?)</div>', html, re.S)
    if not m:
        return 'review'
    text = re.sub(r'<[^>]+>', '', m.group(1)).upper()
    if 'REVIEW NEEDED' in text or 'WIP' in text:
        return 'review'
    if 'FAIL' in text:
        return 'fail'
    if 'PASS' in text:
        return 'pass'
    return 'review'


def _strip_html_text(fragment):
    """Collapse an HTML fragment to its visible text (tags dropped,
    whitespace normalized)."""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', fragment)).strip()


def _extract_report_attention_detail(report_file):
    """Pull the human-facing explanation out of a fail/review report.html.

    The dashboard iframe hides everything except Verified Transactions, so the
    parent view needs the hero badge, summary, unresolved sections, and the
    report author's required/recommended next action. Returns a detail dict or
    None when the report has no recognizable attention information.
    """
    try:
        with open(report_file, 'r', encoding='utf-8', errors='replace') as f:
            html = f.read()
    except OSError:
        return None
    detail = {}
    m = re.search(r'<div class="badge[^"]*">(.*?)</div>', html, re.S)
    if m:
        detail['badge'] = _strip_html_text(m.group(1))
    m = re.search(r'<div class="summary-box">(.*?)</div>', html, re.S)
    if m:
        detail['summary'] = _strip_html_text(m.group(1))
    # Older reports use a flat <h2> + <p class="warn"> layout instead of
    # hero/card wrappers. Their final-status paragraph is both the badge and
    # the best available summary.
    if not detail.get('badge'):
        m = re.search(
            r'<h2[^>]*>Final[^<]*Status</h2>\s*<p[^>]*class=["\'](?:warn|fail)["\'][^>]*>(.*?)</p>',
            html,
            re.S | re.I,
        )
        if m:
            final_text = _strip_html_text(m.group(1))
            detail['badge'] = final_text
            detail.setdefault('summary', final_text)
    issues = []
    for sec in re.finditer(r'<section class="card">(.*?)</section>', html, re.S):
        body = sec.group(1)
        sm = re.search(r'<span class="status-(fail|warn)[^"]*">(.*?)</span>',
                       body, re.S)
        if not sm:
            continue
        hm = re.search(r'<h2[^>]*>(.*?)</h2>', body, re.S)
        # First paragraph of the section, with the status pill itself removed
        # so its label isn't duplicated in the text.
        pm = re.search(r'<p>(.*?)</p>', body, re.S)
        text = ''
        if pm:
            text = _strip_html_text(
                re.sub(r'<span class="status-[^"]*">.*?</span>', '', pm.group(1), flags=re.S))
        issues.append({
            'section': _strip_html_text(hm.group(1)) if hm else '',
            'status': _strip_html_text(sm.group(2)),
            'text': text,
        })
    if issues:
        detail['issues'] = issues
    else:
        # Legacy flat reports put each warning immediately after its heading.
        for sec in re.finditer(
            r'<h2[^>]*>([^<]+)</h2>\s*<p[^>]*class=["\'](warn|fail)["\'][^>]*>(.*?)</p>',
            html,
            re.S | re.I,
        ):
            section = _strip_html_text(sec.group(1))
            if section.lower().startswith('final '):
                continue
            raw_text = _strip_html_text(sec.group(3))
            status_match = re.match(r'([A-Z_ ]+)\s*[—-]\s*(.*)', raw_text)
            issues.append({
                'section': section,
                'status': (status_match.group(1).replace('_', ' ').strip()
                           if status_match else sec.group(2).upper()),
                'text': status_match.group(2).strip() if status_match else raw_text,
            })
        if issues:
            detail['issues'] = issues
    for paragraph in re.finditer(r'<p[^>]*>(.*?)</p>', html, re.S):
        paragraph_text = _strip_html_text(paragraph.group(1))
        action = re.match(
            r'(?:Required|Recommended) next actions?\s*:\s*(.+)',
            paragraph_text,
            re.I,
        )
        if action:
            detail['recommended_action'] = action.group(1).strip()
            break
    return detail or None


def _extract_report_failure_detail(report_file):
    """Backward-compatible name for existing callers and tests."""
    return _extract_report_attention_detail(report_file)


def _rol_reports_base_dir(month_key):
    """Base dir for a month key, e.g. 'feb-2025' -> .../bank_statements/february."""
    sub = ROL_FINANCES_REPORTS_MONTHS.get(
        month_key, ROL_FINANCES_REPORTS_MONTHS[ROL_FINANCES_REPORTS_DEFAULT_MONTH])
    return os.path.join(ROL_FINANCES_REPORTS_PARENT, sub)


def _rol_finance_recent_reports(limit=5):
    """Gather every existing report.html across all months, newest-first, with
    the most recently processed shown as 'latest' and the top `limit` entries
    (needs-attention reports — status 'review'/'fail' — sorted ahead of clean
    'pass' ones, each bucket newest-first) returned as 'items'. Backs the
    dashboard's "New Records" section so a human sees the documents most
    likely to need a look first, not just whatever was touched most recently."""
    candidates = []
    for month_key in ROL_FINANCES_REPORTS_MONTHS:
        base_dir = _rol_reports_base_dir(month_key)
        for r in _rol_finance_reports_for_month(month_key):
            report_file = os.path.join(base_dir, r['dir'], 'report.html')
            try:
                mtime = os.path.getmtime(report_file)
            except OSError:
                continue
            status = _classify_report_status(report_file)
            candidates.append({
                'key': r['key'],
                'label': r['label'],
                'month_key': month_key,
                'status': status,
                'needs_attention': status in ('review', 'fail'),
                'mtime': mtime,
                'url': f'{ROL_FINANCES_REPORTS_URL_PREFIX}/{month_key}/{r["dir"]}/report.html',
            })
    latest = max(candidates, key=lambda c: c['mtime']) if candidates else None
    items = sorted(
        candidates,
        key=lambda c: (0 if c['needs_attention'] else 1, -c['mtime']),
    )[:limit]
    return {'latest': latest, 'items': items}


# ── Recent Report (/recent_report.html) ──────────────────────────────────
# The Reports tab lands on "Recent Report" — a live view of the Verified
# Transactions from the most recently processed document. It is served
# dynamically (never a stale copy): each GET re-reads the current source
# report.html, so recategorizations done through the picker dialog show up on
# the next load. "Most recent" is the newer of:
#   - an explicit pointer written when Mazda's STEP 8 /api/expense-stored
#     callback (or a Reprocess Document run) names/matches a report, and
#   - the newest report.html mtime (Mazda rewriting a report on disk bumps it
#     even when no callback fires).
RECENT_REPORT_PATH = '/recent_report.html'
SCANNER_REPORT_PATH = '/scanner_report.html'
RECENT_REPORT_POINTER_FILE = os.path.join(HERE, 'recent_report.json')
_recent_report_lock = threading.Lock()


def _read_recent_pointer_file():
    """Raw pointer-file contents ({} when missing/corrupt). The file holds BOTH
    the report pointer ({report_path, updated_at}) and the last intake dispatch
    ({intake: {...}}) — scanned documents usually have no report.html, so the
    intake record is what lets /recent_report.html reflect them at all."""
    try:
        with open(RECENT_REPORT_POINTER_FILE, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_recent_pointer_file(data):
    try:
        with open(RECENT_REPORT_POINTER_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        return True
    except OSError:
        return False


def set_recent_report_pointer(report_path):
    """Persist <url path> of the report.html for the most recently processed
    document. No-op (False) when the path doesn't resolve to a real report."""
    if not _report_file_for_url(report_path):
        return False
    with _recent_report_lock:
        data = _read_recent_pointer_file()
        data['report_path'] = report_path
        data['updated_at'] = time.time()
        return _write_recent_pointer_file(data)


def record_recent_intake(image_path, label, kind='scan', facade=None,
                         conversation_id=None, dispatched_at=None,
                         content_sha256=None, archive_path=None,
                         already_seen_before=False):
    """Record an intake dispatch (scan or PDF) the moment Mazda is notified,
    so /recent_report.html can show the document even before — or without —
    any report.html existing for it. Called from process_scanned_document /
    process_pdf_document.

    `facade` is the deterministic classify+parse result (run_intake_facade),
    already computed at dispatch time for every doc — seeds doc_kind/vendor
    for the 'Document Type' field. It's frequently 'unknown' for scanned
    images (no extractable text), in which case merge_recent_intake_event
    overwrites it once Mazda reports her own vision classification back."""
    facade = facade or {}
    with _recent_report_lock:
        data = _read_recent_pointer_file()
        intake = {
            'document': os.path.basename(image_path or ''),
            'image_path': image_path or '',
            'label': label or '',
            'kind': kind,
            'dispatched_at': float(dispatched_at or time.time()),
            'expense_ids': [],
            'duplicate_expense_ids': [],
            'parsed': None,
            'stored': None,
            'doc_kind': facade.get('doc_kind'),
            'vendor': facade.get('vendor'),
            'conversation_id': conversation_id,
            'content_sha256': content_sha256 or '',
            'archive_path': archive_path or '',
            'already_seen_before': bool(already_seen_before),
            'status': 'processing',
            'status_detail': '',
        }
        data['intake'] = intake
        # Scans are ALSO recorded per-scanner (keyed by the scanner's human
        # name), so the Window Scanner / Freezer Scanner tabs keep showing each
        # scanner's own last document while both scanners run concurrently —
        # the shared 'intake' slot above only ever shows whichever dispatch
        # happened last.
        if kind == 'scan' and label:
            scanner_intakes = data.get('scanner_intakes')
            if not isinstance(scanner_intakes, dict):
                scanner_intakes = {}
            scanner_intakes[label] = dict(intake)
            data['scanner_intakes'] = scanner_intakes
        return _write_recent_pointer_file(data)


def _fold_event_into_intake(intake, event):
    """Fold one STEP 8 event's fields (expense ids + parsed/stored counts +
    doc_kind/vendor) into one intake record, in place."""
    ids = list(intake.get('expense_ids') or [])
    duplicate_ids = list(intake.get('duplicate_expense_ids') or [])
    # A corrected duplicate-only callback supersedes any earlier bad store
    # from the same isolated run. Keep only the canonical existing rows named
    # by the final callback instead of permanently unioning a deleted/bad ID
    # into the scanner view.
    try:
        duplicate_only = (int(event.get('stored')) == 0 and
                          bool(event.get('duplicate_expense_ids')))
    except (TypeError, ValueError):
        duplicate_only = False
    if duplicate_only:
        ids = []
        duplicate_ids = []
    # Duplicates matter as much as newly-stored rows here: a re-scan that
    # stores nothing still shows its transactions so they can be
    # recategorized before the next scan.
    for eid in (list(event.get('expense_ids') or [])
                + list(event.get('duplicate_expense_ids') or [])
                + [event.get('expense_id')]):
        try:
            eid = int(eid)
        except (TypeError, ValueError):
            continue
        if eid not in ids:
            ids.append(eid)
    intake['expense_ids'] = ids
    for eid in event.get('duplicate_expense_ids') or []:
        try:
            eid = int(eid)
        except (TypeError, ValueError):
            continue
        if eid not in duplicate_ids:
            duplicate_ids.append(eid)
    intake['duplicate_expense_ids'] = duplicate_ids
    for k in ('parsed', 'stored'):
        if event.get(k) is not None:
            try:
                intake[k] = int(event[k])
            except (TypeError, ValueError):
                pass
    # doc_kind/vendor: Mazda's own classification (STEP 8 payload) beats the
    # facade's dispatch-time guess (often 'unknown' for scanned images) —
    # accept either her doc_kind (statement/receipt/unknown, matching the
    # facade's vocabulary) or classify_scan.py's doc_type/merchant naming.
    doc_kind = event.get('doc_kind') or event.get('doc_type')
    if doc_kind and doc_kind != 'unknown':
        intake['doc_kind'] = doc_kind
    vendor = event.get('vendor') or event.get('merchant')
    if vendor and vendor != 'unknown':
        intake['vendor'] = vendor
    intake['reported_at'] = time.time()
    intake['status'] = (event.get('status') or 'complete').lower()
    if event.get('status_detail'):
        intake['status_detail'] = str(event['status_detail'])


def _event_document_path(event):
    """The source document an event refers to. document_path is explicit in
    the (extended) STEP 8 payload; receipt_url has always carried the scan
    image path for scanner intakes, so it doubles as a fallback for events
    from agents still using the older message template."""
    return (event.get('document_path') or event.get('receipt_url') or '').strip()


def merge_recent_intake_event(event):
    """Fold a STEP 8 /api/expense-stored event into every intake record it
    belongs to — the shared 'last processed document' record and/or the
    per-scanner records — so the Recent Report and per-scanner views can list
    the actual transactions once Mazda reports them.

    Routing: when the event names its source document (document_path /
    receipt_url) and that path matches stored intake(s), only those records
    are updated — this is what keeps two concurrently-running scanners from
    folding each other's results together. An event with no recognizable
    document path falls back to the previous behavior: it updates the current
    shared intake (and its per-scanner mirror, when they are the same
    dispatch)."""
    with _recent_report_lock:
        data = _read_recent_pointer_file()
        main = data.get('intake') if isinstance(data.get('intake'), dict) else None
        scanner_intakes = data.get('scanner_intakes')
        scanners = ([i for i in scanner_intakes.values() if isinstance(i, dict)]
                    if isinstance(scanner_intakes, dict) else [])
        path = _event_document_path(event)
        conversation_id = str(event.get('conversation_id') or '').strip()
        try:
            dispatched_at = float(event.get('dispatched_at') or 0)
        except (TypeError, ValueError):
            dispatched_at = 0.0
        candidates = ([main] if main else []) + scanners
        targets = []
        if conversation_id or dispatched_at:
            for intake in candidates:
                if conversation_id and intake.get('conversation_id') != conversation_id:
                    continue
                if dispatched_at:
                    try:
                        if abs(float(intake.get('dispatched_at') or 0) - dispatched_at) >= 2.0:
                            continue
                    except (TypeError, ValueError):
                        continue
                targets.append(intake)
            # An identified callback must never fall through to filename-only
            # routing: scanner files are reused, so a late prior-run callback
            # would otherwise overwrite the current dispatch.
            if not targets:
                return False
        else:
            targets = [i for i in candidates
                       if path and i.get('image_path') == path]
        if not targets:
            if not main:
                return False
            targets = [main]
            for si in scanners:
                if (si.get('image_path') == main.get('image_path')
                        and si.get('dispatched_at') == main.get('dispatched_at')):
                    targets.append(si)
        for intake in targets:
            _fold_event_into_intake(intake, event)
        return _write_recent_pointer_file(data)


_TERMINAL_INTAKE_STATUSES = {
    'pass', 'corrected', 'fail', 'stalled', 'complete',
    # Nothing more happens on THIS run once a human needs to pick a vendor —
    # stop the Recent Report page's 30s auto-refresh, same as any other
    # finished run (see list_pending_vendor_review()/set_receipt_vendor()).
    'awaiting_vendor_review',
}


def merge_recent_intake_status(update):
    """Apply a Trainer terminal status to the exact dispatched intake.

    Conversation id is the primary correlation key; document path plus dispatch
    timestamp is the compatibility fallback. Never update the merely-latest
    intake when no exact match exists, because Window and Freezer can overlap.
    """
    status = str(update.get('status') or '').strip().lower()
    if status not in _TERMINAL_INTAKE_STATUSES:
        return False
    conversation_id = str(update.get('conversation_id') or '').strip()
    document_path = _event_document_path(update)
    try:
        dispatched_at = float(update.get('dispatched_at') or 0)
    except (TypeError, ValueError):
        dispatched_at = 0.0
    with _recent_report_lock:
        data = _read_recent_pointer_file()
        main = data.get('intake') if isinstance(data.get('intake'), dict) else None
        scanner_intakes = data.get('scanner_intakes')
        scanners = ([i for i in scanner_intakes.values() if isinstance(i, dict)]
                    if isinstance(scanner_intakes, dict) else [])
        candidates = ([main] if main else []) + scanners
        targets = []
        for intake in candidates:
            if conversation_id and intake.get('conversation_id') == conversation_id:
                targets.append(intake)
                continue
            same_path = document_path and intake.get('image_path') == document_path
            try:
                same_dispatch = (dispatched_at and
                                 abs(float(intake.get('dispatched_at') or 0) -
                                     dispatched_at) < 2.0)
            except (TypeError, ValueError):
                same_dispatch = False
            if same_path and same_dispatch:
                targets.append(intake)
        if not targets:
            return False
        for intake in targets:
            intake['status'] = status
            intake['status_detail'] = str(update.get('detail') or '').strip()
            intake['trainer_report'] = str(update.get('report_path') or '').strip()
            intake['reported_at'] = time.time()
        return _write_recent_pointer_file(data)


def record_intake_status(data):
    """Dashboard endpoint used by the Trainer runner after writing its report."""
    merged = merge_recent_intake_status(data or {})
    return {'ok': merged, 'status': (data or {}).get('status', '')}


def _load_recent_report_pointer():
    data = _read_recent_pointer_file()
    rp = data.get('report_path')
    if not rp or not _report_file_for_url(rp):
        return None
    try:
        updated_at = float(data.get('updated_at') or 0)
    except (TypeError, ValueError):
        updated_at = 0.0
    return {'report_path': rp, 'updated_at': updated_at}


def resolve_recent_report():
    """The most recently processed document, as one of:
      {'mode': 'report', 'url', 'file'}   — a report.html to mirror, or
      {'mode': 'intake', 'intake': {...}} — a dispatch with no report.html
                                            (typical for scanned documents).
    Picks the newest among the explicit report pointer, the newest report.html
    mtime, and the last intake dispatch. Returns None when nothing exists."""
    candidates = []
    pointer = _load_recent_report_pointer()
    if pointer:
        candidates.append((pointer['updated_at'], 'report', pointer['report_path']))
    latest = _rol_finance_recent_reports(limit=1).get('latest')
    if latest:
        candidates.append((latest['mtime'], 'report', latest['url']))
    intake = _read_recent_pointer_file().get('intake')
    if isinstance(intake, dict) and intake.get('dispatched_at'):
        candidates.append((float(intake['dispatched_at']), 'intake', intake))
    for _ts, mode, payload in sorted(candidates, key=lambda c: c[0], reverse=True):
        if mode == 'intake':
            return {'mode': 'intake', 'intake': payload}
        fp = _report_file_for_url(payload)
        if fp:
            return {'mode': 'report', 'url': payload, 'file': fp}
    return None


def _fetch_expenses_by_ids(ids):
    """Rows for the synthetic recent-intake view — same shape as the Receipt
    Only rows so the shared picker markup drives them identically."""
    clean = []
    for i in ids or []:
        try:
            clean.append(int(i))
        except (TypeError, ValueError):
            continue
    clean = clean[:200]
    if not clean:
        return []
    placeholders = ','.join(['%s'] * len(clean))
    with _rol_get_connection() as cnx:
        with cnx.cursor() as cur:
            cur.execute('SELECT id, parent_id FROM categories')
            parent_of = {
                int(r['id']): (int(r['parent_id']) if r['parent_id'] is not None else None)
                for r in cur.fetchall()
            }
            cur.execute(
                "SELECT id, expense_date, amount, id_light, description, category_id, receipt_url "
                f"FROM expenses WHERE id IN ({placeholders}) "
                "ORDER BY expense_date, id",
                tuple(clean),
            )
            rows = cur.fetchall()
    out = []
    for r in rows:
        cid = r.get('category_id')
        rep = _reporting_category_for_id(
            int(cid) if cid is not None else None, parent_of)
        out.append({
            'id': int(r['id']),
            'date': str(r['expense_date']),
            'amount': str(r['amount']),
            'vendor_key': (r.get('id_light') or '').strip(),
            'description': (r.get('description') or '').strip(),
            'reporting_category': rep,
            'cat_class': REPORTING_CATEGORY_CLASS.get(rep, 'cat-uncategorized'),
            'receipt_url': (r.get('receipt_url') or '').strip(),
        })
    return out


def _associated_source_paths(rows):
    """Resolve the source PDF and receipt file backing a set of transactions
    (the rows shown on the synthetic Recent Report intake view).

    Reuses the same (date, amount) matching primitives the Set Category
    dialog's View Receipt button and recategorize's report-row search already
    use, rather than re-deriving document/transaction linkage from scratch:
      - _find_matching_report_row + _source_document_path locate the PDF/xlsx
        an existing report.html's row for the same (date, amount) traces back
        to — i.e. this transaction was originally imported from there.
      - _resolve_expense_receipt_path locates a receipt file on disk for a
        row that has a non-empty receipt_url.
    Returns (pdf_path or '', receipt_path or ''), stopping at the first row
    that yields each (rows of one intake are assumed to share one source doc).
    """
    pdf_path, receipt_path = '', ''
    for r in rows or []:
        if not pdf_path:
            match = _find_matching_report_row(
                r.get('date'), r.get('amount'), r.get('vendor_key'))
            if match:
                pdf_path = _source_document_path(match['report_path']) or ''
        if not receipt_path:
            ru = (r.get('receipt_url') or '').strip()
            if ru:
                receipt_path = _resolve_expense_receipt_path(
                    r.get('date'), r.get('amount'), ru) or ''
        if pdf_path and receipt_path:
            break
    return pdf_path, receipt_path


_DOC_KIND_LABELS = {
    'statement': 'Bank Statement',
    'bank_statement': 'Bank Statement',
    'receipt': 'Receipt',
    'tax_document': 'Tax Document',
    'invoice': 'Invoice (awaiting payment counterpart)',
}


def _document_type_label(doc_kind, vendor):
    """Human label for the 'Document Type' field, e.g. 'Chase Bank Statement'.

    doc_kind/vendor come from whichever document classifier ran (the
    deterministic facade's doc_kind/vendor for text-extractable PDFs, or
    Mazda's classify_scan.py vision result — doc_type/merchant — for scanned
    images, folded into the intake record by merge_recent_intake_event)."""
    kind_label = _DOC_KIND_LABELS.get((doc_kind or '').strip().lower())
    vendor = (vendor or '').strip()
    if vendor and vendor.lower() not in ('unknown', 'none'):
        vendor_label = vendor.replace('_', ' ').title()
        return f'{vendor_label} {kind_label}' if kind_label else vendor_label
    return kind_label or 'Unknown'


def _format_month_range(rows):
    """'May 30, 2025 >>---> June 23, 2025' from the earliest/latest expense_date
    among rows, or '--' when there's nothing to show a range for."""
    dates = sorted({r['date'] for r in (rows or []) if r.get('date')})
    if not dates:
        return '--'
    def _fmt(d):
        try:
            return datetime.strptime(d, '%Y-%m-%d').strftime('%B %-d, %Y')
        except ValueError:
            return d
    if len(dates) == 1 or dates[0] == dates[-1]:
        return _fmt(dates[0])
    return f'{_fmt(dates[0])} >>---> {_fmt(dates[-1])}'


def build_recent_intake_html(intake):
    """Synthetic recent-report page for an intake whose document has no
    report.html (the normal case for scanner scans — they store expenses in
    MySQL but never generate a report file). Mirrors the Receipt Only page:
    a #verified-transactions table of the intake's expenses with the same
    embedded category-picker dialog, so recategorize / view-receipt work
    exactly like on a real report."""
    from html import escape as _esc
    doc = intake.get('document') or 'document'
    label = intake.get('label') or ''
    dispatched_at = intake.get('dispatched_at')
    when = ''
    if dispatched_at:
        when = datetime.fromtimestamp(float(dispatched_at)).strftime('%Y-%m-%d %H:%M')
    reported = intake.get('reported_at')
    intake_status = str(intake.get('status') or 'processing').lower()
    status_detail = str(intake.get('status_detail') or '').strip()
    parsed = intake.get('parsed')
    stored = intake.get('stored')
    duplicate_ids = {
        int(i) for i in (intake.get('duplicate_expense_ids') or [])
        if str(i).isdigit()
    }

    rows, row_error = [], None
    try:
        rows = _fetch_expenses_by_ids(intake.get('expense_ids') or [])
    except Exception as exc:
        row_error = str(exc)

    doc_type_label = _document_type_label(intake.get('doc_kind'), intake.get('vendor'))
    month_range = _format_month_range(rows)
    pdf_path, receipt_path = _associated_source_paths(rows)
    if intake.get('kind') == 'pdf':
        # Rule 2: the currently-processed document IS the PDF — it's the
        # source regardless of what (date, amount) matching finds elsewhere.
        pdf_display = '<b>this.</b>'
    elif pdf_path:
        pdf_display = _esc(pdf_path)
    else:
        pdf_display = '--'
    receipt_display = _esc(receipt_path) if receipt_path else '--'

    if intake_status in ('fail', 'stalled'):
        label_text = 'FAILED' if intake_status == 'fail' else 'STALLED'
        status = f'Mazda Trainer reported {label_text}.'
        if status_detail:
            status += f' {status_detail}'
    elif rows:
        if stored == 0 and parsed:
            status = (f'Mazda parsed {parsed} transaction(s); all were already in the '
                      f'database from an earlier run of this document. The {len(rows)} '
                      'matching rows are shown below — click one to (re)categorize it.')
        else:
            status = (f'{len(rows)} transaction(s) recorded by this intake. '
                      'Click a row to set its category.')
    elif row_error:
        status = f'Could not load this intake’s transactions from the database: {row_error}'
    elif reported:
        if parsed and not stored:
            status = (f'Mazda parsed {parsed} transaction(s); all were already in the '
                      'database (duplicates of an earlier run of this document) — '
                      'nothing new was stored.')
        else:
            status = 'Mazda finished this intake without storing new transactions.'
    else:
        status = 'Dispatched to Mazda — processing… this page refreshes automatically.'

    picker_css, picker_html, click_css = '', '', ''
    try:
        picker_css, picker_html, click_css = _receipt_only_picker_assets()
    except Exception:
        pass  # picker unavailable → page still renders, rows just aren't clickable

    scanner_key = next((key for key, cfg in SCANNERS.items()
                        if cfg.get('name') == label), '')
    source_document_url = (
        f'{INTAKE_DOCUMENT_URL_PREFIX}?scanner={scanner_key}'
        if intake.get('kind') == 'scan' and scanner_key else '')
    trs = []
    for r in rows:
        row_id = r.get('id')
        is_duplicate = row_id in duplicate_ids or (stored == 0 and bool(parsed))
        duplicate_badge = (' <strong class="duplicate-badge">DUPLICATE</strong>'
                           if is_duplicate else '')
        trs.append(
            '<tr class="%s%s%s" data-expense-id="%s" '
            'data-source-document="%s" data-is-duplicate="%s" '
            'data-vendor-key="%s" data-description="%s" '
            'data-signed-amount="%s" data-date="%s" onclick="openCategoryPicker(this)" '
            'title="Click row to set category / view receipt">'
            '<td>%s</td><td class="number">%s</td><td>%s</td><td>%s</td></tr>' % (
                r['cat_class'], ' duplicate-row' if is_duplicate else '',
                ' has-receipt' if source_document_url else '',
                row_id or '',
                _esc(source_document_url, quote=True),
                'true' if is_duplicate else 'false',
                _esc(r['vendor_key'], quote=True),
                _esc(r['description'], quote=True),
                _esc(r['amount'], quote=True),
                _esc(r['date'], quote=True),
                _esc(r['description']) + duplicate_badge,
                _esc(r['amount']), _esc(r['date']),
                _esc(r['reporting_category']),
            ))
    table = ''
    if trs:
        table = (
            '  <h2>Verified Transactions</h2>\n'
            '  <table id="verified-transactions"><thead><tr>'
            '<th>Description</th><th class="number">Amount</th><th>Date</th>'
            '<th>Category</th></tr></thead><tbody>\n'
            + '\n'.join(trs) + '\n</tbody></table>\n')
    # Refresh while we're still waiting on Mazda's STEP 8 report-back.
    terminal = intake_status in _TERMINAL_INTAKE_STATUSES
    refresh = '' if (rows or reported or terminal) else '<meta http-equiv="refresh" content="30">'
    sub = f'{label} — ' if label else ''
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        + refresh +
        '<title>Recent Report</title><style>\n'
        '    body { font-family: Arial, sans-serif; margin:0; padding:20px; '
        'background:#f1f5f9; color:#0f172a; }\n'
        '    section.card { background:#fff; border-radius:12px; padding:18px 20px; '
        'margin:0 auto; max-width:1100px; box-shadow:0 1px 3px rgba(0,0,0,.08); }\n'
        '    h1 { font-size:1.4rem; margin:0 0 4px; } h2 { font-size:1.1rem; margin:18px 0 8px; }\n'
        '    table { width:100%; border-collapse:collapse; overflow:hidden; '
        'border-radius:12px; font-size:0.95rem; }\n'
        '    th, td { padding:8px 10px; border-bottom:1px solid #e5e7eb; text-align:left; }\n'
        '    th { background:#0f172a; color:#fff; }\n'
        '    th.number, td.number { text-align:right; }\n'
        '    .muted { color:#6b7280; }\n'
        '    .duplicate-row td { box-shadow:inset 0 2px #b91c1c,inset 0 -2px #b91c1c; }\n'
        '    .duplicate-badge { display:inline-block; margin-left:8px; padding:2px 7px; '
        'border-radius:999px; background:#b91c1c; color:#fff; font-size:.72rem; letter-spacing:.04em; }\n'
        + _receipt_only_cat_css() + '\n'
        + click_css + '\n'
        + picker_css + '\n'
        '  </style></head><body>\n'
        '<section class="card">\n'
        f'  <h1>Most Recent Document: {_esc(doc)}</h1>\n'
        f'  <p class="muted">{_esc(sub)}dispatched {_esc(when)}</p>\n'
        '  <p class="doc-meta">'
        f'Document Type: {_esc(doc_type_label)}<br>'
        f'Month Range: {_esc(month_range)}<br>'
        f'Associated PDF: {pdf_display}<br>'
        f'Associated Receipt: {receipt_display}</p>\n'
        f'  <p>{_esc(status)}</p>\n'
        + table +
        '</section>\n' + picker_html + '\n</body></html>')


def build_recent_report_html():
    """Body for GET /recent_report.html. Two shapes:
      - report mode: the current most-recent report.html with a <base href>
        injected so its relative assets keep resolving under the report's own
        /rol_finances_reports/... directory (the picker dialog posts to
        absolute /api/... URLs, so recategorize works unchanged), or
      - intake mode: a synthetic page for a dispatched document that has no
        report.html (see build_recent_intake_html)."""
    recent = resolve_recent_report()
    if not recent:
        return ('<!doctype html><meta charset="utf-8">'
                '<body style="font-family:sans-serif;padding:2em">'
                '<h2>Recent Report</h2>'
                '<p>No document has been processed yet. Scan or reprocess a '
                'document and this page will show its Verified Transactions.</p>')
    if recent.get('mode') == 'intake':
        return build_recent_intake_html(recent['intake'])
    with open(recent['file'], encoding='utf-8', errors='replace') as f:
        html = f.read()
    base_href = recent['url'].rsplit('/', 1)[0] + '/'
    base_tag = f'<base href="{base_href}">'
    m = re.search(r'<head[^>]*>', html, re.I)
    if m:
        return html[:m.end()] + base_tag + html[m.end():]
    return base_tag + html


def get_scanner_intake(scanner_key):
    """The last intake dispatched from one physical scanner ('window' /
    'freezer'), or None. Reads the per-scanner record written by
    record_recent_intake; falls back to the shared intake record for pointer
    files written before per-scanner records existed."""
    cfg = SCANNERS.get(scanner_key)
    if not cfg:
        return None
    name = cfg.get('name', scanner_key)
    data = _read_recent_pointer_file()
    scanner_intakes = data.get('scanner_intakes')
    if isinstance(scanner_intakes, dict):
        intake = scanner_intakes.get(name)
        if isinstance(intake, dict) and intake.get('dispatched_at'):
            return intake
    intake = data.get('intake')
    if (isinstance(intake, dict) and intake.get('kind') == 'scan'
            and intake.get('label') == name and intake.get('dispatched_at')):
        return intake
    return None


def build_scanner_report_html(scanner_key):
    """Body for GET /scanner_report.html?scanner=<key> — the Verified
    Transactions of the LAST document scanned on that specific scanner,
    regardless of what the other scanner (or a PDF reprocess) did since.
    Reuses the synthetic intake page so recategorize / view-receipt work
    identically to the Recent Report view."""
    cfg = SCANNERS.get(scanner_key)
    if not cfg:
        from html import escape as _esc
        return ('<!doctype html><meta charset="utf-8">'
                '<body style="font-family:sans-serif;padding:2em">'
                f'<h2>Unknown scanner: {_esc(str(scanner_key))}</h2>')
    intake = get_scanner_intake(scanner_key)
    if not intake:
        from html import escape as _esc
        name = _esc(cfg.get('name', scanner_key))
        return ('<!doctype html><meta charset="utf-8">'
                '<body style="font-family:sans-serif;padding:2em">'
                f'<h2>{name}</h2>'
                f'<p>No document has been scanned on the {name} yet. '
                'Scan a document and this page will show its Verified '
                'Transactions.</p>')
    return build_recent_intake_html(intake)


def scanner_intake_document_path(scanner_key):
    """Return the reviewable source image for one scanner's current report.

    Prefer the immutable staged path recorded with the intake. Fall back to the
    scanner's current output for legacy pointer records. Both paths are limited
    to scanner-owned directories so this endpoint cannot expose arbitrary files.
    """
    cfg = SCANNERS.get(scanner_key)
    if not cfg:
        return ''
    intake = get_scanner_intake(scanner_key) or {}
    candidates = [
        intake.get('image_path') or '',
        os.path.join(SCAN_TOOLS_DIR, cfg.get('output', '')),
    ]
    allowed = [os.path.abspath(SCAN_STAGING_REMOTE_DIR),
               os.path.abspath(SCAN_TOOLS_DIR)]
    for candidate in candidates:
        fp = os.path.abspath(candidate) if candidate else ''
        if not fp or not os.path.isfile(fp):
            continue
        try:
            if not any(os.path.commonpath([fp, root]) == root for root in allowed):
                continue
        except ValueError:
            continue
        if os.path.splitext(fp)[1].lower() in ('.jpg', '.jpeg', '.png', '.webp'):
            return fp
    return ''


def _resolve_report_path_alias(report_path):
    """The Recent Report view serves a real report.html at /recent_report.html,
    so the picker dialog injected in that report posts
    report_path='/recent_report.html' (it uses location.pathname). Translate
    the alias to the underlying report URL so row recolor, receipt lookup and
    reprocess hit the actual file on disk."""
    if report_path == RECENT_REPORT_PATH:
        recent = resolve_recent_report()
        if recent and recent.get('mode') == 'report':
            return recent['url']
        # Intake mode (or nothing yet): no report.html backs the page — return
        # '' so recategorize does its search-every-report / DB-only fallback,
        # exactly like the New Records dialog.
        return ''
    if report_path == SCANNER_REPORT_PATH:
        # Scanner reports are always synthetic DB-backed pages. There is no
        # report.html to recolor, so an empty path intentionally selects
        # recategorize_expense's search/static-row-or-DB-only success path.
        return ''
    return report_path


def _split_report_url(report_path):
    """Map '/rol_finances_reports/<month>/<rel>' -> (base_dir, rel), or None if
    malformed or the month key isn't recognized."""
    prefix = ROL_FINANCES_REPORTS_URL_PREFIX + '/'
    if not report_path or not report_path.startswith(prefix):
        return None
    month_key, sep, rel = report_path[len(prefix):].partition('/')
    if not sep or month_key not in ROL_FINANCES_REPORTS_MONTHS:
        return None
    return _rol_reports_base_dir(month_key), rel


def _report_file_for_url(report_path):
    """Map a /rol_finances_reports/<month>/<dir>/report.html URL path to its file on disk."""
    split = _split_report_url(report_path)
    if not split:
        return None
    base, rel = split
    fp = os.path.abspath(os.path.join(base, rel))
    base = os.path.abspath(base)
    if os.path.commonpath([fp, base]) == base and os.path.isfile(fp):
        return fp
    return None


def _iter_existing_report_files():
    """Yield (url, file_path, label) for every report.html that actually exists on
    disk, across every month x report-dir combination. Mirrors the nested loop in
    _rol_finance_recent_reports but returns file paths instead of status info."""
    for month_key in ROL_FINANCES_REPORTS_MONTHS:
        base_dir = _rol_reports_base_dir(month_key)
        for r in ROL_FINANCE_REPORTS:
            report_file = os.path.join(base_dir, r['dir'], 'report.html')
            if os.path.isfile(report_file):
                url = f'{ROL_FINANCES_REPORTS_URL_PREFIX}/{month_key}/{r["dir"]}/report.html'
                yield url, report_file, r['label']


def _find_matching_report_row(date_str, amount_str, vendor_key='', expense_id=None):
    """Search every existing report.html's Verified-Transactions rows for the one
    matching (date, amount) — used by recategorize_expense when it is called with
    no report_path (the New Records dialog's case: it only knows the DB row, not
    which static report.html — if any — already carries a <tr> for the same
    transaction). Report-file vendor_keys are parsed from the bank statement and
    often diverge from the DB's id_light-derived vendor_key (e.g. 'kum_go_2608r'
    vs 'kum_go_2608r_walker'), so vendor_key is NOT required to match — only used
    to disambiguate when more than one row shares the same date+amount.

    Returns {'report_path', 'label', 'row_vendor_key'} for exactly one match, or
    None when zero or unresolvably-many rows matched (leaves report files alone
    in the ambiguous case rather than guessing wrong).
    """
    d = (date_str or '').strip()
    a = (amount_str or '').strip()
    eid = str(expense_id or '').strip()
    if not eid and (not d or not a):
        return None
    matches = []
    for url, file_path, label in _iter_existing_report_files():
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
            matches.append({
                'report_path': url, 'label': label, 'row_vendor_key': vk_m.group(1),
            })
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1 and vendor_key:
        vk = vendor_key.strip()
        narrowed = [mch for mch in matches if mch['row_vendor_key'] and (
            vk.startswith(mch['row_vendor_key']) or mch['row_vendor_key'].startswith(vk))]
        if len(narrowed) == 1:
            return narrowed[0]
    return None


def _update_report_row_color(report_path, vendor_key, date_str, amount_str, new_cls,
                             expense_id=None):
    """Rewrite the cat-* class on the matching Verified-Transactions <tr> on disk.

    Identifies the row by data-vendor-key + the displayed date and amount cells, so
    the saved color is permanent across page refreshes. Returns True if a row changed.
    """
    import re as _re
    fp = _report_file_for_url(report_path)
    if not fp:
        return False
    with open(fp, encoding='utf-8') as f:
        html = f.read()

    vk = (vendor_key or '').strip()
    d = (date_str or '').strip()
    a = (amount_str or '').strip()
    eid = str(expense_id or '').strip()
    if not eid and not vk:
        return False

    def attempt(require_date, require_amount):
        """Rewrite the first vendor-matching row that also meets the given criteria."""
        state = {'done': False}

        def repl(m):
            open_tag, inner = m.group(1), m.group(2)
            if state['done']:
                return m.group(0)
            if eid:
                if ('data-expense-id="%s"' % eid) not in open_tag:
                    return m.group(0)
            else:
                if ('data-vendor-key="%s"' % vk) not in open_tag:
                    return m.group(0)
                if require_date and d and ('>%s<' % d) not in inner:
                    return m.group(0)
                if require_amount and a and ('>%s<' % a) not in inner:
                    return m.group(0)
            # Replace ALL cat-* classes in the class attribute so re-categorizing
            # a row doesn't leave stale old classes behind (or double-add when the
            # same category is picked twice).
            def _swap_cls(cm):
                parts = [p for p in cm.group(1).split()
                         if not _re.match(r'^cat-[a-z0-9-]+$', p)]
                return 'class="%s"' % ' '.join([new_cls] + parts)
            has_class_attr = 'class="' in open_tag
            new_open = _re.sub(r'class="([^"]*)"', _swap_cls, open_tag, count=1)
            if not has_class_attr:  # row had no class attribute at all
                new_open = open_tag + ' class="%s"' % new_cls
            state['done'] = True
            return '<tr%s>%s</tr>' % (new_open, inner)

        out = _re.sub(r'<tr([^>]*)>(.*?)</tr>', repl, html, flags=_re.S)
        return out if state['done'] else None

    attempts = ((False, False),) if eid else ((True, True), (True, False), (False, True))
    for require_date, require_amount in attempts:
        out = attempt(require_date, require_amount)
        if out is not None:
            with open(fp, 'w', encoding='utf-8') as f:
                f.write(out)
            return True
    return False


def _rol_get_connection():
    """get_connection() from the rol_finances receipt_parsing_tools tree."""
    import sys as _sys
    if RECEIPT_PARSING_TOOLS not in _sys.path:
        _sys.path.insert(0, RECEIPT_PARSING_TOOLS)
    from app.db import get_connection  # type: ignore
    return get_connection()


def _vendor_prefix(id_light):
    """Strip the trailing _MM_DD_YY_<amount> from an id_light to get its vendor part."""
    import re as _re
    return _re.sub(r'_\d{2}_\d{2}_\d{2}_\d+_\d+$', '', id_light or '')


def recategorize_expense(date_str, signed_amount, vendor_key, reporting_category,
                         description='', report_path='', expense_id=None):
    """Persist a user's category pick for one Verified-Transactions row.

    Uses expense_id when the row provides it. Legacy standalone report rows fall
    back to (expense_date, abs(amount)); LINE_ITEM rows must provide an ID because
    siblings can share both date and amount.
    """
    from decimal import Decimal, InvalidOperation
    if reporting_category not in REPORTING_CATEGORY_DB_MAP:
        return {'ok': False, 'error': f'Unknown category: {reporting_category}'}
    target_id = REPORTING_CATEGORY_DB_MAP[reporting_category]

    target_expense_id = None
    if expense_id not in (None, ''):
        try:
            target_expense_id = int(expense_id)
        except (TypeError, ValueError):
            return {'ok': False, 'error': f'Bad expense_id: {expense_id!r}'}
    amt = None
    if target_expense_id is None:
        raw_amt = str(signed_amount or '').replace('$', '').replace(',', '').strip()
        try:
            amt = abs(Decimal(raw_amt))
        except (InvalidOperation, ValueError):
            return {'ok': False, 'error': f'Bad amount: {signed_amount!r}'}

    try:
        with _rol_get_connection() as cnx:
            with cnx.cursor() as cur:
                def _find_expense(d):
                    if target_expense_id is not None:
                        cur.execute(
                            "SELECT id, id_light, description, category_id, expense_role "
                            "FROM expenses WHERE id=%s",
                            (target_expense_id,),
                        )
                        return cur.fetchall()
                    cur.execute(
                        "SELECT id, id_light, description, category_id, expense_role "
                        "FROM expenses WHERE expense_date=%s AND amount=%s "
                        "AND expense_role='STANDALONE'",
                        (d, str(amt)),
                    )
                    return cur.fetchall()

                rows = _find_expense(date_str)
                # Credit-card posting dates are often 1-3 days after the purchase
                # date stored in the DB. Try nearby dates when exact lookup fails.
                if not rows and target_expense_id is None:
                    try:
                        base = datetime.strptime(date_str, '%Y-%m-%d').date()
                        for delta in (-1, 1, -2, 2, -3, 3):
                            alt = (base + timedelta(days=delta)).isoformat()
                            rows = _find_expense(alt)
                            if rows:
                                break
                    except (ValueError, AttributeError):
                        pass
                if not rows:
                    if target_expense_id is not None:
                        return {'ok': False,
                                'error': f'Expense {target_expense_id} was not found.'}
                    # Transaction not in DB (e.g. annual summary never imported).
                    # Still persist the color in the HTML file so the pick survives
                    # a page refresh, and return ok so the dialog closes cleanly.
                    file_updated = False
                    if report_path and report_path != RECEIPT_ONLY_REPORT_PATH:
                        try:
                            new_cls = REPORTING_CATEGORY_CLASS.get(reporting_category)
                            if new_cls:
                                file_updated = _update_report_row_color(
                                    report_path, vendor_key, date_str,
                                    signed_amount, new_cls,
                                    expense_id=target_expense_id)
                        except Exception:
                            pass
                    return {'ok': True, 'expense_id': None,
                            'file_updated': file_updated,
                            'warning': 'Transaction not in DB — color saved to report only.'}

                if len(rows) == 1:
                    chosen = rows[0]
                else:
                    chosen = None
                    vk = (vendor_key or '').strip()
                    for r in rows:
                        vp = _vendor_prefix(r.get('id_light'))
                        if vk and vp and (vk.startswith(vp) or vp.startswith(vk)):
                            chosen = r
                            break
                    if chosen is None and description:
                        for r in rows:
                            if (r.get('description') or '').strip() == description.strip():
                                chosen = r
                                break
                    if chosen is None:
                        return {'ok': False,
                                'error': f'{len(rows)} expenses share that date/amount; '
                                         'could not pinpoint which one.'}

                if chosen.get('expense_role') == 'PARENT':
                    return {'ok': False,
                            'error': 'A PARENT is a reconciliation anchor and cannot be categorized.'}

                cur.execute("UPDATE expenses SET category_id=%s WHERE id=%s",
                            (target_id, chosen['id']))
    except Exception as e:
        return {'ok': False, 'error': f'DB error: {e}'}

    # Persist the color into the static report.html so it survives a refresh.
    file_updated = False
    matched_report = None
    if report_path == RECEIPT_ONLY_REPORT_PATH:
        # The Receipt Only tab is a dynamic page rebuilt from the DB on every
        # load — the DB write above is the whole change.
        file_updated = True
    elif not report_path:
        # The New Records dialog doesn't know which report.html (if any) this
        # transaction lives in — search for it instead of assuming there is none
        # (see _find_matching_report_row: DB vs. bank-statement vendor_key spelling
        # often diverges, so a plain report_path lookup can't be done client-side).
        try:
            new_cls = REPORTING_CATEGORY_CLASS.get(reporting_category)
            report_expense_id = (
                chosen['id'] if chosen.get('expense_role') == 'LINE_ITEM' else None)
            found = _find_matching_report_row(
                date_str, signed_amount, vendor_key, report_expense_id) if new_cls else None
            if found:
                if _update_report_row_color(
                        found['report_path'], found['row_vendor_key'],
                        date_str, signed_amount, new_cls,
                        expense_id=report_expense_id):
                    file_updated = True
                    matched_report = {'report_path': found['report_path'], 'label': found['label']}
        except Exception:
            pass
        if not matched_report:
            # Genuinely no static row anywhere (e.g. a standalone receipt with no
            # matching bank transaction) — the DB write above is the whole change.
            file_updated = True
    else:
        try:
            new_cls = REPORTING_CATEGORY_CLASS.get(reporting_category)
            if new_cls:
                # Match the file by the RAW displayed amount the client sent (e.g. "-$150.00",
                # "+$10.00", "296.41") — NOT the normalized abs value used for the DB lookup,
                # which would only match plain rows like "10.25".
                file_updated = _update_report_row_color(
                    report_path, vendor_key, date_str, signed_amount, new_cls,
                    expense_id=(chosen['id']
                                if chosen.get('expense_role') == 'LINE_ITEM'
                                else None))
        except Exception:
            file_updated = False

    return {
        'ok': True,
        'expense_id': chosen['id'],
        'previous_category_id': chosen.get('category_id'),
        'category_id': target_id,
        'reporting_category': reporting_category,
        'file_updated': file_updated,
        'matched_report': matched_report,
    }


# ── Vendor review: pick a vendor_key for a receipt that saved with no category ─
# Companion to the FAIL-CLOSED CATEGORY RULE in build_mazda_scan_message(): when
# Mazda can't resolve a vendor/category, parse_and_categorize.py now still saves
# the receipt image + an expense row with category_id=NULL,
# expense_status='NEEDS_VENDOR_KEY' (see save_receipt_pending_vendor_review() in
# rol_finances) instead of dropping the document. These three functions back the
# dashboard's "pick a vendor" dialog that finishes the save later.
CATEGORIZER_LIB_DIR = os.path.expanduser('~/rol_finances/tools/categorizer/python_libary')


def _vendor_category_lookup():
    import sys as _sys
    if CATEGORIZER_LIB_DIR not in _sys.path:
        _sys.path.insert(0, CATEGORIZER_LIB_DIR)
    from vendor_category_lookup import VendorCategoryLookup  # type: ignore
    return VendorCategoryLookup()


def list_vendor_keys():
    """Every known vendor_key + category, for the "pick a vendor" dialog."""
    try:
        return {'ok': True, 'vendor_keys': _vendor_category_lookup().list_vendor_keys()}
    except Exception as e:
        return {'ok': False, 'error': f'Could not load vendor_category.yaml: {e}', 'vendor_keys': []}


def list_pending_vendor_review():
    """Expenses saved with no category (expense_status=NEEDS_VENDOR_KEY)."""
    try:
        with _rol_get_connection() as cnx:
            with cnx.cursor() as cur:
                cur.execute(
                    "SELECT id, expense_date, amount, description, receipt_url, source_file "
                    "FROM expenses WHERE expense_status='NEEDS_VENDOR_KEY' "
                    "ORDER BY expense_date DESC"
                )
                rows = cur.fetchall()
    except Exception as e:
        return {'ok': False, 'error': f'DB error: {e}', 'rows': []}

    out = []
    for r in rows:
        image_url = None
        source_file = r.get('source_file')
        if source_file and os.path.isfile(source_file):
            try:
                image_url = _receipt_url_for_path(source_file)
            except Exception:
                image_url = None
        out.append({
            'expense_id': r['id'],
            'expense_date': str(r.get('expense_date') or ''),
            'amount': str(r.get('amount') or ''),
            'description': r.get('description') or '',
            'receipt_url': r.get('receipt_url') or '',
            'image_url': image_url,
        })
    return {'ok': True, 'rows': out}


def set_receipt_vendor(expense_id, vendor_key):
    """Resolve a human-picked vendor_key to a category_id and finish the save."""
    try:
        expense_id = int(expense_id)
    except (TypeError, ValueError):
        return {'ok': False, 'error': f'Bad expense_id: {expense_id!r}'}
    vendor_key = (vendor_key or '').strip()
    if not vendor_key:
        return {'ok': False, 'error': 'vendor_key is required'}

    try:
        category_id = _vendor_category_lookup().get_category_id(vendor_key)
    except Exception as e:
        return {'ok': False, 'error': f'Could not load vendor_category.yaml: {e}'}
    if category_id is None:
        return {'ok': False, 'error': f'Unknown vendor_key: {vendor_key}'}

    try:
        with _rol_get_connection() as cnx:
            with cnx.cursor() as cur:
                cur.execute(
                    "UPDATE expenses SET category_id=%s, expense_status='NONE' WHERE id=%s",
                    (category_id, expense_id),
                )
    except Exception as e:
        return {'ok': False, 'error': f'DB error: {e}'}

    return {'ok': True, 'expense_id': expense_id, 'category_id': category_id}


# ── ROL Finance: open the stored receipt for a Verified-Transactions row ──────
# The "View Receipt" button in the category-picker dialog POSTs to
# /api/receipt-lookup; we match the same expenses row recategorize_expense does,
# read its receipt_url, resolve it to a file on disk, and return a dashboard URL
# (served by the /rol_finances_receipts/ GET route) that the dialog window.open()s.
READABLE_DOCS_BASE = os.path.expanduser('~/rol_finances/readable_documents')
RECEIPTS_SUBTREE = os.path.join(READABLE_DOCS_BASE, 'receipts')
ROL_FINANCES_RECEIPTS_URL_PREFIX = '/rol_finances_receipts'

# Receipt files live in MORE THAN ONE tree. The historical tree is
# readable_documents/receipts, but the live intake pipeline
# (receipt_parsing_tools/parse_and_categorize.py save_receipt_non_interactive)
# moves freshly-stored receipts to a separate Windows-side store
# (RECEIPT_STORAGE_ROOT there). If we only index readable_documents, every receipt
# the live pipeline stores is invisible to /api/receipts-present (no red marker)
# and to View Receipt. So we index a LIST of roots and serve from a LIST of mounts.
#
# Each mount is (url_prefix, serve_base, index_subtree):
#   - url_prefix   : the dashboard URL namespace the file is served under
#   - serve_base   : path-traversal root for the GET handler
#   - index_subtree: the directory _build_receipt_index walks for receipt files
# For the canonical mount serve_base (readable_documents) differs from the subtree
# (readable_documents/receipts) because baked URLs are relative to readable_documents
# and therefore carry a leading 'receipts/' segment. For the external store the two
# are the same directory. Override/extend the external root with ROL_RECEIPTS_EXTRA_ROOT.
ROL_FINANCES_RECEIPTS_EXT_URL_PREFIX = '/rol_finances_receipts_ext'
ROL_RECEIPTS_EXTRA_ROOT = os.environ.get(
    'ROL_RECEIPTS_EXTRA_ROOT',
    '/mnt/c/Users/NewUser/Documents/rol_finances/receipts')


def _build_receipt_mounts():
    mounts = [(ROL_FINANCES_RECEIPTS_URL_PREFIX, READABLE_DOCS_BASE, RECEIPTS_SUBTREE)]
    extra = os.path.abspath(ROL_RECEIPTS_EXTRA_ROOT)
    # Only add the external store if it exists AND is not already inside the
    # canonical tree (avoids double-indexing when both point at the same place).
    if (os.path.isdir(extra)
            and os.path.commonpath([extra, os.path.abspath(RECEIPTS_SUBTREE)])
            != os.path.abspath(RECEIPTS_SUBTREE)):
        mounts.append((ROL_FINANCES_RECEIPTS_EXT_URL_PREFIX, extra, extra))
    return mounts


RECEIPT_MOUNTS = _build_receipt_mounts()

# Receipt files are named <vendor>_MM_DD_YY_<dollars>_<cents>.<ext> and filed under
# readable_documents/receipts/** (the tree is kept in sync across the Win11 box and
# mom's machine, so it is fully present locally). The (date, amount) embedded in the
# filename is a far more reliable link to a Verified-Transactions row than the DB's
# receipt_url string (which often differs by extension or vendor spelling). We index
# the tree by that key (cached briefly); both /api/receipt-lookup and the row-marker
# endpoint /api/receipts-present resolve receipts through it.
_RECEIPT_INDEX_CACHE = {'ts': 0.0, 'by_da': None, 'by_stem': None}
_RECEIPT_INDEX_TTL = 300


def _invalidate_receipt_index():
    """Force the next _receipt_index() to rebuild from disk. Called after an intake
    stores a new receipt so its marker/Receipt-Only row appears immediately instead
    of after the 300s TTL — the crux of 'update visible views without a manual refresh'."""
    _RECEIPT_INDEX_CACHE.update(ts=0.0, by_da=None, by_stem=None)


# ── Physical document scanners ──────────────────────────────────────────────
# Two HP scanners attached to this (Win11) box. Both are driven by the shared,
# parameterized scan_device.ps1, which selects the target by NAME (`-NameLike`) —
# NOT "first device found". That distinction matters: WIA enumeration order is
# unstable (the busy Freezer often enumerates first), so the old first-device
# script kept grabbing the wrong scanner. The Freezer (HP063E28) is the non-default
# device and is notorious for "WIA device is busy" until power-cycled.
SCAN_TOOLS_DIR = os.path.expanduser(
    '~/planner/nonprofit_finance_db/receipt_scanning_tools')
SCANNER_IMAGE_URL_PREFIX = '/api/scanner-image'
INTAKE_DOCUMENT_URL_PREFIX = '/api/intake-document'
SCANNERS = {
    'window': {
        'name': 'Window Scanner',
        'device': 'HPI297BEA (HP OfficeJet 8120e series)',
        'script': 'run_scan_window.sh',   # selects HPI297BEA by name
        'output': 'scan.jpg',
    },
    'freezer': {
        'name': 'Freezer Scanner',
        'device': 'HP063E28 (HP DeskJet 4100 series)',
        'script': 'run_scan_freezer.sh',  # selects HP063E28 by name (non-default)
        'output': 'scan_freezer.jpg',
    },
}

# The scanner dialogs also expose a repair for the HP DeskJet's Windows print
# queue. Its old link-local IPv6 port becomes stale after printer/router
# restarts; the printer itself remains reachable on this IPv4 RAW port.
DESKJET_PRINTER_NAME = 'HP063E28 (HP DeskJet 4100 series)'
DESKJET_PRINTER_IP = '10.0.0.243'
DESKJET_PRINTER_PORT = 'IP_10.0.0.243'
_WINDOWS_POWERSHELL = (
    '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe')


def fix_deskjet_printer(runner=subprocess.run):
    """Repair the DeskJet queue through Windows PowerShell.

    This is the same safe repair as the Desktop helper: verify the printer's
    RAW service, create its IPv4 port if needed, bind the existing HP queue to
    that port, and refresh the spooler. Never installs/removes a driver or
    deletes queued jobs.
    """
    interop = _wsl_interop_socket()
    if not interop:
        return {
            'ok': False,
            'text': ('Printer repair needs Windows access. Open a WSL window '
                     'and try Fix Printer again.'),
        }

    script = f"""
$ErrorActionPreference = 'Stop'
$printerName = '{DESKJET_PRINTER_NAME}'
$printerIp = '{DESKJET_PRINTER_IP}'
$portName = '{DESKJET_PRINTER_PORT}'
if (-not (Test-NetConnection -ComputerName $printerIp -Port 9100 -InformationLevel Quiet -WarningAction SilentlyContinue)) {{
    throw "The printer is not reachable at $printerIp. Make sure it is powered on and connected to Wi-Fi."
}}
if (-not (Get-Printer -Name $printerName -ErrorAction SilentlyContinue)) {{
    throw "The HP DeskJet 4100 Windows queue was not found."
}}
if (-not (Get-PrinterPort -Name $portName -ErrorAction SilentlyContinue)) {{
    Add-PrinterPort -Name $portName -PrinterHostAddress $printerIp -PortNumber 9100
}}
Set-Printer -Name $printerName -PortName $portName
try {{
    Restart-Service Spooler -Force
}} catch {{
    # The dashboard's Windows token can update this per-user queue but may not
    # be elevated enough to control the system service. The port switch is the
    # actual repair; let Windows refresh status through the new port normally.
}}
Start-Sleep -Seconds 2
$printer = Get-Printer -Name $printerName
[ordered]@{{
    ok = ([string]$printer.PrinterStatus -eq 'Normal')
    status = [string]$printer.PrinterStatus
    port = [string]$printer.PortName
}} | ConvertTo-Json -Compress
"""
    env = os.environ.copy()
    env['WSL_INTEROP'] = interop
    try:
        proc = runner(
            [_WINDOWS_POWERSHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass',
             '-Command', script],
            capture_output=True, text=True, timeout=35, env=env,
        )
    except subprocess.TimeoutExpired:
        return {'ok': False, 'text': 'Printer repair timed out.'}
    except Exception as exc:  # noqa: BLE001 — surface the actionable failure
        return {'ok': False, 'text': f'Could not start printer repair: {exc}'}

    output = (proc.stdout or '').strip()
    if proc.returncode != 0:
        error = (proc.stderr or output or 'Windows printer repair failed.').strip()
        return {'ok': False, 'text': error[:500]}
    try:
        payload = json.loads(output.splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {
            'ok': False,
            'text': f'Windows returned an unreadable printer status: {output[:300]}',
        }
    status = payload.get('status') or 'Unknown'
    ok = payload.get('ok') is not False
    return {
        'ok': ok,
        'text': (f'Printer fixed. Windows status: {status}.' if ok else
                 f'The port was repaired, but Windows status is still {status}.'),
        'status': status,
        'port': payload.get('port') or DESKJET_PRINTER_PORT,
    }

# Serialize all device access: two concurrent WIA transfers self-induce the very
# "device is busy" error we are trying to detect. Both the manual scan and the
# Freezer's 5s status poll go through this lock.
_SCAN_LOCK = threading.Lock()
# A real flatbed scan (OfficeJet, 300dpi) takes ~33s; allow headroom but cap it
# so a hung WIA call doesn't tie up the lock indefinitely.
SCAN_TIMEOUT_SEC = 90


def _reap_stale_scans(scan_env):
    """Kill leaked scan_device.ps1 Windows processes (see _invoke_scanner)."""
    reaper = os.path.join(SCAN_TOOLS_DIR, 'reap_scans.ps1')
    if not os.path.isfile(reaper):
        return
    try:
        subprocess.run(
            ['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
             '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', './reap_scans.ps1'],
            cwd=SCAN_TOOLS_DIR, capture_output=True, text=True, timeout=20,
            env=scan_env,
        )
    except Exception:  # noqa: BLE001 — reaping is best-effort
        pass


_INTEROP_CACHE = {'sock': None}
_WIN_CMD_EXE = '/mnt/c/Windows/System32/cmd.exe'


def _interop_works(sock):
    """True if WSL_INTEROP=sock can actually launch a Windows .exe.

    The /init binfmt interpreter fails with "Invalid argument" (non-zero exit)
    when the socket doesn't relay to the Windows side, so a trivial `cmd.exe /c
    exit` is a reliable, fast probe.
    """
    try:
        r = subprocess.run(
            [_WIN_CMD_EXE, '/c', 'exit'],
            env={'PATH': '/usr/bin:/bin', 'WSL_INTEROP': sock},
            capture_output=True, timeout=8,
        )
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def _wsl_interop_socket():
    """Return a working WSL_INTEROP socket path, or None.

    The scan script launches Windows `powershell.exe`, which needs a live
    `WSL_INTEROP` relay socket. The dashboard runs as a systemd --user service
    started at boot and inherits no such socket, so powershell.exe fails with
    "Invalid argument". Crucially the /init socket (1_interop/2_interop) does NOT
    relay to Windows — only the per-interactive-session `<pid>_interop` sockets
    do — so we probe candidates (newest first) and cache the first that works.
    Limitation: at least one interactive WSL session must be alive to provide a
    relay; with none open there is no socket the service can borrow.
    """
    cached = _INTEROP_CACHE.get('sock')
    if cached and os.path.exists(cached) and _interop_works(cached):
        return cached
    wsl_run = '/run/WSL'
    cands = []
    try:
        for name in os.listdir(wsl_run):
            if not name.endswith('_interop'):
                continue
            fp = os.path.join(wsl_run, name)
            # Skip the 1_interop symlink and the init socket — they don't relay.
            if os.path.islink(fp) or not os.path.exists(fp):
                continue
            try:
                cands.append((os.path.getmtime(fp), fp))
            except OSError:
                continue
    except OSError:
        return None
    cands.sort(reverse=True)
    for _, fp in cands:
        if _interop_works(fp):
            _INTEROP_CACHE['sock'] = fp
            return fp
    return None


def classify_scan_result(returncode, log, image_exists):
    """Pure classifier for a scan script's outcome → {status, error?, log}.

    Markers emitted by scan_device.ps1: SCANNER_BUSY (also "device is busy"),
    SCANNER_OFFLINE (also "not found"). A clean exit with the image on disk is
    `ready`. Kept pure (no I/O) so it's unit-testable.
    """
    low = (log or '').lower()
    if returncode == 0 and image_exists:
        return {'status': 'ready', 'log': log}
    if 'scanner_busy' in low or 'device is busy' in low:
        return {'status': 'busy', 'error': 'The WIA device is busy.', 'log': log}
    if 'scanner_offline' in low or 'not found' in low:
        return {'status': 'offline',
                'error': 'Scanner not found (powered off or disconnected).',
                'log': log}
    return {'status': 'error',
            'error': log or f'Scan failed (exit {returncode})', 'log': log}


def _invoke_scanner(key):
    """Run a scanner's script and classify the outcome.

    Returns {status, ...} where status is one of:
      ready          — transfer succeeded, scan image written (includes image_url)
      busy           — WIA device busy (needs power-cycle); reported FAST (no scan)
      offline        — named device not enumerated (powered off / disconnected)
      not_configured — no script wired for this scanner
      error          — anything else (interop missing, timeout, script error)

    The same call backs both the manual scan (POST /api/scanner-scan) and the
    Freezer's 5s status poll (GET /api/scanner-status). Because "busy" errors at
    Transfer return immediately, polling does NOT repeatedly run the scanner — a
    real scan (~33s on the OfficeJet at 300dpi) only happens on the one poll where
    the device has recovered. Blocking; ReusableHTTPServer is threaded so the
    dashboard's other pollers are unaffected, and `_SCAN_LOCK` keeps two transfers
    from colliding (concurrent transfers self-induce the "busy" error).

    Critically, every scan is preceded by `_reap_stale_scans()`: on a Python
    timeout we can only kill the bash wrapper, not the Windows powershell.exe it
    launched via interop, so a hung scan leaks a Windows process that keeps the
    device busy and — if they pile up — wedges the whole WIA service (stisvc).
    Reaping under the lock (where no scan of ours is legitimately running) caps
    leaks at zero before each attempt.
    """
    cfg = SCANNERS.get(key)
    if not cfg:
        return {'status': 'error', 'error': f'Unknown scanner: {key}'}
    if not cfg.get('script'):
        return {'status': 'not_configured',
                'error': f"{cfg['name']} ({cfg['device']}) is not wired up yet."}
    script_path = os.path.join(SCAN_TOOLS_DIR, cfg['script'])
    if not os.path.isfile(script_path):
        return {'status': 'error',
                'error': f'Scanner script not found: {script_path}'}
    interop = _wsl_interop_socket()
    if not interop:
        return {'status': 'error',
                'error': 'No usable WSL interop socket — open a WSL session so the '
                         'service can launch the scanner.'}
    scan_env = os.environ.copy()
    scan_env['WSL_INTEROP'] = interop
    with _SCAN_LOCK:
        _reap_stale_scans(scan_env)
        try:
            proc = subprocess.run(
                ['bash', cfg['script']],
                cwd=SCAN_TOOLS_DIR,
                capture_output=True, text=True, timeout=SCAN_TIMEOUT_SEC,
                env=scan_env,
            )
        except subprocess.TimeoutExpired:
            # The bash wrapper is dead, but the Windows powershell.exe is not —
            # reap it so its WIA handle can't wedge the device/service.
            _reap_stale_scans(scan_env)
            return {'status': 'error',
                    'error': f'Scan timed out after {SCAN_TIMEOUT_SEC}s '
                             '(scanner not responding).'}
        except Exception as exc:  # noqa: BLE001 — surface launch failures to the UI
            return {'status': 'error', 'error': f'Failed to start scan: {exc}'}
    log = ((proc.stdout or '') + (proc.stderr or '')).strip()
    img = os.path.join(SCAN_TOOLS_DIR, cfg['output'])
    result = classify_scan_result(proc.returncode, log, os.path.isfile(img))
    if result['status'] == 'ready':
        # Cache-bust so the browser reloads the freshly scanned image each time.
        result['image_url'] = (
            f'{SCANNER_IMAGE_URL_PREFIX}?scanner={key}&t={int(time.time())}')
    return result


MAZDA_AGENT_ID = 'agent-6b536cf4-ec88-4290-b595-fed21d14bd8e'


# Venv python + PYTHONPATH for rol_finances scripts.
#
# Two regressions, two rules, both mandatory on every command we hand Mazda:
#  1. ModuleNotFoundError: No module named 'tools' — Python does not add the cwd
#     to sys.path for a `script.py` invocation, so rol_finances scripts that do
#     `import tools...` need PYTHONPATH=/home/adamsl/rol_finances. (2026-06-28)
#  2. "Command not in allowlist: PYTHONPATH=..." — the executor only strips an
#     inline `PYTHONPATH=...` prefix when the command also contains a shell
#     operator (&&, |, >). A *bare* command (STEP 0 classify) goes straight to
#     the allowlist check with `PYTHONPATH=...` as cmd[0] and is rejected.
#     (2026-06-29 intake run, trace 53.)
# Fix for BOTH: never inline the prefix. Use the full venv python path as the
# executable (it is in the executor allowlist) and pass PYTHONPATH through
# executor_run's own `env` argument, which is applied to the child regardless of
# whether the command takes the shell path. Verified live against pid 1041:8787.
MAZDA_RF_VENV_PY = '/home/adamsl/rol_finances/.venv/bin/python3'
MAZDA_RF_ENV_JSON = '{"PYTHONPATH": "/home/adamsl/rol_finances"}'


def mazda_facade_identified(facade_result):
    """Pure predicate: did the deterministic facade actually identify the doc?

    A facade run that merely exits 0 is NOT enough — for JPEG scans the
    text-extraction router returns ``ok: true`` but ``doc_kind: unknown``,
    ``confidence: 0``, ``recommended_action: reject``. Treating that as success
    is the bug that sent Mazda into investigate/categorize with empty data.
    Only return True when the facade produced a usable classification.
    """
    fr = facade_result or {}
    try:
        confidence = float(fr.get('confidence') or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return bool(
        fr.get('ok')
        and (fr.get('doc_kind') or 'unknown') != 'unknown'
        and fr.get('recommended_action') != 'reject'
        and confidence > 0
    )


def build_mazda_scan_message(scan_image_path, scanner_name, facade_result=None,
                             conversation_id=None, dispatched_at=None):
    """Pure builder for the intake instruction Mazda receives after a scan.

    No I/O — returns the message string so it can be unit-tested. Encodes the
    full investigate → categorize → store → record → judge → propose pipeline,
    and adapts the front half to whether the facade actually identified the
    document (see mazda_facade_identified).
    """
    fr = facade_result or {}
    doc_kind = fr.get('doc_kind', 'unknown')
    vendor = fr.get('vendor') or 'unknown'
    parsed = fr.get('parsed') or {}
    confidence = fr.get('confidence') or 0.0
    identified = mazda_facade_identified(fr)

    # Summarise the most useful parsed fields so the message stays readable.
    parsed_summary = json.dumps(
        {k: parsed[k] for k in ('transaction_date', 'total_amount', 'merchant_name',
                                 'description', 'payment_method') if k in parsed},
        default=str,
    )
    if identified:
        facade_block = (
            f'\n\nThe deterministic facade (classify + parse) ran and IDENTIFIED this document. '
            f'Do NOT re-run classify or parse — use these results directly:\n'
            f'  doc_kind: {doc_kind}\n'
            f'  vendor_key: {vendor}\n'
            f'  routing_key: {fr.get("routing_key")}\n'
            f'  confidence: {confidence} '
            f'(recommended_action: {fr.get("recommended_action")})\n'
            f'  parsed: {parsed_summary}'
        )
        fallback_block = ''
        if doc_kind in ('statement', 'bank_statement'):
            return (
                f'A bank or credit-card statement was scanned on the {scanner_name}. '
                f'The image is: {scan_image_path}\n'
                f'The deterministic vision facade already classified it as statement '
                f'(confidence={confidence}, vendor={vendor}). Do not classify it again.\n\n'
                f'This is a STATEMENT-ONLY intake. Receipt/invoice investigation, '
                f'categorization, and all single-document parsing/storage are forbidden '
                f'and intentionally omitted from this dispatch.\n\n'
                f'1. Call load_wrapper_revision(agent_name="Mazda").\n'
                f'2. Via executor_run with cwd=/home/adamsl/rol_finances and '
                f'env={MAZDA_RF_ENV_JSON}, run:\n'
                f'   {MAZDA_RF_VENV_PY} '
                f'tools/receipt_scanning_tools/parse_statement_scan.py '
                f'{scan_image_path}\n'
                f'3. Write that returned JSON to /tmp/mazda_statement.json, then via '
                f'executor_run with the same cwd/env run:\n'
                f'   {MAZDA_RF_VENV_PY} '
                f'tools/receipt_scanning_tools/store_statement_transactions.py '
                f'-f /tmp/mazda_statement.json --source-file {scan_image_path}\n'
                f'4. Call record_trace(agent_name="Mazda", task_name="document-intake", '
                f'input_text="{scan_image_path}", agent_output=<JSON containing '
                f'document_path, doc_kind="statement", classification_confidence, '
                f'duplicate_checked=true, transactions_parsed, transactions_stored, '
                f'transactions_duplicate, transactions_skipped_credits, deposits_stored, '
                f'and problems>).\n'
                f'5. Call judge_trace(trace_id) always. On FAIL call propose_improvement '
                f'and apply_proposal.\n'
                f'6. Always notify the dashboard via executor_run with curl POST '
                f'http://localhost:8765/api/expense-stored. The JSON must contain all '
                f'expense_ids and duplicate_expense_ids from step 3, parsed/stored counts, '
                f'doc_kind="statement", vendor="{vendor}", '
                f'document_path="{scan_image_path}", '
                f'conversation_id="{conversation_id or ""}", and '
                f'dispatched_at={float(dispatched_at or 0)}.\n'
                f'Do not stop before steps 4-6 even when every transaction is a duplicate.'
            )
    else:
        # Facade did not identify the doc (doc_kind=unknown, confidence=0, or crashed).
        # This is NORMAL for JPEG receipt scans — the facade uses text extraction which
        # fails for images. Tell Mazda to use the vision-capable tools directly.
        err = fr.get('error', '') if fr else ''
        note = (f'error: {err}' if err
                else f'returned doc_kind={doc_kind!r}, confidence={confidence}')
        facade_block = (
            f'\n\nThe facade could not identify this document ({note}). '
            f'This is expected for JPEG scans — the facade uses text extraction, not vision.'
        )
        fallback_block = (
            f'\nSTEP 0 — CLASSIFY + PARSE YOURSELF (facade returned doc_kind=unknown). '
            f'executor_run, cwd=/home/adamsl/rol_finances, env={MAZDA_RF_ENV_JSON}:\n'
            f'  HARD ROUTING BARRIER: run classification as its OWN executor_run call. '
            f'Never chain the classifier to a parser or store command with `&&`, `;`, or '
            f'any other shell operator. Read `doc_type` before choosing the next command.\n'
            f'  a. Classify ONLY (Gemini vision):\n'
            f'     {MAZDA_RF_VENV_PY} tools/classify_scan.py '
            f'{scan_image_path}\n'
            f'     → {{"doc_type": "receipt"|"invoice"|"statement"|"tax_document"|"other", '
            f'"confidence": 0-1, "reason": "..."}}\n'
            f'  If doc_type is `bank_statement` or `statement`, STOP STEP 0 HERE and '
            f'jump directly to STATEMENT BRANCH S1. Running receipt parser/store commands '
            f'on a statement is forbidden.\n'
            f'  b. ONLY for receipt OR invoice, parse in a NEW executor_run call:\n'
            f'     {MAZDA_RF_VENV_PY} '
            f'tools/receipt_scanning_tools/receipt_parsing_tools/parse_and_categorize.py '
            f'-f {scan_image_path} --json --engine=gemini\n'
            f'     → JSON with merchant_name, transaction_date, total_amount, etc.\n'
            f'  Derive vendor_key from merchant_name: lowercase, underscores '
            f'(e.g. "Goodwill Cascade" → "goodwill_cascade").\n\n'
        )

    if identified:
        # Facade gave us the real merchant + vendor_key — prefill the categorizer input.
        categorizer_input = json.dumps(
            {'id_light': '', 'description': parsed.get('merchant_name') or vendor,
             'vendor_key': vendor if vendor != 'unknown' else None},
            default=str,
        )
        categorizer_input_line = (
            f"  printf '%s' '{categorizer_input}' > /tmp/mazda_cat_input.json && "
        )
    else:
        # Facade did NOT identify — by STEP 3 Mazda has REAL parsed data from STEP 0.
        # Do NOT hand her the literal placeholder {"description":"unknown"}; that
        # guarantees a categorizer miss (and pushes it onto the LLM-research path).
        categorizer_input_line = (
            '  Build the input JSON from your STEP 0 results — NOT the literal word '
            '"unknown": write {"id_light": "", "description": "<merchant_name from '
            'STEP 0 parse>", "vendor_key": "<vendor_key you derived in STEP 0>"} to '
            '/tmp/mazda_cat_input.json (e.g. via executor_write or printf), then run:\n'
        )
    return (
        f'A document was just scanned on the {scanner_name}. '
        f'The scanned image is at: {scan_image_path}{facade_block}\n\n'
        f'Complete the AGENTIC back half of the intake pipeline '
        f'(investigate → categorize → store → judge):\n\n'
        f'EXECUTOR RULE (read first): run every command below via executor_run — '
        f'NEVER via run_claude_code_sdk. run_claude_code_sdk executes on a different '
        f'machine where the rol_finances venv does not work; substituting it for '
        f'executor_run is a guaranteed failure. Every executor_run call MUST pass '
        f'env={MAZDA_RF_ENV_JSON}. Do NOT prefix any command with "PYTHONPATH=..." — '
        f'the executor allowlist rejects an inline env-assignment as an unknown command '
        f'("Command not in allowlist: PYTHONPATH=..."). Always use the full venv python '
        f'path shown ({MAZDA_RF_VENV_PY}) and carry PYTHONPATH via the env argument.\n\n'
        f'STEP 1 — load_wrapper_revision(agent_name="Mazda"). The result includes '
        f'`instructions` — your accumulated LEARNED RULES from previous judged runs. '
        f'READ THEM AND APPLY EVERY RULE that matches this document; they override '
        f'the default steps below. Keep the returned wrapper_revision for '
        f'record_trace.\n\n'
        f'ROUTING PRECEDENCE — the explicit `doc_type` returned by classify_scan.py '
        f'is authoritative and its matching branch below overrides generic prose '
        f'rules about emails, bills, or non-receipts. In particular, an email '
        f'screenshot whose enclosed document is `invoice` MUST run the INVOICE '
        f'BRANCH; never route it away merely because it is an email or bill. A '
        f'`receipt` MUST run STEPS 2-4. Only explicit `doc_type=other` is unsupported.\n\n'
        f'{fallback_block}'
        f'STATEMENT BRANCH — if this document is a bank or credit-card statement '
        f'(doc_kind "bank_statement" or "statement" from the facade or STEP 0): SKIP '
        f'STEPS 2-4 entirely — they are for single receipts and a statement can never '
        f'complete them. Run these two commands instead (executor_run, '
        f'cwd=/home/adamsl/rol_finances, env={MAZDA_RF_ENV_JSON}):\n'
        f'  S1. Extract every transaction (Gemini vision):\n'
        f'      {MAZDA_RF_VENV_PY} tools/receipt_scanning_tools/parse_statement_scan.py '
        f'{scan_image_path} -o /tmp/mazda_stmt.json\n'
        f'  S2. Dedupe + store them. Expenses are inserted UNCATEGORIZED (they enter '
        f'the New Records queue for a human to categorize — do NOT run the categorizer '
        f'for statements). Deposits/credits are NOT expenses: the script persists them '
        f'to the bank-side `transactions` ledger (type CREDIT, never categorized, '
        f'never reviewed by a human):\n'
        f'      {MAZDA_RF_VENV_PY} '
        f'tools/receipt_scanning_tools/store_statement_transactions.py '
        f'-f /tmp/mazda_stmt.json --source-file {scan_image_path}\n'
        f'      → {{"transactions_parsed": N, "skipped_credits": N, "duplicates": N, '
        f'"stored": N, "expense_ids": [...], "deposits_stored": N, "deposit_ids": [...], '
        f'"deposit_duplicates": N}}\n'
        f'  EVERY row coming back "duplicates" or "deposit_duplicates" is a SUCCESSFUL '
        f'no-op, not a failure, and a deposit missing from expenses is CORRECT. '
        f'Then continue at STEP 5 with the STATEMENT evidence JSON described there.\n\n'
        f'INVOICE BRANCH — if this document is a bill/invoice requesting payment where the '
        f'document itself does NOT show payment already made (doc_type "invoice" from '
        f'classify_scan.py — e.g. a contractor/consultant invoice with a balance due, not '
        f'stamped paid). An invoice is NOT proof a payment happened; it is a PLACEHOLDER for a '
        f'payment we expect to see evidenced later by a bank statement transaction or a paid '
        f'receipt for the SAME (date, amount). Run STEPS 2-3 normally (investigate + categorize '
        f'this vendor exactly like a receipt), then at STEP 4 add the `--invoice` flag to the '
        f'store command instead of a normal save:\n'
        f'  {MAZDA_RF_VENV_PY} '
        f'tools/receipt_scanning_tools/receipt_parsing_tools/parse_and_categorize.py '
        f'-f {scan_image_path} --save --invoice --category-id=<id from step 3> --engine=gemini\n'
        f'  → {{"success": true, "expense_id": <int>, "expense_status": '
        f'"WAITING_FOR_PAYMENT_COUNTERPART", "linked_counterpart": false, ...}}\n'
        f'This stores ONE expense row with expense_status=WAITING_FOR_PAYMENT_COUNTERPART — do '
        f'NOT create it any other way and do NOT wait for a human to confirm payment first. The '
        f'system links the eventual counterpart automatically: the NEXT time ANY document '
        f'(statement scan or receipt scan) is stored with the SAME (expense_date, amount), the '
        f'storage tools detect the waiting placeholder and UPDATE that same row (receipt_url, '
        f'source_file, notes, expense_status → COUNTERPART_DOCUMENT_LINKED) instead of inserting '
        f'a second expense — so if `linked_counterpart: true` comes back on ANY future receipt '
        f'or statement store, that is CORRECT behavior closing out an earlier invoice, not a '
        f'duplicate to investigate. Continue to STEP 5 using doc_kind "invoice" in the evidence '
        f'JSON.\n\n'
        f'STEP 2 — INVESTIGATE (only with REAL parsed data — never pass "unknown"):\n'
        f'  a. check_vendor_key(id_light="scan", description=<merchant>, '
        f'vendor_key=<vendor_key from facade or derived above>)\n'
        f'     IMPORTANT: if the result contains a normalized/recognized vendor_key that '
        f'differs from what you supplied, USE THE NORMALIZED KEY in every later step '
        f'(categorizer input, evidence JSON) — the vendor store and its category mapping '
        f'are keyed on the normalized form.\n'
        f'  MISSING DATE RULE: if STEP 0/facade could not extract a transaction_date '
        f'(null, unreadable, or no date printed on the receipt), do NOT stop or treat '
        f'it as a blocker — use the placeholder "1970-01-01" as expense_date in '
        f'check_duplicates below and in the STEP 5 evidence JSON. '
        f'parse_and_categorize.py --save already substitutes this same placeholder '
        f'automatically when transaction_date is missing, so STEP 4 needs no special '
        f'handling. This preserves the receipt with an honest sentinel date instead of '
        f'silently guessing a date or losing the document.\n'
        f'  b. check_duplicates(id_light="scan", expense_date=<YYYY-MM-DD, or '
        f'"1970-01-01" if no date was extracted>, '
        f'amount=<decimal string>, description=<merchant>)\n'
        f'  If duplicate → skip only STEP 4 storage. Still run STEP 3 categorization, '
        f'record_trace, judge_trace, and the STEP 8 callback; duplicate detection is '
        f'never permission to stop the run early.\n\n'
        f'STEP 3 — CATEGORIZE (executor_run, cwd=/home/adamsl/rol_finances, '
        f'env={MAZDA_RF_ENV_JSON}):\n'
        f'{categorizer_input_line}'
        f'  {MAZDA_RF_VENV_PY} tools/categorizer/categorizer_main.py '
        f'-i /tmp/mazda_cat_input.json --provider=gemini\n'
        f'  → {{"vendor_key": "...", "category_id": <int>}}\n'
        f'  If that command errors or times out (Gemini CLI/quota trouble), retry ONCE with '
        f'--provider=chatgpt-oauth instead of --provider=gemini (same command otherwise) — '
        f'it already tries your ChatGPT OAuth session, then mom\'s, before giving up, so this '
        f'one retry is really two account attempts. If THAT also fails, retry once more with '
        f'--provider=anthropic (uses an API key, not OAuth — there is no second account for '
        f'this tier). Only fall through to the FAIL-CLOSED CATEGORY RULE below if all three '
        f'providers fail or the vendor is genuinely unresolvable.\n'
        f'  FAIL-CLOSED CATEGORY RULE: merchant/vendor placeholders such as null, "null", '
        f'"unknown", or "receipt" are not real vendors. If merchant/vendor is unresolved '
        f'or category_id is null/zero, STILL run STEP 4 but OMIT --category-id entirely — '
        f'the store tool saves the receipt image and a NULL-category placeholder row '
        f'(expense_status=NEEDS_VENDOR_KEY) instead of failing closed, so a human can pick '
        f'the right vendor_key later via the dashboard instead of the scan being lost. '
        f'Record and judge a truthful trace reflecting the unresolved category (set '
        f'pending_vendor_review:true in the STEP 5 evidence — this is what tells the judge '
        f'a null category is a correct degraded save, not a failure), propose an '
        f'improvement, and send STEP 8 with stored:1 (the row WAS stored) and '
        f'status:"awaiting_vendor_review". If you later find the real category for this '
        f'expense (e.g. via categorizer_main.py or a vendor_category.yaml lookup), correct '
        f'the stored row with '
        f'{MAZDA_RF_VENV_PY} tools/receipt_scanning_tools/receipt_parsing_tools/'
        f'update_expense_category.py --expense-id=<id> --category-id=<id> — NEVER hand-write '
        f'SQL against the finance DB; /api/recategorize-expense is a different tool for a '
        f'different (coarser, 13-value) reporting taxonomy and will reject a vendor_category.yaml '
        f'category name.\n\n'
        f'STEP 4 — STORE (executor_run, cwd=/home/adamsl/rol_finances, '
        f'env={MAZDA_RF_ENV_JSON}). '
        f'Include --category-id=<id from step 3> when STEP 3 resolved a positive one; OMIT '
        f'the flag entirely when it did not (see FAIL-CLOSED CATEGORY RULE above — the tool '
        f'still saves the receipt + a pending-review placeholder row rather than erroring):\n'
        f'  {MAZDA_RF_VENV_PY} '
        f'tools/receipt_scanning_tools/receipt_parsing_tools/parse_and_categorize.py '
        f'-f {scan_image_path} --save --category-id=<id from step 3> --engine=gemini\n'
        f'  → {{"success": true, "expense_id": <int>, "pending_vendor_review": <true when '
        f'--category-id was omitted/invalid>, ...}} OR a duplicate result. '
        f'The save path performs a final duplicate guard using its final parsed/overridden '
        f'date, amount, and merchant. If it reports duplicate, treat the existing expense '
        f'as the result and never retry with --allow-duplicate.\n\n'
        f'STEP 4B — ITEMIZE WHEN EVIDENCE ALLOWS (MCP tool; never hand-build SQL):\n'
        f'  For a newly stored receipt whose parsed JSON has multiple line items, call '
        f'itemize_existing_expense(doc_family="receipt", expense_id=<STEP 4 id>, '
        f'id_light=<stored id_light>, expense_date=<final stored date>, amount=<final '
        f'stored total>, description=<final merchant>, receipt_payload_json=<the exact '
        f'STEP 0 JSON>, category_ids=[<one verified positive category per item>], '
        f'receipt_url=<store result>, source_file="{scan_image_path}").\n'
        f'  The factory checks that source lines sum CENT-EXACTLY to the charge and writes '
        f'PARENT + LINE_ITEM rows in one transaction. itemizable:false is a CORRECT '
        f'fail-closed result: leave the expense STANDALONE and record the reason. Never '
        f'guess missing lines, allocate an Amazon split shipment, retry a partial write, '
        f'or issue parent/child SQL yourself. For Amazon statement charges use '
        f'doc_family="amazon_statement" only when an order ID is present; the same exact '
        f'reconciliation rule applies.\n\n'
        f'STEP 5 — record_trace(agent_name="Mazda", task_name="document-intake", '
        f'input_text=<scan path>, agent_output=<the intake-evidence JSON below>). '
        f'The task_name MUST be exactly "document-intake" so it is judged by the intake '
        f'rubric (not the statement rubric). agent_output MUST be this JSON object recording '
        f'what actually happened — the judge reads these fields:\n'
        f'  {{"document_path": "{scan_image_path}", "doc_kind": "receipt"|"invoice"|"statement"|"unknown", '
        f'"classification_confidence": <0-1>, "vendor_key": "<resolved or null>", '
        f'"vendor_key_recognized": <true|false>, "category_id": <int or null>, '
        f'"duplicate_checked": <true|false>, "is_duplicate": <true|false>, '
        f'"stored": <true|false>, "expense_id": <int or null>, '
        f'"itemization_attempted": <true|false>, "itemized": <true|false>, '
        f'"itemization_reconciled": <true only when itemization succeeded>, '
        f'"itemization_parent_id": <int or null>, '
        f'"itemization_child_ids": [<all child ids>], '
        f'"expense_status": "<NONE|WAITING_FOR_PAYMENT_COUNTERPART|COUNTERPART_DOCUMENT_LINKED, '
        f'from the store response, when doc_kind is invoice or when linked_counterpart was true>", '
        f'"pending_vendor_review": <true when STEP 4 returned pending_vendor_review:true '
        f'(a null/omitted --category-id), else false — REQUIRED whenever category_id is null; '
        f'the judge treats a null category with pending_vendor_review unset as a real failure, '
        f'not the correct degraded save the FAIL-CLOSED CATEGORY RULE describes>, '
        f'"problems": [<strings>]}}\n'
        f'  For a STATEMENT, record this evidence JSON INSTEAD (the judge routes it '
        f'to the statement rubric — the receipt fields above do not apply):\n'
        f'  {{"document_path": "{scan_image_path}", "doc_kind": "statement", '
        f'"classification_confidence": <0-1>, "duplicate_checked": true, '
        f'"transactions_parsed": <N from S2>, "transactions_stored": <N>, '
        f'"transactions_duplicate": <N>, "transactions_skipped_credits": <N>, '
        f'"deposits_stored": <N from S2, deposits persisted to transactions>, '
        f'"problems": [<strings>]}}\n'
        f'  Keep the returned trace_id.\n\n'
        f'STEP 6 — judge_trace(trace_id) — ALWAYS, on success or failure. The intake rubric '
        f'now scores intake correctly: a clean store is PASS, a correctly-detected duplicate '
        f'is PASS, and a broken stage is FAIL. The verdict is what the autonomous reflection '
        f'loop reads, so judging every run is what lets the system heal failures without a '
        f'human.\n\n'
        f'STEP 7 — CLOSE THE LOOP when the verdict is FAIL:\n'
        f'  a. propose_improvement(trace_id, failure_type=<the verdict\'s '
        f'failure_type>, summary=<what went wrong>, expected_benefit=<what improves>) '
        f'→ note the returned proposal_id.\n'
        f'  b. apply_proposal(proposal_id=<that id>, instruction_note=<ONE concrete '
        f'imperative rule that would have prevented this exact failure>). This runs '
        f'the safety gates, appends your rule to the learned instructions as a new '
        f'wrapper revision, and ACTIVATES it — your next run receives it in STEP 1 '
        f'automatically. If it returns pending_approval or a block, stop there; do '
        f'not retry and do not activate anything manually.\n\n'
        f'STEP 8 — NOTIFY DASHBOARD (fire-and-forget; ALWAYS run this after record_trace, '
        f'even when nothing new was stored — e.g. every transaction was a duplicate. The '
        f'dashboard\'s Recent Report view shows this run\'s outcome either way). '
        f'executor_run, no special cwd/env needed:\n'
        f'  curl -s -X POST http://localhost:8765/api/expense-stored '
        f'-H "Content-Type: application/json" '
        f'-d \'{{"expense_id":<first stored id, or null>,'
        f'"expense_ids":[<ALL expense ids stored this run; [] when none>],'
        f'"duplicate_expense_ids":[<the duplicate_expense_ids list from '
        f'store_statement_transactions.py; [] when none>],'
        f'"parsed":<transactions parsed>,"stored":<transactions stored>,'
        f'"deposits_stored":<deposits stored to the transactions ledger this run; '
        f'0 when none>,'
        f'"expense_date":"<YYYY-MM-DD>",'
        f'"amount":"<decimal string>","vendor_key":"<vendor_key>",'
        f'"description":"<merchant_name>","receipt_url":"<scan_image_path>",'
        f'"document_path":"{scan_image_path}",'
        f'"conversation_id":"{conversation_id or ""}",'
        f'"dispatched_at":{float(dispatched_at or 0)},'
        f'"doc_kind":"<statement|receipt|invoice|unknown, from the facade or your own '
        f'classify_scan.py/STEP 0 classification — the same value you recorded '
        f'as doc_kind in STEP 5>","vendor":"<the vendor/merchant name you '
        f'identified, e.g. \\"chase\\", or \\"unknown\\">",'
        f'"status":"<omit this key normally; include "awaiting_vendor_review" ONLY when '
        f'STEP 4 returned pending_vendor_review:true, so the Recent Report view shows '
        f'this document is waiting on a human vendor pick rather than a generic failure>"'
        f'}}\'\n'
        f'Ignore errors — the dashboard degrades gracefully if unreachable.\n'
    )


# Where a scan must live so Mazda's tools can read it. Mazda has TWO executors:
#   - executor_run → THIS box (Letta MCP "executor_server" at 10.0.0.7:8789).
#     This is the PRIMARY intake path — the rol_finances venv and MySQL live
#     here, so the dispatch message routes every rol_finances command to it.
#   - run_claude_code_sdk → the frita-executor container on the Win10 box
#     (:8799). Its mounted rol_finances venv is a broken symlink inside the
#     container (host /usr/local/bin/python3 doesn't exist there), so
#     rol_finances scripts CANNOT run in it — 2026-07-10 incident.
# The scan is therefore staged LOCALLY first (authoritative), and mirrored to
# the Win10 box best-effort so the identical path also resolves for any SDK
# session that merely needs to look at the image.
SCAN_STAGING_HOST = os.environ.get('LETTA_DOCKER_HOST', 'adamsl@100.80.49.10')
SCAN_STAGING_REMOTE_DIR = (
    '/home/adamsl/rol_finances/tools/receipt_scanning_tools/incoming_scans')


def _stage_scan_for_mazda(local_image_path):
    """Copy a scanned image to where Mazda's executor tools can actually read it.

    Copies into this box's rol_finances incoming_scans (executor_run's view —
    required) and mirrors to the Win10 box (run_claude_code_sdk's view —
    best-effort). Returns the staged path (identical on both boxes) or None
    when even the local copy failed — the caller must not hand Mazda a path
    she can't reach.
    """
    if not os.path.isfile(local_image_path):
        return None
    # Scanner output names are reusable (scan.jpg / scan_freezer.jpg), while a
    # Mazda conversation can remain active for minutes.  Never give two runs
    # the same mutable path: a late tool call from the older run could otherwise
    # read and store the newer scan.  Keep the scanner prefix for diagnostics,
    # and add both a dispatch-unique timestamp and a content fingerprint.
    source_name = os.path.basename(local_image_path)
    stem, suffix = os.path.splitext(source_name)
    try:
        with open(local_image_path, 'rb') as src:
            content_hash = hashlib.sha256(src.read()).hexdigest()[:12]
    except OSError as exc:
        print(f'[scan→mazda] Failed to fingerprint scan: {exc}')
        return None
    staged_name = f'{stem}_{time.time_ns()}_{content_hash}{suffix}'
    staged_path = f'{SCAN_STAGING_REMOTE_DIR}/{staged_name}'
    try:
        os.makedirs(SCAN_STAGING_REMOTE_DIR, exist_ok=True)
        shutil.copyfile(local_image_path, staged_path)
    except Exception as exc:
        print(f'[scan→mazda] Failed to stage scan locally for executor: {exc}')
        return None
    try:
        subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes',
             SCAN_STAGING_HOST, 'mkdir', '-p', SCAN_STAGING_REMOTE_DIR],
            capture_output=True, text=True, timeout=15, check=True,
        )
        subprocess.run(
            ['scp', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes',
             local_image_path, f'{SCAN_STAGING_HOST}:{staged_path}'],
            capture_output=True, text=True, timeout=30, check=True,
        )
    except Exception as exc:
        print(f'[scan→mazda] Win10 mirror of scan failed (non-fatal — '
              f'executor_run reads the local copy): {exc}')
    return staged_path


# ── Permanent scan archive ────────────────────────────────────────────────
# Why this exists (2026-07-21): DB duplicate-detection only answers "was this
# TRANSACTION already recorded" — it says nothing about whether the physical
# PAPER in hand has already been digitized. The whole point of scanning is to
# stop treating originals as the record of truth so they can go in the attic
# for IRS retention instead of a filing cabinet. That requires a durable,
# indexed copy of every scan — independent of whatever Mazda decides to do
# with it (store / duplicate / fail) — so this lives in the dashboard, not in
# Mazda's tool contract: it must not depend on the cheap model remembering to
# do it. incoming_scans/ already keeps a uniquely-named copy of every scan,
# but it is a staging directory for the executor (undocumented as an archive,
# no human-facing index) — this gives EG an actual "was this already
# scanned?" answer and a permanent, organized location.
SCAN_ARCHIVE_ROOT = os.environ.get(
    'SCAN_ARCHIVE_ROOT',
    os.path.expanduser('~/rol_finances/readable_documents/scanned_documents_archive'))
SCAN_ARCHIVE_INDEX_PATH = os.path.join(SCAN_ARCHIVE_ROOT, 'index.json')
_scan_archive_lock = threading.Lock()


def _read_scan_archive_index():
    try:
        with open(SCAN_ARCHIVE_INDEX_PATH, 'r') as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_scan_archive_index(data):
    os.makedirs(SCAN_ARCHIVE_ROOT, exist_ok=True)
    tmp_path = SCAN_ARCHIVE_INDEX_PATH + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp_path, SCAN_ARCHIVE_INDEX_PATH)


def archive_scan_permanently(local_image_path, scanner_label, content_sha256=None,
                              dispatched_at=None):
    """Copy a raw scan into a permanent, human-browsable, indexed archive.

    Runs unconditionally on every scan dispatch, before Mazda is even
    notified — archival must never depend on her pipeline succeeding, finding
    a duplicate, or running at all. Returns a dict with `archive_path` (None
    on failure — caller must not treat archival failure as fatal to intake)
    and `already_seen_before` (True when this exact image's content hash was
    archived on an earlier scan — a genuine re-scan of the same paper, not
    merely the same transaction).
    """
    dispatched_at = dispatched_at if dispatched_at is not None else time.time()
    content_sha256 = content_sha256 or _scan_content_sha256(local_image_path)
    if not content_sha256:
        return {'archive_path': None, 'already_seen_before': False}
    with _scan_archive_lock:
        index = _read_scan_archive_index()
        existing = index.get(content_sha256)
        if existing and os.path.isfile(existing.get('archive_path', '')):
            existing['rescan_count'] = int(existing.get('rescan_count', 1)) + 1
            existing['last_seen_at'] = dispatched_at
            index[content_sha256] = existing
            _write_scan_archive_index(index)
            return {'archive_path': existing['archive_path'],
                     'already_seen_before': True,
                     'first_archived_at': existing.get('first_archived_at')}
        dt = datetime.fromtimestamp(dispatched_at)
        dest_dir = os.path.join(SCAN_ARCHIVE_ROOT, dt.strftime('%Y'), dt.strftime('%m'))
        slug = re.sub(r'[^A-Za-z0-9]+', '-', scanner_label or 'scan').strip('-').lower()
        ext = os.path.splitext(local_image_path)[1] or '.jpg'
        dest_name = f'{dt.strftime("%Y%m%d-%H%M%S")}_{slug}_{content_sha256[:12]}{ext}'
        dest_path = os.path.join(dest_dir, dest_name)
        try:
            os.makedirs(dest_dir, exist_ok=True)
            shutil.copyfile(local_image_path, dest_path)
        except OSError as exc:
            print(f'[scan-archive] Failed to archive scan permanently: {exc}')
            return {'archive_path': None, 'already_seen_before': False}
        index[content_sha256] = {
            'archive_path': dest_path,
            'scanner': scanner_label,
            'first_archived_at': dispatched_at,
            'last_seen_at': dispatched_at,
            'rescan_count': 1,
        }
        _write_scan_archive_index(index)
        return {'archive_path': dest_path, 'already_seen_before': False}


def _create_mazda_conversation():
    """Create one isolated Letta conversation for one intake dispatch.

    Never fall back to Mazda's agent-default conversation: that would allow
    simultaneous Window and Freezer scans to share compacted context again.
    """
    try:
        agent_id = quote(MAZDA_AGENT_ID, safe='')
        req = urllib.request.Request(
            f'{LETTA_BASE_URL}/v1/conversations/?agent_id={agent_id}',
            data=b'{}',
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            conversation = json.loads(resp.read().decode())
        conversation_id = conversation.get('id')
        if not isinstance(conversation_id, str) or not conversation_id:
            raise ValueError('Letta returned no conversation id')
        return conversation_id
    except Exception as exc:
        print(f'[scan→mazda] Failed to create isolated conversation: {exc}')
        return None


def _notify_mazda_of_scan(scan_image_path, scanner_name, facade_result=None,
                          conversation_id=None, dispatched_at=None):
    """Background: send the scanned document to Mazda for intake processing.

    scan_image_path must already be reachable from Mazda's executor tools
    (see _stage_scan_for_mazda) — this function does no staging itself.
    """
    if not conversation_id:
        print('[scan→mazda] Refusing shared/default conversation dispatch')
        return False
    try:
        msg = build_mazda_scan_message(
            scan_image_path, scanner_name, facade_result,
            conversation_id=conversation_id, dispatched_at=dispatched_at)
        payload = json.dumps({
            'messages': [{'role': 'user', 'content': msg}],
            'streaming': False,
        }).encode()
        req = urllib.request.Request(
            f'{LETTA_BASE_URL}/v1/conversations/{quote(conversation_id, safe="")}/messages',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            print(f'[scan→mazda] Mazda notified of scan ({scanner_name}): '
                  f'HTTP {resp.status}; conversation={conversation_id}')
        return True
    except Exception as exc:
        print(f'[scan→mazda] Failed to notify Mazda: {exc}')
        return False


# ── Mazda Trainer ────────────────────────────────────────────────────────────
# Every scan dispatched to Mazda also spawns a Codex Trainer agent that watches
# the run, verifies the document was
# processed correctly, and coaches Mazda on failures. Mazda runs on a cheap mini
# model while her self-improvement harness is validated — the Trainer is the
# safety net that makes that acceptable. Fire-and-forget, like the Mazda
# dispatch itself: a broken/missing trainer must never block intake.
TRAINER_SCRIPT = os.path.join(HERE, 'trainer', 'run_mazda_trainer.mjs')
TRAINER_RUNNER = os.environ.get(
    'MAZDA_TRAINER_RUNNER', os.path.expanduser('~/.bun/bin/bun'))
TRAINER_ENABLED = os.environ.get(
    'MAZDA_TRAINER_ENABLED', '1').lower() not in ('0', 'false', 'no')


def build_trainer_command(scan_image_path, scanner_name, facade_result=None,
                          dispatched_at=None, conversation_id=None):
    """Pure builder for the Trainer launch argv — no I/O, unit-tested."""
    cmd = [
        TRAINER_RUNNER, TRAINER_SCRIPT,
        '--scan-path', scan_image_path,
        '--scanner', scanner_name,
        '--facade', json.dumps(facade_result or {}, default=str),
    ]
    if dispatched_at is not None:
        cmd += ['--dispatched-at', str(int(dispatched_at))]
    if conversation_id:
        cmd += ['--conversation-id', conversation_id]
    return cmd


def _notify_trainer_of_scan(scan_image_path, scanner_name, facade_result=None,
                            conversation_id=None, dispatched_at=None):
    """Fire-and-forget: launch the Trainer agent to watch this Mazda run.

    Returns True when the trainer process was spawned. Never raises — the
    trainer is an observer; intake must proceed identically without it.
    """
    if not TRAINER_ENABLED:
        return False
    if not conversation_id:
        print('[scan→trainer] Refusing to watch a shared/default conversation')
        return False
    if not os.path.isfile(TRAINER_SCRIPT):
        print(f'[scan→trainer] Trainer script missing: {TRAINER_SCRIPT}')
        return False
    dispatched_at = int(dispatched_at or time.time())
    scanner_slug = re.sub(r'[^A-Za-z0-9]+', '_', scanner_name).strip('_') or 'scanner'
    conversation_slug = re.sub(r'[^A-Za-z0-9]+', '', conversation_id)[-12:]
    log_path = (f'/tmp/mazda_trainer_{dispatched_at}_{scanner_slug}_'
                f'{conversation_slug}.log')
    cmd = build_trainer_command(
        scan_image_path, scanner_name, facade_result, dispatched_at,
        conversation_id)
    env = dict(os.environ)
    # The systemd --user service's PATH lacks bun/codex; the runner spawns the
    # `codex` CLI, so both bins must be reachable from the child.
    env['PATH'] = ':'.join([
        os.path.expanduser('~/.bun/bin'), os.path.expanduser('~/.local/bin'),
        os.path.expanduser('~/.npm-global/bin'),
        env.get('PATH', '/usr/bin:/bin'),
    ])
    try:
        with open(log_path, 'ab') as log:
            subprocess.Popen(
                cmd, stdout=log, stderr=log, env=env,
                cwd=os.path.dirname(TRAINER_SCRIPT), start_new_session=True)
        print(f'[scan→trainer] Trainer watching {scanner_name} scan; '
              f'log: {log_path}')
        return True
    except Exception as exc:
        print(f'[scan→trainer] Failed to launch trainer: {exc}')
        return False


def _notify_mazda_of_pdf(file_path, label=None, conversation_id=None,
                         dispatched_at=None):
    """Background: send a PDF document to Mazda for intake processing."""
    if not conversation_id:
        print('[pdf→mazda] Refusing shared/default conversation dispatch')
        return False
    try:
        label_str = f' "{label}"' if label else ''
        msg = (
            f'A PDF document{label_str} is ready for processing.\n'
            f'The file is at: {file_path}\n\n'
            f'Please process this document through your intake pipeline:\n'
            f'1. Call load_wrapper_revision to load your active wrapper.\n'
            f'2. Classify and parse the document (cheapest reliable tool first).\n'
            f'3. Call record_trace when done to log this run.\n'
            f'4. If anything fails, call propose_improvement with the failure details.'
            f' Every /api/expense-stored callback must include '
            f'"conversation_id":"{conversation_id}" and '
            f'"dispatched_at":{float(dispatched_at or 0)}.'
        )
        payload = json.dumps({
            'messages': [{'role': 'user', 'content': msg}],
            'streaming': False,
        }).encode()
        req = urllib.request.Request(
            f'{LETTA_BASE_URL}/v1/conversations/{quote(conversation_id, safe="")}/messages',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            print(f'[pdf→mazda] Mazda notified of PDF{label_str}: HTTP {resp.status}; '
                  f'conversation={conversation_id}')
        return True
    except Exception as exc:
        print(f'[pdf→mazda] Failed to notify Mazda: {exc}')
        return False


# Intake-dispatch claim: exactly one Mazda dispatch per (scanner, image file,
# image mtime). Both the server's own post-scan auto-dispatch and the
# frontend's POST /api/process-document funnel through process_scanned_document;
# whichever arrives second sees the claim and skips the dispatch.
_scan_dispatch_claims = {}
_scan_dispatch_claim_lock = threading.Lock()


def _scan_content_sha256(image_path):
    try:
        digest = hashlib.sha256()
        with open(image_path, 'rb') as src:
            for chunk in iter(lambda: src.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ''


def _claim_scan_dispatch(key, image_path, content_sha256=None):
    """Claim a scanner image once, including across dashboard restarts."""
    try:
        stat = os.stat(image_path)
    except OSError:
        return False
    content_sha256 = content_sha256 or _scan_content_sha256(image_path)
    claim = (image_path, stat.st_mtime_ns, stat.st_size, content_sha256)
    with _scan_dispatch_claim_lock:
        if _scan_dispatch_claims.get(key) == claim:
            return False
        # The in-memory claim is lost on a service restart. The per-scanner
        # intake pointer persists the immutable content fingerprint, so an old
        # browser cannot redispatch the same output file after the restart.
        cfg = SCANNERS.get(key) or {}
        previous = get_scanner_intake(key)
        if (content_sha256 and previous and
                previous.get('content_sha256') == content_sha256):
            return False
        _scan_dispatch_claims[key] = claim
        return True


def _release_scan_dispatch(key, image_path):
    """Undo a claim whose dispatch failed (e.g. staging error) so a retry of
    the same image can dispatch."""
    with _scan_dispatch_claim_lock:
        claimed = _scan_dispatch_claims.get(key)
        if claimed and claimed[0] == image_path:
            del _scan_dispatch_claims[key]


_scanner_runtime_status = {}
_scanner_runtime_status_lock = threading.Lock()


def _scanner_intake_in_progress(key, max_age_seconds=35 * 60):
    """True while this scanner's previous Mazda/Trainer run is unfinished."""
    intake = get_scanner_intake(key)
    if not intake or intake.get('status') not in ('processing', 'complete'):
        return False
    try:
        age = time.time() - float(intake.get('dispatched_at') or 0)
    except (TypeError, ValueError):
        return False
    return 0 <= age < max_age_seconds


def run_scanner(key):
    """Manual scan (POST /api/scanner-scan). Adds back-compat `ok` to the status.

    When the scan finishes ready, the SERVER dispatches the intake pipeline in a
    background thread. The frontend still POSTs /api/process-document for its
    inline stage display, but that call no longer carries the dispatch: on
    2026-07-12 a scan's intake was lost because dispatch relied on the browser
    surviving the scan. _claim_scan_dispatch keeps the two paths from ever
    double-dispatching Mazda for the same image.
    """
    if _scanner_intake_in_progress(key):
        return {
            'ok': False,
            'status': 'intake_busy',
            'error': ('The previous document from this scanner is still being '
                      'verified. Wait for its Trainer PASS/FAIL before scanning another.'),
        }
    result = _invoke_scanner(key)
    result['ok'] = (result.get('status') == 'ready')
    with _scanner_runtime_status_lock:
        # GET /api/scanner-status is observation-only. A completed scan is
        # represented as idle there; only this POST response carries `ready`
        # and can cause the frontend to launch intake.
        _scanner_runtime_status[key] = (
            {'status': 'idle', 'ok': True} if result['ok'] else dict(result))
    if result['ok']:
        threading.Thread(
            target=process_scanned_document, args=(key,), daemon=True,
        ).start()
    return result


def scanner_status(key):
    """Read-only scanner state. Never starts WIA or writes a scan image."""
    if key not in SCANNERS:
        return {'status': 'error', 'ok': False, 'error': f'Unknown scanner: {key}'}
    with _scanner_runtime_status_lock:
        return dict(_scanner_runtime_status.get(key, {'status': 'idle', 'ok': True}))


# ── Document intake pipeline (the "Process Document" action) ────────────────
# When a scan finishes, the dashboard fires POST /api/process-document. The
# cheapest reliable tool runs FIRST — the deterministic intake facade
# (mazda_intake.py: classify + parse) — and its result is rendered inline within
# seconds. The deeper, agentic stages (investigate → categorize → store) are
# Mazda's job; they are dispatched fire-and-forget (NO polling) via the existing
# _notify_mazda_of_scan thread. Governing rule: cheapest reliable tool first;
# LLM only when confidence < 0.90 (the facade enforces that threshold itself).
ROL_FINANCES_DIR = os.path.expanduser('~/rol_finances')
MAZDA_INTAKE_FACADE = os.path.join(ROL_FINANCES_DIR, 'tools', 'mazda_intake.py')
MAZDA_INTAKE_PYTHON = os.path.join(ROL_FINANCES_DIR, '.venv', 'bin', 'python3')
INTAKE_FACADE_TIMEOUT_SEC = 120

# The pipeline stages the deterministic facade does NOT run — delegated to Mazda.
MAZDA_DELEGATED_STAGES = ('investigate', 'categorize', 'store')


def run_intake_facade(image_path, org_id=1, engine='gemini'):
    """Run the deterministic intake facade (classify + parse) on one document.

    Returns the facade's structured JSON dict (always carrying an `ok` key).
    Never raises — a missing facade, bad exit, or unparseable stdout becomes
    {'ok': False, 'error': ...} so the caller can always render something inline.
    """
    if not os.path.isfile(image_path):
        return {'ok': False, 'error': f'Scanned image not found: {image_path}'}
    if not os.path.isfile(MAZDA_INTAKE_FACADE):
        return {'ok': False,
                'error': f'Intake facade not found: {MAZDA_INTAKE_FACADE}'}
    python = MAZDA_INTAKE_PYTHON if os.path.isfile(MAZDA_INTAKE_PYTHON) else 'python3'
    try:
        proc = subprocess.run(
            [python, MAZDA_INTAKE_FACADE, image_path,
             f'--org-id={org_id}', '--enable-parse', f'--engine={engine}'],
            cwd=ROL_FINANCES_DIR,
            capture_output=True, text=True,
            timeout=INTAKE_FACADE_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        return {'ok': False,
                'error': f'Intake facade timed out after {INTAKE_FACADE_TIMEOUT_SEC}s'}
    except Exception as exc:
        return {'ok': False, 'error': f'Failed to run intake facade: {exc}'}
    out = (proc.stdout or '').strip()
    # Sub-modules (e.g. LlmPdfParser) may print progress lines to stdout before
    # the final JSON object.  Find the first '{' so those stray lines don't
    # poison json.loads.
    json_start = out.find('{')
    if json_start > 0:
        out = out[json_start:]
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        err = (proc.stderr or '').strip() or out or f'exit {proc.returncode}'
        return {'ok': False, 'error': f'Intake facade returned no JSON: {err[:300]}'}


def build_pipeline_result(facade, mazda_dispatched):
    """Pure shaper: facade dict + dispatch flag → the inline pipeline result.

    Mirrors classify_scan_result — pure, no I/O, unit-tested. Produces an
    ordered `stages` list so the UI can render the full classify → parse →
    investigate → categorize → store pipeline, with the deterministic front half
    filled in and the agentic back half marked delegated (Mazda) or pending.
    """
    facade = facade or {}
    ok = bool(facade.get('ok'))
    classify = {
        'name': 'classify',
        'status': 'done' if ok else 'error',
        'doc_kind': facade.get('doc_kind'),
        'routing_key': facade.get('routing_key'),
        'vendor': facade.get('vendor'),
        'confidence': facade.get('confidence'),
        'method': facade.get('classification_method'),
        'recommended_action': facade.get('recommended_action'),
    }
    parsed = facade.get('parsed')
    parse = {
        'name': 'parse',
        'status': 'done' if (ok and parsed) else ('skipped' if ok else 'error'),
        'parsed': parsed,
    }
    delegated = [
        {'name': stage,
         'status': 'delegated' if mazda_dispatched else 'pending',
         'owner': 'mazda' if mazda_dispatched else None}
        for stage in MAZDA_DELEGATED_STAGES
    ]
    return {
        'ok': ok,
        'error': facade.get('error'),
        'mazda_dispatched': bool(mazda_dispatched),
        'stages': [classify, parse, *delegated],
    }


def process_scanned_document(key, org_id=1, engine='gemini'):
    """Orchestrate the Process Document action for one scanner's latest image.

    1. Resolve the scanner's output image.
    2. Run the deterministic facade (classify + parse) for the inline result.
    3. Dispatch Mazda fire-and-forget for investigate → categorize → store.
    No polling: the deeper stages run in Mazda's own time and surface in her
    own agent transcript, not here.
    """
    cfg = SCANNERS.get(key)
    if not cfg:
        return {'ok': False, 'error': f'Unknown scanner: {key}', 'stages': []}
    image_path = os.path.join(SCAN_TOOLS_DIR, cfg.get('output', ''))
    facade = run_intake_facade(image_path, org_id=org_id, engine=engine)
    mazda_dispatched = False
    trainer_dispatched = False
    stage_error = None
    archive_info = None
    vision_health = document_vision_health()
    if not vision_health.get('ok'):
        # All 3 classify_scan.py vision tiers are down — dispatching Mazda would
        # just strand her mid-trace with nothing that can read the image (see
        # DOCUMENT_VISION_HALT_MESSAGE). Halt here instead: /api/server-health
        # already reports 'document-vision' red for the same reason, and the
        # frontend's VisionHaltAlert modal/tab-red state is driven by that,
        # not by this response.
        result = build_pipeline_result(facade, mazda_dispatched=False)
        result['trainer_dispatched'] = False
        result['vision_halted'] = True
        result['stage_error'] = DOCUMENT_VISION_HALT_MESSAGE
        result['scanner'] = key
        result['image_path'] = image_path
        return result
    if os.path.isfile(image_path):
        content_sha256 = _scan_content_sha256(image_path)
        if not _claim_scan_dispatch(key, image_path, content_sha256):
            # This exact image was already dispatched (the server auto-fires
            # intake when a scan finishes AND the frontend still POSTs
            # /api/process-document) — never send Mazda the same document twice.
            result = build_pipeline_result(facade, mazda_dispatched=True)
            result['trainer_dispatched'] = False
            result['already_dispatched'] = True
            result['scanner'] = key
            result['image_path'] = image_path
            return result
        # Archive BEFORE staging/dispatch, and unconditionally — a permanent
        # copy of the paper must exist even if Mazda's dispatch fails below.
        archive_info = archive_scan_permanently(
            image_path, cfg.get('name', key), content_sha256=content_sha256)
        if archive_info.get('already_seen_before'):
            print(f'[scan-archive] {key}: this exact document was already '
                  f'archived on an earlier scan '
                  f'(first archived {archive_info.get("first_archived_at")}) — '
                  f'a genuine re-scan of the same paper.')
        remote_image_path = _stage_scan_for_mazda(image_path)
        if remote_image_path:
            conversation_id = _create_mazda_conversation()
            if conversation_id:
                dispatched_at = time.time()
                threading.Thread(
                    target=_notify_mazda_of_scan,
                    args=(remote_image_path, cfg.get('name', key), facade,
                          conversation_id, dispatched_at),
                    daemon=True,
                ).start()
                mazda_dispatched = True
                trainer_dispatched = _notify_trainer_of_scan(
                    remote_image_path, cfg.get('name', key), facade,
                    conversation_id, dispatched_at)
                record_recent_intake(
                    remote_image_path, cfg.get('name', key), kind='scan',
                    facade=facade, conversation_id=conversation_id,
                    dispatched_at=dispatched_at,
                    content_sha256=content_sha256,
                    archive_path=archive_info.get('archive_path'),
                    already_seen_before=archive_info.get('already_seen_before', False))
            else:
                _release_scan_dispatch(key, image_path)
                stage_error = ('Could not create an isolated Mazda conversation; '
                               'the scan was not dispatched into shared context.')
        else:
            _release_scan_dispatch(key, image_path)
            stage_error = ('Could not copy the scan to where Mazda can read it '
                            '(SSH/copy to the executor machine failed) — Mazda was not notified.')
    result = build_pipeline_result(facade, mazda_dispatched)
    result['trainer_dispatched'] = trainer_dispatched
    if mazda_dispatched:
        result['conversation_id'] = conversation_id
    if stage_error:
        result['stage_error'] = stage_error
    result['scanner'] = key
    result['image_path'] = image_path
    if archive_info:
        result['archive_path'] = archive_info.get('archive_path')
        result['already_seen_before'] = archive_info.get('already_seen_before', False)
    return result


def process_pdf_document(file_path, label=None, org_id=1, engine='gemini'):
    """Orchestrate the Process Document action for an existing PDF file.

    Mirrors process_scanned_document but accepts an absolute file path instead
    of a scanner key. The path must resolve inside ROL_FINANCES_DIR.
    """
    try:
        real = os.path.realpath(os.path.expanduser(file_path))
        base = os.path.realpath(ROL_FINANCES_DIR)
        if not (real.startswith(base + os.sep) or real == base):
            return {'ok': False,
                    'error': 'File path must be inside the ROL finances directory.',
                    'stages': []}
    except Exception as exc:
        return {'ok': False, 'error': f'Invalid path: {exc}', 'stages': []}
    if not os.path.isfile(real):
        return {'ok': False, 'error': f'File not found: {file_path}', 'stages': []}
    facade = run_intake_facade(real, org_id=org_id, engine=engine)
    doc_label = label or os.path.basename(real)
    vision_health = document_vision_health()
    if not vision_health.get('ok'):
        result = build_pipeline_result(facade, mazda_dispatched=False)
        result['trainer_dispatched'] = False
        result['vision_halted'] = True
        result['stage_error'] = DOCUMENT_VISION_HALT_MESSAGE
        result['file_path'] = real
        result['label'] = doc_label
        return result
    conversation_id = _create_mazda_conversation()
    if not conversation_id:
        result = build_pipeline_result(facade, mazda_dispatched=False)
        result['trainer_dispatched'] = False
        result['stage_error'] = ('Could not create an isolated Mazda conversation; '
                                 'the PDF was not dispatched into shared context.')
        result['file_path'] = real
        result['label'] = doc_label
        return result
    dispatched_at = time.time()
    threading.Thread(
        target=_notify_mazda_of_pdf,
        args=(real, doc_label, conversation_id, dispatched_at),
        daemon=True,
    ).start()
    record_recent_intake(real, doc_label, kind='pdf', facade=facade,
                         conversation_id=conversation_id,
                         dispatched_at=dispatched_at)
    # PDFs already live inside ROL_FINANCES_DIR (enforced above), so no staging
    # is needed — executor_run on this box reads them directly. This also
    # covers reprocess_report, which delegates here.
    trainer_dispatched = _notify_trainer_of_scan(
        real, f'PDF intake ({doc_label})', facade, conversation_id,
        dispatched_at)
    result = build_pipeline_result(facade, mazda_dispatched=True)
    result['trainer_dispatched'] = trainer_dispatched
    result['file_path'] = real
    result['label'] = doc_label
    result['conversation_id'] = conversation_id
    return result


def reprocess_report(report_url):
    """Re-run the full intake pipeline (facade + Mazda) for a report's source document.

    Accepts the iframe URL of a report.html (e.g.
    /rol_finances_reports/jan-2025/fifth_third_non_profit_3119/report.html),
    resolves the source PDF/xlsx in the same directory, and delegates to
    process_pdf_document — which runs the deterministic facade inline and
    dispatches Mazda fire-and-forget for categorize→store→judge.
    """
    if not report_url:
        return {'ok': False, 'error': 'report_url is required.', 'stages': []}
    source_path = _source_document_path(report_url)
    if not source_path:
        return {
            'ok': False,
            'error': 'Could not resolve a source document (PDF/xlsx) for that report URL.',
            'stages': [],
        }
    if not os.path.isfile(source_path):
        return {
            'ok': False,
            'error': f'Source document not found on disk: {source_path}',
            'stages': [],
        }
    label = os.path.basename(os.path.dirname(source_path))
    # A reprocess can add/move receipt files; drop the index so the very next
    # receipts-present / Receipt-Only fetch reflects them without the 300s TTL wait.
    _invalidate_receipt_index()
    result = process_pdf_document(source_path, label=label)
    # This document is now the most recently processed one — point
    # /recent_report.html at it regardless of how the pipeline run ends.
    # Set AFTER process_pdf_document so this report pointer is newer than the
    # intake record written inside it: a reprocessed document HAS a report.html
    # to show, so report mode must win the recency race.
    set_recent_report_pointer(report_url)
    result['report_url'] = report_url
    return result


# ── Expense-stored event bus ─────────────────────────────────────────────────
# Mazda calls POST /api/expense-stored after a successful store (STEP 8 in the
# scan message). The dashboard accumulates these lightweight events so the
# Reports tab can poll GET /api/expense-stored-events?since=<unix_ts> and
# reload any open report iframe to pick up newly-linked receipt markers.

_stored_expense_events = deque(maxlen=200)
_stored_expense_lock = threading.Lock()


def record_stored_expense(data):
    """Append one document-intake event (called from POST /api/expense-stored).

    Also drops the receipt-index cache so a receipt stored by this same intake is
    visible to the NEXT /api/receipts-present / Receipt-Only fetch the frontend makes
    when it reloads — no waiting out the 300s TTL, no manual refresh.

    `kind` distinguishes what changed so the frontend can refresh the right views:
      receipt   — a receipt was stored (default; row marker + Receipt-Only tab)
      statement — a bank statement was imported (transaction rows changed)
      reprocess — a document was re-run end to end
    `report_path`, when present, names the specific report.html that changed so the
    frontend can target just that view instead of reloading every open iframe.
    """
    _invalidate_receipt_index()
    event = {
        'stored_at': time.time(),
        'kind': (data.get('kind') or 'receipt'),
        'expense_id': data.get('expense_id'),
        'expense_date': data.get('expense_date', ''),
        'amount': data.get('amount', ''),
        'vendor_key': data.get('vendor_key', ''),
        'description': data.get('description', ''),
        'receipt_url': data.get('receipt_url', ''),
        'report_path': data.get('report_path', ''),
        'document_path': data.get('document_path', ''),
        'expense_ids': data.get('expense_ids') or [],
        'duplicate_expense_ids': data.get('duplicate_expense_ids') or [],
        'deposits_stored': data.get('deposits_stored') or 0,
        'parsed': data.get('parsed'),
        'stored': data.get('stored'),
        'doc_kind': data.get('doc_kind') or data.get('doc_type') or '',
        'vendor': data.get('vendor') or data.get('merchant') or '',
        # Preserve exact dispatch identity.  Reusable scanner filenames are
        # insufficient routing keys when an older conversation reports late.
        'conversation_id': data.get('conversation_id', ''),
        'dispatched_at': data.get('dispatched_at'),
    }
    with _stored_expense_lock:
        _stored_expense_events.append(event)
    # Keep /recent_report.html current. Best-effort: the callback must succeed
    # even if the recent-report bookkeeping can't.
    try:
        # Fold ids/counts into the last intake record so the synthetic recent
        # view can list this run's transactions.
        merge_recent_intake_event(event)
        # Only move the recent-report pointer when the event itself names its
        # source report (a real reprocess of that report's document) — NOT
        # when a report is merely found via date/amount coincidence. A
        # coincidental match (e.g. a scanned receipt whose expense happens to
        # land on the same date/amount as some row in an unrelated bank
        # statement) must never hijack "most recent" away from the actual
        # intake, or /recent_report.html shows that statement's full
        # transaction table instead of the scan's own 1-row view.
        rp = event['report_path']
        if rp:
            set_recent_report_pointer(rp)
    except Exception as exc:
        print(f'[expense-stored] recent-report update failed: {exc}')
    return {'ok': True}


def get_stored_expense_events(since_ts=0.0):
    """Return events stored after since_ts (unix float). Zero → return all."""
    with _stored_expense_lock:
        events = list(_stored_expense_events)
    return [e for e in events if e['stored_at'] > since_ts]


def _build_receipt_index():
    import re as _re
    name_re = _re.compile(r'_(\d{2})_(\d{2})_(\d{2})_(\d+)_(\d{2})\.[A-Za-z0-9]+$')
    by_da, by_stem = {}, {}
    seen = set()
    # Walk every receipt index subtree (canonical readable_documents/receipts plus
    # any external store such as the Windows-side live-pipeline destination). The
    # canonical tree is walked first, so a file present in both keeps its canonical
    # path (and dedupe below prevents the external copy from being added twice).
    for _prefix, _base, subtree in RECEIPT_MOUNTS:
        if not os.path.isdir(subtree):
            continue
        for root, _dirs, files in os.walk(subtree):
            for fn in files:
                fp = os.path.join(root, fn)
                rp = os.path.realpath(fp)
                if rp in seen:
                    continue
                seen.add(rp)
                by_stem.setdefault(os.path.splitext(fn)[0].lower(), []).append(fp)
                m = name_re.search(fn)
                if m:
                    mm, dd, yy, dol, cents = m.groups()
                    key = ('20%s-%s-%s' % (yy, mm, dd), '%s.%s' % (dol, cents))
                    by_da.setdefault(key, []).append(fp)
    return by_da, by_stem


def _receipt_index():
    now = time.time()
    if (_RECEIPT_INDEX_CACHE['by_da'] is None
            or now - _RECEIPT_INDEX_CACHE['ts'] > _RECEIPT_INDEX_TTL):
        by_da, by_stem = _build_receipt_index()
        _RECEIPT_INDEX_CACHE.update(ts=now, by_da=by_da, by_stem=by_stem)
    return _RECEIPT_INDEX_CACHE['by_da'], _RECEIPT_INDEX_CACHE['by_stem']


def _norm_amount(signed_amount):
    from decimal import Decimal, InvalidOperation
    raw = str(signed_amount or '').replace('$', '').replace(',', '').strip()
    try:
        return str(abs(Decimal(raw)))
    except (InvalidOperation, ValueError):
        return None


def _resolve_receipt_url_path(receipt_url):
    """Resolve one expense's non-empty receipt_url to a local receipt file.

    Searches every receipt mount (canonical readable_documents store + any external
    store such as the live-pipeline Windows destination), so a receipt_url that
    names a file in either tree resolves.
    """
    _by_da, by_stem = _receipt_index()
    ru = (receipt_url or '').strip().lstrip('/')
    if not ru:
        return None
    # Direct path under any serve base (path-traversal guarded).
    for _prefix, serve_base, _subtree in RECEIPT_MOUNTS:
        base = os.path.abspath(serve_base)
        direct = os.path.abspath(os.path.join(base, ru))
        if os.path.commonpath([direct, base]) == base and os.path.isfile(direct):
            return direct
    stem = os.path.splitext(os.path.basename(ru))[0].lower()
    if stem in by_stem:
        return by_stem[stem][0]
    # by_stem already indexes every basename under every receipt subtree. Do
    # not repeat recursive glob walks for missing files: a month can contain
    # dozens of stale receipt_url values and those redundant scans made the
    # Receipt Only page appear blank for 10+ seconds.
    return None


def _resolve_receipt_path(date_str, amount_str, receipt_url=None):
    """Legacy receipt-file resolver used by non-record-specific maintenance code."""
    by_da, _by_stem = _receipt_index()
    if date_str and amount_str:
        hits = by_da.get((date_str, amount_str))
        if hits:
            return hits[0]
    return _resolve_receipt_url_path(receipt_url)


def _resolve_expense_receipt_path(date_str, amount_str, receipt_url):
    """Resolve a receipt only for an expense that owns a non-empty receipt_url.

    Stored receipt_url values are not always byte-for-byte file paths, so after
    trying the URL directly we retain the established date/amount filename
    fallback. The non-empty URL guard is what prevents a receipt from leaking
    onto a different or receipt-less expense.
    """
    if not (receipt_url or '').strip():
        return None
    direct = _resolve_receipt_url_path(receipt_url)
    if direct:
        return direct
    by_da, _by_stem = _receipt_index()
    hits = by_da.get((date_str, amount_str)) if date_str and amount_str else None
    return hits[0] if hits else None


def _receipt_url_for_path(fp):
    """Build the dashboard URL that serves a receipt file, choosing the mount whose
    serve_base contains the file so external-store receipts get the right prefix."""
    ap = os.path.abspath(fp)
    for prefix, serve_base, _subtree in RECEIPT_MOUNTS:
        base = os.path.abspath(serve_base)
        if os.path.commonpath([ap, base]) == base:
            rel = os.path.relpath(ap, base)
            return prefix + '/' + '/'.join(quote(part) for part in rel.split(os.sep))
    # Fallback: canonical mount (preserves prior behaviour for unexpected paths).
    rel = os.path.relpath(ap, os.path.abspath(READABLE_DOCS_BASE))
    return ROL_FINANCES_RECEIPTS_URL_PREFIX + '/' + '/'.join(
        quote(part) for part in rel.split(os.sep))


def _select_matching_expense(rows, vendor_key, description):
    """Select one expense from same-date/same-amount candidates."""
    if not rows:
        return None
    if len(rows) == 1:
        chosen = rows[0]
    else:
        chosen = None
        vk = (vendor_key or '').strip()
        for r in rows:
            vp = _vendor_prefix(r.get('id_light'))
            if vk and vp and (vk.startswith(vp) or vp.startswith(vk)):
                chosen = r
                break
        if chosen is None and description:
            for r in rows:
                if (r.get('description') or '').strip() == description.strip():
                    chosen = r
                    break
        if chosen is None:
            chosen = rows[0]
    return chosen


def _matching_expense(cur, date_str, amount_str, vendor_key, description,
                      expense_id=None):
    """Return the expense matching a report row using the recategorization rules."""
    if expense_id not in (None, ''):
        try:
            eid = int(expense_id)
        except (TypeError, ValueError):
            return None
        cur.execute(
            "SELECT id, id_light, description, receipt_url, notes, expense_date, amount "
            "FROM expenses WHERE id=%s",
            (eid,),
        )
        return _select_matching_expense(cur.fetchall(), vendor_key, description)
    cur.execute(
        "SELECT id, id_light, description, receipt_url, notes, expense_date, amount "
        "FROM expenses WHERE expense_date=%s AND amount=%s "
        "AND expense_role <> 'LINE_ITEM'",
        (date_str, amount_str),
    )
    return _select_matching_expense(cur.fetchall(), vendor_key, description)


def _source_document_path(report_path, receipt_path=None):
    """Resolve the original statement document represented by a report URL."""
    raw = unquote((report_path or '').split('?', 1)[0])
    report_file = None
    split = _split_report_url(raw)
    if split:
        base, rel = split
        candidate = os.path.abspath(os.path.join(base, rel))
        base = os.path.abspath(base)
        if os.path.commonpath([candidate, base]) == base:
            report_file = candidate
    if report_file:
        directory = os.path.dirname(report_file)
        preferred = []
        for name in os.listdir(directory):
            fp = os.path.join(directory, name)
            ext = os.path.splitext(name)[1].lower()
            if os.path.isfile(fp) and ext in ('.pdf', '.xlsx', '.xls', '.csv'):
                preferred.append(fp)
        if preferred:
            priority = {'.pdf': 0, '.xlsx': 1, '.xls': 2, '.csv': 3}
            preferred.sort(key=lambda fp: (priority[os.path.splitext(fp)[1].lower()],
                                           os.path.basename(fp).lower()))
            return preferred[0]
        if os.path.isfile(report_file):
            return report_file
    return receipt_path or ''


def _document_machine_origin():
    import socket
    hostname = socket.gethostname().lower()
    return "Mom's machine" if 'rosemary' in hostname else 'Win 11'


def lookup_receipt(date_str, signed_amount, vendor_key, description='', report_path='',
                   expense_id=None):
    """Return receipt and source-document metadata for one report row."""
    amt = _norm_amount(signed_amount)
    if amt is None and expense_id in (None, ''):
        return {'ok': False, 'error': f'Bad amount: {signed_amount!r}'}
    chosen = None
    resolve_date = date_str
    try:
        with _rol_get_connection() as cnx:
            with cnx.cursor() as cur:
                chosen = _matching_expense(
                    cur, date_str, amt, vendor_key, description, expense_id)
                if chosen is not None and expense_id not in (None, ''):
                    resolve_date = str(chosen.get('expense_date') or date_str)
                    amt = _norm_amount(chosen.get('amount')) or amt
                if chosen is None and date_str and expense_id in (None, ''):
                    try:
                        base = datetime.strptime(date_str, '%Y-%m-%d').date()
                        for delta in (-1, 1, -2, 2, -3, 3):
                            alt = (base + timedelta(days=delta)).isoformat()
                            c = _matching_expense(cur, alt, amt, vendor_key, description)
                            if c:
                                chosen = c
                                resolve_date = alt
                                break
                    except (ValueError, AttributeError):
                        pass
    except Exception as e:
        return {'ok': False, 'error': f'DB error: {e}'}

    metadata = {
        'expense_id': chosen['id'] if chosen else '',
        'receipt_url': '',
        'receipt_path': '',
        'notes': (chosen.get('notes') or '') if chosen else '',
        'machine_origin': _document_machine_origin(),
        'source_document_path': _source_document_path(report_path),
    }
    if chosen is None:
        return dict(metadata, ok=False,
                    error='No matching expense in DB for that date/amount (bank-only row).')
    ru = (chosen.get('receipt_url') or '').strip()
    if not ru:
        return dict(metadata, ok=False, error='No receipt on file for this expense.')
    fp = _resolve_expense_receipt_path(resolve_date, amt, ru)
    if not fp:
        return dict(metadata, ok=False,
                    error=f'Receipt recorded ({ru}) but the file was not found on disk.')
    metadata.update(
        ok=True,
        receipt_url=_receipt_url_for_path(fp),
        receipt_path=fp,
        source_document_path=_source_document_path(report_path, fp),
    )
    return metadata


# ── ROL Finance: save a free-text note for a Verified-Transactions row ────────
# The "Set Category" dialog's notes textarea POSTs here on Close. Matches the same
# expense row recategorize_expense/lookup_receipt use, then writes expenses.notes.
def save_expense_notes(date_str, signed_amount, vendor_key, description, notes,
                       expense_id=None):
    amt = _norm_amount(signed_amount)
    if amt is None and expense_id in (None, ''):
        return {'ok': False, 'error': f'Bad amount: {signed_amount!r}'}
    try:
        with _rol_get_connection() as cnx:
            with cnx.cursor() as cur:
                chosen = _matching_expense(
                    cur, date_str, amt, vendor_key, description, expense_id)
                if chosen is None:
                    return {'ok': False,
                            'error': 'No matching expense in DB for that date/amount (bank-only row).'}
                cur.execute("UPDATE expenses SET notes=%s WHERE id=%s", (notes, chosen['id']))
    except Exception as e:
        return {'ok': False, 'error': f'DB error: {e}'}
    return {'ok': True, 'expense_id': chosen['id']}


def receipts_present(rows):
    """Given [{date, signed_amount, vendor_key, description}, ...] return
    {'ok': True, 'present': [bool, ...]} -- True where a receipt file resolves for the
    row. Drives the red 'has a receipt' corner marker. One FS index + one DB read total."""
    expense_map = {}
    try:
        with _rol_get_connection() as cnx:
            with cnx.cursor() as cur:
                cur.execute(
                    "SELECT id, expense_date, amount, id_light, description, receipt_url "
                    "FROM expenses"
                )
                for r in cur.fetchall():
                    key = (str(r['expense_date']), str(r['amount']))
                    expense_map.setdefault(key, []).append(r)
    except Exception:
        expense_map = {}
    out = []
    for row in rows or []:
        amt = _norm_amount(row.get('signed_amount'))
        date_str = (row.get('date') or '').strip()
        present = False
        if amt is not None:
            vk = row.get('vendor_key', '')
            desc = row.get('description', '')
            chosen = _select_matching_expense(
                expense_map.get((date_str, amt), []), vk, desc)
            resolve_date = date_str
            # Credit-card posting dates are often 1-3 days after the purchase date
            # stored in the DB (from the actual receipt). Try nearby dates when exact
            # lookup finds nothing.
            if chosen is None and date_str:
                try:
                    base = datetime.strptime(date_str, '%Y-%m-%d').date()
                    for delta in (-1, 1, -2, 2, -3, 3):
                        alt = (base + timedelta(days=delta)).isoformat()
                        candidates = expense_map.get((alt, amt), [])
                        if candidates:
                            c = _select_matching_expense(candidates, vk, desc)
                            if c:
                                chosen = c
                                resolve_date = alt
                                break
                except (ValueError, AttributeError):
                    pass
            ru = (chosen.get('receipt_url') or '').strip() if chosen else ''
            present = bool(_resolve_expense_receipt_path(resolve_date, amt, ru))
        out.append(present)
    return {'ok': True, 'present': out}


# ── ROL Finance: "Receipt Only" tab ───────────────────────────────────────────
# Receipts that are NOT associated with any bank-statement transaction. A receipt is
# "on a statement" when its expense's (date, abs amount) matches a row in the
# `transactions` table (the imported bank-statement lines). Receipt-only records are
# expenses that have no such transactions match — typically cash/other purchases
# evidenced only by a receipt. They are real `expenses` rows, so the SAME category
# picker (/api/recategorize-expense) and View Receipt (/api/receipt-lookup) the
# per-statement reports use work here unchanged. Per the spec these never go into an
# individual document's report.html (they have no document association); they live
# only on this synthetic page.
#
# Membership requires an ACTUAL receipt file to resolve (via _resolve_receipt_path —
# the same test that drives the red "has-receipt" corner marker), NOT merely a
# non-empty expenses.receipt_url: ~48 rows carry a receipt_url whose file is missing
# on disk (the known data gap) and must be excluded so every row shown has a receipt
# (and a marker). This also catches rows whose receipt_url is blank but whose receipt
# file is still found by (date, amount).
def _reporting_category_for_id(category_id, parent_of):
    """Walk a leaf category_id up its parent chain to a reporting-bucket name."""
    seen = set()
    cur = category_id
    while cur is not None and cur not in seen:
        seen.add(cur)
        name = REPORTING_CATEGORY_ANCESTOR_MAP.get(cur)
        if name:
            return name
        cur = parent_of.get(cur)
    return 'Uncategorized'


def _fetch_receipt_only_rows(month_key=None):
    """expenses with no matching bank-statement transaction (same date + abs amount)
    AND a receipt file that actually resolves on disk, each tagged with its current
    reporting category. The resolve check keeps the tab in lockstep with the red
    has-receipt marker so every row shown genuinely has a receipt."""
    # January is the intentionally special all-year receipt display. Every
    # other configured month is restricted to its own calendar date range.
    month_range = None if month_key == ROL_FINANCES_REPORTS_DEFAULT_MONTH else \
        ROL_FINANCES_MONTH_RANGES.get(month_key)
    date_clause = ''
    date_params = ()
    if month_range:
        date_clause = ' AND e.expense_date BETWEEN %s AND %s'
        date_params = month_range
    with _rol_get_connection() as cnx:
        with cnx.cursor() as cur:
            cur.execute('SELECT id, parent_id FROM categories')
            parent_of = {
                int(r['id']): (int(r['parent_id']) if r['parent_id'] is not None else None)
                for r in cur.fetchall()
            }
            cur.execute(
                "SELECT e.id, e.expense_date, e.amount, e.id_light, e.description, "
                "       e.category_id, e.receipt_url, e.expense_role "
                "FROM expenses e "
                "WHERE e.expense_role <> 'PARENT' "
                "AND NOT EXISTS (SELECT 1 FROM transactions t "
                "                  WHERE t.transaction_date=e.expense_date "
                "                    AND ABS(t.amount)=ABS(e.amount)) "
                f"{date_clause} "
                "ORDER BY e.expense_date, e.id",
                date_params,
            )
            rows = cur.fetchall()
    out = []
    for r in rows:
        date_str = str(r['expense_date'])
        amt = _norm_amount(r['amount'])
        if amt is None:
            continue
        # Only include rows whose receipt file actually exists (same resolution the
        # has-receipt marker uses). Excludes the receipt_url-but-no-file data gap.
        if not _resolve_expense_receipt_path(date_str, amt, r.get('receipt_url')):
            continue
        cid = r.get('category_id')
        rep = _reporting_category_for_id(
            int(cid) if cid is not None else None, parent_of)
        out.append({
            'id': int(r['id']),
            'date': date_str,
            'amount': str(r['amount']),
            'vendor_key': (r.get('id_light') or '').strip(),
            'description': (r.get('description') or '').strip(),
            'reporting_category': rep,
            'cat_class': REPORTING_CATEGORY_CLASS.get(rep, 'cat-uncategorized'),
        })
    return out


# ── ROL Finance: recently-scanned queue + green/yellow month status ──────────
# A scanned receipt becomes an `expenses` row (created_at auto-set on INSERT), so
# "recently scanned, newest first" is just ORDER BY created_at DESC — no separate
# queue store is needed. An expense has "unfinished business" while it is still
# uncategorized; setting its category (via /api/recategorize-expense) resolves it.
# Uncategorized == category_id NULL, or 1/364 which both resolve to 'Uncategorized'
# in REPORTING_CATEGORY_ANCESTOR_MAP (the same buckets the picker's "Uncategorized"
# choice writes back, i.e. category_id -> None).
_UNCATEGORIZED_CATEGORY_IDS = (1, 364)


def _is_uncategorized(category_id):
    """True when an expense row still needs a category (the 'unfinished' state)."""
    return category_id is None or int(category_id) in _UNCATEGORIZED_CATEGORY_IDS


def _rol_finance_categories():
    """The reporting-category palette (name/cls/bg/fg) in display order for the
    New Records 'Set Category' dialog. Built from the same maps
    /api/recategorize-expense validates against, so the picker never offers a
    category the writer would reject."""
    cats = []
    for name, cls in REPORTING_CATEGORY_CLASS.items():
        bg, fg = REPORTING_CATEGORY_STYLE.get(name, ('#BFBFBF', '#000000'))
        cats.append({'name': name, 'cls': cls, 'bg': bg, 'fg': fg})
    return cats


def _fetch_recent_scans(limit=5, month_key=None):
    """The most-recently-scanned expenses that are still uncategorized, newest
    first — the 'recently scanned viewing area'. Returning only up to `limit`
    unfinished rows IS the 'keep the view at <=5, backfill the next one' rule:
    as each row gets categorized it drops out and the next surfaces. Also returns
    queue_total = how many uncategorized rows are waiting overall."""
    limit = max(1, min(int(limit or 5), 50))
    month_range = ROL_FINANCES_MONTH_RANGES.get(month_key)
    where_suffix = ''
    where_params = ()
    if month_range:
        where_suffix = ' AND expense_date BETWEEN %s AND %s'
        where_params = month_range
    with _rol_get_connection() as cnx:
        with cnx.cursor() as cur:
            cur.execute(
                "SELECT id, id_light, description, expense_date, amount, "
                "       category_id, receipt_url, created_at, notes "
                "FROM expenses "
                "WHERE (category_id IS NULL OR category_id IN (%s, %s))"
                " AND expense_role <> 'PARENT'"
                f"{where_suffix} "
                "ORDER BY created_at DESC, id DESC LIMIT %s",
                (*_UNCATEGORIZED_CATEGORY_IDS, *where_params, limit),
            )
            rows = cur.fetchall()
            cur.execute(
                "SELECT COUNT(*) AS n FROM expenses "
                "WHERE (category_id IS NULL OR category_id IN (%s, %s))"
                " AND expense_role <> 'PARENT'"
                f"{where_suffix}",
                (*_UNCATEGORIZED_CATEGORY_IDS, *where_params),
            )
            total = int(cur.fetchone()['n'])
    out = []
    for r in rows:
        date_str = str(r['expense_date'])
        amt = _norm_amount(r['amount'])
        # Why this record is in "New Records": prefer a specific note written by
        # the intake pipeline / Mazda (expenses.notes); otherwise the generic
        # reason it lands here — categorization never completed.
        notes = (r.get('notes') or '').strip()
        reason = notes or (
            'Categorization incomplete — no reporting category was assigned. '
            'Pick one, or ask Mazda how to resolve it.')
        out.append({
            'id': int(r['id']),
            'vendor_key': _vendor_prefix(r.get('id_light')),
            'id_light': (r.get('id_light') or '').strip(),
            'description': (r.get('description') or '').strip(),
            'expense_date': date_str,
            'amount': str(r['amount']),
            'created_at': str(r.get('created_at') or ''),
            'reporting_category': 'Uncategorized',
            'reason': reason,
            'receipt_present': bool(
                _resolve_expense_receipt_path(date_str, amt, r.get('receipt_url'))
                if amt is not None else False),
        })
    return {'rows': out, 'queue_total': total, 'limit': limit, 'month_key': month_key}


def _fetch_month_status():
    """Per-month green/yellow status for the report month tabs. A month is
    'yellow' (work to do) when its most-recently-scanned expense is still
    uncategorized, else 'green'. Keys off the most-recent scan to match the
    spec: the tab reacts to the newest document's unfinished business."""
    result = []
    with _rol_get_connection() as cnx:
        with cnx.cursor() as cur:
            for month_key, (start, end) in ROL_FINANCES_MONTH_RANGES.items():
                cur.execute(
                    "SELECT id, id_light, description, expense_date, amount, "
                    "       category_id, created_at "
                    "FROM expenses WHERE expense_date BETWEEN %s AND %s "
                    "AND expense_role <> 'PARENT' "
                    "ORDER BY created_at DESC, id DESC LIMIT 1",
                    (start, end),
                )
                newest = cur.fetchone()
                cur.execute(
                    "SELECT COUNT(*) AS n FROM expenses "
                    "WHERE expense_date BETWEEN %s AND %s "
                    "AND expense_role <> 'PARENT' "
                    "AND (category_id IS NULL OR category_id IN (%s, %s))",
                    (start, end, *_UNCATEGORIZED_CATEGORY_IDS),
                )
                uncat = int(cur.fetchone()['n'])
                if newest is None:
                    status = 'green'
                    most_recent = None
                else:
                    unfinished = _is_uncategorized(newest.get('category_id'))
                    status = 'yellow' if unfinished else 'green'
                    most_recent = {
                        'id': int(newest['id']),
                        'vendor_key': _vendor_prefix(newest.get('id_light')),
                        'description': (newest.get('description') or '').strip(),
                        'expense_date': str(newest['expense_date']),
                        'amount': str(newest['amount']),
                        'uncategorized': unfinished,
                    }
                result.append({
                    'month_key': month_key,
                    'status': status,
                    'uncategorized_count': uncat,
                    'most_recent_unfinished': most_recent,
                })
    return result


def _receipt_only_picker_assets():
    """The category-picker dialog markup/CSS reused verbatim from the report.html
    injector, so the Receipt Only tab behaves identically to Verified Transactions."""
    import importlib
    import sys as _sys
    if VERIFICATION_LIB not in _sys.path:
        _sys.path.insert(0, VERIFICATION_LIB)
    rv = importlib.import_module('restructure_verified_transactions')
    return rv.CATEGORY_PICKER_CSS, rv.CATEGORY_PICKER_HTML, rv.CLICKABLE_ROW_CSS


def _receipt_only_cat_css():
    lines = []
    for name, cls in REPORTING_CATEGORY_CLASS.items():
        bg, fg = REPORTING_CATEGORY_STYLE.get(name, ('#BFBFBF', '#000000'))
        lines.append(
            '    #verified-transactions tbody tr.%s td { background:%s; color:%s; }'
            % (cls, bg, fg))
    return '\n'.join(lines)


def build_receipt_only_report_html(month_key=None):
    """A standalone, same-origin report page for receipt-only records. Mirrors the
    restructured Verified Transactions table (Description | Amount | Date, clickable
    rows with data-* attrs) and embeds the identical category picker, so the existing
    /api/receipts-present marker, /api/recategorize-expense and /api/receipt-lookup
    all drive it without change."""
    from html import escape as _esc
    picker_css, picker_html, click_css = _receipt_only_picker_assets()
    rows = _fetch_receipt_only_rows(month_key)
    trs = []
    for r in rows:
        trs.append(
            '<tr class="%s" data-expense-id="%s" data-vendor-key="%s" data-description="%s" '
            'data-signed-amount="%s" data-date="%s" onclick="openCategoryPicker(this)" '
            'title="Click row to set category / view receipt">'
            '<td>%s</td><td class="number">%s</td><td>%s</td></tr>' % (
                r['cat_class'],
                _esc(r['id'], quote=True),
                _esc(r['vendor_key'], quote=True),
                _esc(r['description'], quote=True),
                _esc(r['amount'], quote=True),
                _esc(r['date'], quote=True),
                _esc(r['description']), _esc(r['amount']), _esc(r['date']),
            ))
    body_rows = '\n'.join(trs) if trs else (
        '<tr><td colspan="3" class="muted">No receipt-only records.</td></tr>')
    head = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Receipt Only</title><style>\n'
        '    body { font-family: Arial, sans-serif; margin:0; padding:20px; '
        'background:#f1f5f9; color:#0f172a; }\n'
        '    section.card { background:#fff; border-radius:12px; padding:18px 20px; '
        'margin:0 auto; max-width:1100px; box-shadow:0 1px 3px rgba(0,0,0,.08); }\n'
        '    h1 { font-size:1.4rem; margin:0 0 4px; } h2 { font-size:1.1rem; margin:18px 0 8px; }\n'
        '    table { width:100%; border-collapse:collapse; overflow:hidden; '
        'border-radius:12px; font-size:0.95rem; }\n'
        '    th, td { padding:8px 10px; border-bottom:1px solid #e5e7eb; text-align:left; }\n'
        '    th { background:#0f172a; color:#fff; }\n'
        '    th.number, td.number { text-align:right; }\n'
        '    .muted { color:#6b7280; }\n'
        + _receipt_only_cat_css() + '\n'
        + click_css + '\n'
        + picker_css + '\n'
        '  </style></head><body>\n'
        '<section class="card">\n'
        '  <h1>Receipt Only</h1>\n'
        '  <p class="muted">Receipts not associated with any bank-statement '
        'transaction. Click a row to set its category or view the receipt.</p>\n'
        '  <h2>Verified Transactions</h2>\n'
        '  <table id="verified-transactions"><thead><tr>'
        '<th>Description</th><th class="number">Amount</th><th>Date</th>'
        '</tr></thead><tbody>\n'
    )
    return head + body_rows + '\n</tbody></table>\n</section>\n' + picker_html + '\n</body></html>'


# Letta API base URL — override with LETTA_BASE_URL env var
LETTA_BASE_URL = os.environ.get('LETTA_BASE_URL', 'http://100.80.49.10:8283').rstrip('/')

# Model handles selectable per-agent from Input Options. These are the ONLY
# handles the chatgpt-plus-pro (Codex OAuth) provider accepts — verified
# 2026-07-08 by probing chatgpt.com/backend-api/codex/responses directly:
# every other handle (gpt-5.3, gpt-5.2, all *-codex variants) returns
# "model is not supported when using Codex with a ChatGPT account".
AGENT_MODEL_OPTIONS = [
    'chatgpt-plus-pro/gpt-5.5',
    'chatgpt-plus-pro/gpt-5.4',
    'chatgpt-plus-pro/gpt-5.4-mini',
]

AGENT_VOICE_OPTIONS = [
    'en-US-AnaNeural',
    'en-US-AriaNeural',
    'en-US-AvaNeural',
    'en-US-AvaMultilingualNeural',
    'en-US-EmmaNeural',
    'en-US-EmmaMultilingualNeural',
    'en-US-JennyNeural',
    'en-US-MichelleNeural',
    'en-US-AndrewNeural',
    'en-US-BrianNeural',
    'en-US-ChristopherNeural',
    'en-US-EricNeural',
    'en-US-GuyNeural',
    'en-US-RogerNeural',
    'en-US-SteffanNeural',
]
AGENT_VOICE_METADATA_KEY = 'dashboard_voice'

def agent_model_options(current_handle):
    """Dropdown options for an agent: the vetted Codex handles, plus the
    agent's own handle at the top when it's on another provider (lc-gemini,
    etc.) so the dropdown never lies about the current state."""
    options = list(AGENT_MODEL_OPTIONS)
    if current_handle and current_handle not in options:
        options.insert(0, current_handle)
    return options

def agent_voice_from_metadata(agent_data):
    """Return a valid dashboard voice stored on the Letta agent, or ''."""
    meta = (agent_data or {}).get('metadata') or {}
    if not isinstance(meta, dict):
        return ''
    voice = meta.get(AGENT_VOICE_METADATA_KEY) or ''
    return voice if voice in AGENT_VOICE_OPTIONS else ''

def agent_voice_payload(agent_id):
    """Read one agent's dashboard voice preference from Letta metadata."""
    lid = letta_id_for(agent_id)
    if not lid:
        return {'ok': False, 'error': 'not a Letta agent',
                'voice': '', 'options': AGENT_VOICE_OPTIONS}
    data = letta_get(f'/v1/agents/{lid}', timeout=15) or {}
    return {'ok': True, 'voice': agent_voice_from_metadata(data),
            'options': AGENT_VOICE_OPTIONS}

def patch_agent_voice(agent_id, voice):
    """Persist one agent's dashboard voice preference in Letta metadata."""
    lid = letta_id_for(agent_id)
    if not lid:
        return {'ok': False, 'error': 'not a Letta agent'}
    voice = voice or ''
    if voice and voice not in AGENT_VOICE_OPTIONS:
        return {'ok': False, 'error': f'voice {voice!r} is not in the allowed list'}

    cur = letta_get(f'/v1/agents/{lid}', timeout=15) or {}
    meta = cur.get('metadata') or {}
    if not isinstance(meta, dict):
        meta = {}
    meta = dict(meta)
    if voice:
        meta[AGENT_VOICE_METADATA_KEY] = voice
    else:
        meta.pop(AGENT_VOICE_METADATA_KEY, None)

    req = urllib.request.Request(
        f'{LETTA_BASE_URL}/v1/agents/{lid}',
        data=json.dumps({'metadata': meta}).encode(),
        headers={'Content-Type': 'application/json'},
        method='PATCH',
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read().decode())
    return {'ok': True, 'voice': agent_voice_from_metadata(resp)}

# Agents that are wired to the Letta API automatically.
# Add any new Letta agent here: { 'name': '...', 'id': '<real-letta-agent-id>' }
# Set 'id' to None to auto-discover by name from the Letta agent list.
_MINION_TOOLS = ['run_claude_code_sdk']
# Mazda's health is signalled by her self-improvement MCP tools (served by
# mazda-tools-mcp.service on :8791) — they attach/detach together, so requiring a
# few core ones cleanly flags an unprovisioned Mazda (e.g. the MCP server down)
# without flapping. NOTE: do NOT require relay_message_to_chatgpt — that's a
# browser-relay tool from a discarded design; this incarnation of Mazda does not
# carry it (verified live: her tools are record_trace/propose_improvement/
# run_experiment/judge_trace/gate_check/activate_wrapper/rollback_wrapper/
# load_wrapper_revision/propose_memory_note/verify_statement_totals).
_MAZDA_TOOLS = [
    'record_trace',
    'propose_improvement',
    'run_experiment',
    'itemize_existing_expense',
]

# Mazda + all 5 minions run on the same chatgpt-plus-pro OAuth account, so a
# ChatGPT/Codex rate limit (HTTP 429 from chatgpt.com/backend-api/codex/responses)
# hits all of them simultaneously — see mazda_chatgpt_429_rate_limit_2026_06_18
# memory. Tagging them lets _poll_chatgpt_provider_once() turn every one of
# their tabs red from a single canary probe instead of needing a manual Test
# send against each agent first.
CHATGPT_PLUS_PRO = 'chatgpt-plus-pro'

LETTA_AGENTS = [
    {'name': 'Scissari', 'id': 'agent-5955b0c2-7922-4ffe-9e43-b116053b80fa'},
    {'name': 'Frita',    'id': 'agent-881a883f-edd0-4963-bf67-6ef178b8f018', 'uses_claude_sdk': True},
    {'name': 'Hailey',   'id': 'agent-2b4f760c-e22a-4b6a-9c8d-0ace7b9bac03'},
    {'name': 'Jeri',     'id': None},
    {'name': 'Mazda',    'id': 'agent-6b536cf4-ec88-4290-b595-fed21d14bd8e', 'required_tools': _MAZDA_TOOLS, 'llm_provider': CHATGPT_PLUS_PRO, 'orchestrator': True},
    {'name': 'Mazda Router',           'id': 'agent-bc561f63-a5bd-4192-806e-58d92593da2b', 'required_tools': _MINION_TOOLS, 'llm_provider': CHATGPT_PLUS_PRO},
    {'name': 'Mazda Parser',           'id': 'agent-a5063757-46c7-4054-a07d-2b1263db43a8', 'required_tools': _MINION_TOOLS, 'llm_provider': CHATGPT_PLUS_PRO, 'provider_canary': True},
    {'name': 'Mazda Vendor Identity',  'id': 'agent-acd624ac-17f2-4a74-aa34-78036cac4d66', 'required_tools': _MINION_TOOLS, 'llm_provider': CHATGPT_PLUS_PRO},
    {'name': 'Mazda Receipt Linker',   'id': 'agent-9a14f800-d848-4914-bfd4-53ab62bc177b', 'required_tools': _MINION_TOOLS, 'llm_provider': CHATGPT_PLUS_PRO},
    {'name': 'Mazda Categorization',   'id': 'agent-c429ff25-c8af-4f1a-a6f1-6d48307e2874', 'required_tools': _MINION_TOOLS, 'llm_provider': CHATGPT_PLUS_PRO, 'provider_canary': True},
    {'name': 'Suzuki',                 'id': 'agent-c4e58e29-8c06-4ca9-a18d-b8536442af13', 'orchestrator': True, 'llm_provider': CHATGPT_PLUS_PRO},
    {'name': 'Suzuki Router',          'id': 'agent-df4deb48-3a46-4fe4-887a-6aeb95ddc6d6', 'llm_provider': CHATGPT_PLUS_PRO},
    {'name': 'Suzuki Reproducer',      'id': 'agent-ad0c3e39-bd14-4f79-af95-140e4cf21325', 'llm_provider': CHATGPT_PLUS_PRO},
    {'name': 'Suzuki Static Analysis', 'id': 'agent-a820e191-bc39-413c-bb0c-6344d5b37643', 'llm_provider': CHATGPT_PLUS_PRO},
    {'name': 'Suzuki Patch',           'id': 'agent-2c585993-1193-42d8-9bf5-1805b426a0da', 'llm_provider': CHATGPT_PLUS_PRO},
    {'name': 'Suzuki Test Runner',     'id': 'agent-a90f1413-6599-4750-b7e0-ee55634984162', 'llm_provider': CHATGPT_PLUS_PRO},
    {'name': 'Suzuki Regression',      'id': 'agent-8af8fec4-5114-40b3-99ab-173edd35ebd2', 'llm_provider': CHATGPT_PLUS_PRO},
]

# Cache of name→id resolved from the Letta API
_letta_id_cache = {}
_letta_id_cache_lock = threading.Lock()
# When the full roster was last fetched. A registry name absent from the server
# (e.g. a renamed/deleted agent) must not re-trigger the ~12s roster fetch on
# every lookup — within this window a cache miss is answered None without I/O.
_letta_roster_fetched_at = 0.0
LETTA_ROSTER_NEG_TTL = 300
_agent_list_cache = {'value': None, 'ts': 0.0}
_agent_list_cache_lock = threading.Lock()
AGENT_LIST_CACHE_TTL = 300

_agent_activity_cache = {'value': None, 'ts': 0.0}
_agent_activity_cache_lock = threading.Lock()
# Even fetched in parallel, an 11-agent sweep over the DERP-relayed Letta API
# (reference_tailscale_derp_relay_100_80_49_10) takes ~30s. The frontend polls
# every 5s, so without a lock + cache, each poll would kick off its own
# overlapping 30s sweep. The lock makes concurrent pollers share one sweep;
# the TTL (longer than a sweep) lets most polls skip the network entirely.
AGENT_ACTIVITY_CACHE_TTL = 30


AGENT_CARDS = {
    'Scissari': {
        'identity': 'Scissari',
        'role': 'Lead coordination and execution agent focused on cross-agent orchestration, dashboard work, and operational follow-through.',
        'responsibilities': [
            'Coordinate multi-agent tasks and user-facing follow-up',
            'Drive dashboard and observability improvements',
            'Track execution flow across agents and tools',
        ],
        'tools': [
            'Letta agent messaging',
            'executor_run / host command execution',
            'dashboard inspection and API verification',
        ],
        'memory_summary': 'Maintains durable project context and coordination state so shared workflows stay consistent across sessions.',
    },
    'Frita': {
        'identity': 'Frita',
        'role': 'Infrastructure and deployment agent for the Windows 10 dashboard host and public exposure path.',
        'responsibilities': [
            'Publish and repair dashboard hosting on the Win10 machine',
            'Inspect live services, tunnels, and dashboard backends',
            'Deploy and verify dashboard/API fixes end-to-end',
        ],
        'tools': [
            'win10_run',
            'cloudflared / tunnel operations',
            'host file and process inspection',
        ],
        'memory_summary': 'Keeps operational knowledge about the Win10 dashboard environment, serving paths, and tunnel setup.',
    },
    'Hailey': {
        'identity': 'Hailey',
        'role': 'Support agent available for collaboration and delegated operational tasks.',
        'responsibilities': [
            'Assist with shared task execution',
            'Provide agent-side support when routed work is assigned',
        ],
        'tools': [
            'Letta messaging and standard agent workflows',
        ],
        'memory_summary': 'Participates in the shared agent ecosystem with retained project context when available.',
    },
    'Jeri': {
        'identity': 'Jeri',
        'role': 'Financial analyst agent focused on finance workflows, document interpretation, and structured operational guidance.',
        'responsibilities': [
            'Support January and finance-analysis workflows',
            'Interpret financial material and process-related inputs',
            'Participate in A2A-oriented coordination flows',
        ],
        'tools': [
            'A2A messaging patterns',
            'finance workflow guidance',
            'dashboard-driven visibility and control surfaces',
        ],
        'memory_summary': 'Designed as a specialized analyst persona with persistent behavioral and workflow guidance.',
    },
    'Mazda': {
        'identity': 'Mazda',
        'role': 'Self-improving engineering/operations agent focused on thoughtful execution and clearer agent self-description.',
        'responsibilities': [
            'Execute assigned technical tasks',
            'Improve agent-facing structure and usability',
            'Help define clearer agent identity and card patterns',
        ],
        'tools': [
            'Agent messaging',
            'technical execution workflows',
            'structured self-description patterns',
        ],
        'memory_summary': 'Uses retained context to refine its own behavior and improve the system around it over time.',
    },
    'Claude': {
        'identity': 'Claude',
        'role': 'External coding collaborator represented in the dashboard for shared visibility.',
        'responsibilities': [
            'Contribute code-focused implementation and analysis',
            'Coordinate with the local agent ecosystem when integrated',
        ],
        'tools': [
            'Code editing and analysis workflows',
            'shared dashboard visibility',
        ],
        'memory_summary': 'Not a Letta-backed agent here, but included as a visible collaborator in the dashboard ecosystem.',
    },
    'Suzuki': {
        'identity': 'Suzuki',
        'role': 'Self-improving software debugging orchestrator — triages bugs, delegates to specialist minions, verifies patches, and learns across runs.',
        'responsibilities': [
            'Receive bug reports and run the 12-stage debug workflow',
            'Delegate triage, reproduction, static analysis, patching, test execution, and regression checking to specialist minions',
            'Record traces and propose wrapper improvements after each run',
        ],
        'tools': [
            'DebugStageEnvelope handoff contract',
            'executor_run / host command execution',
            'self-improvement MCP tools (record_trace, propose_improvement, run_experiment)',
        ],
        'memory_summary': 'Accumulates debugging lessons across runs via the shared self-improvement kernel inherited from Mazda.',
    },
}


# Per-agent system message files, shown verbatim on the agent's Agent Card tab.
AGENT_SYSTEM_MESSAGE_FILES = {
    'Mazda': os.path.expanduser('~/rol_finances/external_agents/mazda/system_message.xml'),
}


def build_agent_card(agent_name, agent_id):
    card = AGENT_CARDS.get(agent_name, {
        'identity': agent_name,
        'role': 'Agent in the shared dashboard ecosystem.',
        'responsibilities': [],
        'tools': [],
        'memory_summary': 'No card details have been filled in yet.',
    }).copy()
    card['agent_id'] = agent_id
    card['name'] = agent_name
    system_message_path = AGENT_SYSTEM_MESSAGE_FILES.get(agent_name)
    if system_message_path:
        try:
            with open(system_message_path, 'r') as f:
                card['system_message'] = f.read()
        except OSError:
            pass
    return card

# Claude Code log files (persistent, local)
CLAUDE_LOG_FILE = os.path.join(HERE, 'claude_messages.json')
CLAUDE_TOOL_LOG_FILE = os.path.join(HERE, 'claude_toolcalls.json')
_claude_log_lock = threading.Lock()
_claude_tool_log_lock = threading.Lock()

# Voice transcripts (raw whisper vs. cleaned) — for diagnosing mishears.
VOICE_LOG_FILE = os.path.join(HERE, 'voice_transcripts.json')
_voice_log_lock = threading.Lock()

# Voice OUTPUT (text-to-speech) — the agents speak with the same edge-tts
# voice the pickle_cpp scoreboard uses (en-GB-SoniaNeural, see
# rpi-rgb-led-matrix/pickle_cpp/tools/generate_placeholder_sounds.py).
# Like whisper, we shell out to the CLI so the server stays stdlib-only.
EDGE_TTS_BIN = os.environ.get(
    'EDGE_TTS_BIN', os.path.expanduser('~/.local/bin/edge-tts'))
EDGE_TTS_VOICE = os.environ.get('EDGE_TTS_VOICE', 'en-GB-SoniaNeural')
EDGE_TTS_TIMEOUT_SEC = int(os.environ.get('EDGE_TTS_TIMEOUT_SEC', 30))
TTS_MAX_TEXT_LEN = 4000
TTS_CACHE_DIR = os.environ.get('TTS_CACHE_DIR', '/tmp/dashboard_tts_cache')
_VOICE_NAME_RE = re.compile(r'^[A-Za-z]{2}-[A-Za-z]{2,}-[A-Za-z0-9]+$')


def tts_cache_path(text, voice):
    """Deterministic cache file for a (voice, text) pair (pure)."""
    key = hashlib.sha256(f'{voice}\x00{text}'.encode('utf-8')).hexdigest()
    return os.path.join(TTS_CACHE_DIR, f'{voice}_{key[:32]}.mp3')


def synthesize_speech(text, voice=None, runner=subprocess.run):
    """Text → MP3 file via edge-tts; returns {ok, path, cached} or {ok:False, error}.

    `runner` is injected so tests never hit the network. Results are cached by
    (voice, text) hash — repeated phrases (agent names, short acks) are served
    from disk instantly.
    """
    text = (text or '').strip()
    if not text:
        return {'ok': False, 'error': 'empty text'}
    if len(text) > TTS_MAX_TEXT_LEN:
        text = text[:TTS_MAX_TEXT_LEN]
    voice = voice or EDGE_TTS_VOICE
    if not _VOICE_NAME_RE.match(voice):
        return {'ok': False, 'error': f'invalid voice name: {voice!r}'}

    path = tts_cache_path(text, voice)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return {'ok': True, 'path': path, 'cached': True}

    if not os.path.exists(EDGE_TTS_BIN):
        return {'ok': False, 'error': f'edge-tts binary not found: {EDGE_TTS_BIN}'}
    os.makedirs(TTS_CACHE_DIR, exist_ok=True)
    tmp_path = f'{path}.tmp{os.getpid()}'
    try:
        proc = runner(
            [EDGE_TTS_BIN, '--voice', voice, '--text', text,
             '--write-media', tmp_path],
            capture_output=True, text=True, timeout=EDGE_TTS_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': f'edge-tts timed out after {EDGE_TTS_TIMEOUT_SEC}s'}
    except Exception as exc:
        return {'ok': False, 'error': f'edge-tts failed to run: {exc}'}
    if proc.returncode != 0 or not os.path.exists(tmp_path) \
            or os.path.getsize(tmp_path) == 0:
        err = (proc.stderr or '').strip() or f'exit {proc.returncode}'
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return {'ok': False, 'error': f'edge-tts failed: {err[:300]}'}
    os.replace(tmp_path, path)  # atomic — concurrent requests can't collide
    return {'ok': True, 'path': path, 'cached': False}

# Port this dashboard is served on (also used for the dashboard self-health check).
PORT = int(os.environ.get('PORT', 8765))

# The executor server runs LOCALLY on this same machine (started by the
# `start_executor_server` alias in ~/.bashrc -> ~/server_tools/start_executor_server.sh,
# which launches the REST executor on :8787 and the MCP front door on :8789).
# We launch the script directly (no SSH) and tail its combined output here.
EXECUTOR_START_SCRIPT = os.path.expanduser('~/server_tools/start_executor_server.sh')
EXECUTOR_STARTUP_LOG = '/tmp/executor_startup.log'

# The Logger API's mysql + php-api containers live on the same Win10 box as the
# Letta server (100.80.49.10) but aren't part of the letta-src compose project,
# so they don't auto-restart on reboot — see [[reference_logger_api_ops]].
# `start_logger_api.sh` (deployed to ~/server_tools/ on that box) runs
# `docker-compose up -d` in ~/logger-api and re-injects the Apache rewrite
# config the PHP front controller needs (lost whenever the container is
# recreated). We launch it over SSH (same host/auth as the Letta log puller)
# and tail its combined output into a local cache, just like the executor.
LOGGER_API_START_SCRIPT = '~/server_tools/start_logger_api.sh'
LOGGER_API_STARTUP_LOG = '/tmp/logger_api_startup.log'

# Frita's executor runs as a Docker container on the Win10 box (100.80.49.10),
# joined to the letta-src_default network so letta-server can reach it by DNS
# name.  Port 8787 is internal to the Docker network; 8797 is published to the
# Win10 host so we can health-check it from here.
FRITA_EXECUTOR_DEPLOY_SCRIPT = '~/server_tools/deploy_frita_executor.sh'
FRITA_EXECUTOR_STARTUP_LOG = '/tmp/frita_executor_startup.log'

# This dashboard restarts itself via its own systemd --user unit (see the
# "Re-start Dashboard Server" button on the Dashboard Server tab).
DASHBOARD_SYSTEMD_UNIT = 'dashboard-server.service'
DASHBOARD_RESTART_LOG = '/tmp/dashboard_restart.log'

# The Letta server itself runs in Docker on the Win10 box (100.80.49.10), so we
# can't tail its log locally — a background thread periodically pulls it over
# SSH (passwordless key auth + passwordless sudo, both already set up on that
# box for the `adamsl` account) into a local cache file that the existing
# log_file/tail_lines machinery can serve like any other server's log.
#
# `pull_letta_server_logs.sh` (deployed to ~/server_tools/ on the box) resolves
# WHICH container is actually serving :8283 by content-sniffing recently-written
# json-logs for Letta's `Letta.<module> - LEVEL - ...` lines, rather than
# assuming the name `letta-server` — see [[reference_letta_server_docker_architecture]]:
# docker-proxy on that box has repeatedly forwarded :8283 to an *untracked*
# orphaned containerd task while the docker-ps-visible `letta-server` sits idle,
# so `docker logs letta-server` would silently show the wrong (dead-quiet) process.
LETTA_DOCKER_HOST = os.environ.get('LETTA_DOCKER_HOST', 'adamsl@100.80.49.10')
LETTA_REMOTE_LOG_PULL_SCRIPT = '~/server_tools/pull_letta_server_logs.sh'
LETTA_REMOTE_LOG_CACHE = '/tmp/letta_server_remote.log'
LETTA_REMOTE_LOG_PULL_INTERVAL = 30   # seconds between SSH pulls
LETTA_REMOTE_LOG_LOOKBACK = 300       # seconds of history to seed the cache with on first pull
LETTA_REMOTE_LOG_CACHE_MAX_LINES = 4000  # trim threshold so /tmp doesn't grow unbounded

# ── Server Management registry ────────────────────────────────────────────────
# Each server we monitor. Fields (all optional except key/name):
#   log_file   — absolute path to a local log file to tail
#   health_url — URL to ping; an "up/down" status row is derived from it
#   note       — short human description shown in the UI
# A server can have a log_file, a health_url, or both. Remote servers we can't
# tail locally (Docker on another host) are monitored via health_url only,
# UNLESS we have SSH access to pull their logs into a local cache (see "letta"
# below) — an unreachable health check is itself the "something is awry" signal
# for the ones we can't.
SERVERS = [
    {
        'key': 'win10-node',
        'name': 'Win10 WSL Node',
        'check': 'win10_node_health',
        'remote': True,
        'note': 'The Win10 WSL host (100.80.49.10) that runs Letta, the Frita SDK executor, '
                'and the Logger API. ROOT CAUSE indicator: if this is red, those are all '
                'symptoms — fix the node first (Restart revives tailscaled via the Windows host).',
    },
    {
        'key': 'letta',
        'name': 'Letta Server',
        'health_url': f'{LETTA_BASE_URL}/v1/health/',
        'log_file': LETTA_REMOTE_LOG_CACHE,
        'remote': True,
        'win10_docker': True,
        'depends_on': 'win10-node',
        'note': f'Letta API ({LETTA_BASE_URL}) — logs pulled periodically over SSH from '
                f'{LETTA_DOCKER_HOST} (Docker container on the Win10 box)',
    },
    {
        'key': 'chatgpt-provider',
        'name': 'ChatGPT Provider (Mazda LLM)',
        'check': 'chatgpt_provider_health',
        'remote': True,
        'depends_on': 'letta',
        'note': 'OAuth token on the chatgpt-plus-pro Letta provider — the credential '
                'Mazda + the Suzuki fleet make every LLM call with. RED = token dead '
                '(e.g. expired access token + invalid refresh token): every dispatch '
                'to the fleet fails with HTTP 401 even while scans and all other '
                'servers look fine. Restart swaps in the standby account token '
                '(swap_chatgpt_provider_token.sh on the Letta box).',
    },
    {
        'key': 'executor',
        'name': 'Executor Server',
        'health_url': 'http://127.0.0.1:8787/health',
        'log_file': EXECUTOR_STARTUP_LOG,
        'note': 'executor_run REST backend — runs locally on this machine (:8787)',
    },
    {
        'key': 'mcp-proxy',
        'name': 'MCP Executor Bridge',
        'tcp_check': ('127.0.0.1', 8789),
        'note': 'mcp-proxy stdio bridge for executor_run MCP tool (:8789) — '
                'if this dies Scissari/Codex executor_run silently fails',
    },
    {
        'key': 'dashboard',
        'name': 'Dashboard Server',
        'health_url': f'http://localhost:{PORT}/',
        'log_file': '/tmp/dashboard_8765.log',
        'note': 'This dashboard (server.py)',
    },
    {
        'key': 'dashboard-proxy',
        'name': 'Dashboard Proxy (Win10)',
        'health_url': 'http://100.80.49.10:8765/',
        'remote': True,
        'depends_on': 'win10-node',
        'note': 'WSL TCP proxy on the Win10 box (100.80.49.10:8765) that relays to '
                'this dashboard so the Win10-side browser can reach it via '
                'http://localhost:8765 without the (offline) Win10 Tailscale node. '
                'If this is red, http://localhost:8765 on the Win10 machine will not load.',
    },
    {
        'key': 'logger-api',
        'name': 'Logger API',
        # The bare root has no index file (DocumentRoot serves a directory with
        # no index.php) — Apache 403s there even when the API is fully healthy,
        # so the health check would never flip green. Hit a real PHP+MySQL+
        # Apache-rewrite endpoint instead (same one the smoke test in
        # [[reference_logger_api_ops]] uses) — 200 means the whole stack works.
        'health_url': 'http://100.80.49.10:8284/libraries/local-php-api/object/select?object_view_id=OrchestratorAgent_2026',
        'log_file': LOGGER_API_STARTUP_LOG,
        'remote': True,
        'win10_docker': True,
        'depends_on': 'win10-node',
        'note': 'Docker logger API (live agent log viewer) — mysql + php-api containers '
                'on the Win10 box, started over SSH (see Start button)',
    },
    {
        'key': 'lettabot',
        'name': 'Lettabot (Telegram)',
        'health_url': 'http://localhost:8091/health',
        'log_file': os.path.expanduser('~/lettabot/cron-log.jsonl'),
        'note': 'Scissari Telegram bot — internal API :8091; '
                'heartbeat/cron log at ~/lettabot/cron-log.jsonl '
                '(stdout goes to systemd journal: `journalctl --user -u lettabot -f`)',
    },
    {
        'key': 'thought-bridge',
        'name': 'Thought Bridge',
        'health_url': 'http://localhost:8899/',
        'note': 'lettabot → browser live thought stream (monitor :8899, WS bridge :8766)',
    },
    {
        'key': 'frita-executor',
        'name': 'Frita Executor (Win10)',
        'check': 'frita_executor_health',
        'remote': True,
        'win10_docker': True,
        'depends_on': 'win10-node',
        'note': 'Frita\'s win10_run + Claude-SDK runner. Verifies the SDK-capable '
                'executor on host :8799 (what the Mazda minions reach) AND watches '
                'for a stale no-SDK "ghost" executor on :8797 (the recurring '
                'duplicate-stack bug). Restart via "Start" button.',
    },
    {
        'key': 'mazda-tools-mcp',
        'name': 'Mazda Tools MCP',
        'tcp_check': ('127.0.0.1', 8791),
        'note': 'mcp-proxy for Mazda\'s Letta tools (mazda-tools-mcp.service, :8791) — '
                'if down, Mazda\'s tool calls silently fail',
    },
    {
        'key': 'document-vision',
        'name': 'Document Vision (Scan Classify)',
        'check': 'document_vision_health',
        'note': 'classify_scan.py\'s 3-tier fallback (Gemini -> ChatGPT-OAuth/Codex CLI -> '
                'OpenAI key) that lets Mazda classify/read a scanned document. RED here '
                '(all 3 tiers down) means process_scanned_document() refuses to dispatch '
                'Mazda at all — see DOCUMENT_VISION_HALT_MESSAGE.',
    },
    {
        'key': 'mazda-categorizer-llm',
        'name': 'LLM Provider Fallbacks (Categorizer)',
        'check': 'mazda_categorizer_fallback_health',
        'note': 'tools/categorizer/categorizer_main.py\'s vendor->category LLM chain '
                '(gemini -> chatgpt-oauth [EG\'s account, then mom\'s] -> anthropic), '
                'read from real call outcomes in ~/.mazda/provider_health.json — never '
                'a synthetic probe. YELLOW = a fallback fired recently (still working, '
                'worth a look). RED = every tracked tier failed on its last attempt. '
                'Built 2026-07-20 after the gemini CLI broke silently for 3+ days.',
    },
]

# SSH connections this dashboard can reach for remote administration. Each
# entry is checked with a real `ssh ... echo CONNECTED` round trip — there's
# no proxy/relay to fall back on, so "down" here means SSH itself is broken,
# not just a single service.
SSH_CONNECTIONS = [
    {
        'key': 'win10-host',
        'name': 'Windows 10 Host',
        'host': '100.69.80.89',
        'user': 'NewUser',
        'note': 'Windows side of the WSL host, for admin scripts run from /mnt/c (100.69.80.89)',
    },
    {
        'key': 'win10-wsl-letta',
        'name': 'Win10 WSL (Letta Docker Host)',
        'host': '100.80.49.10',
        'user': 'adamsl',
        # Reachable only via Tailscale DERP(ord) relay — observed RTT ranges from
        # 1.8s up to a real 43s+ round trip (see reference_tailscale_derp_relay_
        # 100_80_49_10 memory; re-measured 2026-07-09 at 43.1s worst case), far past
        # every other connection here. 30s previously caused false "down" flips —
        # give it its own generous timeout rather than penalizing fast hosts'
        # down-detection.
        'timeout': 55,
        'note': 'WSL side of the Win10 box — actual LETTA_DOCKER_HOST used for Letta server, '
                'Logger API, and Frita executor admin (100.80.49.10)',
    },
    {
        'key': 'win11',
        'name': 'Win11 (Lettabot/Dashboard)',
        'host': '100.72.158.63',
        'user': 'adamsl',
        'note': 'Lettabot + the live dashboard deployment (100.72.158.63)',
    },
    {
        'key': 'rosemary46',
        'name': 'Rosemary46',
        'host': '100.72.34.38',
        'user': 'adamsl',
        'note': 'Rosemary46 Linux box (100.72.34.38)',
    },
    {
        'key': 'android-phone',
        'name': 'Android Phone (Samsung)',
        'host': '100.111.161.7',
        'user': None,
        'check': 'tailscale',
        'note': 'Samsung phone — checked via `tailscale status` (no sshd). Must show '
                '"online" here for the tailnet-only live dashboard URL '
                '(desktop-2obsqmc-24.tailb8fc54.ts.net) to be reachable from it.',
    },
    {
        'key': 'chromebook-a13',
        'name': 'ChromeBook A13',
        'host': '100.82.55.63',
        'user': None,
        'check': 'tailscale',
        'note': 'Chromebook (tailnet device "octopus", eg1972@gmail.com, Android 13, '
                'Tailscale 1.96.4) — checked via `tailscale status` (no sshd).',
    },
]

SSH_CONNECT_TIMEOUT = 8          # default seconds given to `ssh` to connect + run the check
                                 # command; individual SSH_CONNECTIONS entries may override
                                 # via a 'timeout' key for known-slow paths (DERP relays etc).
SSH_HEALTH_POLL_INTERVAL = 30    # background poll cadence
SSH_HEALTH_FAIL_THRESHOLD = 2    # consecutive failures required before flipping to "down"
SSH_LOG_TAIL = 50                # how many past connection-test results to keep per connection

SERVER_LOG_TAIL = 300   # how many trailing log lines to expose

# Track servers that are currently starting (for a limited time).
_starting_servers = {}  # { key: timestamp_when_started }
_starting_lock = threading.Lock()

# Track how long each server has been non-healthy, so the UI can show
# "down for 54m" and escalate a stale outage (today Letta was dead 54 min before
# anyone looked). down_for_seconds + stale are emitted per server.
_server_down_since = {}  # { key: epoch_when_first_seen_non_up }
_server_down_lock = threading.Lock()
SERVER_STALE_DOWN_SECONDS = 600  # 10 min non-healthy → "stale" (escalate)


def track_down_duration(key, status):
    """Update/return how long `key` has been non-healthy. 'up' clears the clock;
    'starting' (transient) doesn't start one. Returns (down_for_seconds, stale)."""
    with _server_down_lock:
        now = time.time()
        if status in ('up', 'starting'):
            if status == 'up':
                _server_down_since.pop(key, None)
            since = _server_down_since.get(key)
            return ((int(now - since), (now - since) >= SERVER_STALE_DOWN_SECONDS)
                    if since else (0, False))
        since = _server_down_since.get(key)
        if since is None:
            _server_down_since[key] = since = now
        dur = now - since
        return (int(dur), dur >= SERVER_STALE_DOWN_SECONDS)


def mark_server_starting(key):
    """Mark a server as 'starting' for the next 120 seconds."""
    with _starting_lock:
        _starting_servers[key] = datetime.now()


def clear_server_starting(key):
    """Drop the 'starting' mark — call this once a real health check succeeds
    so the UI can flip to 'up' immediately instead of waiting out the window."""
    with _starting_lock:
        _starting_servers.pop(key, None)


def is_server_starting(key):
    """Check if a server is in the 'starting' window (within 120 seconds)."""
    with _starting_lock:
        if key not in _starting_servers:
            return False
        elapsed = (datetime.now() - _starting_servers[key]).total_seconds()
        if elapsed > 120:
            del _starting_servers[key]
            return False
        return True


def start_executor_server():
    """Launch the executor server locally — it runs on this same machine, not remotely.

    `start_executor_server.sh` starts the REST executor on :8787 in the background
    and then runs mcp-proxy in the foreground, so it never exits on its own — it
    must be launched detached (not awaited) and tailed via its log file instead."""
    try:
        with open(EXECUTOR_STARTUP_LOG, 'a') as logf:
            logf.write(f'\n--- launch requested {datetime.now().isoformat(timespec="seconds")} ---\n')
            logf.flush()
            subprocess.Popen(
                ['bash', EXECUTOR_START_SCRIPT],
                stdout=logf, stderr=subprocess.STDOUT,
                cwd=os.path.dirname(EXECUTOR_START_SCRIPT),
                start_new_session=True,
            )
        mark_server_starting('executor')
        return {'ok': True, 'text': f'Launched {os.path.basename(EXECUTOR_START_SCRIPT)} locally — tailing {EXECUTOR_STARTUP_LOG}'}
    except FileNotFoundError:
        return {'ok': False, 'text': f'Start script not found: {EXECUTOR_START_SCRIPT}'}
    except Exception as e:
        return {'ok': False, 'text': str(e)}


def start_frita_executor():
    """Deploy/restart Frita's executor container on the Win10 box over SSH.

    Runs deploy_frita_executor.sh (idempotent — stops old container, starts new
    one with --restart unless-stopped and port 8797:8787 published).  Output
    tailed to FRITA_EXECUTOR_STARTUP_LOG so the server tab has a log to show."""
    try:
        with open(FRITA_EXECUTOR_STARTUP_LOG, 'a') as logf:
            logf.write(f'\n--- launch requested {datetime.now().isoformat(timespec="seconds")} ---\n')
            logf.flush()
            subprocess.Popen(
                ['ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes', LETTA_DOCKER_HOST,
                 'bash', FRITA_EXECUTOR_DEPLOY_SCRIPT],
                stdout=logf, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        mark_server_starting('frita-executor')
        return {'ok': True, 'text': f'Launched {os.path.basename(FRITA_EXECUTOR_DEPLOY_SCRIPT)} '
                                    f'on {LETTA_DOCKER_HOST} — tailing {FRITA_EXECUTOR_STARTUP_LOG}'}
    except Exception as e:
        return {'ok': False, 'text': str(e)}


def restart_dashboard_server():
    """Restart THIS dashboard via its systemd --user unit.

    The restart kills the process serving this very request, so two things matter:
    (1) defer the restart by ~1s so this HTTP response flushes back to the browser
    first, and (2) run it from OUTSIDE this service's cgroup — a plain detached
    child would be in the dashboard service's cgroup and get SIGTERM'd by systemd
    mid-restart. `systemd-run --user` launches a transient scope that survives the
    restart, so the `systemctl restart` actually completes."""
    deferred = f'sleep 1; systemctl --user restart {DASHBOARD_SYSTEMD_UNIT}'
    try:
        with open(DASHBOARD_RESTART_LOG, 'a') as logf:
            logf.write(f'\n--- restart requested {datetime.now().isoformat(timespec="seconds")} ---\n')
            logf.flush()
            subprocess.Popen(
                ['systemd-run', '--user', '--collect',
                 '--unit', 'dashboard-self-restart',
                 'bash', '-c', deferred],
                stdout=logf, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        return {'ok': True, 'text': f'Restarting {DASHBOARD_SYSTEMD_UNIT} in ~1s — '
                                    'this page will briefly disconnect, then reconnect on refresh.'}
    except FileNotFoundError:
        return {'ok': False, 'text': 'systemd-run not found — cannot self-restart on this host.'}
    except Exception as e:
        return {'ok': False, 'text': str(e)}


# docker-compose v1.29.2 (required on this box — see [[reference_logger_api_ops]])
# throws `KeyError: 'ContainerConfig'` when it tries to "recreate" a container
# stuck in the `Created` state (e.g. an interrupted `docker-compose up`, or an
# image rebuilt with BuildKit). When that happens, every subsequent
# `docker-compose up -d` fails the same way forever — the containers must be
# `docker rm`'d first so compose creates fresh ones instead of recreating.
# See [[dashboard_logger_api_containerconfig_2026_06_10]].
LOGGER_API_STUCK_CONTAINER_CLEANUP = (
    "docker ps -a --filter 'status=created' --format '{{.ID}} {{.Names}}' "
    "| awk '$2 ~ /logger-api/ {print $1}' "
    "| xargs -r docker rm"
)


def build_logger_api_start_command():
    """Build the SSH command for the Logger API "Start" button.

    Removes any logger-api containers stuck in `Created` state before
    running `start_logger_api.sh`, so the button is self-healing against the
    `KeyError: 'ContainerConfig'` failure mode instead of repeating it."""
    remote_script = f'{LOGGER_API_STUCK_CONTAINER_CLEANUP}; bash {LOGGER_API_START_SCRIPT}'
    return ['ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes', LETTA_DOCKER_HOST,
            'bash', '-c', remote_script]


def start_logger_api():
    """Launch the Logger API's mysql + php-api Docker containers over SSH.

    They live on the Win10 box (same host as the Letta server, reused
    LETTA_DOCKER_HOST/auth) but aren't part of the letta-src compose project,
    so they don't survive a reboot — see [[reference_logger_api_ops]].
    `start_logger_api.sh` runs `docker-compose up -d` and re-injects the
    Apache rewrite the PHP front controller needs. SSH + compose can take a
    while, so launch it detached and tail its output like the executor."""
    try:
        with open(LOGGER_API_STARTUP_LOG, 'a') as logf:
            logf.write(f'\n--- launch requested {datetime.now().isoformat(timespec="seconds")} ---\n')
            logf.flush()
            subprocess.Popen(
                build_logger_api_start_command(),
                stdout=logf, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        mark_server_starting('logger-api')
        return {'ok': True, 'text': f'Launched {os.path.basename(LOGGER_API_START_SCRIPT)} on {LETTA_DOCKER_HOST} — tailing {LOGGER_API_STARTUP_LOG}'}
    except Exception as e:
        return {'ok': False, 'text': str(e)}


# ── Win10 WSL node reachability (root-cause indicator) ────────────────────────
# The Win10 WSL node hosts Letta, the Frita SDK executor, and the Logger API. When
# IT goes offline (today: a stuck Tailscale session), all of those go red as
# SYMPTOMS. This single check is the root cause, and the dependents are grouped
# under it (blocked_by) so six reds collapse into one actionable signal.
WIN10_NODE_HOST = LETTA_DOCKER_HOST.split('@')[-1] if '@' in LETTA_DOCKER_HOST else '100.80.49.10'
# The Windows side of the same box (online even when the WSL node drops) — used to
# revive the WSL node by restarting tailscaled inside the distro.
WIN10_WINDOWS_HOST = os.environ.get('WIN10_WINDOWS_HOST', 'NewUser@100.69.80.89')
WIN10_WSL_DISTRO = os.environ.get('WIN10_WSL_DISTRO', 'Ubuntu-24.04')
_win10_node_cache = {'value': None, 'ts': 0.0}
_win10_node_lock = threading.Lock()
WIN10_NODE_CACHE_TTL = 20


def win10_node_health(timeout=None):
    """Is the Win10 WSL node reachable at all? TCP-connect to its SSH port — cheap
    and independent of any one service. Cached so it doesn't probe every poll."""
    with _win10_node_lock:
        now = time.time()
        if _win10_node_cache['value'] is not None and now - _win10_node_cache['ts'] < WIN10_NODE_CACHE_TTL:
            return _win10_node_cache['value']
    t = timeout or 5
    try:
        s = socket.create_connection((WIN10_NODE_HOST, 22), timeout=t)
        s.close()
        res = {'ok': True, 'text': f'Win10 WSL node {WIN10_NODE_HOST} reachable (ssh:22).'}
    except Exception as e:
        res = {'ok': False,
               'text': f'Win10 WSL node {WIN10_NODE_HOST} OFFLINE — Letta, Frita SDK and '
                       f'Logger API are all blocked by this. Click Restart to revive the '
                       f'WSL node (restarts tailscaled via the Windows host). ({e})'}
    with _win10_node_lock:
        _win10_node_cache['value'] = res
        _win10_node_cache['ts'] = time.time()
    return res


def restart_win10_node():
    """Revive the Win10 WSL node by restarting tailscaled inside the distro from the
    (still-online) Windows host — today's manual recovery, as a button."""
    cmd = f'wsl.exe -d {WIN10_WSL_DISTRO} -u root -- bash -lc "systemctl restart tailscaled"'
    _log_restart(f'win10-node: ssh {WIN10_WINDOWS_HOST} {cmd}')
    try:
        with open(RESTART_LOG, 'a') as logf:
            subprocess.Popen(
                ['ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes', WIN10_WINDOWS_HOST, cmd],
                stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
        mark_server_starting('win10-node')
        with _win10_node_lock:  # force a fresh probe next poll
            _win10_node_cache['ts'] = 0.0
        return {'ok': True, 'text': f'Restarting tailscaled in WSL via {WIN10_WINDOWS_HOST} — '
                                    'node should reappear within ~15s.'}
    except Exception as e:
        return {'ok': False, 'text': f'win10-node restart error: {e}'}


# Indicator #2: surface Docker container exit-code / restart-count for the
# Win10-hosted servers — "Exited (139) 54m ago" / "Restarting (3×)" tells you it
# crashed (139=OOM/segfault) or is crash-looping, not just "down".
WIN10_CONTAINERS = {
    'letta': ['letta-server', 'letta-memfs'],
    'logger-api': ['logger-api-php', 'logger-api-mysql'],
    'frita-executor': ['frita-executor'],
}
_win10_containers_cache = {'value': None, 'ts': 0.0}
_win10_containers_lock = threading.Lock()
WIN10_CONTAINERS_CACHE_TTL = 20


def win10_container_states(timeout=10):
    """One cached `docker ps -a` on the box → {container_name: status_string}.
    The status string already carries exit code + restart count from Docker."""
    with _win10_containers_lock:
        now = time.time()
        if (_win10_containers_cache['value'] is not None
                and now - _win10_containers_cache['ts'] < WIN10_CONTAINERS_CACHE_TTL):
            return _win10_containers_cache['value']
    states = {}
    try:
        r = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes', LETTA_DOCKER_HOST,
             'docker', 'ps', '-a', '--format', '{{.Names}}|{{.Status}}'],
            capture_output=True, text=True, timeout=timeout)
        for line in (r.stdout or '').splitlines():
            if '|' in line:
                name, status = line.split('|', 1)
                states[name.strip()] = status.strip()
    except Exception:
        states = {}
    with _win10_containers_lock:
        _win10_containers_cache['value'] = states
        _win10_containers_cache['ts'] = time.time()
    return states


def container_status_for(key, states):
    """Human container-status summary for a server key, or '' if not a Docker server
    or the probe failed. e.g. 'letta-server: Exited (139) 54 minutes ago'."""
    names = WIN10_CONTAINERS.get(key)
    if not names or not states:
        return ''
    parts = [f'{n}: {states[n]}' for n in names if n in states]
    return ' · '.join(parts)


# ── Generic restart dispatch (every Server Management tab gets a Restart button) ──
# Goal: a dashboard user never needs the command line. Each server key maps to a
# restart handler returning {ok, text}; handlers call mark_server_starting() so
# the tab shows the yellow "recently restarted / verifying" state until the next
# health check confirms green.
RESTART_LOG = '/tmp/dashboard_restarts.log'


def _log_restart(line):
    try:
        with open(RESTART_LOG, 'a') as f:
            f.write(f'[{datetime.now().isoformat(timespec="seconds")}] {line}\n')
    except Exception:
        pass


def ensure_win10_docker(timeout=45):
    """Recover the Win10 box's native dockerd when it dies on a stale pid file —
    the recurring failure behind "Frita HTTP 404 / :8799 down" (see
    frita_executor_ghost_container memory, 2026-06-22): remove the stale
    /var/run/docker.pid, reset the failed unit, start it. Idempotent + safe to
    call before any Win10-docker restart. Returns {ok, text}."""
    cmd = ('sudo -n rm -f /var/run/docker.pid; '
           'sudo -n systemctl reset-failed docker.service 2>/dev/null; '
           'sudo -n systemctl start docker.service 2>&1; '
           'sleep 2; systemctl is-active docker.service')
    try:
        r = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes',
             LETTA_DOCKER_HOST, 'bash', '-lc', cmd],
            capture_output=True, text=True, timeout=timeout)
        out = ((r.stdout or '') + (r.stderr or '')).strip()
        last = (r.stdout or '').strip().splitlines()[-1].strip() if (r.stdout or '').strip() else ''
        return {'ok': last == 'active', 'text': out[-200:] or 'no output'}
    except Exception as e:
        return {'ok': False, 'text': f'ensure docker error: {e}'}


# Cached probe of the Win10 dockerd, for the "dependency needs a reboot" yellow
# state on the Win10-docker-backed servers (letta / logger-api / frita-executor).
_win10_docker_cache = {'value': None, 'ts': 0.0}
_win10_docker_lock = threading.Lock()
WIN10_DOCKER_CACHE_TTL = 30


def win10_docker_ok(timeout=8):
    """Return True (active) / False (down) / None (unknown) for the Win10 dockerd.
    Cached for WIN10_DOCKER_CACHE_TTL so it doesn't SSH on every health poll."""
    with _win10_docker_lock:
        now = time.time()
        if (_win10_docker_cache['value'] is not None
                and now - _win10_docker_cache['ts'] < WIN10_DOCKER_CACHE_TTL):
            return _win10_docker_cache['value']
    val = None
    try:
        r = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes',
             LETTA_DOCKER_HOST, 'systemctl', 'is-active', 'docker.service'],
            capture_output=True, text=True, timeout=timeout)
        val = (r.stdout.strip() == 'active')
    except Exception:
        val = None
    with _win10_docker_lock:
        _win10_docker_cache['value'] = val
        _win10_docker_cache['ts'] = time.time()
    return val


def _restart_user_unit(key, unit, timeout=25):
    """Restart a local systemd --user unit (lettabot / thought-bridge / mazda-tools-mcp)."""
    _log_restart(f'{key}: systemctl --user restart {unit}')
    try:
        r = subprocess.run(['systemctl', '--user', 'restart', unit],
                           capture_output=True, text=True, timeout=timeout)
        mark_server_starting(key)
        if r.returncode == 0:
            return {'ok': True, 'text': f'Restarted {unit} (systemd --user).'}
        return {'ok': False, 'text': f'systemctl restart {unit} failed: {(r.stderr or r.stdout).strip()[:200]}'}
    except Exception as e:
        return {'ok': False, 'text': f'restart {unit} error: {e}'}


def _restart_remote(key, remote_cmd):
    """Run a restart command on LETTA_DOCKER_HOST over SSH, detached + logged.
    SSH+Docker is slow over the DERP relay, so launch detached and let the health
    check confirm recovery; mark the server 'starting' (yellow) meanwhile."""
    _log_restart(f'{key}: ssh {LETTA_DOCKER_HOST} {remote_cmd[:120]}')
    try:
        with open(RESTART_LOG, 'a') as logf:
            subprocess.Popen(
                ['ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes', LETTA_DOCKER_HOST,
                 'bash', '-lc', remote_cmd],
                stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
        mark_server_starting(key)
        return {'ok': True, 'text': f'Launched {key} restart on {LETTA_DOCKER_HOST} — tailing {RESTART_LOG}'}
    except Exception as e:
        return {'ok': False, 'text': f'ssh restart error: {e}'}


def restart_frita_executor():
    """Restart Frita's SDK executor: ensure the Win10 dockerd is up first (the
    recurring stale-pid failure), then run the idempotent deploy."""
    docker = ensure_win10_docker()
    res = start_frita_executor()
    if not docker['ok']:
        res['text'] = f'{res.get("text", "")} (docker recovery: {docker["text"][:80]})'
    return res


def restart_document_vision():
    """"Restart" for Document Vision: there's no service to bounce — of the 3
    classify_scan.py tiers, only the ChatGPT-OAuth/Codex-CLI one is a token
    that can self-heal via refresh (same client_id the Model Stats Codex
    extractor uses). Gemini/OpenAI are static keys in rol_finances/.env with
    nothing to restart; if those are what's down this just reports the
    breakdown so the user knows what needs a manual key rotation."""
    auth_path = os.path.expanduser('~/.codex/auth.json')
    try:
        auth = json.load(open(auth_path))
        tokens = auth.get('tokens', {})
        refresh_token = tokens.get('refresh_token')
        if not refresh_token:
            health = document_vision_health()
            return {'ok': health['ok'], 'text': f'No Codex refresh_token found. {health["text"]}'}
        body = json.dumps({
            'grant_type': 'refresh_token',
            'client_id': 'app_EMoamEEZ73f0CkXaXp7hrann',
            'refresh_token': refresh_token,
            'scope': 'openid profile email',
        }).encode()
        req = urllib.request.Request(
            'https://auth.openai.com/oauth/token', data=body,
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=20) as r:
            new_tokens = json.loads(r.read().decode())
        tokens['access_token'] = new_tokens.get('access_token', tokens.get('access_token'))
        tokens['id_token'] = new_tokens.get('id_token', tokens.get('id_token'))
        tokens['refresh_token'] = new_tokens.get('refresh_token', refresh_token)
        auth['tokens'] = tokens
        auth['last_refresh'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        with open(auth_path, 'w') as f:
            json.dump(auth, f)
        health = document_vision_health()
        return {'ok': health['ok'], 'text': f'Refreshed Codex OAuth token. {health["text"]}'}
    except Exception as exc:
        health = document_vision_health()
        return {'ok': health['ok'],
                'text': f'Codex refresh failed ({exc}). {health["text"]} '
                        f'Gemini/OpenAI keys must be fixed by hand in rol_finances/.env.'}


# server key → restart handler (returns {ok, text}). Covers ALL SERVERS so every
# Server Management tab can be restarted from the UI.
def chatgpt_provider_health(timeout=None):
    """Zero-token health of the chatgpt-plus-pro OAuth credential itself — the
    token every Mazda/Suzuki LLM step runs on. Distinct from the Letta tile
    (server up != token valid): on 2026-07-13 a scan dispatched cleanly, Letta
    was green, and Mazda silently got nothing because the provider token had
    expired with a dead refresh token (HTTP 401 on every dispatch). This tile
    makes that state RED in Server Management instead of only Agent Management."""
    try:
        creds, ptype = _fetch_provider_oauth_creds(CHATGPT_PLUS_PRO)
    except Exception as e:
        return {'ok': False, 'text': f'cannot read provider row from Letta API: {e}'}
    if not creds:
        return {'ok': False, 'text': f'{CHATGPT_PLUS_PRO}: provider row has no OAuth creds'}
    probe_fn = PROVIDER_USAGE_PROBES.get(ptype)
    if not probe_fn:
        return {'ok': False, 'text': f'no usage probe for provider type {ptype!r}'}
    probe = probe_fn(creds, timeout=timeout or 8)
    if probe['ok']:
        return {'ok': True, 'text': f'{CHATGPT_PLUS_PRO} token valid — usage {probe["text"]}'}
    return {'ok': False, 'hard': True,  # a restart click can't revive a dead token by itself
            'text': f'{CHATGPT_PLUS_PRO} token UNUSABLE — {probe["text"]} — Mazda + fleet '
                    f'cannot run a single LLM step (dispatches fail HTTP 401); '
                    f'Restart swaps to the standby account token'}


def restart_chatgpt_provider():
    """'Restart' for the provider tile = swap the chatgpt-plus-pro row to the
    standby account token on the Letta box (same script auto-failover uses).
    Only helps when the standby token is alive — the tile stays red otherwise."""
    _log_restart('chatgpt-provider: swap provider token to standby')
    ok, note = _run_chatgpt_failover_swap()
    if not ok:
        return {'ok': False, 'text': f'token swap failed — {note}'}
    try:
        _poll_chatgpt_provider_once()  # refresh the fleet's send-errors now, not in 90s
    except Exception:
        pass
    return {'ok': True, 'text': f'provider token swapped to standby — {note}'}


RESTART_HANDLERS = {
    'win10-node': restart_win10_node,          # revive WSL node via the Windows host
    'executor': start_executor_server,        # script frees the port + relaunches
    'mcp-proxy': start_executor_server,        # mcp-proxy :8789 is part of that script
    'dashboard': restart_dashboard_server,
    'logger-api': start_logger_api,            # idempotent self-healing compose up
    'frita-executor': restart_frita_executor,  # docker recovery + idempotent deploy
    'lettabot': lambda: _restart_user_unit('lettabot', 'lettabot.service'),
    'thought-bridge': lambda: _restart_user_unit('thought-bridge', 'thought-bridge.service'),
    'mazda-tools-mcp': lambda: _restart_user_unit('mazda-tools-mcp', 'mazda-tools-mcp.service'),
    'letta': lambda: _restart_remote(
        'letta',
        'docker restart letta-server 2>&1 | tail -3 || '
        '(cd ~/letta-src && docker compose restart 2>&1 | tail -3)'),
    'dashboard-proxy': lambda: _restart_remote(
        'dashboard-proxy',
        'systemctl --user restart dashboard-proxy.service 2>&1 | tail -3 || '
        'echo "no dashboard-proxy.service — start mechanism unknown, please configure"'),
    'document-vision': restart_document_vision,
    'mazda-categorizer-llm': lambda: restart_mazda_categorizer_llm(),
    'chatgpt-provider': restart_chatgpt_provider,  # swap provider row to standby token
}
RESTARTABLE_KEYS = set(RESTART_HANDLERS)


def restart_server(key):
    """Dispatch a restart for any Server Management entry. Returns {ok, text}."""
    handler = RESTART_HANDLERS.get(key)
    if handler is None:
        return {'ok': False, 'text': f'No restart handler for "{key}".'}
    try:
        return handler()
    except Exception as e:
        return {'ok': False, 'text': f'restart {key} error: {e}'}


# ── Remote Letta server log pulling (SSH) ─────────────────────────────────────
# The Letta server itself is Docker-on-Win10 — there's nothing to tail locally,
# so a background thread (started in `__main__`) periodically SSHes in and
# appends new lines to LETTA_REMOTE_LOG_CACHE, which the "letta" SERVERS entry
# points its `log_file` at. Everything downstream (server_log_rows, tail_lines,
# the /api/server-logs route) treats it exactly like any other tailed log.

_letta_log_pull_lock = threading.Lock()
_letta_log_pull_since = None  # ISO8601 UTC ('...Z'); seeded with a lookback window on first pull


def _trim_log_cache(path, max_lines):
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


def _pull_letta_remote_logs_once():
    """Run pull_letta_server_logs.sh on the Win10 box over SSH and append any
    new lines to the local cache.

    Tracks a remembered "since" watermark (module-level, not the cache file's
    mtime) advanced only on success, so a dropped SSH connection re-fetches
    that window next time rather than silently losing it — small overlaps
    across pulls are possible (and harmless to a log viewer) but gaps aren't."""
    global _letta_log_pull_since
    now = datetime.now(timezone.utc)
    with _letta_log_pull_lock:
        since = _letta_log_pull_since or \
            (now - timedelta(seconds=LETTA_REMOTE_LOG_LOOKBACK)).strftime('%Y-%m-%dT%H:%M:%SZ')
    cmd = ['ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes', LETTA_DOCKER_HOST,
           'bash', LETTA_REMOTE_LOG_PULL_SCRIPT, since]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    except Exception as e:
        print(f'[letta-log-pull] ssh to {LETTA_DOCKER_HOST} failed: {e}')
        return
    if result.returncode != 0:
        print(f'[letta-log-pull] {LETTA_DOCKER_HOST}: {result.stderr.strip() or "non-zero exit"}')
        return
    if result.stdout:
        with open(LETTA_REMOTE_LOG_CACHE, 'a') as f:
            f.write(result.stdout)
        _trim_log_cache(LETTA_REMOTE_LOG_CACHE, LETTA_REMOTE_LOG_CACHE_MAX_LINES)
    with _letta_log_pull_lock:
        _letta_log_pull_since = now.strftime('%Y-%m-%dT%H:%M:%SZ')


def _letta_remote_log_pull_loop():
    """Background daemon thread body: keep pulling Letta server logs over SSH."""
    while True:
        _pull_letta_remote_logs_once()
        time.sleep(LETTA_REMOTE_LOG_PULL_INTERVAL)


# ── Letta API helpers ────────────────────────────────────────────────────────

def letta_get(path, timeout=6):
    """GET from Letta API; returns parsed JSON or None on error."""
    try:
        url = f'{LETTA_BASE_URL}{path}'
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None

def _resolve_letta_id(name):
    """Look up agent ID by name from the Letta API (cached per server run)."""
    global _letta_roster_fetched_at
    with _letta_id_cache_lock:
        if name in _letta_id_cache:
            return _letta_id_cache[name]
        if time.time() - _letta_roster_fetched_at < LETTA_ROSTER_NEG_TTL:
            return None  # roster is fresh; the name genuinely isn't on the server
    data = letta_get('/v1/agents', timeout=30)
    if not data:
        return None
    agents = data if isinstance(data, list) else data.get('agents', [])
    with _letta_id_cache_lock:
        for a in agents:
            _letta_id_cache[a['name']] = a['id']
        _letta_roster_fetched_at = time.time()
        return _letta_id_cache.get(name)

def get_letta_id(agent_cfg):
    """Return the real Letta agent ID for an agent config dict."""
    if agent_cfg.get('id'):
        return agent_cfg['id']
    return _resolve_letta_id(agent_cfg['name'])

def letta_messages(agent_id, limit=200):
    """Fetch all message types for an agent from the Letta API.

    Backs the Messages/Thoughts/Tool Calls tabs. Uses a longer-than-default
    timeout because the Letta box is currently only reachable over a Tailscale
    DERP relay (no direct connection to this box), which regularly takes
    10-20s round trip — the 6s default was cutting the request off before the
    reply arrived, so these tabs showed empty ("no messages recorded yet")
    even though the agent had messages. 25s keeps this under the browser's
    30s fetch abort while giving the slow relay path room to finish.
    """
    data = letta_get(f'/v1/agents/{agent_id}/messages?limit={limit}', timeout=25)
    if not data:
        return []
    return data if isinstance(data, list) else data.get('messages', data.get('results', []))

def _msg_date(m):
    """Return the best available timestamp string for a Letta message."""
    return str(m.get('created_at') or m.get('date') or '')[:19]


def _msg_text(m):
    """Extract display text from a Letta message object."""
    # assistant_message / user_message: content is a string
    content = m.get('content', '')
    if isinstance(content, list):
        content = ' '.join(c.get('text', '') for c in content if isinstance(c, dict))
    # tool_call_message: tool_call.name + arguments
    tc = m.get('tool_call', {})
    if tc:
        args = tc.get('arguments', {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                pass
        arg_str = ', '.join(f'{k}={str(v)[:80]}' for k, v in (args.items() if isinstance(args, dict) else []))
        return f'{tc.get("name", "?")}({arg_str})'
    # tool_return_message
    tr = m.get('tool_return', '')
    if tr:
        if isinstance(tr, dict):
            return str(tr.get('content', ''))[:300]
        return str(tr)[:300]
    # approval_request_message
    approvals = m.get('tool_calls') or []
    if approvals and isinstance(approvals, list):
        names = [tc.get('name', '?') for tc in approvals if isinstance(tc, dict)]
        if names:
            return 'approval requested: ' + ', '.join(names)
    # reasoning_message
    reasoning = m.get('reasoning', '')
    if reasoning:
        return reasoning
    return str(content)

def letta_thoughts(agent_id):
    msgs = letta_messages(agent_id, limit=200)
    rows = []
    for m in msgs:
        mt = m.get('message_type', '')
        if mt != 'reasoning_message':
            continue
        text = _msg_text(m)
        if not text.strip():
            continue
        rows.append({
            'date': _msg_date(m),
            'type': 'thought',
            'text': text[:500],
        })
    if rows:
        return rows

    # Fallback for agents whose API stream does not expose reasoning_message.
    # Prefer assistant content as the closest proxy for visible "thoughts".
    assistant_rows = []
    for m in msgs:
        if m.get('message_type') != 'assistant_message':
            continue
        text = _msg_text(m)
        if not text.strip():
            continue
        assistant_rows.append({
            'date': _msg_date(m),
            'text': text[:500],
        })
    if assistant_rows:
        return assistant_rows

    # Final fallback only when there is no assistant/reasoning content at all.
    fallback_types = {
        'tool_call_message': 'tool',
        'tool_return_message': 'tool',
        'approval_request_message': 'approval',
        'approval_response_message': 'approval',
        'user_message': 'user',
    }
    for m in msgs:
        mt = m.get('message_type', '')
        if mt not in fallback_types:
            continue
        text = _msg_text(m)
        if not text.strip():
            continue
        rows.append({
            'date': _msg_date(m),
            'type': fallback_types[mt],
            'text': text[:500],
        })
    return rows

MESSAGES_MAX_AGE_SECONDS = 5 * 3600  # only show messages from the last 5 hours

def _within_max_age(m, now):
    """True if a message's timestamp is within MESSAGES_MAX_AGE_SECONDS (or unparseable)."""
    age = _msg_age_seconds(m, now)
    return age is None or age <= MESSAGES_MAX_AGE_SECONDS

def letta_convo(agent_id):
    msgs = letta_messages(agent_id, limit=200)
    now = datetime.now(timezone.utc)
    rows = []
    for m in msgs:
        mt = m.get('message_type', '')
        if mt not in ('user_message', 'assistant_message'):
            continue
        if not _within_max_age(m, now):
            continue
        text = _msg_text(m)
        if not text.strip():
            continue
        rows.append({
            'date': _msg_date(m),
            'type': mt,
            'text': text,
        })
    return rows

def letta_toolcalls(agent_id):
    msgs = letta_messages(agent_id, limit=200)
    rows = []
    for m in msgs:
        mt = m.get('message_type', '')
        if mt not in ('tool_call_message', 'tool_return_message'):
            continue
        text = _msg_text(m)
        if not text.strip():
            continue
        display_type = 'tool_call' if mt == 'tool_call_message' else 'tool_return'
        if mt == 'tool_call_message':
            tc = m.get('tool_call', {})
            display_type = tc.get('name', 'tool_call')
        rows.append({
            'date': _msg_date(m),
            'type': display_type,
            'text': text[:300],
        })
    return rows


def run_letta_headless(agent_id, prompt_text):
    """Run letta in headless mode with JSON output (no terminal UI).

    This bypasses the letta CLI's Ink spinner/interactive output, returning
    clean JSON instead. Used by the "Ask Mazda" dialog to get readable output.

    Returns: {'ok': bool, 'output': str, 'error': str}
    """
    try:
        result = run_letta_code_message(agent_id, prompt_text, timeout=60)
        return {'ok': True, 'output': result['reply']}
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': 'letta command timed out (60s)'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


# ── Claude Code local log helpers ────────────────────────────────────────────

def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def _write_json(path, rows):
    with open(path, 'w') as f:
        json.dump(rows, f, indent=2)


def _append_json(path, lock, entry, maxlen=200):
    with lock:
        rows = _load_json(path)
        rows.append(entry)
        if len(rows) > maxlen:
            rows = rows[-maxlen:]
        _write_json(path, rows)


def _clear_json(path, lock):
    with lock:
        _write_json(path, [])


# ── Server Management helpers ─────────────────────────────────────────────────

def get_server(key):
    """Return the SERVERS config dict for a key, or None."""
    for s in SERVERS:
        if s['key'] == key:
            return s
    return None

# Frita / Claude-SDK executor endpoints. The Mazda minions reach the SDK
# executor via the host bridge on :8799 (the live letta-server runs in a
# separate containerd "ghost" stack whose own `frita-executor` DNS points at a
# stale no-SDK executor — see frita_executor_ghost_container memory). :8797 is
# where that stale ghost typically surfaces, so we watch it explicitly.
FRITA_EXEC_GOOD_URL = 'http://100.80.49.10:8799/claude_sdk_status'
FRITA_EXEC_GHOST_URL = 'http://100.80.49.10:8797/claude_sdk_status'
# The actual WORK endpoint the minions' run_claude_code_sdk tool POSTs to. The
# status endpoint above can be perfectly healthy while THIS route 404s — which
# is exactly the "HTTP Error 404: Not Found" Frita hit. We probe it cheaply so
# the affected agents' tabs go red. See agent_health_check / uses_claude_sdk.
FRITA_EXEC_WORK_URL = 'http://100.80.49.10:8799/claude_sdk'
# The push side of claude-creds-sync.{timer,path,service} (see
# server_tools/sync_claude_creds_to_frita.sh) — this box's Claude OAuth token
# refreshes constantly via normal use, but the copy pushed to the executor's
# frita-claude-home can still go stale in the gap before the next sync fires.
# frita_executor_health() runs this directly on a creds_valid:false reading so
# a health *check* also fixes the thing it found broken, instead of just
# reporting yellow until claude-creds-sync.path/timer gets around to it.
FRITA_CREDS_SYNC_SCRIPT = os.path.expanduser('~/server_tools/sync_claude_creds_to_frita.sh')


def _resync_frita_creds(timeout):
    """Best-effort: re-push this box's current Claude OAuth token to the
    frita-executor. Returns True iff the script ran and exited 0 — a non-zero
    exit (e.g. local token itself expiring within 5min) just means "can't help
    right now", not an error worth raising."""
    try:
        r = subprocess.run([FRITA_CREDS_SYNC_SCRIPT], capture_output=True,
                            timeout=timeout, text=True)
        return r.returncode == 0
    except Exception:
        return False


def _probe_claude_sdk_endpoint(url, timeout):
    """Cheap reachability probe of the /claude_sdk WORK route. Returns one of:

      'ok'          — the route exists (any non-404 response, including a 405
                      'method not allowed' for our GET against a POST-only route,
                      or even a 4xx/5xx — the point is the path is mounted).
      'not_found'   — HTTP 404: the route the tool POSTs to is missing. This is
                      Frita's exact failure; the affected tabs must go red.
      'unreachable' — connection refused / timeout / DNS — executor is down.

    Deliberately does NOT POST a real job (that would launch an SDK run on every
    health sweep); a GET is enough to tell 'route missing' from 'route present'."""
    try:
        req = urllib.request.Request(url, method='GET')
        urllib.request.urlopen(req, timeout=timeout)
        return 'ok'
    except urllib.error.HTTPError as e:
        return 'not_found' if e.code == 404 else 'ok'
    except Exception:
        return 'unreachable'


def _probe_sdk_status(url, timeout):
    """GET a /claude_sdk_status endpoint; return parsed dict or None on failure."""
    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read(2000).decode('utf-8', errors='replace'))
    except Exception:
        return None


def frita_executor_health(timeout=None):
    """Health for the Claude-SDK executor that the Mazda minions actually use.

    GREEN only when the SDK-capable executor answers on :8799 (sdk + claude CLI
    + mom's-token creds all present). Also probes :8797 and, if a *different*
    no-SDK executor answers there, flags the recurring "ghost / duplicate stack"
    condition right in the status text so it never has to be hunted down again."""
    t = timeout or 6
    good = _probe_sdk_status(FRITA_EXEC_GOOD_URL, t)
    ghost = _probe_sdk_status(FRITA_EXEC_GHOST_URL, t)

    # Ghost detection on :8797. Three cases, in order:
    #  1) it answers the new status endpoint but is NOT SDK-ready, or is a
    #     different container than the good one on :8799  → confirmed ghost.
    #  2) status endpoint 404s but the old /health still answers → a stale
    #     executor running pre-status-endpoint code → also a ghost.
    #  3) nothing answers :8797 → clean, no ghost.
    ghost_warn = ''
    good_host = (good or {}).get('host')
    if ghost is not None:
        ghost_host = ghost.get('host')
        if not ghost.get('ready') or (good_host and ghost_host and ghost_host != good_host):
            ghost_warn = f' ⚠ GHOST on :8797 (host={ghost_host}, sdk={ghost.get("sdk_present")})'
    else:
        ghost_health = _probe_sdk_status('http://100.80.49.10:8797/health', t)
        if ghost_health is not None:
            ghost_warn = ' ⚠ GHOST on :8797 (stale executor, no SDK-status endpoint)'

    if good is None:
        return {'ok': False,
                'text': 'SDK executor UNREACHABLE on :8799 — Mazda minions cannot run '
                        'run_claude_code_sdk. Click "Start" to redeploy.' + ghost_warn}
    if not good.get('ready'):
        missing = [k for k in ('sdk_present', 'claude_present', 'creds_present')
                   if not good.get(k)]
        # creds_present-but-expired is the one failure mode this box can fix by
        # itself (re-push a fresh token) rather than needing a redeploy — try
        # that once before reporting down. See _resync_frita_creds.
        if good.get('creds_present') and good.get('creds_valid') is False:
            missing.append('creds_valid')
            if _resync_frita_creds(t):
                healed = _probe_sdk_status(FRITA_EXEC_GOOD_URL, t)
                if healed and healed.get('ready'):
                    return {'ok': True,
                            'concern': True,  # surfaced, but self-healed this sweep
                            'text': f'SDK OK on :8799 (host={healed.get("host")}) — '
                                    'auto-resynced an expired token.' + ghost_warn}
        return {'ok': False,
                'text': f'SDK executor on :8799 NOT ready (missing: {", ".join(missing)}; '
                        f'host={good.get("host")}) — minions broken.' + ghost_warn}
    return {'ok': True,
            'concern': bool(ghost_warn),  # up, but a shadowing ghost → yellow, not green
            'text': f'SDK OK on :8799 (host={good.get("host")}).' + ghost_warn}


# ── Document Vision health (classify_scan.py's 3-tier fallback) ─────────────
# tools/classify_scan.py falls back Gemini Flash -> ChatGPT-OAuth vision (reuses
# the Codex CLI's ~/.codex/auth.json session) -> a standalone OpenAI key. This
# check mirrors that exact chain so the dashboard can tell, cheaply (no paid API
# calls — just key/token presence and expiry, same signal classify_scan.py's own
# key-resolution would find), whether a scan dispatched right now has anything
# that can actually read it. GREEN needs 2+ tiers so single-tier flakiness (e.g.
# a Codex token that hasn't refreshed yet) doesn't cry wolf; YELLOW at exactly 1
# tier (one more outage away from a real halt); RED only when ALL THREE are
# unavailable — that's the signal process_scanned_document() gates on before
# dispatching Mazda at all (see DOCUMENT_VISION_HALT_MESSAGE).
ROL_FINANCES_ENV_PATH = os.path.join(ROL_FINANCES_DIR, '.env')


def _read_env_var(name, env_path=None):
    """Look up name in os.environ, falling back to a simple KEY=VALUE .env file.

    env_path defaults to the CURRENT value of ROL_FINANCES_ENV_PATH, read at
    call time (not as a mutable-default-arg frozen at def time), so tests can
    monkeypatch server.ROL_FINANCES_ENV_PATH and have it take effect."""
    val = os.environ.get(name)
    if val:
        return val
    if env_path is None:
        env_path = ROL_FINANCES_ENV_PATH
    try:
        for line in open(env_path):
            line = line.strip()
            if line.startswith(f'{name}='):
                return line.split('=', 1)[1].strip().strip('"').strip("'") or None
    except OSError:
        pass
    return None


def _jwt_claims(token):
    """Best-effort decode of a JWT's payload (no signature check — we only need exp)."""
    import base64
    try:
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def document_vision_health(timeout=None):
    """Health of the receipt/statement scan-classification vision chain.

    Checks the SAME three tiers classify_scan.py tries, in order, without
    spending any API budget: Gemini key present, Codex CLI OAuth access_token
    present and unexpired, standalone OpenAI key present."""
    tiers_up = []
    tiers_down = []

    gemini_key = _read_env_var('GEMINI_API_KEY') or _read_env_var('GOOGLE_API_KEY')
    if gemini_key:
        tiers_up.append('Gemini')
    else:
        tiers_down.append('Gemini (no GEMINI_API_KEY/GOOGLE_API_KEY)')

    codex_auth_path = os.path.expanduser('~/.codex/auth.json')
    try:
        auth = json.load(open(codex_auth_path))
        access_token = auth.get('tokens', {}).get('access_token', '')
        exp = _jwt_claims(access_token).get('exp', 0)
        if access_token and exp > time.time():
            tiers_up.append('ChatGPT-OAuth (Codex CLI)')
        else:
            tiers_down.append('ChatGPT-OAuth (Codex CLI token expired)')
    except (OSError, json.JSONDecodeError, AttributeError):
        tiers_down.append('ChatGPT-OAuth (no ~/.codex/auth.json)')

    if _read_env_var('OPENAI_API_KEY'):
        tiers_up.append('OpenAI key')
    else:
        tiers_down.append('OpenAI key (not configured)')

    n_up = len(tiers_up)
    text = f'{n_up}/3 vision tiers available: {", ".join(tiers_up) or "none"}.'
    if tiers_down:
        text += f' Down: {", ".join(tiers_down)}.'

    if n_up == 0:
        return {'ok': False,
                'text': 'ALL vision tiers down — Mazda cannot classify or read '
                        'scanned documents. ' + text}
    return {'ok': True, 'concern': n_up == 1, 'text': text}


MAZDA_PROVIDER_HEALTH_PATH = os.path.expanduser('~/.mazda/provider_health.json')
MAZDA_PROVIDER_HEALTH_WINDOW_SECONDS = 24 * 3600


def mazda_categorizer_fallback_health(timeout=None):
    """Health of the vendor-CATEGORIZATION LLM chain (STEP 3 of receipt intake:
    tools/categorizer/categorizer_main.py's gemini -> chatgpt-oauth (EG's
    account, then mom's) -> anthropic tiers). Distinct from document_vision_health
    above, which covers the earlier vision-CLASSIFICATION step and only checks
    credential presence, not real call outcomes.

    WHY THIS EXISTS: on 2026-07-20 the gemini CLI was missing/quota-exhausted
    on the executor for 3+ days before anyone noticed — every receipt just
    silently degraded to a null-category pending-review row, which looked like
    normal operation everywhere except a pile of NEEDS_VENDOR_KEY rows nobody
    was watching for. This reads tools/provider_health.py's event log (written
    by every real production call, not a synthetic probe — never burns quota
    just to monitor) so a provider going bad shows up here within one scan
    instead of days later."""
    try:
        with open(MAZDA_PROVIDER_HEALTH_PATH) as f:
            state = json.load(f)
    except FileNotFoundError:
        return {'ok': True, 'text': 'no categorizer LLM calls logged yet'}
    except (OSError, json.JSONDecodeError) as e:
        return {'ok': False, 'text': f'cannot read {MAZDA_PROVIDER_HEALTH_PATH}: {e}'}

    now = time.time()
    cutoff = now - MAZDA_PROVIDER_HEALTH_WINDOW_SECONDS

    recent_fallbacks = []
    account_entries = {}
    for key, entry in state.items():
        if key.endswith(':_fallbacks'):
            provider = key.rsplit(':', 1)[0]
            for ev in entry.get('events', []):
                if ev.get('time', 0) >= cutoff:
                    recent_fallbacks.append((provider, ev))
            continue
        account_entries[key] = entry

    if not account_entries:
        return {'ok': True, 'text': 'no categorizer LLM calls logged yet'}

    # "down" only when EVERY tracked provider:account's most recent event was
    # a failure — i.e. every known tier (including mom's fallback account) has
    # failed, not just one link in the chain that a later tier covered for.
    most_recent_per_account = []
    for key, entry in account_entries.items():
        last_success = entry.get('last_success', 0)
        last_failure = entry.get('last_failure', 0)
        most_recent_per_account.append((key, last_success >= last_failure, entry))

    all_last_failed = all(not ok for _, ok, _ in most_recent_per_account)

    if all_last_failed:
        details = '; '.join(
            f'{key}: {classify_failure(entry.get("last_failure_detail", ""))[1]}'
            for key, _, entry in most_recent_per_account
        )
        return {'ok': False, 'hard': True,
                'text': f'ALL categorizer LLM tiers currently failing — {details}. '
                        f'Receipts will degrade to null-category pending-review rows.'}

    if recent_fallbacks:
        summary = '; '.join(
            f'{provider} {ev["from"]}->{ev["to"]} ({classify_failure(ev.get("error",""))[1]})'
            for provider, ev in recent_fallbacks[-5:]
        )
        return {'ok': True, 'concern': True,
                'text': f'{len(recent_fallbacks)} fallback(s) in last 24h: {summary}'}

    return {'ok': True, 'text': f'{len(account_entries)} provider account(s) healthy on primary tier'}


def restart_mazda_categorizer_llm():
    """'Restart' for the LLM Provider Fallbacks tile: there's no service to
    bounce (this reads an event log, not a running process). The one real
    recovery action available here is re-pulling mom's cached Codex token
    (sync_moms_codex_token.sh) in case it just needed a refresh — then
    re-report current status. EG's own token/gemini quota/anthropic key have
    no remote fix a dashboard button can perform."""
    try:
        r = subprocess.run(
            [os.path.expanduser('~/server_tools/sync_moms_codex_token.sh')],
            capture_output=True, text=True, timeout=30)
        sync_note = (r.stdout or r.stderr or '').strip()[:200]
    except Exception as exc:
        sync_note = f'sync script error: {exc}'
    health = mazda_categorizer_fallback_health()
    return {'ok': health['ok'], 'text': f'Re-synced mom\'s Codex token ({sync_note}). {health["text"]}'}


DOCUMENT_VISION_HALT_MESSAGE = (
    'Scan NOT dispatched to Mazda: all document-vision tiers are down '
    '(Gemini key, ChatGPT-OAuth/Codex CLI, and OpenAI key all unavailable) — '
    'she has no way to classify or read the scanned image right now. '
    'Fix at least one vision tier, then use "Process Document" to retry.'
)


# Registry of named check functions usable via a SERVERS entry's 'check' key.
HEALTH_CHECKS = {
    'frita_executor_health': frita_executor_health,
    'win10_node_health': win10_node_health,
    'document_vision_health': document_vision_health,
    'chatgpt_provider_health': chatgpt_provider_health,
    'mazda_categorizer_fallback_health': mazda_categorizer_fallback_health,
}


def server_health(cfg, timeout=None):
    """Ping a server's health_url or tcp_check. Returns {ok, text} (or None if neither set).

    A cfg may instead provide 'check': <name> referencing HEALTH_CHECKS for a
    custom, body-aware probe (e.g. verifying the SDK executor, not just HTTP up).

    tcp_check: (host, port) — used for MCP proxies and other non-HTTP servers that
    only need a TCP connection test (no HTTP response to parse)."""
    check = cfg.get('check')
    if check:
        fn = HEALTH_CHECKS.get(check)
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


def classify_failure(text):
    """Map a raw error string to (class, human_label) so the dashboard reports the
    REAL failure mode instead of a generic/misleading one (today the ChatGPT
    provider canary labelled a 404 as 'rate-limited', which sent diagnosis down
    the wrong path). Used for provider + server errors."""
    t = (text or '').lower()
    if '429' in t or 'rate limit' in t or 'rate-limit' in t or 'rate_limit' in t or 'too many requests' in t or 'quota' in t:
        return ('rate_limit', 'rate-limited')
    if '401' in t or '403' in t or 'unauth' in t or 'forbidden' in t or 'invalid_api_key' in t or 'authentication' in t:
        return ('auth', 'auth error')
    if '404' in t or 'not found' in t:
        return ('not_found', 'provider error (404)')
    if 'timed out' in t or 'timeout' in t:
        return ('timeout', 'timeout')
    if 'connection refused' in t or 'refused' in t:
        return ('refused', 'connection refused')
    if 'unreachable' in t or 'no route' in t or 'name or service not known' in t:
        return ('unreachable', 'unreachable')
    return ('error', 'error')


def server_status_kind(cfg, health):
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
        d = win10_docker_ok()
        dependency_down = (d is False)
        host_unreachable = (d is None)
    return compute_server_status(
        health,
        starting=is_server_starting(key),
        restartable=key in RESTARTABLE_KEYS,
        host_unreachable=host_unreachable,
        dependency_down=dependency_down)


# ── Health-check caching ─────────────────────────────────────────────────────
# Servers reachable only via Tailscale DERP relay (e.g. the Letta Server box at
# 100.80.49.10 — `tailscale ping` shows it routing via DERP(ord) with 1.8s-10s+
# latency, sometimes timing out outright) have latency far beyond a single
# request's timeout. Polling them synchronously inside /api/server-health
# (hit every 5s by the frontend) made the status LED flap red/green as
# individual probes randomly raced the timeout. Instead, poll all
# active-check servers in a background thread with a generous timeout, and
# require consecutive failures before flipping a server to "down" — a single
# slow/dropped probe no longer flashes the LED red.
HEALTH_POLL_INTERVAL = 8
HEALTH_CHECK_TIMEOUT = 10
HEALTH_FAIL_THRESHOLD = 2

_health_cache = {}
_health_cache_lock = threading.Lock()


def _poll_all_health_once():
    for cfg in SERVERS:
        if not (cfg.get('health_url') or cfg.get('tcp_check') or cfg.get('check')):
            continue
        h = server_health(cfg, timeout=HEALTH_CHECK_TIMEOUT)
        with _health_cache_lock:
            entry = _health_cache.get(cfg['key'], {'fails': 0, 'result': None})
            if h.get('ok'):
                entry['fails'] = 0
                entry['result'] = h
            else:
                entry['fails'] += 1
                if entry['result'] is None or entry['fails'] >= HEALTH_FAIL_THRESHOLD:
                    entry['result'] = h
            _health_cache[cfg['key']] = entry


def _health_poll_loop():
    """Background daemon thread body: keep the health cache fresh."""
    while True:
        _poll_all_health_once()
        time.sleep(HEALTH_POLL_INTERVAL)


def cached_server_health(cfg):
    """Debounced health result for cfg from the background poll loop.

    Falls back to a synchronous (slow) probe on first access, before the
    background loop has populated the cache. Returns None for configs with
    neither health_url nor tcp_check, like server_health does."""
    if not (cfg.get('health_url') or cfg.get('tcp_check') or cfg.get('check')):
        return None
    with _health_cache_lock:
        entry = _health_cache.get(cfg['key'])
    if entry is not None:
        return entry['result']
    h = server_health(cfg, timeout=HEALTH_CHECK_TIMEOUT)
    with _health_cache_lock:
        _health_cache[cfg['key']] = {'fails': 0 if h.get('ok') else 1, 'result': h}
    return h


# ── SSH connection checks ────────────────────────────────────────────────────

_ssh_health_cache = {}
_ssh_health_lock = threading.Lock()
_ssh_log_cache = {}    # key -> deque of {seq, text}
_ssh_log_seq = 0
_ssh_log_lock = threading.Lock()


def get_ssh_connection(key):
    """Return the SSH_CONNECTIONS config dict for a key, or None."""
    for c in SSH_CONNECTIONS:
        if c['key'] == key:
            return c
    return None


def ssh_test(cfg, timeout=SSH_CONNECT_TIMEOUT):
    """Run a real `ssh ... echo CONNECTED` round trip against cfg. Returns {ok, text}."""
    target = f"{cfg['user']}@{cfg['host']}"
    cmd = ['ssh', '-o', f'ConnectTimeout={timeout}', '-o', 'BatchMode=yes',
           '-o', 'StrictHostKeyChecking=accept-new', target, 'echo CONNECTED && hostname']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
        out_lines = result.stdout.strip().splitlines()
        if result.returncode == 0 and out_lines and out_lines[0].strip() == 'CONNECTED':
            host = out_lines[1].strip() if len(out_lines) > 1 else '?'
            return {'ok': True, 'text': f'CONNECTED — {host}'}
        err_lines = (result.stderr or result.stdout or '').strip().splitlines()
        text = err_lines[-1][:160] if err_lines else f'ssh exited {result.returncode}'
        return {'ok': False, 'text': text}
    except subprocess.TimeoutExpired:
        return {'ok': False, 'text': f'ssh to {target} timed out after {timeout}s'}
    except Exception as e:
        return {'ok': False, 'text': f'ssh to {target} failed: {e}'}


def _tailscale_cli():
    """Return the available Tailscale CLI, including the WSL host fallback.

    A freshly migrated WSL distro may not have the Linux package installed
    even though the Windows host is connected to the same tailnet.  WSL
    interop exposes that host client as ``tailscale.exe``; using it keeps the
    peer-only entries in SSH Connections meaningful during/after migration.
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


def _tailscale_ping_test(host, timeout):
    ping_timeout = f'{timeout}s' if isinstance(timeout, int) else str(timeout)
    cmd = [
        _tailscale_cli(), 'ping',
        '--c=1',
        '--until-direct=false',
        f'--timeout={ping_timeout}',
        host,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 2,
        )
    except subprocess.TimeoutExpired:
        return {'ok': False, 'text': f'tailscale ping timed out after {timeout}s'}
    except Exception as e:
        return {'ok': False, 'text': f'tailscale ping failed: {e}'}

    out = (result.stdout or result.stderr or '').strip()
    first_line = out.splitlines()[0][:160] if out else f'tailscale ping exited {result.returncode}'
    return {'ok': result.returncode == 0, 'text': first_line}


def tailscale_test(cfg, timeout=SSH_CONNECT_TIMEOUT):
    """Check whether a Tailscale peer is actually reachable.

    `tailscale status` can briefly report mobile peers as offline even when a
    DERP ping succeeds, so fall back to a single Tailscale-layer ping before
    showing the dashboard red.
    """
    status_text = None
    try:
        result = subprocess.run(
            [_tailscale_cli(), 'status'],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        for line in result.stdout.splitlines():
            if line.split()[:1] == [cfg['host']]:
                status_text = line.strip()
                if 'offline' in line:
                    break
                return {'ok': True, 'text': status_text}
        if status_text is None:
            status_text = f"{cfg['host']} not found in tailscale status"
    except subprocess.TimeoutExpired:
        return {'ok': False, 'text': f'tailscale status timed out after {timeout}s'}
    except Exception as e:
        return {'ok': False, 'text': f'tailscale status failed: {e}'}

    ping = _tailscale_ping_test(cfg['host'], timeout)
    if ping.get('ok'):
        return {'ok': True, 'text': f"reachable by tailscale ping — {ping['text']}"}
    return {'ok': False, 'text': f"{status_text}; {ping['text']}"}


def connection_test(cfg, timeout=None):
    """Dispatch to the right health check based on cfg['check'] (default 'ssh').

    Uses cfg['timeout'] when set (for known-slow paths like DERP relays),
    falling back to SSH_CONNECT_TIMEOUT."""
    timeout = timeout if timeout is not None else cfg.get('timeout', SSH_CONNECT_TIMEOUT)
    if cfg.get('check') == 'tailscale':
        return tailscale_test(cfg, timeout=timeout)
    return ssh_test(cfg, timeout=timeout)


def _record_ssh_log(key, text):
    global _ssh_log_seq
    with _ssh_log_lock:
        _ssh_log_seq += 1
        buf = _ssh_log_cache.setdefault(key, deque(maxlen=SSH_LOG_TAIL))
        buf.append({'seq': _ssh_log_seq, 'text': text})


def _poll_all_ssh_once():
    for cfg in SSH_CONNECTIONS:
        h = connection_test(cfg)
        with _ssh_health_lock:
            entry = _ssh_health_cache.get(cfg['key'], {'fails': 0, 'result': None})
            if h.get('ok'):
                entry['fails'] = 0
                entry['result'] = h
            else:
                entry['fails'] += 1
                if entry['result'] is None or entry['fails'] >= SSH_HEALTH_FAIL_THRESHOLD:
                    entry['result'] = h
            _ssh_health_cache[cfg['key']] = entry
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        _record_ssh_log(cfg['key'], f"[{ts}] {'OK' if h['ok'] else 'FAIL'} — {h['text']}")


def _ssh_poll_loop():
    """Background daemon thread body: keep the SSH connection cache fresh."""
    while True:
        _poll_all_ssh_once()
        time.sleep(SSH_HEALTH_POLL_INTERVAL)


def cached_ssh_health(cfg):
    """Debounced SSH health result for cfg from the background poll loop —
    requires SSH_HEALTH_FAIL_THRESHOLD consecutive failures before reporting
    down, since a single slow DERP-relayed probe isn't a real outage.

    Falls back to a synchronous (slow) probe on first access, before the
    background loop has populated the cache."""
    with _ssh_health_lock:
        entry = _ssh_health_cache.get(cfg['key'])
    if entry is not None:
        return entry['result']
    h = connection_test(cfg)
    with _ssh_health_lock:
        _ssh_health_cache[cfg['key']] = {'fails': 0 if h.get('ok') else 1, 'result': h}
    return h

# How recently a log-only server (no health_url) must have written to its log
# to count as "appears running". Lettabot's heartbeat writes every ~5 minutes,
# so 15 minutes tolerates a couple of missed cycles before flipping red.
LOG_ACTIVITY_WINDOW = 900

def _format_age(seconds):
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
    only "is it alive" signal available. Returns {ok, text}, or None if the
    server has a health_url (use server_health instead) or no log_file."""
    if cfg.get('health_url') or not cfg.get('log_file'):
        return None
    log_file = cfg['log_file']
    try:
        age = time.time() - os.path.getmtime(log_file)
    except OSError:
        return {'ok': False, 'text': 'no log file found'}
    if age <= LOG_ACTIVITY_WINDOW:
        return {'ok': True, 'text': f'log active — last write {_format_age(age)} ago'}
    return {'ok': False, 'text': f'no recent log activity — last write {_format_age(age)} ago'}

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

def server_log_rows(cfg, q=''):
    """Build {status, rows} for a server. rows carry a stable 'seq' line key."""
    out = {'rows': []}

    # A real "up" health check always wins — flip green the moment the server
    # actually answers, rather than waiting out the "starting" window below.
    # The detail panel's status must agree with the sidebar tab — both go through
    # server_status_kind so a down-but-restartable server reads the same yellow
    # "concern" in the panel as on the tab (not a bare red "Down").
    health = cached_server_health(cfg)
    if health is not None and health.get('ok'):
        clear_server_starting(cfg['key'])
        out['status'] = dict(health)
        out['status']['kind'] = server_status_kind(cfg, health)
    elif is_server_starting(cfg['key']):
        out['status'] = {'ok': False, 'kind': 'starting',
                         'text': 'STARTING... — server startup in progress'}
    elif health is not None:
        out['status'] = dict(health)
        out['status']['kind'] = server_status_kind(cfg, health)
    else:
        # No health_url to ping — fall back to "is it still writing logs?".
        log_health = log_activity_health(cfg)
        if log_health is not None:
            out['status'] = dict(log_health)
            out['status']['kind'] = server_status_kind(cfg, log_health)

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


# ── Agent registry ────────────────────────────────────────────────────────────

def _msg_age_seconds(m, now):
    """Return how many seconds ago a message was created, or None on parse error."""
    from datetime import timezone
    raw = str(m.get('created_at') or m.get('date') or '').strip()
    if not raw:
        return None
    if raw.endswith('Z'):
        raw = raw[:-1] + '+00:00'
    elif len(raw) >= 19 and '+' not in raw and 'T' in raw:
        raw += '+00:00'
    try:
        ts = datetime.fromisoformat(raw[:32])
        if ts.tzinfo is None:
            from datetime import timezone
            ts = ts.replace(tzinfo=timezone.utc)
        return (now - ts).total_seconds()
    except Exception:
        return None


def _agent_activity_one(cfg, now):
    """Compute the activity status for a single agent config. Returns (dash_id, status)."""
    real_id = get_letta_id(cfg)
    dash_id = real_id or f'unknown-{cfg["name"].lower()}'
    if not real_id:
        return dash_id, 'idle'
    msgs = letta_messages(real_id, limit=5)
    if not msgs:
        return real_id, 'idle'
    # Sort ascending so last item is most recent message
    msgs_sorted = sorted(msgs, key=lambda m: str(m.get('created_at') or m.get('date') or ''))
    last = msgs_sorted[-1]
    age = _msg_age_seconds(last, now)
    if age is None or age > 60:
        return real_id, 'idle'
    mt = last.get('message_type', '')
    if mt in ('user_message', 'tool_call_message', 'reasoning_message'):
        return real_id, 'active'
    if mt == 'tool_return_message':
        tr = last.get('tool_return', {})
        if isinstance(tr, dict) and tr.get('status') == 'error':
            return real_id, 'error'
        return real_id, 'active'
    # assistant_message or unknown — agent just finished responding
    return real_id, 'idle'


def agent_activity_status():
    """Return {agent_id: 'active'|'error'|'idle'} for every configured Letta agent.

    Each agent's status requires a DERP-relayed round trip to the Letta API
    (3-8s). Fetched in parallel (not serially) and cached briefly so the
    frontend's 5s poll doesn't pile up dozens of concurrent multi-agent sweeps."""
    # Hold the lock for the whole get-or-compute so concurrent pollers share
    # one sweep instead of each starting their own.
    with _agent_activity_cache_lock:
        now_ts = time.time()
        cached = _agent_activity_cache.get('value')
        if cached is not None and now_ts - _agent_activity_cache.get('ts', 0.0) < AGENT_ACTIVITY_CACHE_TTL:
            return cached

        from datetime import timezone
        now = datetime.now(timezone.utc)
        results = {}
        with ThreadPoolExecutor(max_workers=max(1, len(LETTA_AGENTS))) as pool:
            for dash_id, status in pool.map(lambda cfg: _agent_activity_one(cfg, now), LETTA_AGENTS):
                results[dash_id] = status

        _agent_activity_cache['value'] = results
        _agent_activity_cache['ts'] = time.time()
        return results


# ── Agent health checks ───────────────────────────────────────────────────────

_agent_health_cache = {'value': None, 'ts': 0.0}
_agent_health_cache_lock = threading.Lock()
AGENT_HEALTH_CACHE_TTL = 60  # seconds; heavier than activity poll (fetches tool lists)

# Functional send errors: {agent_id: {'text': '...', 'ts': float}}
# Set when /api/test returns an error reply; cleared on next success.
# Persists across the 5s activity poll so the tab stays red until fixed.
_agent_send_errors: dict = {}
_agent_send_errors_lock = threading.Lock()


def record_agent_send_error(agent_id: str, error_text: str) -> None:
    with _agent_send_errors_lock:
        _agent_send_errors[agent_id] = {'text': error_text, 'ts': time.time()}
    # Invalidate health cache so next poll picks up the new error immediately.
    with _agent_health_cache_lock:
        _agent_health_cache['value'] = None


def clear_agent_send_error(agent_id: str) -> None:
    with _agent_send_errors_lock:
        _agent_send_errors.pop(agent_id, None)
    with _agent_health_cache_lock:
        _agent_health_cache['value'] = None


# ── ChatGPT/Codex provider-wide rate-limit probe ────────────────────────────
#
# 2026-06-18: messaging Mazda Receipt Linker "timed out" — actually an instant
# HTTP 429 llm_rate_limit from the shared chatgpt-plus-pro OAuth account, and
# every other agent tagged with that provider was equally broken (verified by
# probing Mazda Router too). _agent_send_errors only got populated when a
# human used the dashboard's Test feature, so the tabs stayed green until
# someone happened to try. This background loop probes the provider and, like
# Server Management/SSH Connections, turns every agent sharing it red as soon
# as the probe itself detects a problem.
#
# 2026-07-07: the probe used to SEND A REAL LLM MESSAGE ("ping") to a canary
# agent every sweep — ~40 full-context gpt-5.4-mini calls per awake-hour, and
# the canary's history grew with every ping/reply pair, so each probe got more
# expensive AND burned the very quota it was watching. Replaced with a
# ZERO-TOKEN probe: read the provider's own OAuth token from the Letta API
# (on this self-hosted server /v1/providers/ returns api_key_enc as plaintext
# token JSON) and ask the account's usage endpoint directly — the same
# endpoint Model Stats uses, but with the PROVIDER's token, so it still works
# after an Adam↔mom token swap. Extend PROVIDER_USAGE_PROBES to cover new
# provider types; no agent is ever messaged.
CHATGPT_PROVIDER_POLL_INTERVAL = 90  # seconds; each probe is a free usage-API call (zero LLM tokens)


def _provider_agent_ids(provider_name):
    """Real Letta IDs of every LETTA_AGENTS entry tagged with this llm_provider."""
    ids = []
    for cfg in LETTA_AGENTS:
        if cfg.get('llm_provider') == provider_name:
            real_id = get_letta_id(cfg)
            if real_id:
                ids.append(real_id)
    return ids


def _fetch_provider_oauth_creds(provider_name):
    """Return (creds_dict, provider_type) for a Letta provider, or (None, type).

    On this self-hosted server /v1/providers/ returns api_key_enc as plaintext
    JSON holding the OAuth bundle ({'access_token', 'account_id', ...}) — the
    same token the Letta server spends when an agent talks to the model, so a
    probe using it always watches the account the fleet is actually on."""
    with urllib.request.urlopen(f'{LETTA_BASE_URL}/v1/providers/', timeout=10) as resp:
        providers = json.loads(resp.read().decode())
    for p in providers:
        if p.get('name') != provider_name:
            continue
        raw = p.get('api_key_enc') or p.get('api_key')
        if not raw:
            return None, p.get('provider_type')
        try:
            creds = json.loads(raw)
        except ValueError:
            creds = {'access_token': raw}
        return creds, p.get('provider_type')
    return None, None


def _classify_codex_usage(usage):
    """Pure: map a chatgpt.com/backend-api/wham/usage payload to the probe's
    {'ok', 'text'} contract. Error text starts with 'llm_rate_limit:' so
    classify_failure() labels it 'rate-limited' like the old LLM probe did."""
    rl = usage.get('rate_limit') or {}
    windows = []
    for wkey, wlabel in (('primary_window', '5h'), ('secondary_window', 'weekly')):
        w = rl.get(wkey)
        if isinstance(w, dict):
            pct = float(w.get('used_percent') or 0)
            windows.append((wlabel, pct, _human_reset(w.get('reset_at')) or '?'))
    maxed = [f'{lbl} window {pct:.0f}% used, resets {reset}'
             for lbl, pct, reset in windows if pct >= 100]
    if rl.get('limit_reached') or maxed or not rl.get('allowed', True):
        return {'ok': False, 'text': f"llm_rate_limit: {'; '.join(maxed) or 'limit reached'}"}
    return {'ok': True, 'text': ' / '.join(f'{lbl} {pct:.0f}%' for lbl, pct, _ in windows)}


def _classify_claude_usage(usage):
    """Pure: map an api.anthropic.com/api/oauth/usage payload (same field
    contract as the Model Stats extractor: five_hour/seven_day utilization)
    to the probe's {'ok', 'text'} contract."""
    windows = []
    for key, label in (('five_hour', '5h'), ('seven_day', 'weekly')):
        w = usage.get(key) or {}
        pct = float(w.get('utilization') or 0)
        windows.append((label, pct, _human_reset(w.get('resets_at')) or '?'))
    maxed = [f'{lbl} window {pct:.0f}% used, resets {reset}'
             for lbl, pct, reset in windows if pct >= 100]
    if maxed:
        return {'ok': False, 'text': f"llm_rate_limit: {'; '.join(maxed)}"}
    return {'ok': True, 'text': ' / '.join(f'{lbl} {pct:.0f}%' for lbl, pct, _ in windows)}


def _probe_usage_endpoint(url, headers, classify, timeout=20):
    """Shared fetch half of the zero-token probes: GET a usage endpoint with the
    provider's token and classify the payload. 401 → auth error (the provider's
    token is what Letta itself would fail with); 429 → the account is already
    being throttled at the door."""
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return classify(json.loads(resp.read().decode()))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return {'ok': False, 'text': 'provider OAuth token rejected (HTTP 401)'}
        if e.code == 429:
            return {'ok': False, 'text': 'llm_rate_limit: usage API returned HTTP 429'}
        return {'ok': False, 'text': f'HTTP {e.code}'}
    except Exception as e:
        return {'ok': False, 'text': str(e)}


def _probe_codex_usage(creds, timeout=20):
    """Zero-token ChatGPT/Codex quota check via the wham/usage endpoint (the
    same one Model Stats reads, but with the PROVIDER's token, not ~/.codex)."""
    return _probe_usage_endpoint(
        'https://chatgpt.com/backend-api/wham/usage',
        {'Authorization': 'Bearer ' + (creds.get('access_token') or ''),
         'ChatGPT-Account-Id': creds.get('account_id', ''),
         'OpenAI-Beta': 'codex-1', 'originator': 'codex_cli_rs', 'User-Agent': 'codex'},
        _classify_codex_usage, timeout)


def _probe_claude_usage(creds, timeout=20):
    """Zero-token Anthropic quota check. No Letta provider is Claude-backed
    today, but registering it means any future one gets the same free probe."""
    token = (creds.get('access_token')
             or (creds.get('claudeAiOauth') or {}).get('accessToken') or '')
    return _probe_usage_endpoint(
        'https://api.anthropic.com/api/oauth/usage',
        {'Authorization': 'Bearer ' + token,
         'anthropic-beta': 'oauth-2025-04-20', 'User-Agent': 'claude-code/2.0.32'},
        _classify_claude_usage, timeout)


# provider_type (from /v1/providers/) → zero-token usage probe. Add entries here
# to cover new provider types; a type with no entry is silently skipped rather
# than pinged with an LLM call.
PROVIDER_USAGE_PROBES = {
    'chatgpt_oauth': _probe_codex_usage,
    'anthropic': _probe_claude_usage,
    'anthropic_oauth': _probe_claude_usage,
}


# ── ChatGPT provider auto-failover ────────────────────────────────────────────
# Two ChatGPT Plus accounts exist; the provider row holds one token and the
# other is parked in a standby file on the Letta box. When the ACTIVE account
# exhausts a rate window but the STANDBY probe shows headroom, swap the row
# (the swap script also parks the displaced token as the new standby), so the
# fleet degrades to "other account" instead of "dead until reset".
CHATGPT_FAILOVER_HOST = 'adamsl@100.80.49.10'
CHATGPT_FAILOVER_STANDBY_FILE = '/home/adamsl/letta-backups/chatgpt_standby_token.json'
CHATGPT_FAILOVER_SWAP_CMD = '/home/adamsl/server_tools/swap_chatgpt_provider_token.sh'
CHATGPT_FAILOVER_MIN_INTERVAL = int(os.environ.get('CHATGPT_FAILOVER_MIN_INTERVAL', '1800'))
_chatgpt_failover = {'last_swap_ts': 0.0, 'last_note': ''}


def failover_should_trigger(probe_text, now_ts, last_swap_ts,
                            min_interval=None):
    """Pure gate: only a genuine rate-limit triggers failover (auth/network
    errors would just install a token with the same problem), and swaps are
    spaced at least min_interval apart so two capped accounts can't ping-pong."""
    if min_interval is None:
        min_interval = CHATGPT_FAILOVER_MIN_INTERVAL
    if not str(probe_text).startswith('llm_rate_limit'):
        return False
    return (now_ts - last_swap_ts) >= min_interval


def _standby_has_headroom():
    """Read the standby token off the Letta box and probe its usage API.
    Returns (ok, note); ok=True only when the standby is NOT rate-limited."""
    try:
        r = subprocess.run(['ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes',
                            CHATGPT_FAILOVER_HOST, f'cat {CHATGPT_FAILOVER_STANDBY_FILE}'],
                           capture_output=True, text=True, timeout=20)
        if r.returncode != 0 or not r.stdout.strip():
            return False, 'standby token file missing/unreadable'
        creds = json.loads(r.stdout.strip())
    except Exception as e:
        return False, f'standby read failed: {e}'
    probe = _probe_codex_usage(creds)
    if probe['ok']:
        return True, f"standby has headroom ({probe['text']})"
    return False, f"standby also limited ({probe['text'][:80]})"


def _run_chatgpt_failover_swap():
    """Execute the swap script on the Letta box. Returns (ok, note)."""
    try:
        r = subprocess.run(['ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes',
                            CHATGPT_FAILOVER_HOST, CHATGPT_FAILOVER_SWAP_CMD],
                           capture_output=True, text=True, timeout=60)
        out = ((r.stdout or '') + (r.stderr or '')).strip()
        return ('SWAP_OK' in out), (out[-200:] or f'swap exited {r.returncode}')
    except Exception as e:
        return False, f'swap failed: {e}'


def _maybe_chatgpt_failover(probe, provider_name):
    """Called when the active account's probe failed. On a successful swap,
    returns a fresh probe of the newly-installed token; otherwise None."""
    now = time.time()
    if not failover_should_trigger(probe.get('text', ''), now,
                                   _chatgpt_failover['last_swap_ts']):
        return None
    ok, note = _standby_has_headroom()
    if not ok:
        _chatgpt_failover['last_note'] = note
        return None
    _chatgpt_failover['last_swap_ts'] = now  # even a failed attempt starts the cooldown
    swapped, snote = _run_chatgpt_failover_swap()
    _chatgpt_failover['last_note'] = snote
    if not swapped:
        print(f'[chatgpt-failover] swap FAILED: {snote}', flush=True)
        return None
    print(f'[chatgpt-failover] provider token swapped to standby account — {note}', flush=True)
    try:
        creds, _ptype = _fetch_provider_oauth_creds(provider_name)
        if creds:
            return _probe_codex_usage(creds)
    except Exception:
        pass
    return None


def _poll_chatgpt_provider_once(provider_name=CHATGPT_PLUS_PRO):
    """One sweep: read the provider's OAuth token from the Letta API, ask the
    account's usage endpoint whether it's rate-limited (zero LLM tokens), and
    propagate ok/error to every tagged agent via _agent_send_errors."""
    affected = _provider_agent_ids(provider_name)
    if not affected:
        return
    try:
        creds, provider_type = _fetch_provider_oauth_creds(provider_name)
    except Exception:
        return  # Letta API unreachable — that's Server Management's signal, not a quota fact
    probe_fn = PROVIDER_USAGE_PROBES.get(provider_type)
    if not creds or not probe_fn:
        return  # no token / unprobeable provider type — leave agent state alone
    probe = probe_fn(creds)
    if not probe['ok'] and provider_type == 'chatgpt_oauth':
        fresh = _maybe_chatgpt_failover(probe, provider_name)
        if fresh is not None and fresh['ok']:
            probe = fresh
    for agent_id in affected:
        if probe['ok']:
            clear_agent_send_error(agent_id)
        else:
            _cls, label = classify_failure(probe['text'])
            record_agent_send_error(agent_id, f'{provider_name} {label} — {probe["text"]}')


def _chatgpt_provider_poll_loop():
    """Background daemon thread body: keep the chatgpt-plus-pro provider probe fresh."""
    while True:
        try:
            _poll_chatgpt_provider_once()
        except Exception:
            pass
        time.sleep(CHATGPT_PROVIDER_POLL_INTERVAL)


def _uses_claude_sdk(cfg):
    """True for agents whose tool calls hit the /claude_sdk WORK endpoint — either
    flagged explicitly (Frita, who has no required_tools) or via run_claude_code_sdk
    in required_tools (the Mazda minions)."""
    return bool(cfg.get('uses_claude_sdk')) or 'run_claude_code_sdk' in cfg.get('required_tools', [])


def agent_health_check(cfg, timeout=15, sdk_status=None):
    """Check if an agent is structurally healthy: ID resolvable + required tools attached.
    Also checks _agent_send_errors for functional failures recorded by /api/test, and
    (for Claude-SDK agents) that the /claude_sdk work endpoint isn't 404ing.

    Returns {ok, text, name} — ok=False turns the agent's tab red in the dashboard.
    Uses a longer timeout than letta_get's default (6s) because the /tools endpoint
    returns verbose JSON for agents with many tools over the DERP relay.

    sdk_status, when provided, is a pre-computed _probe_claude_sdk_endpoint() result
    shared across a health sweep so the work endpoint is probed once, not per-agent."""
    name = cfg.get('name', '?')
    real_id = get_letta_id(cfg)
    if not real_id:
        return {'ok': False, 'text': f'{name}: agent not found in Letta', 'name': name}

    # Functional failure recorded by a recent /api/test call?
    with _agent_send_errors_lock:
        send_err = _agent_send_errors.get(real_id)
    if send_err:
        return {'ok': False,
                'text': f'{name}: last send failed — {send_err["text"][:80]}',
                'name': name}

    # Claude-SDK work endpoint reachable? The dashboard's Frita-Executor LED only
    # watches /claude_sdk_status; this catches a 404 on /claude_sdk itself — the
    # route the tool actually POSTs to (Frita's "HTTP Error 404: Not Found").
    if _uses_claude_sdk(cfg):
        st = sdk_status if sdk_status is not None else _probe_claude_sdk_endpoint(FRITA_EXEC_WORK_URL, timeout)
        if st == 'not_found':
            return {'ok': False,
                    'text': f'{name}: Claude SDK endpoint /claude_sdk returns 404 — '
                            f'run_claude_code_sdk tool calls will fail',
                    'name': name}
        if st == 'unreachable':
            return {'ok': False,
                    'text': f'{name}: Claude SDK executor unreachable on :8799 — '
                            f'run_claude_code_sdk tool calls will fail',
                    'name': name}

    required = cfg.get('required_tools', [])
    if not required:
        return {'ok': True, 'text': f'{name}: agent found', 'name': name}

    # Letta paginates this endpoint at 10 by default; agents with more tools
    # would falsely report required tools as missing without an explicit limit.
    tools_data = letta_get(f'/v1/agents/{real_id}/tools?limit=100', timeout=timeout)
    if tools_data is None:
        return {'ok': False, 'text': f'{name}: could not fetch tool list from Letta', 'name': name}

    tool_names = {t.get('name') for t in (tools_data if isinstance(tools_data, list) else [])}
    missing = [t for t in required if t not in tool_names]
    if missing:
        return {'ok': False,
                'text': f'{name}: missing required tools: {", ".join(missing)}',
                'name': name}
    return {'ok': True,
            'text': f'{name}: {", ".join(required)} present',
            'name': name}


def agent_health_status():
    """Return {agent_id: {ok, text, name}} for every agent that declares required_tools.

    Fetches tool lists via the Letta API (one request per agent with required_tools);
    results cached for AGENT_HEALTH_CACHE_TTL seconds."""
    with _agent_health_cache_lock:
        now_ts = time.time()
        cached = _agent_health_cache.get('value')
        if cached is not None and now_ts - _agent_health_cache.get('ts', 0.0) < AGENT_HEALTH_CACHE_TTL:
            return cached

        checked = [cfg for cfg in LETTA_AGENTS
                   if cfg.get('required_tools') or _uses_claude_sdk(cfg)]
        # Probe the shared /claude_sdk work endpoint ONCE for the whole sweep — a
        # 404/outage there is infrastructure-wide, so every SDK agent reflects the
        # same result (mirrors the chatgpt-provider canary turning the fleet red).
        sdk_status = (_probe_claude_sdk_endpoint(FRITA_EXEC_WORK_URL, 6)
                      if any(_uses_claude_sdk(c) for c in checked) else None)
        results = {}
        with ThreadPoolExecutor(max_workers=max(1, len(checked))) as pool:
            for result in pool.map(lambda c: agent_health_check(c, timeout=15, sdk_status=sdk_status), checked):
                name = result['name']
                # Find the agent's real ID to use as the map key
                cfg = next((c for c in checked if c['name'] == name), None)
                if cfg:
                    real_id = get_letta_id(cfg) or f'unknown-{name.lower()}'
                    results[real_id] = result

        _agent_health_cache['value'] = results
        _agent_health_cache['ts'] = time.time()
        return results


def _refresh_agent_list_bg():
    """Background stale-while-revalidate refresh for build_agent_list."""
    try:
        build_agent_list(force_refresh=True)
    finally:
        with _agent_list_cache_lock:
            _agent_list_cache['refreshing'] = False


def build_agent_list(force_refresh=False):
    """Return the agent list for /api/agents, combining Letta agents + Claude."""
    now = time.time()
    if not force_refresh:
        with _agent_list_cache_lock:
            cached = _agent_list_cache.get('value')
            if cached is not None:
                if now - _agent_list_cache.get('ts', 0.0) < AGENT_LIST_CACHE_TTL:
                    return cached
                # Stale: serve it immediately and refresh in the background —
                # a cold rebuild can block >10s on the Letta roster fetch,
                # which trips the browser's fetch timeout.
                if not _agent_list_cache.get('refreshing'):
                    _agent_list_cache['refreshing'] = True
                    threading.Thread(target=_refresh_agent_list_bg, daemon=True).start()
                return cached

    agents = []
    for cfg in LETTA_AGENTS:
        real_id = get_letta_id(cfg)
        agents.append({
            'id': real_id or f'unknown-{cfg["name"].lower()}',
            'name': cfg['name'],
            'model': '',   # could fetch from Letta but keep it fast
            'letta': True,
        })
    agents.append({
        'id': 'agent-claude',
        'name': 'Claude',
        'model': 'claude-sonnet-4-6',
        'letta': False,
    })
    with _agent_list_cache_lock:
        _agent_list_cache['value'] = agents
        _agent_list_cache['ts'] = now
    return agents

def letta_id_for(agent_id):
    """Given a dashboard agent ID, return the Letta agent ID (or None if not Letta)."""
    if agent_id == 'agent-claude':
        return None
    # It already IS the Letta ID if it starts with 'agent-' and is a UUID
    if agent_id.startswith('agent-') and len(agent_id) > 15:
        return agent_id
    return None


# ── Model Stats (per-OAuth/CLI session token usage) ───────────────────────────
# Catch token-exhaustion early: each source reports current session usage % +
# reset date. Codex (ChatGPT OAuth) exposes a rich `rate_limits` block (5h +
# weekly used_percent + resets_at) in its session rollouts; Claude exposes
# cumulative tokens/cost per model in ~/.claude/stats-cache.json (no weekly
# limit %); Gemini has no machine-readable limit, so it's account-only.
# W11 = this box (local); R46 = mom's machine (rosemary46) over SSH.
R46_SSH_HOST = os.environ.get('R46_SSH_HOST', 'adamsl@100.72.34.38')

MODEL_STAT_SOURCES = {
    'w11-codex':  {'label': 'W11 Codex OAuth',  'kind': 'codex',  'host': None},
    'r46-codex':  {'label': 'R46 Codex OAuth',  'kind': 'codex',  'host': R46_SSH_HOST},
    'w11-claude': {'label': 'W11 Claude OAuth', 'kind': 'claude', 'host': None},
    'r46-claude': {'label': 'R46 Claude OAuth', 'kind': 'claude', 'host': R46_SSH_HOST},
    'gemini':     {'label': 'Antigravity CLI',  'kind': 'gemini', 'host': None},
}

# Extractors run on the target machine (locally or piped over SSH). Each prints a
# single JSON line so the dashboard parses one stdout blob regardless of host.
_CODEX_EXTRACT_PY = r'''
import json, os, time, urllib.request, urllib.error
home = os.path.expanduser("~")
model = None
try:
    for line in open(os.path.join(home, ".codex", "config.toml")):
        s = line.strip()
        if s.startswith("model") and "=" in s and "reasoning" not in s and "provider" not in s:
            model = s.split("=", 1)[1].strip().strip("\"'"); break
except Exception:
    pass
AUTH = os.path.join(home, ".codex", "auth.json")
def _usage(t):
    req = urllib.request.Request("https://chatgpt.com/backend-api/wham/usage",
        headers={"Authorization": "Bearer " + t["access_token"],
                 "ChatGPT-Account-Id": t.get("account_id", ""),
                 "OpenAI-Beta": "codex-1", "originator": "codex_cli_rs", "User-Agent": "codex"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
def _refresh_token(rt):
    body = json.dumps({"grant_type": "refresh_token", "client_id": "app_EMoamEEZ73f0CkXaXp7hrann",
                       "refresh_token": rt, "scope": "openid profile email"}).encode()
    req = urllib.request.Request("https://auth.openai.com/oauth/token", data=body,
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=25).read().decode())
def _persist(d, r):
    t = d["tokens"]
    for k in ("access_token", "refresh_token", "id_token"):
        if r.get(k): t[k] = r[k]
    d["last_refresh"] = time.strftime("%Y-%m-%dT%H:%M:%S.000000Z", time.gmtime())
    json.dump(d, open(AUTH, "w"))
    return t
def _refresh(d):
    return _persist(d, _refresh_token(d["tokens"]["refresh_token"]))
def _heal(d):
    # Codex refresh tokens are single-use/rotating: the live auth.json token may be
    # stale (already consumed) while a backup file still holds a valid one the codex
    # CLI left behind. Try each backup's token; on success persist into auth.json.
    import glob
    for f in sorted(glob.glob(AUTH + "*"), reverse=True):
        if f == AUTH:
            continue
        try:
            rt = json.load(open(f))["tokens"].get("refresh_token")
        except Exception:
            continue
        if not rt:
            continue
        try:
            return _persist(d, _refresh_token(rt)), f
        except Exception:
            continue
    return None, None
out = {"model": model, "as_of": time.time()}
# LIVE usage with SELF-HEAL on 401: refresh via the stored token, and if THAT is
# rejected (invalid_refresh_token), auto-recover from a still-valid backup token.
try:
    d = json.load(open(AUTH)); t = d["tokens"]
    try:
        out["usage"] = _usage(t)
    except urllib.error.HTTPError as e:
        if e.code != 401:
            raise
        try:
            out["usage"] = _usage(_refresh(d)); out["refreshed"] = True
        except urllib.error.HTTPError:
            healed, src = _heal(d)
            if healed is None:
                raise
            out["usage"] = _usage(healed); out["refreshed"] = True
            out["healed_from"] = os.path.basename(src)
except urllib.error.HTTPError as e:
    code = None
    try:
        code = (json.loads(e.read().decode()).get("error") or {}).get("code")
    except Exception:
        pass
    out["error"] = code or ("HTTP %d" % e.code)
    ra = e.headers.get("Retry-After") if e.headers else None
    if ra:
        try:
            out["retry_after"] = int(ra)
        except ValueError:
            pass
except Exception as e:
    out["error"] = str(e)[:140]
print(json.dumps(out))
'''

_CLAUDE_EXTRACT_PY = r'''
import json, os, time, subprocess, urllib.request, urllib.error
home = os.path.expanduser("~")
CRED = os.path.join(home, ".claude", ".credentials.json")
def _usage(at):
    req = urllib.request.Request("https://api.anthropic.com/api/oauth/usage",
        headers={"Authorization": "Bearer " + at,
                 "anthropic-beta": "oauth-2025-04-20", "User-Agent": "claude-code/2.0.32"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
def _refresh(d):
    o = d["claudeAiOauth"]
    body = json.dumps({"grant_type": "refresh_token", "refresh_token": o["refreshToken"],
                       "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e"}).encode()
    req = urllib.request.Request("https://platform.claude.com/v1/oauth/token", data=body,
        headers={"Content-Type": "application/json", "User-Agent": "anthropic"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=25).read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return _cli_refresh()
        raise
    o["accessToken"] = r["access_token"]
    if r.get("refresh_token"): o["refreshToken"] = r["refresh_token"]
    if r.get("expires_in"): o["expiresAt"] = int((time.time() + r["expires_in"]) * 1000)
    json.dump(d, open(CRED, "w"))
    return o["accessToken"]
def _cli_refresh():
    subprocess.run(["bash", "-lc", 'claude -p "ok"'], capture_output=True, timeout=30)
    d2 = json.load(open(CRED))
    return d2["claudeAiOauth"]["accessToken"]
out = {"as_of": time.time()}
try:
    d = json.load(open(CRED)); o = d["claudeAiOauth"]
    expired = bool(o.get("expiresAt")) and o["expiresAt"] / 1000 < time.time() + 60
    try:
        if expired:
            out["usage"] = _usage(_refresh(d)); out["refreshed"] = True
        else:
            out["usage"] = _usage(o["accessToken"])
    except urllib.error.HTTPError as e:
        if e.code in (401, 429):
            out["usage"] = _usage(_refresh(d)); out["refreshed"] = True
        else:
            raise
except urllib.error.HTTPError as e:
    out["error"] = "HTTP %d" % e.code
    ra = e.headers.get("Retry-After") if e.headers else None
    if ra:
        try:
            out["retry_after"] = int(ra)
        except ValueError:
            pass
except Exception as e:
    out["error"] = str(e)[:140]
try:
    sc = json.load(open(os.path.join(home, ".claude", "stats-cache.json")))
    days = sc.get("dailyModelTokens") or []
    if days:
        tbm = (days[-1].get("tokensByModel") or {})
        if tbm:
            out["recent_model"] = max(tbm, key=lambda k: sum(tbm[k].values()) if isinstance(tbm[k], dict) else tbm[k])
except Exception:
    pass
print(json.dumps(out))
'''

# Gemini CLI was shut off for individual accounts on 2026-06-18 and replaced by
# Google's Antigravity CLI (`agy`). Antigravity has no dedicated real-time quota
# API for free consumer accounts, so we derive a daily-requests window: the tier's
# daily request cap (loadCodeAssist) as the limit, and today's count of
# `streamGenerateContent` calls in agy's session logs as "used".
_ANTIGRAVITY_EXTRACT_PY = r'''
import json, os, glob, datetime, urllib.request, urllib.error
HOME = os.path.expanduser("~")
AG = os.path.join(HOME, ".gemini", "antigravity-cli")
out = {"account": None, "tier": None, "tier_id": None, "limit": None,
       "used": None, "resets_at": None, "logged_in": False, "error": None}
TOKEN = os.path.join(AG, "antigravity-oauth-token")
try:
    at = json.load(open(TOKEN))["token"]["access_token"]
    out["logged_in"] = True
    # Tier + daily request cap.
    req = urllib.request.Request(
        "https://daily-cloudcode-pa.googleapis.com/v1internal:loadCodeAssist",
        data=json.dumps({"metadata": {"ideType": "IDE_UNSPECIFIED",
            "platform": "PLATFORM_UNSPECIFIED", "pluginType": "GEMINI"}}).encode(),
        headers={"Authorization": "Bearer " + at, "Content-Type": "application/json"})
    d = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
    ct = d.get("currentTier") or {}
    out["tier"] = ct.get("name"); out["tier_id"] = ct.get("id")
    # Free Code Assist for individuals = 1000 req/day; paid tiers = 1500 req/day.
    out["limit"] = 1000 if ct.get("id") == "free-tier" else 1500
    # Account email (best-effort).
    try:
        ureq = urllib.request.Request("https://www.googleapis.com/oauth2/v1/userinfo",
            headers={"Authorization": "Bearer " + at})
        out["account"] = json.loads(urllib.request.urlopen(ureq, timeout=15).read().decode()).get("email")
    except Exception:
        pass
    # Used today = streamGenerateContent calls across today's session logs.
    today = datetime.date.today().strftime("%Y%m%d")
    used = 0
    for f in glob.glob(os.path.join(AG, "log", "cli-%s_*.log" % today)):
        try:
            with open(f, errors="ignore") as fh:
                used += sum(1 for ln in fh if "streamGenerateContent" in ln)
        except Exception:
            pass
    out["used"] = used
    # Google quota resets at midnight Pacific.
    try:
        from zoneinfo import ZoneInfo
        pt = ZoneInfo("America/Los_Angeles")
        now = datetime.datetime.now(pt)
        nxt = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        out["resets_at"] = nxt.astimezone(datetime.timezone.utc).isoformat()
    except Exception:
        pass
except FileNotFoundError:
    out["error"] = "not logged in (run `agy` and sign in)"
except urllib.error.HTTPError as e:
    out["error"] = "HTTP %d" % e.code
except Exception as e:
    out["error"] = str(e)[:160]
print(json.dumps(out))
'''


def _run_extractor(py_src, host, timeout=18):
    """Run an extractor on a machine (local if host is None, else over SSH) and
    return its parsed JSON, or {'error': ...}."""
    try:
        if host:
            # Feed the script over stdin (`python3 -`) so the remote shell can't
            # mangle a multi-line `-c` argument.
            cmd = ['ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes', host, 'python3', '-']
        else:
            cmd = [sys.executable, '-']
        r = subprocess.run(cmd, input=py_src, capture_output=True, text=True, timeout=timeout)
        line = (r.stdout or '').strip().splitlines()[-1] if (r.stdout or '').strip() else ''
        return json.loads(line) if line else {'error': (r.stderr or 'no output')[:200]}
    except Exception as e:
        return {'error': str(e)}


def _human_reset(when):
    """'in 3h 12m' / 'in 5d 2h' from a reset time (Unix epoch OR ISO-8601 string)."""
    if not when:
        return None
    if isinstance(when, str):
        try:
            from datetime import datetime
            when = datetime.fromisoformat(when.replace('Z', '+00:00')).timestamp()
        except Exception:
            return None
    secs = int(when - time.time())
    if secs <= 0:
        return 'now'
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f'in {d}d {h}h'
    if h:
        return f'in {h}h {m}m'
    return f'in {m}m'


_model_stats_cache = {}   # key → (timestamp, result)
MODEL_STATS_CACHE_TTL = 120  # seconds – prevent 429s from rapid polling

# Codex rate-limit windows are labeled by their duration (limit_window_seconds),
# not by position in the payload, so a single-window response still labels correctly.
_CODEX_WINDOW_ORDER = {'5-hour': 0, 'weekly': 1}

def _codex_window_label(seconds):
    try:
        s = int(seconds or 0)
    except (TypeError, ValueError):
        s = 0
    if s <= 0:
        return 'usage'
    if s <= 6 * 3600:       # ~5-hour window (18000s), allow slack
        return '5-hour'
    if s <= 8 * 86400:      # ~weekly window (604800s)
        return 'weekly'
    days = round(s / 86400)
    return f'{days}-day'

def model_stats(source_key):
    """Build the Model Stats payload for one source: provider/model, usage windows
    (used_percent + reset), a tokens summary, and a status (up/concern/down) so the
    tab can go red at 100%."""
    cached = _model_stats_cache.get(source_key)
    if cached and time.time() - cached[0] < MODEL_STATS_CACHE_TTL:
        return cached[1]
    src = MODEL_STAT_SOURCES.get(source_key)
    if not src:
        return {'ok': False, 'error': f'unknown source {source_key}'}
    out = _model_stats_uncached(source_key, src)
    try:
        _attach_usage_metrics(source_key, out)   # rate-of-change bar + leak detector
    except Exception as e:
        print(f'[model-usage] {source_key} attach failed: {e}')
    _model_stats_cache[source_key] = (time.time(), out)
    return out


def _looks_rate_limited(err):
    t = str(err).lower()
    return ('429' in t or 'rate limit' in t or 'rate_limit' in t
            or 'too many requests' in t)


def _fill_rate_limited(out, d, err):
    """A provider-side 429 means the ACCOUNT is throttled — that's red
    ('you cannot use this provider right now'), not a yellow 'usage
    unavailable' shrug. Surface the reset as an absolute epoch so the
    frontend can render a live countdown."""
    out['status'] = 'down'
    out['rate_limited'] = True
    retry_after = d.get('retry_after')
    if retry_after:
        until = (d.get('as_of') or time.time()) + retry_after
        out['rate_limited_until'] = until
        out['detail'] = f'RATE LIMITED ({err}) — resets {_human_reset(until)}'
    else:
        out['detail'] = f'RATE LIMITED ({err}) — reset time not reported'
    return out


def _model_stats_uncached(source_key, src):
    out = {'ok': True, 'key': source_key, 'label': src['label'], 'kind': src['kind'],
           'windows': [], 'status': 'up', 'detail': ''}

    if src['kind'] == 'codex':
        d = _run_extractor(_CODEX_EXTRACT_PY, src['host'], timeout=35)
        out['model'] = d.get('model')
        out['as_of'] = d.get('as_of')
        u = d.get('usage') or {}
        if d.get('error') or not u:
            err = d.get('error', 'no data')
            if _looks_rate_limited(err):
                return _fill_rate_limited(out, d, err)
            out['status'] = 'concern'
            hint = ' — run `codex login`' if 'expired' in str(err) or 'token' in str(err) else ''
            out['detail'] = f'usage unavailable: {err}{hint}'
            return out
        rl = u.get('rate_limit') or {}
        out['detail'] = f'plan: {u.get("plan_type", "?")}'
        worst = 0.0
        # Label each window by its actual duration (limit_window_seconds), NOT by
        # position: Codex sometimes returns only the weekly window in
        # primary_window with secondary_window null, so the old positional
        # ('primary'→5-hour, 'secondary'→weekly) mapping mislabeled the weekly bar
        # as "5-hour" and dropped the weekly bar entirely.
        for wkey, fallback_label in (
                ('primary_window', '5-hour'),
                ('secondary_window', 'weekly')):
            w = rl.get(wkey)
            if not isinstance(w, dict):
                continue
            up = float(w.get('used_percent') or 0)
            worst = max(worst, up)
            seconds = w.get('limit_window_seconds')
            out['windows'].append({
                # Current payloads identify windows by duration. Retain the
                # old positional labels only for legacy/mocked payloads that
                # omit it, instead of producing two generic "usage" rows.
                'label': (_codex_window_label(seconds)
                          if seconds is not None else fallback_label),
                'used_percent': round(up, 1),
                'resets_at': w.get('reset_at'),
                'resets_in': _human_reset(w.get('reset_at')),
            })
        # OpenAI temporarily removed the rolling 5-hour Codex cap on Plus/Pro/
        # Business tiers on 2026-07-12 (following the GPT-5.6 Sol launch), so
        # wham/usage now returns secondary_window: null — there's genuinely no
        # 5-hour data to show, not a bug on our end. Insert a placeholder row
        # for parity with the Claude card, which always shows both windows;
        # flip back to real data automatically once OpenAI restores the window.
        if not any(x['label'] == '5-hour' for x in out['windows']):
            out['windows'].append({
                'label': '5-hour', 'used_percent': None, 'resets_at': None,
                'resets_in': None, 'unavailable': True,
                'note': 'OpenAI paused the 5-hour cap 2026-07-12 (weekly-only, for now)',
            })
        out['windows'].sort(key=lambda x: _CODEX_WINDOW_ORDER.get(x['label'], 99))
        if rl.get('limit_reached') or worst >= 100:
            out['status'] = 'down'        # maxed → red, with reset shown
        elif worst >= 80:
            out['status'] = 'concern'     # getting close → yellow
        return out

    if src['kind'] == 'claude':
        d = _run_extractor(_CLAUDE_EXTRACT_PY, src['host'], timeout=35)
        out['as_of'] = d.get('as_of')
        out['model'] = d.get('recent_model') or 'Claude subscription'
        u = d.get('usage') or {}
        if d.get('error') or not u:
            err = d.get('error', 'no data')
            if _looks_rate_limited(err):
                return _fill_rate_limited(out, d, err)
            out['status'] = 'concern'
            out['detail'] = f'usage unavailable: {err}'
            return out
        worst = 0.0
        for key, label in (('five_hour', '5-hour'), ('seven_day', 'weekly')):
            w = u.get(key) or {}
            up = float(w.get('utilization') or 0)
            worst = max(worst, up)
            out['windows'].append({
                'label': label,
                'used_percent': round(up, 1),
                'resets_at': w.get('resets_at'),
                'resets_in': _human_reset(w.get('resets_at')),
            })
        eu = u.get('extra_usage') or {}
        if eu.get('is_enabled'):
            out['detail'] = f'extra usage {round(eu.get("utilization", 0))}% of ${eu.get("monthly_limit")}'
        else:
            out['detail'] = 'subscription (5h + weekly)'
        if worst >= 100:
            out['status'] = 'down'
        elif worst >= 80:
            out['status'] = 'concern'
        return out

    if src['kind'] == 'gemini':
        # Gemini CLI is retired; this reads Google's Antigravity CLI (`agy`).
        d = _run_extractor(_ANTIGRAVITY_EXTRACT_PY, src['host'], timeout=45)
        out['model'] = 'Antigravity (Code Assist)'
        if d.get('error') or not d.get('logged_in'):
            out['status'] = 'concern'
            out['detail'] = f'usage unavailable: {d.get("error", "no data")}'
            return out
        limit = d.get('limit') or 1000
        used = d.get('used') or 0
        up = (100.0 * used / limit) if limit else 0.0
        out['windows'].append({
            'label': 'daily requests',
            'used_percent': round(up, 1),
            'resets_at': d.get('resets_at'),
            'resets_in': _human_reset(d.get('resets_at')),
        })
        acct = d.get('account') or '?'
        tier = d.get('tier') or '?'
        out['detail'] = f'{acct} — {tier} — {used}/{limit} requests today'
        if up >= 100:
            out['status'] = 'down'
        elif up >= 80:
            out['status'] = 'concern'
        return out

    return out


# ── Model usage: rate-of-change bar + slow-leak detector ─────────────────────
#
# Rate metric (first version, deliberately simple): percentage-POINTS of the
# source's PRIMARY quota window (windows[0]: the 5-hour window for Codex and
# Claude, the daily request count for Antigravity) consumed per hour, measured
# over the last RATE_WINDOW_MINUTES of snapshots. This borrows the SRE
# "error-budget burn rate" idea (sre.google/workbook/alerting-on-slos): a quota
# window spanning H hours replenishes at 100/H %-points per hour, so
#
#     burn_multiple = observed %-points/hour ÷ (100 / window_hours)
#
# burn 1.0x = spending exactly as fast as the window refills — sustainable
# forever; anything above 1.0x will eventually max the account out. That makes
# the numbers comparable across providers with different window sizes, and it
# gives the thresholds real meaning instead of magic numbers:
#
#   RATE_WARN_BURN_MULTIPLE (default 1.0)  — the bar blinks yellow when the
#       last half-hour burned faster than the window replenishes. Interactive
#       coding legitimately bursts past 1.0x, so expect blinks during heavy
#       use; the point is "on pace to hit the cap", not "something is broken".
#       Raise it (e.g. 1.5–2.0) if it blinks too often in practice.
#   RATE_BAR_FULL_SCALE_MULTIPLE (default 2.0) — the bar renders 100% wide at
#       this burn multiple, so HALF a bar always means "sustainable pace".
#
# Leak detector (slow drain): the rate bar only sees the last 30 minutes, so a
# slow drip can hide under bursty-but-legit use — the 2026-07-07 provider-probe
# ping loop burned ~1.1x sustainable for HOURS and never looked dramatic in
# any 30-minute slice. Following the SRE multiwindow pattern (short window
# catches fast burns, long window catches slow ones), we also look back
# LEAK_LOOKBACK_MINUTES, split the history into LEAK_BUCKET_MINUTES buckets,
# and flag "slow token drain" when usage rose at least LEAK_MIN_RISE_PCT
# %-points in LEAK_MIN_RISING_BUCKETS CONSECUTIVE buckets. A single burst
# (one busy bucket, flat elsewhere) does NOT flag. This first version cannot
# know whether a task *should* be running, so a genuine 2-hour work session
# will also flag — acceptable for an early-warning light; tune below.
#
# History comes from two feeds through the same recording point
# (_attach_usage_metrics, called on every model-stats cache miss): the UI's
# 120s poll while the tab is open, plus _model_usage_sample_loop in the
# background so the 2h lookback exists even when nobody is watching. Snapshots
# persist to MODEL_USAGE_HISTORY_FILE so a dashboard restart doesn't blind the
# leak detector. Known first-version quirks (documented, not bugs): a rolling
# window's used_percent can FALL as old usage ages out — negative deltas clamp
# to 0; an Adam<->mom token swap jumps the percentage discontinuously and may
# cause one false warning cycle.

def _env_float(name, default):
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


MODEL_USAGE_SAMPLE_INTERVAL = _env_int('MODEL_USAGE_SAMPLE_INTERVAL', 300)         # s between background snapshots
RATE_WINDOW_MINUTES = _env_int('MODEL_RATE_WINDOW_MINUTES', 30)                    # rate looks at the last N minutes
RATE_MIN_SPAN_MINUTES = _env_int('MODEL_RATE_MIN_SPAN_MINUTES', 5)                 # need >= this span before showing a rate
RATE_WARN_BURN_MULTIPLE = _env_float('MODEL_RATE_WARN_BURN_MULTIPLE', 1.0)         # blink yellow above this burn multiple
RATE_BAR_FULL_SCALE_MULTIPLE = _env_float('MODEL_RATE_BAR_FULL_SCALE', 2.0)        # bar is 100% wide at this burn multiple
LEAK_BUCKET_MINUTES = _env_int('MODEL_LEAK_BUCKET_MINUTES', 30)
LEAK_LOOKBACK_MINUTES = _env_int('MODEL_LEAK_LOOKBACK_MINUTES', 120)
LEAK_MIN_RISE_PCT = _env_float('MODEL_LEAK_MIN_RISE_PCT', 0.5)                     # a bucket "rises" if it gains >= this
LEAK_MIN_RISING_BUCKETS = _env_int('MODEL_LEAK_MIN_RISING_BUCKETS', 3)             # consecutive rising buckets => leak
MODEL_USAGE_HISTORY_FILE = os.environ.get('MODEL_USAGE_HISTORY_FILE', '/tmp/model_usage_history.json')
MODEL_USAGE_HISTORY_KEEP_MINUTES = LEAK_LOOKBACK_MINUTES + 60                      # prune margin past the lookback

# windows[0] label → hours that quota window spans (drives the replenish rate).
# Unknown labels fall back to 5h, the most common primary window.
_WINDOW_HOURS = {'5-hour': 5.0, 'weekly': 168.0, 'daily requests': 24.0}
_DEFAULT_WINDOW_HOURS = 5.0

_usage_history_lock = threading.Lock()
_usage_history = None   # source_key → [[ts, pct], ...]; lazy-loaded from disk


def _load_usage_history():
    try:
        with open(MODEL_USAGE_HISTORY_FILE) as f:
            data = json.load(f)
        return {k: [list(map(float, s)) for s in v] for k, v in data.items()}
    except Exception:
        return {}


def _record_usage_sample(source_key, pct, now=None):
    """Append one (timestamp, used_percent) snapshot for a source, prune history
    older than the leak lookback (+margin), persist best-effort, and return a
    copy of the source's samples for the pure calculators below."""
    global _usage_history
    now = now if now is not None else time.time()
    with _usage_history_lock:
        if _usage_history is None:
            _usage_history = _load_usage_history()
        samples = _usage_history.setdefault(source_key, [])
        samples.append([now, float(pct)])
        cutoff = now - MODEL_USAGE_HISTORY_KEEP_MINUTES * 60
        while samples and samples[0][0] < cutoff:
            samples.pop(0)
        try:
            with open(MODEL_USAGE_HISTORY_FILE, 'w') as f:
                json.dump(_usage_history, f)
        except Exception:
            pass   # persistence is a nicety; in-memory history still works
        return [tuple(s) for s in samples]


def compute_usage_rate(samples, window_hours, now=None,
                       window_minutes=None, warn_multiple=None, full_scale=None):
    """Pure: %-points/hour consumed over the last window_minutes of samples,
    plus the burn multiple vs the window's replenish rate (see section comment
    for the math). Thresholds are parameters so tests don't depend on env."""
    now = now if now is not None else time.time()
    window_minutes = window_minutes if window_minutes is not None else RATE_WINDOW_MINUTES
    warn_multiple = warn_multiple if warn_multiple is not None else RATE_WARN_BURN_MULTIPLE
    full_scale = full_scale if full_scale is not None else RATE_BAR_FULL_SCALE_MULTIPLE
    recent = [s for s in samples if s[0] >= now - window_minutes * 60]
    if len(recent) < 2 or recent[-1][0] - recent[0][0] < RATE_MIN_SPAN_MINUTES * 60:
        return {'available': False,
                'reason': f'gathering data (need ≥{RATE_MIN_SPAN_MINUTES} min of snapshots)'}
    span_hours = (recent[-1][0] - recent[0][0]) / 3600.0
    # Rolling windows decay: used_percent can drop as old usage ages out, which
    # is not "negative spending" — clamp to 0 instead of showing it.
    pct_per_hour = max(0.0, recent[-1][1] - recent[0][1]) / span_hours
    sustainable = 100.0 / window_hours          # replenish rate of this window
    burn = pct_per_hour / sustainable
    return {
        'available': True,
        'pct_per_hour': round(pct_per_hour, 1),
        'burn_multiple': round(burn, 2),
        'sustainable_pct_per_hour': round(sustainable, 1),
        'bar_percent': round(min(100.0, 100.0 * burn / full_scale)),
        'warn': burn >= warn_multiple,
        'warn_at_multiple': warn_multiple,
        'window_minutes': window_minutes,
    }


def detect_slow_leak(samples, now=None, bucket_minutes=None, lookback_minutes=None,
                     min_rise_pct=None, min_rising_buckets=None):
    """Pure: flag a slow, steady token drain — usage rising in several
    CONSECUTIVE buckets across the long lookback, the pattern a background
    drip leaves and a single legitimate burst does not (see section comment)."""
    now = now if now is not None else time.time()
    bucket_minutes = bucket_minutes if bucket_minutes is not None else LEAK_BUCKET_MINUTES
    lookback_minutes = lookback_minutes if lookback_minutes is not None else LEAK_LOOKBACK_MINUTES
    min_rise_pct = min_rise_pct if min_rise_pct is not None else LEAK_MIN_RISE_PCT
    min_rising_buckets = min_rising_buckets if min_rising_buckets is not None else LEAK_MIN_RISING_BUCKETS
    n_buckets = max(1, lookback_minutes // bucket_minutes)
    longest_run = run = 0
    rising = evaluated = 0
    for i in range(n_buckets):                      # oldest bucket first
        end = now - (n_buckets - 1 - i) * bucket_minutes * 60
        start = end - bucket_minutes * 60
        inside = [s for s in samples if start <= s[0] < end]
        if len(inside) < 2:
            run = 0                                 # a data gap breaks "consecutive"
            continue
        evaluated += 1
        if inside[-1][1] - inside[0][1] >= min_rise_pct:
            rising += 1
            run += 1
            longest_run = max(longest_run, run)
        else:
            run = 0
    suspected = longest_run >= min_rising_buckets
    in_window = [s for s in samples if s[0] >= now - lookback_minutes * 60]
    total_rise = round(in_window[-1][1] - in_window[0][1], 1) if len(in_window) >= 2 else 0.0
    hours = lookback_minutes / 60
    return {
        'suspected': suspected,
        'rising_buckets': rising,
        'consecutive_rising': longest_run,
        'buckets_evaluated': evaluated,
        'needed_consecutive': min_rising_buckets,
        'total_rise_pct': total_rise,
        'text': (f'Slow token drain — +{total_rise}% over last {hours:g}h '
                 f'({longest_run} consecutive rising {bucket_minutes}-min windows)')
                if suspected else '',
    }


def _attach_usage_metrics(source_key, out):
    """Record a snapshot and attach 'rate' + 'leak' to a model-stats payload.
    Runs on every cache-miss fetch (UI poll or background sampler — the 120s
    stats cache dedupes). Also logs one debug line per fetch with the raw
    value, computed rate, thresholds, and leak verdict so the math can be
    checked against /tmp/dashboard_8765.log."""
    windows = out.get('windows') or []
    if out.get('ok') is False or not windows:
        return
    primary = windows[0]
    pct = primary.get('used_percent')
    if pct is None:
        return
    now = time.time()
    samples = _record_usage_sample(source_key, float(pct), now)
    window_hours = _WINDOW_HOURS.get(primary.get('label'), _DEFAULT_WINDOW_HOURS)
    rate = compute_usage_rate(samples, window_hours, now)
    rate['window_label'] = primary.get('label')
    leak = detect_slow_leak(samples, now)
    out['rate'] = rate
    out['leak'] = leak
    # Early warning propagates to the sub-nav tab color (yellow), never
    # overriding a real 'down'/'concern' from the quota itself.
    if (rate.get('warn') or leak['suspected']) and out.get('status') == 'up':
        out['status'] = 'concern'
    print(f"[model-usage] {source_key} pct={pct} samples={len(samples)} "
          f"rate={rate.get('pct_per_hour')}%/hr burn={rate.get('burn_multiple')}x "
          f"(warn≥{RATE_WARN_BURN_MULTIPLE}x → {rate.get('warn')}) "
          f"leak: {leak['consecutive_rising']}/{leak['needed_consecutive']} consecutive rising, "
          f"+{leak['total_rise_pct']}% over {LEAK_LOOKBACK_MINUTES}m → {leak['suspected']}")


def _model_usage_sample_loop():
    """Background snapshotter: fetch every source on a fixed cadence so usage
    history keeps flowing while nobody has the Model Stats tab open — without
    it the leak detector would only have data from moments someone watched.
    model_stats() itself records the snapshot; its cache dedupes with the UI."""
    while True:
        for key in MODEL_STAT_SOURCES:
            try:
                model_stats(key)
            except Exception:
                pass
        time.sleep(MODEL_USAGE_SAMPLE_INTERVAL)


# ── Web Terminal (Input Options → Terminal) ──────────────────────────────────
# A browser xterm.js panel connects to GET /api/terminal (WebSocket) and gets a
# full login shell in a pty on this box; when ?agent=<letta-id> is present the
# shell is primed with `letta --agent <id>` so the terminal opens inside a
# letta-code session for that agent (exiting letta drops back to bash).
#
# The server must stay stdlib-only, so the RFC 6455 handshake + framing are
# implemented here rather than pulling in `websockets`. ThreadingHTTPServer
# already gives each connection its own thread, so the handler thread simply
# stays alive for the socket's lifetime: a reader thread pulls frames off the
# browser socket (keystrokes, resizes, pings) while the handler thread pumps
# pty output back as binary frames.
#
# Wire protocol: client→server text frames carry JSON {"t":"i","d":<keys>} for
# input and {"t":"r","c":cols,"r":rows} for resize; server→client frames are
# binary raw pty bytes (binary, not text, because a pty read can split a UTF-8
# sequence mid-character and browsers kill the socket on invalid text frames).

import base64
import fcntl
import hashlib
import pty
import signal
import struct
import termios

_WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
_TERMINAL_ID_RE = re.compile(r'^[A-Za-z0-9_-]+$')
_LETTA_CODE_MAX_PROMPT_CHARS = 20000
_LETTA_CODE_FORBIDDEN_INPUT_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def validate_letta_code_prompt(value):
    """Accept message text while rejecting terminal-control traffic."""
    if not isinstance(value, str):
        raise ValueError('message must be text')
    value = value.replace('\r\n', '\n').replace('\r', '\n')
    if not value.strip():
        raise ValueError('message is empty')
    if len(value) > _LETTA_CODE_MAX_PROMPT_CHARS:
        raise ValueError(f'message is too long (maximum {_LETTA_CODE_MAX_PROMPT_CHARS} characters)')
    if _LETTA_CODE_FORBIDDEN_INPUT_RE.search(value):
        raise ValueError('message contains unsupported control characters')
    return value


def _letta_code_command():
    """Return a service-safe command prefix for this checkout's CLI.

    dashboard-server.service has a deliberately small PATH and the repo may not
    have a built letta.js yet. Prefer the canonical TypeScript dev entry point
    through Bun, using its stable user install path, then fall back to a linked
    or built CLI when needed.
    """
    bun = LETTA_CODE_BUN if os.path.isfile(LETTA_CODE_BUN) else shutil.which('bun')
    if bun:
        return [bun, 'run', 'dev', '--']
    letta = shutil.which('letta')
    if letta:
        return [letta]
    built = os.path.join(REPO_ROOT, 'letta.js')
    if os.path.isfile(built):
        return [built]
    raise FileNotFoundError(
        'Letta Code runtime not found (expected ~/.bun/bin/bun, PATH letta, '
        f'or {built})')


def run_letta_code_message(agent_id, prompt, timeout=330):
    """Run one Letta Code turn and expose only its final JSON result."""
    lid = letta_id_for(agent_id)
    if not lid or not _TERMINAL_ID_RE.fullmatch(lid):
        raise ValueError('invalid Letta agent id')
    clean_prompt = validate_letta_code_prompt(prompt)
    command = _letta_code_command()
    # `bun run dev` expands to a package script that invokes `bun` once more.
    # Preserve the resolved runtime directory for that nested command even
    # under dashboard-server.service's intentionally minimal PATH.
    runtime_path = os.path.dirname(command[0])
    child_path = os.environ.get('PATH', '')
    if runtime_path:
        child_path = runtime_path + (os.pathsep + child_path if child_path else '')
    proc = subprocess.run(
        [*command, '--agent', lid, '--prompt', clean_prompt,
         '--output-format', 'json', '--memfs-startup', 'skip'],
        cwd=REPO_ROOT, text=True, capture_output=True, timeout=timeout,
        env={**os.environ, 'PATH': child_path, 'LETTA_BASE_URL': LETTA_BASE_URL},
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or 'Letta Code failed').strip()
        raise RuntimeError(detail[-1000:])
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError('Letta Code returned invalid JSON') from exc
    result = payload.get('result')
    if not isinstance(result, str) or not result.strip():
        raise RuntimeError('Mazda returned no answer')
    return {'ok': True, 'reply': result, 'run': {
        'agent_id': payload.get('agent_id'),
        'conversation_id': payload.get('conversation_id'),
    }}


def ws_accept_key(sec_websocket_key):
    """Sec-WebSocket-Accept value for a client's Sec-WebSocket-Key (RFC 6455 §4.2.2)."""
    digest = hashlib.sha1((sec_websocket_key + _WS_GUID).encode('ascii')).digest()
    return base64.b64encode(digest).decode('ascii')


def ws_encode_frame(payload, opcode=0x2):
    """Encode one unmasked (server→client) WebSocket frame, FIN set."""
    head = bytes([0x80 | opcode])
    n = len(payload)
    if n < 126:
        head += bytes([n])
    elif n < 65536:
        head += bytes([126]) + struct.pack('!H', n)
    else:
        head += bytes([127]) + struct.pack('!Q', n)
    return head + payload


def ws_read_frame(rfile):
    """Read one client→server frame from a blocking file object.

    Returns (opcode, payload:bytes) with client masking removed and fragmented
    messages reassembled. Raises ConnectionError on EOF/protocol violation.
    """
    opcode = None
    payload = b''
    while True:
        head = rfile.read(2)
        if len(head) < 2:
            raise ConnectionError('websocket closed')
        fin = head[0] & 0x80
        op = head[0] & 0x0F
        masked = head[1] & 0x80
        n = head[1] & 0x7F
        if n == 126:
            n = struct.unpack('!H', rfile.read(2))[0]
        elif n == 127:
            n = struct.unpack('!Q', rfile.read(8))[0]
        if n > 1 << 20:
            raise ConnectionError('websocket frame too large')
        mask = rfile.read(4) if masked else b''
        data = rfile.read(n)
        if len(data) < n:
            raise ConnectionError('websocket closed mid-frame')
        if masked:
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        if op != 0:               # first (or only) fragment carries the opcode
            opcode = op
        payload += data
        if fin:
            return opcode, payload


def _terminal_spawn_shell(cols, rows, letta_agent_id):
    """pty.fork() a login shell sized cols×rows; returns (child_pid, master_fd).

    When letta_agent_id is set the command to open that agent is typed into the
    pty so it shows up in the terminal and runs as soon as bash is up.
    """
    pid, master_fd = pty.fork()
    if pid == 0:  # child
        env = dict(os.environ)
        env['TERM'] = 'xterm-256color'
        env['COLORTERM'] = 'truecolor'
        os.chdir(os.path.expanduser('~'))
        os.execvpe('bash', ['bash', '-l'], env)
    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, struct.pack('!HHHH', rows, cols, 0, 0))
    if letta_agent_id:
        os.write(master_fd, f'letta --agent {letta_agent_id}\n'.encode())
    return pid, master_fd


def _session_pids(sid):
    """PIDs whose session id == sid (read from /proc/<pid>/stat field 6).

    letta-code detaches into its own process group and reparents to init, so a
    process-group kill misses it — but it can't leave the pty's *session*
    without setsid(), which it doesn't call. Reaping by session catches it.
    """
    pids = []
    for entry in os.listdir('/proc'):
        if not entry.isdigit():
            continue
        try:
            with open(f'/proc/{entry}/stat', 'rb') as f:
                fields = f.read().rsplit(b')', 1)[1].split()
            # after the ')' the fields are: state ppid pgrp session ...
            if int(fields[3]) == sid:
                pids.append(int(entry))
        except (OSError, ValueError, IndexError):
            continue
    return pids


def _terminal_reap(pid):
    """Tear down the shell and every process in its pty session.

    pty.fork() made `pid` the session leader (sid == pid). We SIGHUP the whole
    session, then SIGKILL any survivor, so detached children (bun/letta) die too.
    """
    for sig, grace in ((signal.SIGHUP, 1.0), (signal.SIGKILL, 0.5)):
        for target in _session_pids(pid) or [pid]:
            try:
                os.kill(target, sig)
            except (ProcessLookupError, PermissionError):
                pass
        deadline = time.time() + grace
        while time.time() < deadline:
            try:
                done, _status = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                done = pid  # already reaped by someone else
            if done:
                break
            time.sleep(0.05)


# ── PC Monitor (per-machine RAM / disk / network) ─────────────────────────────
# One tab per PC. Each PC reports three metrics as 0-100 percentages so the
# frontend can draw progress bars and blink the tab yellow when any metric
# crosses its alert threshold. Collection runs a tiny POSIX-shell snippet on
# the target (locally for this box, over the existing key-auth SSH for the
# others) and parses the /proc + df output here, so the remote machines need
# nothing installed. Caveat: the Windows boxes are sampled through their WSL
# distro, so RAM reflects the WSL VM and network the VM's NICs. Disk samples
# the real Windows C: drive via the /mnt/c drvfs mount (falling back to / on
# a box without one) — the WSL VHD's sparse 1TB root was misleading.
#
# Tuning: thresholds and the network bar's full-scale capacity are env vars —
# override in dashboard-server.service, no code change needed.
PC_MONITORS = {
    'win11': {'label': 'Windows 11', 'host': None,
              'note': 'This machine — the live dashboard box, sampled via its WSL distro.'},
    'win10': {'label': 'Windows 10', 'host': LETTA_DOCKER_HOST,
              'note': 'The Letta box (100.80.49.10), sampled via its WSL distro.'},
    'moms46': {'label': 'Moms 46', 'host': R46_SSH_HOST,
               'note': "Mom's Rosemary46 Linux box (100.72.34.38)."},
}

PC_ALERT_THRESHOLDS = {
    'ram': float(os.environ.get('PC_ALERT_RAM_PERCENT', '90')),
    # Disk alerts on FREE space, not percent: yellow under warn GB free,
    # red (critical) at crit GB free or less.
    'disk_free_warn_gb': float(os.environ.get('PC_ALERT_DISK_FREE_WARN_GB', '5')),
    'disk_free_crit_gb': float(os.environ.get('PC_ALERT_DISK_FREE_CRIT_GB', '2')),
    'net': float(os.environ.get('PC_ALERT_NET_PERCENT', '80')),
}
# Full scale for the Network Traffic bar: 100% = this many Mbit/s of rx+tx.
PC_NET_CAPACITY_MBPS = float(os.environ.get('PC_NET_CAPACITY_MBPS', '100'))

_PC_METRICS_SH = (
    "echo ===MEM===; grep -E 'MemTotal|MemAvailable' /proc/meminfo; "
    "echo ===DISK===; df -kP /mnt/c 2>/dev/null || df -kP /; "
    "echo ===NET===; cat /proc/net/dev"
)


def parse_pc_metrics_output(text):
    """Parse the ===MEM===/===DISK===/===NET=== collector output into raw
    numbers: memory kB, disk 1K blocks (the Windows C: drive via /mnt/c, or /
    on a non-WSL box), and cumulative rx/tx bytes summed over every interface
    except loopback. Pure — unit-tested."""
    out = {'mem_total_kb': None, 'mem_avail_kb': None,
           'disk_total_kb': None, 'disk_used_kb': None, 'disk_avail_kb': None,
           'disk_mount': None,
           'net_rx_bytes': 0, 'net_tx_bytes': 0}
    section = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('===') and s.endswith('===') and len(s) > 6:
            section = s.strip('=')
            continue
        if section == 'MEM':
            if s.startswith('MemTotal:'):
                out['mem_total_kb'] = int(s.split()[1])
            elif s.startswith('MemAvailable:'):
                out['mem_avail_kb'] = int(s.split()[1])
        elif section == 'DISK':
            parts = s.split()
            if len(parts) >= 6 and parts[-1] in ('/mnt/c', '/') and parts[1].isdigit():
                out['disk_total_kb'] = int(parts[1])
                out['disk_used_kb'] = int(parts[2])
                out['disk_avail_kb'] = int(parts[3])
                out['disk_mount'] = parts[-1]
        elif section == 'NET' and ':' in s:
            name, _, rest = s.partition(':')
            fields = rest.split()
            # /proc/net/dev: rx bytes is field 0, tx bytes is field 8.
            if name.strip() != 'lo' and len(fields) >= 9:
                out['net_rx_bytes'] += int(fields[0])
                out['net_tx_bytes'] += int(fields[8])
    return out


def _pc_gb(kb):
    return kb / (1024.0 * 1024.0)


def build_pc_metrics(parsed, prev_net, now, thresholds=None, net_capacity_mbps=None):
    """Pure: parsed collector numbers + the previous network sample →
    (metric rows, new network sample). Each row carries percent / human text /
    level ('ok'|'warn'|'crit') so the frontend only has to draw bars. Disk
    alerts on GB free (warn under 5, crit at 2 or less by default); RAM and
    network alert on percent. Network traffic is a rate, so it needs two
    samples — the first request shows 'measuring…'."""
    th = thresholds or PC_ALERT_THRESHOLDS
    cap_mbps = net_capacity_mbps or PC_NET_CAPACITY_MBPS
    metrics = []

    mem_total = parsed.get('mem_total_kb')
    if mem_total:
        used = mem_total - (parsed.get('mem_avail_kb') or 0)
        pct = round(100.0 * used / mem_total, 1)
        level = 'warn' if pct >= th['ram'] else 'ok'
        metrics.append({'key': 'ram', 'label': 'RAM Usage', 'percent': pct,
                        'text': f'{_pc_gb(used):.1f} / {_pc_gb(mem_total):.1f} GB',
                        'level': level, 'alert': level != 'ok',
                        'tip': f"Alerts at {th['ram']:.0f}%"})

    disk_total = parsed.get('disk_total_kb')
    if disk_total:
        used = parsed.get('disk_used_kb') or 0
        free_gb = _pc_gb(parsed.get('disk_avail_kb') or 0)
        warn_gb = th.get('disk_free_warn_gb', 5.0)
        crit_gb = th.get('disk_free_crit_gb', 2.0)
        level = 'crit' if free_gb <= crit_gb else ('warn' if free_gb < warn_gb else 'ok')
        pct = round(100.0 * used / disk_total, 1)
        drive = 'C: ' if parsed.get('disk_mount') == '/mnt/c' else ''
        metrics.append({'key': 'disk', 'label': 'Hard Drive Usage', 'percent': pct,
                        'text': f'{drive}{_pc_gb(used):.0f} / {_pc_gb(disk_total):.0f} GB'
                                f' ({free_gb:.1f} GB free)',
                        'level': level, 'alert': level != 'ok',
                        'tip': f'Yellow under {warn_gb:.0f} GB free, '
                               f'red at {crit_gb:.0f} GB free or less'})

    total_bytes = parsed.get('net_rx_bytes', 0) + parsed.get('net_tx_bytes', 0)
    new_sample = (now, total_bytes)
    if prev_net and now > prev_net[0] and total_bytes >= prev_net[1]:
        rate_mbps = (total_bytes - prev_net[1]) * 8.0 / (now - prev_net[0]) / 1e6
        pct = round(min(100.0, 100.0 * rate_mbps / cap_mbps), 1)
        level = 'warn' if pct >= th['net'] else 'ok'
        metrics.append({'key': 'net', 'label': 'Network Traffic', 'percent': pct,
                        'text': f'{rate_mbps:.2f} Mbit/s (bar full at {cap_mbps:.0f})',
                        'level': level, 'alert': level != 'ok',
                        'tip': f"Alerts at {th['net']:.0f}%"})
    else:
        metrics.append({'key': 'net', 'label': 'Network Traffic', 'percent': 0,
                        'text': 'measuring…', 'level': 'ok', 'alert': False,
                        'tip': f"Alerts at {th['net']:.0f}%"})
    return metrics, new_sample


_pc_metrics_cache = {}    # key → (timestamp, payload)
_pc_net_last = {}         # key → (timestamp, cumulative rx+tx bytes)
_pc_last_good = {}        # key → last ok payload, served (marked stale) on a failed sample
PC_METRICS_CACHE_TTL = 10  # seconds — also the effective network-rate window


def pc_metrics(key):
    """Payload for one PC: run the collector (local or SSH), derive the three
    metric bars, and cache briefly so the frontend's tab-colour polling doesn't
    trigger an SSH per tab per tick. A failed sample (the cross-box Tailscale
    path stalls now and then, esp. on the first attempt after idle) serves the
    last good reading marked stale instead of an error — the next poll retries."""
    cfg = PC_MONITORS.get(key)
    if not cfg:
        return {'ok': False, 'error': f'unknown pc {key}', 'alert': False}
    cached = _pc_metrics_cache.get(key)
    if cached and time.time() - cached[0] < PC_METRICS_CACHE_TTL:
        return cached[1]
    host = cfg.get('host')
    if host:
        cmd = ['ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes',
               '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2',
               host, _PC_METRICS_SH]
    else:
        cmd = ['sh', '-c', _PC_METRICS_SH]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if not (r.stdout or '').strip():
            raise RuntimeError((r.stderr or 'collector produced no output').strip()[:200])
        parsed = parse_pc_metrics_output(r.stdout)
        now = time.time()
        metrics, sample = build_pc_metrics(parsed, _pc_net_last.get(key), now)
        _pc_net_last[key] = sample
        levels = [m.get('level', 'ok') for m in metrics]
        level = 'crit' if 'crit' in levels else ('warn' if 'warn' in levels else 'ok')
        out = {'ok': True, 'key': key, 'label': cfg['label'], 'note': cfg.get('note', ''),
               'metrics': metrics, 'alert': level != 'ok', 'level': level, 'as_of': now}
        _pc_last_good[key] = out
    except Exception as e:
        good = _pc_last_good.get(key)
        if good:
            out = dict(good)
            out['stale'] = True
            out['stale_error'] = str(e)
        else:
            out = {'ok': False, 'key': key, 'label': cfg['label'], 'error': str(e),
                   'alert': False, 'level': 'ok'}
    _pc_metrics_cache[key] = (time.time(), out)
    return out


# ── HTTP Handler ──────────────────────────────────────────────────────────────

class DashboardHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        agent_id = query.get('agent', [''])[0]

        if path == '/api/terminal':
            return self.handle_terminal_ws(query)

        if path == '/api/code-status':
            return self.json_response(get_code_status())
        if path == '/api/agents':
            return self.json_response(build_agent_list(force_refresh=query.get('refresh', ['0'])[0] == '1'))

        if path == '/api/agent-model':
            lid = letta_id_for(agent_id)
            if not lid:
                return self.json_response({'ok': False, 'error': 'not a Letta agent', 'options': []})
            data = letta_get(f'/v1/agents/{lid}', timeout=15) or {}
            llm = data.get('llm_config') or {}
            handle = llm.get('handle') or llm.get('model') or ''
            return self.json_response({'ok': True, 'current': handle,
                                        'options': agent_model_options(handle)})

        if path == '/api/router-agent':
            from router.classify import build_router_strategy
            strategy = build_router_strategy()
            if not strategy.agent_id:
                return self.json_response({'ok': False, 'error': 'router agent not found'})
            return self.json_response({'ok': True, 'agent_id': strategy.agent_id})

        if path == '/api/agent-voice':
            return self.json_response(agent_voice_payload(agent_id))

        if path == '/api/agent-activity':
            return self.json_response(agent_activity_status())

        if path == '/api/agent-health':
            return self.json_response(agent_health_status())

        if path == '/api/vendor-keys':
            return self.json_response(list_vendor_keys())

        if path == '/api/pending-vendor-review':
            return self.json_response(list_pending_vendor_review())

        if path == '/api/model-stats-sources':
            return self.json_response([
                {'key': k, 'label': v['label'], 'kind': v['kind']}
                for k, v in MODEL_STAT_SOURCES.items()
            ])

        if path == '/api/model-stats':
            src = query.get('source', [''])[0]
            return self.json_response(model_stats(src))

        if path == '/api/pc-monitors':
            return self.json_response([
                {'key': k, 'label': v['label'], 'note': v.get('note', '')}
                for k, v in PC_MONITORS.items()
            ])

        if path == '/api/pc-metrics':
            return self.json_response(pc_metrics(query.get('pc', [''])[0]))

        if path == '/api/agent-card':
            agent = next((a for a in build_agent_list()
                          if a['id'] == agent_id or a['name'] == agent_id), None)
            if not agent:
                return self.json_response({'error': 'agent not found'})
            return self.json_response(build_agent_card(agent['name'], agent['id']))

        if path == '/api/thoughts':
            if agent_id == 'agent-claude':
                return self.json_response([])   # Claude Code doesn't have thoughts
            lid = letta_id_for(agent_id)
            if lid:
                return self.json_response(letta_thoughts(lid))
            return self.json_response([])

        if path == '/api/messages':
            if agent_id == 'agent-claude':
                now = datetime.now(timezone.utc)
                rows = _load_json(CLAUDE_LOG_FILE)
                rows = [r for r in rows if _within_max_age(r, now)]
                return self.json_response(rows)
            lid = letta_id_for(agent_id)
            if lid:
                return self.json_response(letta_convo(lid))
            return self.json_response([])

        if path == '/api/toolcalls':
            if agent_id == 'agent-claude':
                return self.json_response(_load_json(CLAUDE_TOOL_LOG_FILE))
            lid = letta_id_for(agent_id)
            if lid:
                return self.json_response(letta_toolcalls(lid))
            return self.json_response([])

        if path == '/api/servers':
            return self.json_response([
                {
                    'key': s['key'],
                    'name': s['name'],
                    'note': s.get('note', ''),
                    'url': s.get('health_url'),
                    'health_url': s.get('health_url'),
                    'skills': s.get('skills', []),
                }
                for s in SERVERS
            ])

        if path == '/api/server-logs':
            key = query.get('server', [''])[0]
            q = query.get('q', [''])[0]
            cfg = get_server(key)
            if not cfg:
                return self.json_response({'status': {'ok': False, 'text': 'unknown server'}, 'rows': []})
            return self.json_response(server_log_rows(cfg, q))

        if path == '/api/server-health':
            # Overall health: returns per-server status + aggregate status.
            # A server is "down" if it has a health_url and it doesn't respond OK.
            # A server is "starting" if marked as such by a recent start action.
            # Log-only servers (no health_url) have no endpoint to ping — their
            # status is derived from whether they're still writing to their log
            # (see log_activity_health): recent writes → up, stale/missing → down.
            result = {
                'servers': [],
                'all_up': True,
                'any_down': False,
                'any_concern': False,
                'any_stale': False,
            }
            status_by_key = {}
            container_states = [None]  # lazily probed once per build if needed
            for cfg in SERVERS:
                has_active_check = cfg.get('health_url') or cfg.get('tcp_check') or cfg.get('check')
                key = cfg['key']
                restartable = key in RESTARTABLE_KEYS
                health = None
                if has_active_check:
                    health = cached_server_health(cfg)
                elif cfg.get('log_file'):
                    health = log_activity_health(cfg)

                if health is not None and health.get('ok'):
                    # A real "up" always wins — flip out of the starting window.
                    clear_server_starting(key)
                # Same classifier the detail panel uses (server_status_kind) so the
                # tab and the opened page never disagree.
                status = server_status_kind(cfg, health)
                if status is None:
                    continue
                status_by_key[key] = status

                # Root-cause grouping: if this server depends on a node that's not
                # healthy, mark it blocked_by so it reads as a symptom, not its own
                # failure (the node is restartable, so it reads 'concern' not 'down').
                dep = cfg.get('depends_on')
                blocked_by = dep if (dep and status_by_key.get(dep) not in (None, 'up')) else None

                down_for, stale = track_down_duration(key, status)
                _fc = classify_failure((health or {}).get('text', '')) if status != 'up' else None
                entry = {
                    'key': key,
                    'name': cfg['name'],
                    'status': status,
                    'restartable': restartable,
                    'down_for_seconds': down_for,
                    'stale': stale,
                }
                if blocked_by:
                    entry['blocked_by'] = blocked_by
                if _fc:
                    entry['failure_class'] = _fc[0]
                # Indicator #2: attach the Docker container status (exit code /
                # restart count) for Win10-hosted servers when they're not up.
                if key in WIN10_CONTAINERS and status != 'up':
                    if container_states[0] is None:
                        container_states[0] = win10_container_states()
                    cs = container_status_for(key, container_states[0])
                    if cs:
                        entry['container_status'] = cs
                result['servers'].append(entry)
                if status == 'down':
                    result['any_down'] = True
                    result['all_up'] = False
                elif status in ('concern', 'starting'):
                    result['any_concern'] = True
                if stale:
                    result['any_stale'] = True
            return self.json_response(result)

        if path == '/api/rol-finance-reports':
            month_key = query.get('month', [ROL_FINANCES_REPORTS_DEFAULT_MONTH])[0]
            if month_key not in ROL_FINANCES_REPORTS_MONTHS:
                month_key = ROL_FINANCES_REPORTS_DEFAULT_MONTH
            base_dir = _rol_reports_base_dir(month_key)
            result = []
            for r in _rol_finance_reports_for_month(month_key):
                report_file = os.path.join(base_dir, r['dir'], 'report.html')
                exists = os.path.isfile(report_file)
                status = _classify_report_status(report_file) if exists else 'missing'
                entry = {
                    'key': r['key'],
                    'label': r['label'],
                    'exists': exists,
                    'status': status,
                    'url': f'{ROL_FINANCES_REPORTS_URL_PREFIX}/{month_key}/{r["dir"]}/report.html' if exists else None,
                }
                # Red and yellow reports carry the human-facing reason and
                # recommended action pulled from the report itself, since the
                # iframe hides everything but Verified Transactions.
                if status in ('fail', 'review'):
                    detail = _extract_report_attention_detail(report_file)
                    if not detail:
                        detail = {
                            'badge': 'REVIEW NEEDED' if status == 'review' else 'FAILED',
                            'summary': 'This report needs attention but does not include a structured explanation.',
                            'recommended_action': 'Open the full report, identify the unresolved verification item, and update or reprocess the document.',
                        }
                    entry['attention_detail'] = detail
                    if detail:
                        # Preserve the existing API field for older red-row
                        # clients while they migrate to attention_detail.
                        if status == 'fail':
                            entry['failure_detail'] = detail
                result.append(entry)
            # Synthetic "Receipt Only" tab: receipts with no bank-statement
            # transaction. Include the exact resolved-file count so completed
            # receipt work is visible in the month overview even while every
            # statement/document placeholder is still red.
            receipt_count = len(_fetch_receipt_only_rows(month_key))
            result.append({
                'key': 'receipt-only',
                'label': 'Receipt Only',
                'exists': True,
                'status': None,
                'receipt_count': receipt_count,
                'url': f'{RECEIPT_ONLY_REPORT_PATH}?month={month_key}',
            })
            return self.json_response(result)

        if path == '/api/rol-finance-recent-reports':
            try:
                limit = int(query.get('limit', ['5'])[0])
            except (ValueError, TypeError):
                limit = 5
            return self.json_response(_rol_finance_recent_reports(limit))

        if path == '/api/expense-stored-events':
            try:
                since_ts = float(query.get('since', ['0'])[0])
            except (ValueError, TypeError):
                since_ts = 0.0
            return self.json_response(get_stored_expense_events(since_ts))

        if path == '/api/rol-finance-recent-scans':
            try:
                limit = int(query.get('limit', ['5'])[0])
            except (TypeError, ValueError):
                limit = 5
            month = (query.get('month', [''])[0] or '').strip() or None
            try:
                return self.json_response(_fetch_recent_scans(limit, month))
            except Exception as e:
                return self.json_response(
                    {'rows': [], 'queue_total': 0, 'limit': 5, 'error': str(e)})

        if path == '/api/rol-finance-month-status':
            try:
                return self.json_response({'months': _fetch_month_status()})
            except Exception as e:
                return self.json_response({'months': [], 'error': str(e)})

        if path == '/api/rol-finance-categories':
            return self.json_response({'categories': _rol_finance_categories()})

        if path == '/api/ssh-connections':
            return self.json_response([
                {'key': c['key'], 'name': c['name'], 'note': c.get('note', '')}
                for c in SSH_CONNECTIONS
            ])

        if path == '/api/ssh-connection-health':
            # Overall SSH health: a real `ssh ... echo CONNECTED` round trip per
            # connection. "down" means SSH itself is broken to that host.
            result = {'connections': [], 'all_up': True, 'any_down': False}
            for cfg in SSH_CONNECTIONS:
                h = cached_ssh_health(cfg)
                status = 'up' if h.get('ok') else 'down'
                result['connections'].append({'key': cfg['key'], 'name': cfg['name'], 'status': status})
                if status == 'down':
                    result['any_down'] = True
                    result['all_up'] = False
            return self.json_response(result)

        if path == '/api/ssh-connection-logs':
            key = query.get('conn', [''])[0]
            cfg = get_ssh_connection(key)
            if not cfg:
                return self.json_response({'status': {'ok': False, 'text': 'unknown connection'}, 'rows': []})
            with _ssh_log_lock:
                rows = list(_ssh_log_cache.get(key, []))
            return self.json_response({'status': cached_ssh_health(cfg), 'rows': rows})

        if path == '/api/ssh-connection-test':
            key = query.get('conn', [''])[0]
            cfg = get_ssh_connection(key)
            if not cfg:
                return self.json_response({'ok': False, 'text': 'unknown connection'})
            h = connection_test(cfg)
            with _ssh_health_lock:
                _ssh_health_cache[key] = {'fails': 0 if h.get('ok') else 1, 'result': h}
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            _record_ssh_log(key, f"[{ts}] {'OK' if h['ok'] else 'FAIL'} — {h['text']} (manual test)")
            return self.json_response(h)

        if path == '/' or path == '':
            return self.serve_file(os.path.join(HERE, 'dashboard.html'), 'text/html')

        if path == ROL_FINANCES_PLAN_PATH:
            return self.serve_file(ROL_FINANCES_PLAN_FILE, 'text/html')

        if path == RECEIPT_ONLY_REPORT_PATH:
            try:
                month_key = query.get('month', [ROL_FINANCES_REPORTS_DEFAULT_MONTH])[0]
                if month_key not in ROL_FINANCES_REPORTS_MONTHS:
                    month_key = ROL_FINANCES_REPORTS_DEFAULT_MONTH
                body = build_receipt_only_report_html(month_key)
            except Exception as e:
                from html import escape as _esc
                body = ('<!doctype html><meta charset="utf-8"><body>'
                        '<pre>Receipt Only build error: %s</pre>' % _esc(str(e)))
            data = body.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path == RECENT_REPORT_PATH:
            try:
                body = build_recent_report_html()
            except Exception as e:
                from html import escape as _esc
                body = ('<!doctype html><meta charset="utf-8"><body>'
                        '<pre>Recent Report build error: %s</pre>' % _esc(str(e)))
            data = body.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            # Always re-resolved — a cached copy would pin an older document.
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)
            return

        if path == SCANNER_REPORT_PATH:
            try:
                body = build_scanner_report_html(query.get('scanner', [''])[0])
            except Exception as e:
                from html import escape as _esc
                body = ('<!doctype html><meta charset="utf-8"><body>'
                        '<pre>Scanner Report build error: %s</pre>' % _esc(str(e)))
            data = body.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            # Always re-resolved — a cached copy would pin an older scan.
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)
            return

        if path.startswith(ROL_FINANCES_REPORTS_URL_PREFIX + '/'):
            fp = _report_file_for_url(path)
            if fp:
                return self.serve_file(fp, 'text/html')
            self.send_error(404)
            return

        if path == '/api/scanner-status':
            return self.json_response(scanner_status(query.get('scanner', [''])[0]))

        if path == SCANNER_IMAGE_URL_PREFIX:
            key = query.get('scanner', [''])[0]
            cfg = SCANNERS.get(key)
            if cfg:
                fp = os.path.join(SCAN_TOOLS_DIR, cfg['output'])
                if os.path.isfile(fp):
                    ctype = 'image/jpeg' if fp.endswith(('.jpg', '.jpeg')) else 'image/png'
                    return self.serve_file(fp, ctype)
            self.send_error(404)
            return

        if path == INTAKE_DOCUMENT_URL_PREFIX:
            fp = scanner_intake_document_path(query.get('scanner', [''])[0])
            if fp:
                ext = os.path.splitext(fp)[1].lower()
                ctype = {
                    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                    '.png': 'image/png', '.webp': 'image/webp',
                }.get(ext, 'application/octet-stream')
                return self.serve_file(fp, ctype)
            self.send_error(404)
            return

        for _prefix, _serve_base, _subtree in RECEIPT_MOUNTS:
            if path.startswith(_prefix + '/'):
                rel = unquote(path[len(_prefix) + 1:])
                base = os.path.abspath(_serve_base)
                fp = os.path.abspath(os.path.join(base, rel))
                if os.path.commonpath([fp, base]) == base and os.path.isfile(fp):
                    ext = fp.rsplit('.', 1)[-1].lower()
                    ctype = {
                        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
                        'gif': 'image/gif', 'webp': 'image/webp', 'pdf': 'application/pdf',
                    }.get(ext, 'application/octet-stream')
                    return self.serve_file(fp, ctype)
                self.send_error(404)
                return

        if path.startswith('/'):
            rel = path.lstrip('/')
            for base in (HERE, REPO_ROOT):
                fp = os.path.join(base, rel)
                if os.path.isfile(fp):
                    return self.serve_file(fp)

        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length)

        # /api/voice carries a binary audio blob — handle before decoding as text.
        if path == '/api/voice':
            return self._handle_voice(raw)

        body = raw.decode('utf-8', errors='replace')

        if path == '/api/claude-log':
            try:
                data = json.loads(body)
                _append_json(CLAUDE_LOG_FILE, _claude_log_lock, {
                    'date': data.get('date', datetime.now().isoformat()),
                    'type': data.get('type', 'assistant_message'),
                    'text': data.get('text', ''),
                })
                return self.json_response({'ok': True})
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)

        if path == '/api/claude-toollog':
            try:
                data = json.loads(body)
                _append_json(CLAUDE_TOOL_LOG_FILE, _claude_tool_log_lock, {
                    'date': data.get('date', datetime.now().isoformat()),
                    'type': data.get('type', 'tool_call'),
                    'text': data.get('text', ''),
                }, maxlen=200)
                return self.json_response({'ok': True})
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)

        if path == '/api/server-action':
            try:
                data = json.loads(body)
                server = data.get('server', '')
                action = data.get('action', '')

                if action == 'start' and server == 'executor':
                    result = start_executor_server()
                    return self.json_response(result)

                if action == 'start' and server == 'logger-api':
                    result = start_logger_api()
                    return self.json_response(result)

                if action == 'start' and server == 'frita-executor':
                    result = start_frita_executor()
                    return self.json_response(result)

                if action in ('start', 'restart') and server == 'dashboard':
                    result = restart_dashboard_server()
                    return self.json_response(result)

                # Generic restart — every Server Management entry is restartable
                # from the UI so the user never needs the command line.
                if action == 'restart':
                    return self.json_response(restart_server(server))

                return self.json_response({'ok': False, 'text': f'Unknown action: {action} for {server}'})
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)

        if path == '/api/tts':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            result = synthesize_speech(data.get('text', ''),
                                       voice=data.get('voice'))
            if not result.get('ok'):
                return self.json_response(result)
            return self.serve_file(result['path'], content_type='audio/mpeg')

        if path == '/api/scanner-scan':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(run_scanner(data.get('scanner', '')))

        if path == '/api/fix-printer':
            return self.json_response(fix_deskjet_printer())

        if path == '/api/process-document':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(process_scanned_document(
                data.get('scanner', ''),
                org_id=data.get('org_id', 1),
                engine=data.get('engine', 'gemini'),
            ))

        if path == '/api/process-pdf':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(process_pdf_document(
                data.get('file_path', ''),
                label=data.get('label'),
                org_id=data.get('org_id', 1),
                engine=data.get('engine', 'gemini'),
            ))

        if path == '/api/reprocess-report':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(reprocess_report(
                _resolve_report_path_alias(data.get('report_url', ''))))

        if path == '/api/expense-stored':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(record_stored_expense(data))

        if path == '/api/intake-status':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            result = record_intake_status(data)
            return self.json_response(result)

        if path == '/api/route-detect':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            from router.classify import build_router_strategy
            result = build_router_strategy().classify(data.get('text', ''))
            return self.json_response({'ok': True, **result})

        if path == '/api/agent-model':
            try:
                data = json.loads(body)
                lid = letta_id_for(data.get('agent', ''))
                model = data.get('model', '')
                if not lid:
                    return self.json_response({'ok': False, 'error': 'not a Letta agent'})
                cur = letta_get(f'/v1/agents/{lid}', timeout=15) or {}
                cur_handle = (cur.get('llm_config') or {}).get('handle') or ''
                if model not in agent_model_options(cur_handle):
                    return self.json_response({'ok': False, 'error': f'model {model!r} is not in the allowed list'})
                req = urllib.request.Request(
                    f'{LETTA_BASE_URL}/v1/agents/{lid}',
                    data=json.dumps({'model': model}).encode(),
                    headers={'Content-Type': 'application/json'},
                    method='PATCH',
                )
                with urllib.request.urlopen(req, timeout=30) as r:
                    resp = json.loads(r.read().decode())
                new_handle = (resp.get('llm_config') or {}).get('handle') or model
                return self.json_response({'ok': True, 'model': new_handle})
            except urllib.error.HTTPError as e:
                return self.json_response({'ok': False, 'error': f'letta {e.code}: {e.read().decode()[:200]}'})
            except Exception as e:
                return self.json_response({'ok': False, 'error': str(e)})

        if path == '/api/agent-voice':
            try:
                data = json.loads(body)
                return self.json_response(
                    patch_agent_voice(data.get('agent', ''), data.get('voice', '')))
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            except urllib.error.HTTPError as e:
                return self.json_response(
                    {'ok': False, 'error': f'letta {e.code}: {e.read().decode()[:200]}'})
            except Exception as e:
                return self.json_response({'ok': False, 'error': str(e)})

        if path == '/api/test':
            try:
                data = json.loads(body)
                agent_id = data.get('agent', '')
                text = data.get('text', '')

                if agent_id == 'agent-claude':
                    _clear_json(CLAUDE_LOG_FILE, _claude_log_lock)
                    _clear_json(CLAUDE_TOOL_LOG_FILE, _claude_tool_log_lock)
                    return self.json_response({'replies': [{'type': 'assistant_message', 'text': f'[stub] {agent_id} got: {text}'}]})

                lid = letta_id_for(agent_id)
                if lid:
                    reset_req = urllib.request.Request(
                        f'{LETTA_BASE_URL}/v1/agents/{lid}/reset-messages',
                        data=json.dumps({'add_default_initial_messages': False}).encode(),
                        headers={'Content-Type': 'application/json'},
                        method='PATCH',
                    )
                    try:
                        with urllib.request.urlopen(reset_req, timeout=10):
                            pass
                    except Exception:
                        pass

                    # Send a real message to the Letta agent
                    payload = json.dumps({
                        'messages': [{'role': 'user', 'content': text}],
                        'stream': False,
                    }).encode()
                    req = urllib.request.Request(
                        f'{LETTA_BASE_URL}/v1/agents/{lid}/messages',
                        data=payload,
                        headers={'Content-Type': 'application/json'},
                        method='POST',
                    )
                    try:
                        # Jeri may delegate to a Mazda minion via send_letta_message,
                        # which blocks on run_claude_code_sdk (up to a 300s subprocess
                        # timeout). Give the round trip enough headroom that a slow
                        # delegation doesn't look like a dashboard timeout.
                        with urllib.request.urlopen(req, timeout=330) as r:
                            resp = json.loads(r.read().decode())
                        replies = []
                        for m in resp.get('messages', []):
                            if m.get('message_type') == 'assistant_message':
                                replies.append({'type': 'assistant_message', 'text': _msg_text(m)})
                        if not replies:
                            # The agent ended its turn without a final assistant_message
                            # (e.g. it ran a tool and stopped). Fall back to showing
                            # the last tool call/return so the user sees what happened
                            # instead of a bare "(no reply)".
                            for m in resp.get('messages', []):
                                mtype = m.get('message_type')
                                if mtype in ('tool_call_message', 'tool_return_message', 'reasoning_message'):
                                    replies.append({'type': mtype, 'text': _msg_text(m)})
                        clear_agent_send_error(lid)
                        return self.json_response({'replies': replies or [{'type': 'assistant_message', 'text': '(no reply)'}]})
                    except Exception as e:
                        err_text = str(e)
                        record_agent_send_error(lid, err_text)
                        return self.json_response({'replies': [{'type': 'error', 'text': err_text}]})
                return self.json_response({'replies': [{'type': 'assistant_message', 'text': f'[stub] {agent_id} got: {text}'}]})
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)

        if path == '/api/letta-code-message':
            try:
                data = json.loads(body)
                return self.json_response(run_letta_code_message(
                    data.get('agent', ''), data.get('text', '')))
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            except ValueError as e:
                return self.error_response(str(e), 400)
            except subprocess.TimeoutExpired:
                return self.error_response('Mazda took too long to answer', 504)
            except Exception as e:
                return self.error_response(str(e), 502)
        if path == '/api/headless-prompt':
            # Headless mode: run letta -p with JSON output (no terminal UI noise)
            # Used by "Ask Mazda" to get clean, readable output without ANSI codes
            try:
                data = json.loads(body)
                agent_id = data.get('agent', '')
                prompt_text = data.get('prompt', '')
                if not prompt_text.strip():
                    return self.json_response({'ok': False, 'error': 'prompt is required'})
                return self.json_response(run_letta_headless(agent_id, prompt_text))
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)

        if path == '/api/recategorize-expense':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(recategorize_expense(
                data.get('date', ''),
                data.get('signed_amount', ''),
                data.get('vendor_key', ''),
                data.get('reporting_category', ''),
                data.get('description', ''),
                _resolve_report_path_alias(data.get('report_path', '')),
                data.get('expense_id'),
            ))

        if path == '/api/set-receipt-vendor':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(set_receipt_vendor(
                data.get('expense_id'), data.get('vendor_key', '')))

        if path == '/api/receipt-lookup':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(lookup_receipt(
                data.get('date', ''),
                data.get('signed_amount', ''),
                data.get('vendor_key', ''),
                data.get('description', ''),
                _resolve_report_path_alias(data.get('report_path', '')),
                data.get('expense_id'),
            ))

        if path == '/api/receipts-present':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(receipts_present(data.get('rows', [])))

        if path == '/api/save-expense-notes':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)
            return self.json_response(save_expense_notes(
                data.get('date', ''),
                data.get('signed_amount', ''),
                data.get('vendor_key', ''),
                data.get('description', ''),
                data.get('notes', ''),
                data.get('expense_id'),
            ))

        self.send_error(404)

    def _handle_voice(self, audio_bytes):
        filename = self.headers.get('X-Filename', 'audio.webm')
        result = handle_voice_upload(build_pipeline(), audio_bytes, filename)
        if result.get('ok'):
            _append_json(VOICE_LOG_FILE, _voice_log_lock, {
                'date': datetime.now().isoformat(),
                'raw': result.get('raw_transcript', ''),
                'cleaned': result.get('cleaned_text', ''),
            })
        return self.json_response(result)

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length).decode('utf-8')

    def _send_no_cache_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')

    def serve_file(self, file_path, content_type=None):
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            if content_type is None:
                ext = file_path.rsplit('.', 1)[-1]
                content_type = {
                    'html': 'text/html', 'js': 'application/javascript',
                    'css': 'text/css', 'json': 'application/json',
                    'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
                    'pdf': 'application/pdf',
                }.get(ext, 'application/octet-stream')
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(content))
            self._send_no_cache_headers()
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)

    def handle_terminal_ws(self, query):
        """Upgrade GET /api/terminal to a WebSocket and bridge it to a pty shell."""
        key = self.headers.get('Sec-WebSocket-Key')
        upgrade = (self.headers.get('Upgrade') or '').lower()
        if not key or upgrade != 'websocket':
            return self.error_response('expected a websocket upgrade', 400)

        letta_agent_id = ''
        raw_agent = query.get('agent', [''])[0]
        if raw_agent:
            lid = letta_id_for(raw_agent)
            # letta_id_for returns the id as-is for Letta agents; guard the exec.
            if lid and _TERMINAL_ID_RE.match(lid):
                letta_agent_id = lid
        try:
            cols = max(20, min(500, int(query.get('cols', ['80'])[0])))
            rows = max(5, min(200, int(query.get('rows', ['24'])[0])))
        except ValueError:
            cols, rows = 80, 24

        # Write the 101 by hand: a WebSocket upgrade must be HTTP/1.1, but this
        # handler's protocol_version is HTTP/1.0 (send_response would emit the
        # wrong status line and browsers would reject the upgrade). We also skip
        # the default Server/Date headers to keep the handshake minimal.
        handshake = (
            'HTTP/1.1 101 Switching Protocols\r\n'
            'Upgrade: websocket\r\n'
            'Connection: Upgrade\r\n'
            f'Sec-WebSocket-Accept: {ws_accept_key(key)}\r\n\r\n'
        )
        try:
            self.wfile.write(handshake.encode('ascii'))
            self.wfile.flush()
        except OSError:
            return

        sock = self.connection
        pid, master_fd = _terminal_spawn_shell(cols, rows, letta_agent_id)
        alive = threading.Event()
        alive.set()

        def pump_browser_to_pty():
            """Reader thread: browser frames → pty (input, resize, close)."""
            try:
                while alive.is_set():
                    opcode, data = ws_read_frame(self.rfile)
                    if opcode == 0x8:              # close
                        break
                    if opcode == 0x9:              # ping → pong
                        try:
                            sock.sendall(ws_encode_frame(data, opcode=0xA))
                        except OSError:
                            break
                        continue
                    if opcode not in (0x1, 0x2):   # ignore pong/other
                        continue
                    try:
                        msg = json.loads(data.decode('utf-8', 'ignore'))
                    except ValueError:
                        continue
                    if msg.get('t') == 'i':
                        os.write(master_fd, str(msg.get('d', '')).encode('utf-8'))
                    elif msg.get('t') == 'r':
                        c = max(20, min(500, int(msg.get('c', cols))))
                        r = max(5, min(200, int(msg.get('r', rows))))
                        fcntl.ioctl(master_fd, termios.TIOCSWINSZ,
                                    struct.pack('!HHHH', r, c, 0, 0))
            except (ConnectionError, OSError, ValueError):
                pass
            finally:
                alive.clear()

        reader = threading.Thread(target=pump_browser_to_pty, daemon=True)
        reader.start()

        # Handler thread: pty output → browser, until either side closes.
        import select as _select
        try:
            while alive.is_set():
                ready, _w, _e = _select.select([master_fd], [], [], 0.25)
                if not ready:
                    continue
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                try:
                    sock.sendall(ws_encode_frame(chunk, opcode=0x2))
                except OSError:
                    break
        finally:
            alive.clear()
            try:
                sock.sendall(ws_encode_frame(b'', opcode=0x8))
            except OSError:
                pass
            try:
                os.close(master_fd)
            except OSError:
                pass
            _terminal_reap(pid)

    def json_response(self, data):
        body = json.dumps(data, indent=2).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self._send_no_cache_headers()
        self.end_headers()
        self.wfile.write(body)

    def error_response(self, message, code=400):
        body = json.dumps({'error': message}).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self._send_no_cache_headers()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f'[{self.log_date_time_string()}] {fmt % args}')


class ReusableHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8765))
    server = ReusableHTTPServer(('0.0.0.0', port), DashboardHandler)
    print(f'Dashboard server on http://localhost:{port}/')
    print(f'Letta API: {LETTA_BASE_URL}')
    threading.Thread(target=_letta_remote_log_pull_loop, daemon=True).start()
    print(f'Pulling Letta server logs over SSH from {LETTA_DOCKER_HOST} every '
          f'{LETTA_REMOTE_LOG_PULL_INTERVAL}s -> {LETTA_REMOTE_LOG_CACHE}')
    # Pre-warm the agent-list cache so the first /api/agents after a restart
    # doesn't block the browser on the slow (~12-30s) Letta roster fetch.
    threading.Thread(target=build_agent_list, daemon=True).start()
    print('Pre-warming /api/agents cache in the background')
    threading.Thread(target=_health_poll_loop, daemon=True).start()
    print(f'Polling server health every {HEALTH_POLL_INTERVAL}s '
          f'(timeout={HEALTH_CHECK_TIMEOUT}s, fail-threshold={HEALTH_FAIL_THRESHOLD})')
    threading.Thread(target=_ssh_poll_loop, daemon=True).start()
    print(f'Polling {len(SSH_CONNECTIONS)} SSH connections every {SSH_HEALTH_POLL_INTERVAL}s')
    threading.Thread(target=_chatgpt_provider_poll_loop, daemon=True).start()
    print(f'Polling chatgpt-plus-pro provider health every {CHATGPT_PROVIDER_POLL_INTERVAL}s '
          f'(Mazda + {len(_provider_agent_ids(CHATGPT_PLUS_PRO)) - 1} minions)')
    threading.Thread(target=_model_usage_sample_loop, daemon=True).start()
    print(f'Sampling model usage every {MODEL_USAGE_SAMPLE_INTERVAL}s '
          f'(rate warn ≥{RATE_WARN_BURN_MULTIPLE}x sustainable; leak: '
          f'{LEAK_MIN_RISING_BUCKETS}×{LEAK_BUCKET_MINUTES}m rising of {LEAK_LOOKBACK_MINUTES}m)')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
