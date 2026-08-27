#!/usr/bin/env python3
"""
Dashboard SPA server.
Serves dashboard.html and proxies agent data from the Letta API.
Run: python3 server.py   (from /home/adamsl/letta-code/dashboard/)
Then open: http://localhost:8765/
"""
import json
import glob
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

from agents.letta_gateway import ILettaGateway
from agents.model_options import AgentModelOptionsService, select_model_options
from agents.urllib_letta_gateway import UrllibLettaGateway

from pydantic import ValidationError

from voice.synthesis import EdgeTtsSynthesizer, cache_path as synthesis_cache_path
from category_taxonomy import FallbackCategoryTaxonomy, MySqlCategoryTaxonomy
from chatgpt_provider_accounts import PROVIDER_ACCOUNT_SOURCES
from chatgpt_provider_status import chatgpt_provider_account_status
# The intake dispatch Mazda receives after a scan: 536 lines of prompt, split
# into named sections in intake/scan_message.py so one rule can be read and
# tested without scrolling past the other 500. Re-exported under their
# historical names -- callers, tests and the route harness reach them through
# `server`.
from intake.scan_message import (
    MAZDA_RF_ENV_JSON,
    MAZDA_RF_VENV_PY,
    build_scan_message as build_mazda_scan_message,
    facade_identified as mazda_facade_identified,
)
from intake.mazda_mode import (
    JsonFileMazdaModeStore,
    MazdaModeService,
    resolve_execution_mode,
)
# The dispatch fork and the scan notification it guards. Imported as a module,
# not as names: the wrappers below rebuild its Collaborators bundle per call,
# and importing the functions individually would invite a test to monkeypatch
# `server.<name>` and isolate nothing (the moved code closes over its own
# module globals).
from intake import mazda_dispatch
from intake.mazda_dispatch import HUMAN_ONLY_MODE_STAGE_MESSAGE
from category_taxonomy_seed import LEGACY_TAXONOMY
from document_annotation import (
    ExpenseEvidence,
    IExpenseDocumentAnnotationService,
    build_document_annotation_service,
    render_excel_for_browser,
)
from agent_thoughts import select_thoughts
from background_result_proxy import BackgroundResultProxy
from category_picker import category_row_css, render_assets
from recent_intake_view import collapse_check_evidence_rows
from supporting_document_service import (
    normalize_supporting_document_reference,
    references_same_underlying_document,
    should_suppress_source_document,
)
from supporting_document_slots import SUPPORTING_DOCUMENT_CATALOG
from finance.expense_schema import InformationSchemaProbe, ShowColumnsProbe
from finance.expense_edit_model import ExpenseEdit, ExpenseNotFound
from finance.http_coercion import as_float, as_int
from finance.category_naming import ICategoryNamer, TaxonomyCategoryNamer
from finance.expense_edit_repository import (
    MySqlExpenseRecordRepository,
    readable_validation_error,
    records_as_json,
    search_criteria_from_request,
)
from finance.receipt_relocation import FilesystemReceiptFileRelocator
from finance.report_page import ReportPageRoutes, ReportRowMatch
from finance import (archive_path, intake_report_model, intake_report_page,
                     manual_entry, sales_tax, vendor_lookup)
from finance.intake_report_model import (
    META_EMPTY,
    document_type_label as _document_type_label,
    format_month_range as _format_month_range,
)
from finance.recent_report_image import RecentReportImageSynchronizer
from finance.supporting_documents import (
    CallableIntakePageLookup,
    SupportingDocumentPageResolver,
    slot_reference,
)
from supporting_document_application import (
    ISupportingDocumentService,
    SupportingDocumentPorts,
    SupportingDocumentRequest,
    SupportingDocumentService,
)
from scanner_state import intake_is_in_progress
from intake.trainer_contracts import IntakeCallback, TrainerLaunchRequest
from intake.trainer_escalation import (
    CallbackTrainerEscalationRecorder,
    NullTrainerEscalationService,
    ProblemOnlyTrainerEscalationService,
    ThreadingDeadlineScheduler,
)
from intake.trainer_notifier import (
    DetachedTrainerNotifier,
)
from intake.trainer_recovery import recover_pending_trainer_watches
from finance.statement_dashboard_adapters import (
    CallableStatementPreflight,
    CallbackStatementIntakeRecorder,
)
from finance.statement_extraction_adapter import PreflightStatementExtractor
from finance.mazda_fill import (
    CallableDocumentClassifier,
    CallableReceiptReader,
    MazdaFillRequest,
    MazdaFillService,
)
from finance.statement_models import StatementBreakupRequest, StatementStoreRequest
from finance.statement_service import StatementBreakupService
from finance.statement_store import ScriptStatementStore
from paths import HERE, LETTA_CODE_BUN, REPO_ROOT  # noqa: E402

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
    os.path.join(HERE, 'agents'),
    os.path.join(HERE, 'intake'),
    os.path.join(HERE, 'document_annotation.py'),
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
# The month tabs and the statement report cards moved to
# finance/report_registry.py as typed `ReportMonth`s and `FinanceReportSpec`s.
# The months were two parallel dicts on the same four keys — folder and calendar
# range — with nothing checking they agreed; a month in one and not the other is
# a tab whose /api/rol-finance-month-status query silently returns nothing.
# `ReportMonth` also checks the range actually IS the month the key names, so
# 'feb-2025' ending 2025-02-29 stops being writable.
#
# NOTE the cross-language duplication this does not yet fix: the JS
# RolFinanceReportsController hardcodes the same four month keys (and the two
# scanner keys, and the Mazda agent id) as default constructor arguments. The
# Python side is now one typed collection so the JS can read it from an
# endpoint; that change is a separate commit.
ROL_FINANCES_REPORTS_PARENT = os.path.expanduser(
    '~/rol_finances/readable_documents/bank_statements')
from finance.report_registry import (  # noqa: E402
    DEFAULT_MONTH_KEY as ROL_FINANCES_REPORTS_DEFAULT_MONTH,
)
from finance.report_registry import (  # noqa: E402
    ROL_FINANCE_REPORTS,
    ROL_FINANCES_MONTH_RANGES,
    ROL_FINANCES_REPORTS_MONTHS,
)


def _rol_finance_reports_for_month(month_key):
    """Document cards for a month; all-year cards live only under January.

    Deliberately NOT imported from finance.report_registry, even though it lives
    there too. ~15 tests drive the report paths by monkeypatching
    `server.ROL_FINANCE_REPORTS`, and a function that closes over the registry's
    own global would not see that — the exact second-binding failure plan rule 3
    is about, which shows up as a green test that read the real filesystem. The
    registry's copy is for callers that want the real list; this one is the one
    server.py's own readers and their patch target share.
    """
    if month_key == ROL_FINANCES_REPORTS_DEFAULT_MONTH:
        return ROL_FINANCE_REPORTS
    return [r for r in ROL_FINANCE_REPORTS if not r.get('all_year')]


ROL_FINANCES_REPORTS_BASE = os.path.join(
    ROL_FINANCES_REPORTS_PARENT, ROL_FINANCES_REPORTS_MONTHS[ROL_FINANCES_REPORTS_DEFAULT_MONTH])
ROL_FINANCES_REPORTS_URL_PREFIX = '/rol_finances_reports'

# ── ROL Finance: recategorize a Verified-Transactions row ─────────────────
# The category-picker dialog injected into each report.html (by
# rol_finances/tools/python_tasks/verification_lib/restructure_verified_transactions.py)
# POSTs to /api/recategorize-expense. We reuse the same DB access create_spreadsheet.py
# uses (app.db.get_connection from the rol_finances receipt_parsing_tools tree), so the
# next create_spreadsheet run sees the user's correction.
RECEIPT_PARSING_TOOLS = os.path.expanduser('~/rol_finances/receipt_parsing_tools')

# The four reporting-category maps moved to finance/reporting_categories.py,
# where one typed `ReportingCategory` list per bucket derives all four. They
# were four parallel dicts that had to agree and nothing checked that they did:
# a bucket added to one and missed in another produced a report row with no CSS
# class or no colour, served and indistinguishable from a styling choice.
#
# They are re-imported here because server.py itself still reads CLASS and
# DB_MAP on the taxonomy-miss fallback below, and because tests/ and the
# category-taxonomy seed name them through `server`. All four are SUPERSEDED at
# runtime by ICategoryTaxonomy (category_taxonomy.py), which reads the DB's
# is_report_category / report_category_id columns (migration 2026_07_28_002
# backfilled them to match these values exactly). Change the categories table,
# not this list.
from finance.reporting_categories import (  # noqa: E402
    REPORTING_CATEGORY_ANCESTOR_MAP,
    REPORTING_CATEGORY_CLASS,
    REPORTING_CATEGORY_DB_MAP,
    REPORTING_CATEGORY_STYLE,
)

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
REPORT_PAGE_ROUTES = ReportPageRoutes(
    scanner_path=SCANNER_REPORT_PATH,
    recent_path=RECENT_REPORT_PATH,
)
_SUPPORTING_DOCUMENT_PAGES = None
_SUPPORTING_DOCUMENT_SERVICE = None
RECENT_REPORT_POINTER_FILE = os.path.join(HERE, 'recent_report.json')
_recent_report_lock = threading.Lock()

# Fail-loud intake-halt surface: rol_finances' DashboardIntakeHaltNotifier POSTs
# here when an intake step crashes (a fault, not a "no match"), so the pipeline
# HALTS instead of silently inserting a duplicate. Unlike the document-vision
# halt (which self-clears when a provider tier recovers), a code fault does not
# recover on its own — it stays active until a human acknowledges it.
INTAKE_HALT_FILE = os.path.join(HERE, 'intake_halt.json')
_intake_halt_lock = threading.Lock()


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
                         content_sha256=None, status='processing',
                         status_detail=''):
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
            'archive_paths': [],
            'archive_years': [],
            # Usually 'processing' -- a dispatch that Mazda will report back
            # on. A capture rejected before dispatch (blank page, empty scanner
            # output) records its own terminal 'fail' here instead, so the
            # scanner's tab shows the failure rather than going on displaying
            # the previous document.
            'status': status,
            'status_detail': status_detail,
            'execution_mode': current_execution_mode(),
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


def _duplicate_event_rows(ids):
    """Raw date/amount identity for duplicate callback validation."""
    clean = []
    for value in ids or []:
        try:
            value = int(value)
        except (TypeError, ValueError):
            continue
        if value not in clean:
            clean.append(value)
    if not clean:
        return []
    placeholders = ','.join(['%s'] * len(clean))
    with _rol_get_connection() as cnx:
        with cnx.cursor() as cur:
            cur.execute(
                "SELECT id, expense_date, amount FROM expenses "
                f"WHERE id IN ({placeholders})",
                tuple(clean),
            )
            return list(cur.fetchall())


def _duplicate_callback_integrity_error(event):
    """Reject a duplicate ID whose stored date/amount is not this receipt."""
    duplicate_ids = event.get('duplicate_expense_ids') or []
    try:
        duplicate_only = int(event.get('stored')) == 0 and bool(duplicate_ids)
    except (TypeError, ValueError):
        duplicate_only = False
    date_s = str(event.get('expense_date') or '').strip()
    amount_s = str(event.get('amount') or '').strip()
    if not duplicate_only or not date_s or not amount_s:
        return ''
    try:
        expected_amount = abs(float(
            amount_s.replace(',', '').replace('$', '')))
        clean_ids = [int(value) for value in duplicate_ids]
        rows = _duplicate_event_rows(clean_ids)
    except Exception as exc:
        print(f'[expense-stored] duplicate callback validation skipped: {exc}')
        return ''
    by_id = {int(row['id']): row for row in rows}
    for expense_id in clean_ids:
        row = by_id.get(expense_id)
        if row is None:
            return f'Duplicate callback named missing expense {expense_id}.'
        try:
            stored_amount = abs(float(row.get('amount')))
        except (TypeError, ValueError):
            return f'Duplicate expense {expense_id} has an unreadable amount.'
        stored_date = str(row.get('expense_date') or '').strip()
        if stored_date != date_s or abs(stored_amount - expected_amount) >= 0.005:
            return (
                f'Duplicate callback mismatch: current parse is {date_s} '
                f'${expected_amount:.2f}, but expense {expense_id} is '
                f'{stored_date or "unknown date"} ${stored_amount:.2f}.'
            )
    return ''


def _fold_event_into_intake(intake, event):
    """Fold one STEP 8 event's fields (expense ids + parsed/stored counts +
    doc_kind/vendor) into one intake record, in place."""
    integrity_error = _duplicate_callback_integrity_error(event)
    if integrity_error:
        # Never let a coincidental/old DB row become this scan's displayed
        # receipt. Preserve the current source document and surface the failed
        # correlation for the Trainer instead.
        event = dict(event)
        event['expense_id'] = None
        event['expense_ids'] = []
        event['duplicate_expense_ids'] = []
        intake['expense_ids'] = []
        intake['duplicate_expense_ids'] = []
        intake['integrity_error'] = integrity_error
        intake['status'] = 'fail'
        intake['status_detail'] = integrity_error
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
                + list(event.get('scanned_statement_attached') or [])
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
    for k in ('parsed', 'stored', 'rolled_back_row_count'):
        if event.get(k) is not None:
            try:
                intake[k] = int(event[k])
            except (TypeError, ValueError):
                pass
    # Safety net for a duplicate run that named no ids. The receipt/invoice
    # branch of Mazda's STEP 8 has more than once posted
    # duplicate_expense_ids:[] even though check_duplicates knew the existing
    # row's id, which left the Recent Report page with nothing to render — the
    # user sees "already in the database" and no Verified Transactions table at
    # all. The event still carries the date/amount it matched on, so resolve
    # the pre-existing row here rather than depending on the agent's payload.
    if (not ids and not duplicate_ids
            and intake.get('stored') == 0 and (intake.get('parsed') or 0) > 0):
        recovered = _resolve_duplicate_expense_ids(
            event.get('expense_date'), event.get('amount'))
        if recovered:
            intake['expense_ids'] = list(recovered)
            intake['duplicate_expense_ids'] = list(recovered)
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
    if event.get('archive_paths') is not None:
        intake['archive_paths'] = [
            str(path).strip() for path in (event.get('archive_paths') or [])
            if str(path).strip()
        ]
    if event.get('archive_years') is not None:
        cleaned_years = []
        for year in event.get('archive_years') or []:
            try:
                cleaned_years.append(int(year))
            except (TypeError, ValueError):
                continue
        intake['archive_years'] = cleaned_years
    intake['reported_at'] = time.time()
    event_status = str(event.get('status') or '').strip().lower()
    # STEP 8 and Trainer updates can race. A late expense-stored callback has
    # no status of its own and must not downgrade an already-terminal Trainer
    # PASS/FAIL back to "complete", which would re-lock the scanner after a
    # service restart.
    if event_status:
        intake['status'] = event_status
    elif intake.get('status_source') == 'transport':
        # A synchronous Letta POST can time out after the isolated
        # conversation accepted the message. Its later STEP 8 callback is
        # authoritative proof of delivery; clear only that provisional
        # transport failure, never a Trainer verdict.
        intake['status'] = 'complete'
        intake['status_detail'] = ''
        intake['status_source'] = 'callback'
    elif str(intake.get('status') or '').lower() not in {
            'pass', 'corrected', 'fail', 'stalled'}:
        intake['status'] = 'complete'
    if event.get('status_detail'):
        intake['status_detail'] = str(event['status_detail'])
    if event.get('trainer_dispatched') is not None:
        intake['trainer_dispatched'] = bool(event['trainer_dispatched'])
    if event.get('trainer_escalation_reason'):
        intake['trainer_escalation_reason'] = str(
            event['trainer_escalation_reason'])


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
            # Two scanners dispatched within 2s of each other both satisfy a
            # dispatched_at-only callback, so it would fold the Freezer's
            # transactions into Last Window Scan. The document path decides
            # between them -- but only as a tie-breaker, never a filter: a
            # callback naming a renamed or archived copy matches nothing here
            # and must still update the dispatch it was correlated to.
            if path and len(targets) > 1:
                named = [i for i in targets if i.get('image_path') == path]
                if named:
                    targets = named
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


def merge_statement_review_result(payload):
    """Publish a successful review retry through the normal report event path."""
    report = (payload or {}).get('report') or {}
    if not report.get('ok') or not report.get('source_file'):
        return False
    return merge_recent_intake_event({
        'document_path': report.get('source_file'),
        'doc_kind': 'statement',
        'vendor': report.get('bank_name'),
        'parsed': report.get('transactions_parsed'),
        'stored': report.get('stored'),
        'expense_ids': report.get('expense_ids') or [],
        'duplicate_expense_ids': report.get('duplicate_expense_ids') or [],
        'status': 'complete',
    })


# The terminal-status vocabulary moved to intake/statuses.py as a Literal.
# merge_recent_intake_status() DROPS any update whose status is not in this set,
# silently, so a status the Trainer sends that this set does not know leaves the
# document on `processing` forever — round 11's defect.
from intake.statuses import TERMINAL_INTAKE_STATUSES as _TERMINAL_INTAKE_STATUSES  # noqa: E402


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
            integrity_error = str(
                intake.get('integrity_error') or '').strip()
            if status in {'pass', 'corrected'} and integrity_error:
                intake['status'] = 'fail'
                intake['status_detail'] = integrity_error
            else:
                intake['status'] = status
                intake['status_detail'] = str(
                    update.get('detail') or '').strip()
            intake['status_source'] = str(
                update.get('status_source') or 'trainer').strip()
            intake['trainer_report'] = str(update.get('report_path') or '').strip()
            intake['reported_at'] = time.time()
        return _write_recent_pointer_file(data)


def record_intake_status(data):
    """Dashboard endpoint used by the Trainer runner after writing its report."""
    merged = merge_recent_intake_status(data or {})
    return {'ok': merged, 'status': (data or {}).get('status', '')}


def submit_manual_receipt_entry(data):
    """POST /api/manual-receipt-entry: the needs_human_review form's Save button.

    Stores the human-entered fields through manual_entry.py (the exact tool
    Mazda's own pipeline uses, just with --engine local instead of her LLM
    turn), then folds a STEP-8-shaped event into the intake record — same as
    Mazda's own /api/expense-stored callback — so expense_ids populate (the
    Verified Transactions table and the archive-verification terminal both
    key off that), and status flips from needs_human_review to complete. A
    failure leaves the intake queued so the form reappears, same as the
    statement review dialog's "pops up again" contract.
    """
    data = data or {}
    # HTTP JSON is untrusted shape, not just untrusted value: coerce here, at
    # the boundary, before the strict Pydantic model — ManualReceiptEntry's
    # strict=True deliberately rejects a numeric field arriving as a string
    # rather than silently coercing it.
    try:
        total_amount = as_float(data.get('total_amount'), 'total_amount')
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}
    category_name = str(data.get('category_name') or '').strip()
    category_id = None
    if category_name:
        category_id, category_cls = _resolve_reporting_category(category_name)
        if category_cls is None:
            return {'ok': False, 'error': f'Unknown category: {category_name!r}'}
    try:
        org_id = as_int(data.get('org_id') or 1, 'org_id')
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}
    try:
        entry = manual_entry.ManualReceiptEntry(
            image_path=data.get('image_path', ''),
            merchant_name=data.get('merchant_name', ''),
            transaction_date=data.get('transaction_date', ''),
            total_amount=total_amount,
            category_id=category_id,
            org_id=org_id,
            vendor_key=str(data.get('vendor_key') or '').strip(),
            learn_vendor=bool(data.get('learn_vendor')),
        )
    except ValidationError as exc:
        return {'ok': False, 'error': str(exc)}

    ok, payload = manual_entry.submit_manual_receipt_entry(entry)
    if not ok:
        return {'ok': False, **payload}

    # A successful --save just moved a receipt file into readable_documents/
    # out-of-process (the parse_and_categorize.py subprocess), invisible to
    # this process's in-memory index until the 300s TTL expires. Without this,
    # the archive-verification terminal and the View Receipt button that fire
    # immediately after this call see a stale index and report no receipt at
    # all -- same as record_stored_expense (Mazda's callback) and
    # reprocess_report already do for their own out-of-process receipt writes.
    _invalidate_receipt_index()
    report = payload.get('report') or {}
    expense_id = report.get('expense_id')
    duplicate = bool(report.get('duplicate'))
    conversation_id = str(data.get('conversation_id') or '').strip()
    merge_recent_intake_event({
        'conversation_id': conversation_id,
        'document_path': entry.image_path,
        'expense_ids': [] if expense_id is None else [expense_id],
        'duplicate_expense_ids': [expense_id] if duplicate and expense_id is not None else [],
        'parsed': 1,
        'stored': 0 if duplicate else 1,
        'doc_kind': 'receipt',
        'vendor': entry.merchant_name,
        'status': 'complete',
        'status_detail': (f'Entered manually by operator — expense_id={expense_id}'
                          if not duplicate
                          else f'Matched an existing expense (id={expense_id}); not double-entered.'),
    })
    record = {
        'id': int(expense_id),
        'transaction_date': entry.transaction_date,
        'total_amount': entry.total_amount,
        'description': entry.merchant_name,
        'id_light': '',
        'category_id': category_id,
        'category_name': category_name,
    } if expense_id is not None else None
    image_sync = {'renamed': False}
    if expense_id is not None:
        try:
            stored = _get_expense_edit_repository().read(int(expense_id))
            record = records_as_json([stored])[0]
        except Exception:  # noqa: BLE001 - retain the validated saved values
            pass
        image_sync = _synchronize_recent_report_image(
            int(expense_id),
            vendor_key=entry.vendor_key,
            transaction_date=entry.transaction_date,
            fallback_vendor_key=_vendor_prefix(
                str((record or {}).get('id_light') or '')),
            fallback_date=entry.transaction_date,
        )
    return {
        'ok': True,
        'expense_id': expense_id,
        'duplicate': duplicate,
        'vendor_remembered': report.get('vendor_remembered'),
        'record': record,
        'image': image_sync,
    }


def preview_manual_entry_archive_path(data):
    """POST /api/manual-receipt-entry-archive-preview: live path preview as
    the operator fills in vendor/date/amount, so they can see where a Save
    will file the document before pressing it."""
    data = data or {}
    try:
        total_amount = as_float(data.get('total_amount'), 'total_amount')
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}
    try:
        result = archive_path.preview_archive_path(
            data.get('image_path', ''),
            data.get('merchant_name', ''),
            data.get('transaction_date', ''),
            total_amount,
            data.get('archive_kind') or 'receipt',
            custom_root=data.get('custom_archive_root'),
        )
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}
    return {'ok': True, **result}


def taxonomy_category_namer() -> ICategoryNamer:
    """Composition root for ICategoryNamer: this module's taxonomy, wired in.

    The lambdas are the point. Handing over the function objects would freeze
    whichever ones existed at wiring time, and `_get_expense_edit_repository`
    caches its namer for the process lifetime; going through the module global
    on every call keeps a test that replaces either function honoured, which is
    what the class did before it moved to finance/category_naming.py.
    """
    return TaxonomyCategoryNamer(
        lambda category_id: _reporting_category_for_id(category_id),
        lambda name: _resolve_reporting_category(name),
    )


_expense_edit_repository = None
_expense_edit_repository_lock = threading.Lock()


def _get_expense_edit_repository():
    """Composition root for the Edit Expense search/update boundary."""
    global _expense_edit_repository
    with _expense_edit_repository_lock:
        if _expense_edit_repository is None:
            _expense_edit_repository = MySqlExpenseRecordRepository(
                lambda: _rol_get_connection(), taxonomy_category_namer(),
                relocator=FilesystemReceiptFileRelocator(
                    resolve_path=_resolve_receipt_url_path))
    return _expense_edit_repository


def _update_recent_receipt_references(expense_ids, path):
    """Keep every row on one receipt pointed at its newly renamed image."""
    ids = tuple(dict.fromkeys(int(value) for value in expense_ids if int(value) > 0))
    if not ids:
        return
    with _rol_get_connection() as cnx:
        with cnx.cursor() as cur:
            schema = InformationSchemaProbe().read(
                cur, ('receipt_url', 'source_file'))
            assignments = []
            values = []
            if schema.has('receipt_url'):
                assignments.append('receipt_url = %s')
                values.append(os.path.basename(path))
            if schema.has('source_file'):
                assignments.append('source_file = %s')
                values.append(path)
            if not assignments:
                return
            placeholders = ','.join(['%s'] * len(ids))
            cur.execute(
                f"UPDATE expenses SET {', '.join(assignments)} "
                f"WHERE id IN ({placeholders})",
                tuple(values) + ids,
            )
            cnx.commit()


def _synchronize_recent_report_image(expense_id, **changes):
    """Composition boundary for the archived-image naming policy."""
    try:
        with _recent_report_lock:
            return RecentReportImageSynchronizer(
                read_pointer=_read_recent_pointer_file,
                write_pointer=_write_recent_pointer_file,
                fetch_rows=_fetch_expenses_by_ids,
                update_references=_update_recent_receipt_references,
            ).synchronize(expense_id, **changes)
    except Exception as exc:  # noqa: BLE001 - the expense write already landed
        return {
            'renamed': False,
            'warning': f'Expense saved, but its image could not be renamed: '
                       f'{type(exc).__name__}: {exc}',
        }


def search_stored_expenses(data, repository=None):
    """POST /api/expense-search: rows behind the Edit Expense button.

    Read-only. A criteria error is the operator's to fix ("enter a merchant, a
    date range, or an amount"), so it comes back as a message rather than a
    500; a database failure does not, so it is reported as itself.
    """
    repo = repository or _get_expense_edit_repository()
    try:
        criteria = search_criteria_from_request(data)
    except (ValueError, ValidationError) as exc:
        return {'ok': False, 'error': readable_validation_error(exc)}
    try:
        records = repo.search(criteria)
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator verbatim
        return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
    return {'ok': True, 'records': records_as_json(records)}


def edit_stored_expense(data, repository=None, namer=None):
    """POST /api/expense-edit: write one correction to one stored row.

    Mirrors submit_manual_receipt_entry's boundary discipline exactly -- coerce
    the untrusted JSON shape here, then let the strict Pydantic model be the
    single place the three field rules are enforced.
    """
    data = data or {}
    repo = repository or _get_expense_edit_repository()
    resolver = namer or taxonomy_category_namer()
    try:
        expense_id = as_int(data.get('expense_id'), 'expense_id')
        total_amount = as_float(data.get('total_amount'), 'total_amount')
        category_id = resolver.id_for(data.get('category_name'))
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}
    try:
        edit = ExpenseEdit(
            expense_id=expense_id,
            merchant_name=data.get('merchant_name', ''),
            transaction_date=data.get('transaction_date', ''),
            total_amount=total_amount,
            category_id=category_id,
        )
    except ValidationError as exc:
        return {'ok': False, 'error': readable_validation_error(exc)}
    learning_vendor_key = ''
    vendor_remembered = None
    if data.get('learn_vendor'):
        learning_vendor_key = str(data.get('vendor_key') or '').strip()
        if not learning_vendor_key or category_id is None:
            return {
                'ok': False,
                'error': 'A new vendor requires vendor_key and category.',
            }
        try:
            vendor_remembered = vendor_lookup.remember_vendor(
                edit.merchant_name, category_id,
                learning_vendor_key).model_dump()
        except Exception as exc:  # noqa: BLE001 - no DB write happened yet
            return {
                'ok': False,
                'error': f'Could not learn vendor: {type(exc).__name__}: {exc}',
            }
        if not vendor_remembered.get('remembered'):
            reason = vendor_remembered.get('reason') or 'the vendor rule was not persisted'
            returned_key = vendor_remembered.get('vendor_key')
            # remember() may return an existing stored key chosen from a broad
            # human entry. Accept that safe repeat only when a real key and
            # the precise "already known" result are both present.
            if not returned_key or reason != 'vendor_key already known':
                return {'ok': False, 'error': f'Could not learn vendor: {reason}'}
    try:
        result = repo.apply_edit(edit)
    except ExpenseNotFound as exc:
        return {'ok': False, 'error': str(exc)}
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator verbatim
        return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
    # An edit can move a row's date/amount, which is what every report.html
    # row and the receipt index key off -- drop the cached index so "View
    # Receipt" re-resolves against the new values, same as a fresh save does.
    _invalidate_receipt_index()
    image_sync = _synchronize_recent_report_image(
        expense_id,
        vendor_key=str(data.get('vendor_key') or ''),
        transaction_date=edit.transaction_date,
        fallback_vendor_key=_vendor_prefix(result.record.id_light),
        fallback_date=result.record.transaction_date,
        replace_identity=True,
    )
    warnings = list(result.warnings)
    if image_sync.get('path'):
        warnings = [warning for warning in warnings
                    if 'receipt file on disk was not renamed' not in warning]
    if image_sync.get('warning'):
        warnings.append(image_sync['warning'])
    return {
        'ok': True,
        'record': records_as_json([result.record])[0],
        'changed_fields': list(result.changed_fields),
        'warnings': warnings,
        'vendor_remembered': vendor_remembered,
        'image': image_sync,
    }


def delete_stored_expense(data, repository=None):
    """POST /api/expense-delete: remove one stored row.

    The Delete button on a Verified Transactions row. Deliberately narrower
    than edit_stored_expense: the only thing an operator can say here is
    *which* row, so the only thing to coerce is an id. Confirmation is the
    browser's job (a dialog naming the merchant), not this function's -- a
    request that reaches here has already been agreed to.
    """
    data = data or {}
    repo = repository or _get_expense_edit_repository()
    try:
        expense_id = as_int(data.get('expense_id'), 'expense_id')
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}
    if expense_id <= 0:
        return {'ok': False, 'error': 'expense_id must be a positive row id'}
    try:
        deletion = repo.delete(expense_id)
    except ExpenseNotFound as exc:
        return {'ok': False, 'error': str(exc)}
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator verbatim
        return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
    # The receipt index keys off (date, amount) per row; a removed row must
    # stop answering "View Receipt" for the file it used to claim.
    _invalidate_receipt_index()
    image_sync = _synchronize_recent_report_image(
        expense_id, deleted=True,
        fallback_vendor_key=_vendor_prefix(deletion.record.id_light),
        fallback_date=deletion.record.transaction_date,
    )
    response = {'ok': True,
        'record': records_as_json([deletion.record])[0],
        'line_item_ids': list(deletion.line_item_ids)}
    if image_sync.get('path') or image_sync.get('warning'):
        response['image'] = image_sync
    return response


def add_sales_tax_to_expense(data, repository=None):
    """POST /api/expense-add-tax: put sales tax back on one stored row.

    The "Add 6%" button. The row is re-read here and the new amount computed
    here rather than sent up from the browser, for two reasons that are really
    the same reason: the rate is a fact about Michigan (finance/sales_tax.py
    owns it, so it cannot drift between the page and the reports), and the
    arithmetic is exact Decimal rather than a float multiply in a script tag.
    The write then goes through the ordinary edit path, so a taxed row picks up
    the same id_light linkage warning any other amount change earns.
    """
    data = data or {}
    repo = repository or _get_expense_edit_repository()
    try:
        expense_id = as_int(data.get('expense_id'), 'expense_id')
        # This endpoint is the concrete "Add 6%" command, not a general tax
        # calculator.  Ignore no caller-controlled rate because allowing one
        # would let the button's invariant be bypassed by a crafted request.
        rate = sales_tax.MICHIGAN_SALES_TAX_RATE
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}
    if expense_id <= 0:
        return {'ok': False, 'error': 'expense_id must be a positive row id'}
    try:
        before = repo.read(expense_id)
    except ExpenseNotFound as exc:
        return {'ok': False, 'error': str(exc)}
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator verbatim
        return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
    taxed = sales_tax.with_sales_tax(before.total_amount, rate)
    # Preserve the stored category id directly. Sending its display name back
    # through today's taxonomy can reject an otherwise valid historical row
    # after a category rename, even though this command changes only amount.
    try:
        result = repo.apply_edit(ExpenseEdit(
            expense_id=expense_id,
            merchant_name=before.description,
            transaction_date=before.transaction_date,
            total_amount=float(taxed),
            category_id=before.category_id,
        ))
    except (ExpenseNotFound, ValidationError) as exc:
        return {'ok': False, 'error': readable_validation_error(exc)}
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator verbatim
        return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
    _invalidate_receipt_index()
    image_sync = _synchronize_recent_report_image(
        expense_id,
        fallback_vendor_key=_vendor_prefix(result.record.id_light),
        fallback_date=result.record.transaction_date,
    )
    return {
        'ok': True,
        'record': records_as_json([result.record])[0],
        'changed_fields': list(result.changed_fields),
        'warnings': list(result.warnings),
        'tax_added': float(sales_tax.tax_on(before.total_amount, rate)),
        'rate': float(rate),
        'previous_amount': before.total_amount,
        'image': image_sync,
    }


def record_intake_halt(data):
    """Persist a fail-loud intake halt so the dashboard can raise the alert.

    Called by rol_finances' DashboardIntakeHaltNotifier. Stores the single most
    recent halt as active; a human clears it via /api/intake-halt-ack. Kept as a
    discrete event (not merged) because each halt is a distinct fault to see."""
    event = data or {}
    record = {
        'active': True,
        'halted_at': time.time(),
        'step': str(event.get('step', '')),
        'cause': str(event.get('cause', '')),
        'exception_type': str(event.get('exception_type', '')),
        'document_path': str(event.get('document_path', '')),
        'repo_path': str(event.get('repo_path', '')),
        'metadata': event.get('metadata') if isinstance(event.get('metadata'), dict) else {},
    }
    with _intake_halt_lock:
        try:
            with open(INTAKE_HALT_FILE, 'w') as fh:
                json.dump(record, fh)
        except OSError as exc:
            return {'ok': False, 'error': str(exc)}
    return {'ok': True, 'active': True}


def read_intake_halt():
    """Current intake-halt state for the front-end poller."""
    with _intake_halt_lock:
        try:
            with open(INTAKE_HALT_FILE) as fh:
                record = json.load(fh)
        except (OSError, ValueError):
            return {'ok': True, 'active': False}
    if not isinstance(record, dict) or not record.get('active'):
        return {'ok': True, 'active': False}
    return {'ok': True, 'active': True, 'event': record}


def acknowledge_intake_halt():
    """Clear the active halt once a human has seen it (the alert's Acknowledge)."""
    with _intake_halt_lock:
        try:
            with open(INTAKE_HALT_FILE) as fh:
                record = json.load(fh)
        except (OSError, ValueError):
            return {'ok': True, 'active': False}
        if isinstance(record, dict):
            record['active'] = False
            try:
                with open(INTAKE_HALT_FILE, 'w') as fh:
                    json.dump(record, fh)
            except OSError as exc:
                return {'ok': False, 'error': str(exc)}
    return {'ok': True, 'active': False}


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
    Only rows so the shared picker markup drives them identically.

    A PARENT is a reconciliation anchor and carries no category of its own, so
    the picker refuses it (see recategorize_expense). When STEP 8 reports a
    PARENT id we therefore substitute its LINE_ITEM children — those are the
    rows that actually hold the category — so the intake page shows something
    the user can click and set. The child description is prefixed with the
    parent's (e.g. "Consumers Energy — Amount Due") so the vendor is still
    recognizable in the table."""
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
                "SELECT 1 AS present FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'expenses' "
                "AND COLUMN_NAME = 'expense_role' LIMIT 1")
            has_expense_roles = bool(cur.fetchone())
            role_select = ', expense_role' if has_expense_roles else ''
            # A narrower live schema must not fail the whole page: absent
            # optional columns come back as NULL (see finance.expense_schema).
            optional_columns = (
                'id_light', 'receipt_url', 'document_url',
                'scanned_statement_url', 'moms_ledger',
            )
            schema = InformationSchemaProbe().read(cur, optional_columns)
            select_sql = schema.select_clause(
                ('id', 'expense_date', 'amount', 'description', 'category_id'),
                optional_columns,
            )
            cur.execute(
                f"SELECT {select_sql}{role_select} "
                f"FROM expenses WHERE id IN ({placeholders}) "
                "ORDER BY expense_date, id",
                tuple(clean),
            )
            rows = cur.fetchall()

            # Expand each PARENT anchor into its categorizable LINE_ITEM children.
            parent_ids = [int(r['id']) for r in rows
                          if has_expense_roles
                          and (r.get('expense_role') or '') == 'PARENT']
            if parent_ids:
                parent_desc = {int(r['id']): (r.get('description') or '').strip()
                               for r in rows}
                ph2 = ','.join(['%s'] * len(parent_ids))
                cur.execute(
                    "SELECT id, expense_date, amount, id_light, description, category_id, "
                    "receipt_url, document_url, scanned_statement_url, moms_ledger, "
                    "expense_role, parent_expense_id "
                    f"FROM expenses WHERE parent_expense_id IN ({ph2}) "
                    "AND expense_role='LINE_ITEM' "
                    "ORDER BY expense_date, id",
                    tuple(parent_ids),
                )
                children = cur.fetchall()
                child_by_parent = {}
                for ch in children:
                    pdesc = parent_desc.get(int(ch.get('parent_expense_id') or 0), '')
                    cdesc = (ch.get('description') or '').strip()
                    if pdesc and cdesc and pdesc.lower() not in cdesc.lower():
                        ch['description'] = f'{pdesc} — {cdesc}'
                    child_by_parent.setdefault(
                        int(ch['parent_expense_id']), []).append(ch)
                # STEP 8 reports the anchor AND the children it created, so a
                # child is usually in `rows` already. Keyed by id, the spliced
                # copy wins: it is the one carrying the parent's vendor prefix.
                expanded = {}
                for r in rows:
                    if (r.get('expense_role') or '') == 'PARENT':
                        # Drop the anchor; show its children instead. A parent
                        # with no children left (data anomaly) is simply omitted
                        # rather than shown as an uncategorizable dead row.
                        for ch in child_by_parent.get(int(r['id']), []):
                            expanded[int(ch['id'])] = ch
                    else:
                        expanded.setdefault(int(r['id']), r)
                rows = sorted(
                    expanded.values(),
                    key=lambda r: (str(r.get('expense_date') or ''), int(r['id'])),
                )
    out = []
    for r in rows:
        cid = r.get('category_id')
        rep = _reporting_category_for_id(
            int(cid) if cid is not None else None, parent_of)
        out.append({
            'id': int(r['id']),
            'date': str(r['expense_date']),
            'amount': str(r['amount']),
            'id_light': (r.get('id_light') or '').strip(),
            # Filled from the display/source description immediately before
            # rendering; never conflate id_light with a reusable vendor key.
            'vendor_key': '',
            'description': (r.get('description') or '').strip(),
            'reporting_category': rep,
            'cat_class': _css_class_for_report_name(rep),
            'receipt_url': (r.get('receipt_url') or '').strip(),
            'document_url': (r.get('document_url') or '').strip(),
            'scanned_statement_url': (r.get('scanned_statement_url') or '').strip(),
            'moms_ledger': (r.get('moms_ledger') or '').strip(),
        })
    return out


def _resolve_duplicate_expense_ids(expense_date, amount, limit=3):
    """Ids of already-stored expenses matching (expense_date, |amount|).

    Used only as the last-resort recovery in _fold_event_into_intake when a
    duplicate-only callback named no ids at all. Deliberately narrow:

    - (date, amount) is the same join this codebase already trusts for
      receipt↔row linkage (see _resolve_expense_receipt_path), and it is the only
      identifying pair a duplicate callback reliably carries — vendor_key is
      NOT usable here, because check_duplicates reports the stored row's
      id_light (e.g. consumers_energy_01_23_25_222_65) while STEP 8 reports the
      normalized vendor key (consumers_7996); requiring them to agree would
      reject every real match.
    - More than `limit` hits means the pair is ambiguous (a common round amount
      on a busy day), so return nothing rather than showing rows that may
      belong to an unrelated document. Guessing wrong here is worse than the
      empty table this is trying to fix.

    Best-effort: any DB problem yields [] and the caller renders as before.
    """
    date_s = str(expense_date or '').strip()
    amount_s = str(amount or '').strip()
    if not date_s or not amount_s:
        return []
    try:
        amount_f = abs(float(amount_s.replace(',', '').replace('$', '')))
    except ValueError:
        return []
    try:
        with _rol_get_connection() as cnx:
            with cnx.cursor() as cur:
                cur.execute(
                    'SELECT id FROM expenses '
                    'WHERE expense_date = %s AND ABS(ABS(amount) - %s) < 0.005 '
                    'ORDER BY id LIMIT %s',
                    (date_s, amount_f, limit + 1),
                )
                rows = cur.fetchall()
    except Exception as exc:
        print(f'[expense-stored] duplicate id recovery failed: {exc}')
        return []
    ids = [int(r['id']) for r in rows]
    return [] if len(ids) > limit else ids


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
                pdf_path = _source_document_path(match.report_path) or ''
            if not pdf_path:
                # No report.html traces back to this row, but the expense may
                # still carry its own document_url (e.g. a bank-downloaded
                # statement/xlsx attached directly, never via a report row).
                du = (r.get('document_url') or '').strip()
                if du:
                    pdf_path = _resolve_local_supporting_document(du, 'source') or ''
        if not receipt_path:
            ru = (r.get('receipt_url') or '').strip()
            if ru:
                receipt_path = _resolve_expense_receipt_path(
                    r.get('date'), r.get('amount'), ru) or ''
        if pdf_path and receipt_path:
            break
    return pdf_path, receipt_path


def _associated_evidence_paths(rows):
    """Resolve the remaining two supporting-document evidence slots
    (`scanned_statement_url`, `moms_ledger`) backing a set of transactions —
    the counterparts to `_associated_source_paths`'s PDF/receipt.

    Scanner intakes routinely populate `scanned_statement_url` (the archived
    photo of the printed statement) without ever touching `document_url` or
    `receipt_url`, so these are surfaced separately rather than folded into
    _associated_source_paths's two slots. See the 4-evidence-slot model.
    Returns (scanned_statement_path or '', moms_ledger_path or ''), stopping at
    the first row that yields each.
    """
    scanned_statement_path, moms_ledger_path = '', ''
    for r in rows or []:
        if not scanned_statement_path:
            ref = (r.get('scanned_statement_url') or '').strip()
            if ref:
                scanned_statement_path = (
                    _resolve_local_supporting_document(ref, 'scanned_statement')
                    or ref)
        if not moms_ledger_path:
            ref = (r.get('moms_ledger') or '').strip()
            if ref:
                moms_ledger_path = (
                    _resolve_local_supporting_document(ref, 'moms_ledger') or ref)
        if scanned_statement_path and moms_ledger_path:
            break
    return scanned_statement_path, moms_ledger_path


STATEMENT_INTAKE_DOC_KINDS = {'statement', 'bank_statement', 'credit_card_statement'}


def _rows_are_statement_rows(rows):
    """Do these transactions come off a scanned statement page?

    scanned_statement_url is set for statement rows and for nothing else, so it
    identifies the document even when the intake record forgot to.
    """
    return any((r.get('scanned_statement_url') or '').strip() for r in rows or [])


def _statement_archive_path(rows, vendor_key=''):
    """Locate the canonically-named bank_statements archive copy of a scanned
    statement — readable_documents/bank_statements/<year>/<month>/
    <vendor>_<slug>/<vendor>_<slug>.<ext>, where slug is built from the
    statement's own date range (e.g. 'july_31__august_15').

    Scanner intakes only ever populate scanned_statement_url with the raw
    scan filename (e.g. window_scan_...jpg) — the properly-named copy filed
    under bank_statements/ isn't linked from the DB anywhere, so it has to be
    found by matching this slug against every year/month folder rather than
    looked up directly. Vendor tokens disambiguate when more than one folder
    shares a date range; an unresolved ambiguity returns '' rather than
    guessing (same fail-closed shape as _find_matching_report_row).
    """
    dates = sorted({r.get('date') for r in rows or [] if r.get('date')})
    if not dates:
        return ''
    try:
        start = datetime.strptime(dates[0], '%Y-%m-%d')
        end = datetime.strptime(dates[-1], '%Y-%m-%d')
    except ValueError:
        return ''
    slug = (f'{start.strftime("%B").lower()}_{start.day:02d}__'
            f'{end.strftime("%B").lower()}_{end.day:02d}')
    pattern = os.path.join(
        READABLE_DOCS_BASE, 'bank_statements', str(start.year), '*', f'*{slug}')
    folders = sorted(glob.glob(pattern))
    if len(folders) > 1 and vendor_key:
        tokens = [t for t in vendor_key.lower().split('_') if t.isalpha()]
        narrowed = [f for f in folders
                    if any(t in os.path.basename(f).lower() for t in tokens)]
        if narrowed:
            folders = narrowed
    if len(folders) != 1:
        return ''
    folder = folders[0]
    name = os.path.basename(folder)
    for ext in ('.jpg', '.jpeg', '.png', '.pdf', '.xlsx'):
        candidate = os.path.join(folder, name + ext)
        if os.path.isfile(candidate):
            return candidate
    return ''


def _recent_intake_archive_path(intake, rows, receipt_path=''):
    """Return this intake's durable filed scan, never its staging name."""
    archive_paths = [
        str(path).strip() for path in (intake.get('archive_paths') or [])
        if str(path).strip()
    ]
    if archive_paths:
        return archive_paths[0]
    # A receipt scan can arrive with doc_kind=unknown because the scanner
    # facade dispatches before Mazda's classifier reports back. The rows' own
    # receipt path is still authoritative and must win before the statement
    # fallback below; otherwise archive verification reports "Archive path not
    # found" even though the receipt file is present on disk.
    if receipt_path and os.path.isfile(receipt_path):
        return str(receipt_path).strip()
    doc_kind = str(intake.get('doc_kind') or '').strip().lower()
    if doc_kind in {'receipt', 'invoice'}:
        return str(receipt_path or '').strip()
    if doc_kind in STATEMENT_INTAKE_DOC_KINDS or _rows_are_statement_rows(rows):
        # doc_kind is frequently absent: a scan dispatched with no facade, or
        # one whose only outcome was duplicates, never records one. The rows
        # themselves settle it -- scanned_statement_url is populated for
        # statement transactions and nothing else -- so an unlabelled intake
        # still finds its filed copy instead of showing no archive at all.
        return _statement_archive_path(
            rows, vendor_key=(rows[0].get('vendor_key') if rows else ''))
    return ''


def scanner_intake_archive_path(intake, rows):
    """Resolve the durable archive file used by scanner verification.

    Prefer the canonical ``bank_statements`` copy for statements. Older and
    corrected duplicate-only intakes may only have the DB-backed
    ``scanned_statement_url`` copy, so use that existing file as a safe
    fallback instead of reporting that no archive exists.
    """
    doc_kind = str((intake or {}).get('doc_kind') or '').strip().lower()
    archive_file = ''
    if doc_kind in STATEMENT_INTAKE_DOC_KINDS:
        archive_file = _statement_archive_path(
            rows, vendor_key=(rows[0].get('vendor_key') if rows else ''))
    if archive_file:
        return archive_file
    if doc_kind in STATEMENT_INTAKE_DOC_KINDS:
        scanned_statement_path, _moms_ledger_path = _associated_evidence_paths(rows)
        if scanned_statement_path and os.path.isfile(scanned_statement_path):
            return scanned_statement_path
    _pdf_path, receipt_path = _associated_source_paths(rows)
    return _recent_intake_archive_path(
        intake or {}, rows, receipt_path=receipt_path)


# The nine intake steps moved to intake/progress.py as typed
# `MazdaProgressStep`s. _mazda_progress_from_messages() below indexes a parallel
# statuses list BY POSITION (statuses[1], [2], [7]), which is only correct
# because the labels are in STEP order; the module now asserts position == step
# number, so those indices are guarded by the data they index into.
from intake.progress import MAZDA_PROGRESS_LABELS as _MAZDA_PROGRESS_LABELS  # noqa: E402


def _mazda_progress_from_messages(intake, messages):
    """Derive intake progress only from successful tool returns."""
    calls = {}
    returns = {}
    for message in messages or []:
        call = message.get('tool_call') or {}
        call_id = call.get('tool_call_id') or message.get('tool_call_id')
        if message.get('message_type') == 'tool_call_message' and call_id:
            calls[call_id] = call
        if message.get('message_type') == 'tool_return_message' and call_id:
            returns[call_id] = message

    statuses = ['pending'] * len(_MAZDA_PROGRESS_LABELS)
    doc_kind = str((intake or {}).get('doc_kind') or 'unknown').lower()
    if doc_kind != 'unknown':
        statuses[1] = 'skipped'
    if doc_kind in ('statement', 'bank_statement'):
        statuses[2] = 'done'  # dashboard preflight validated metadata/rows

    def classify(call):
        name = str(call.get('name') or '')
        args = call.get('arguments') or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {}
        command = str(
            args.get('command') or args.get('cmd') or args.get('input') or '')
        if name == 'load_wrapper_revision':
            return 0
        if name == 'executor_run':
            if ('classify_scan.py' in command
                    or 'parse_and_categorize.py' in command
                    and '--save' not in command
                    or 'parse_statement_scan.py' in command):
                return 1
            if 'categorizer_main.py' in command:
                return 3
            if ('parse_and_categorize.py' in command and '--save' in command
                    or 'store_statement_transactions.py' in command):
                return 4
            if '/api/expense-stored' in command:
                return 8
        if name in ('check_vendor_key', 'check_duplicates'):
            return 2
        if name == 'record_trace':
            return 5
        if name == 'judge_trace':
            return 6
        if name in ('propose_improvement', 'apply_proposal'):
            return 7
        return None

    judge_passed = False
    for call_id, call in calls.items():
        index = classify(call)
        if index is None:
            continue
        returned = returns.get(call_id)
        successful = bool(
            returned and str(returned.get('status') or 'success').lower()
            in ('success', 'ok', 'completed'))
        if successful:
            statuses[index] = 'done'
            if index == 6:
                content = returned.get('tool_return') or returned.get('content') or ''
                if isinstance(content, dict):
                    verdict = content.get('verdict')
                else:
                    match = re.search(r'"verdict"\s*:\s*"([^"]+)"', str(content))
                    verdict = match.group(1) if match else ''
                judge_passed = str(verdict).upper() == 'PASS'
        elif statuses[index] == 'pending':
            statuses[index] = 'active'
    if judge_passed:
        statuses[7] = 'skipped'

    steps = [
        {'label': label, 'status': status}
        for label, status in zip(_MAZDA_PROGRESS_LABELS, statuses)
    ]
    completed = sum(status == 'done' for status in statuses)
    required = sum(status != 'skipped' for status in statuses)
    percent = round(completed * 100 / required) if required else 100
    return {
        'steps': steps,
        'completed': completed,
        'required': required,
        'percent': percent,
    }


def mazda_intake_progress(intake):
    """Read this isolated conversation and return its verified progress."""
    conversation_id = str((intake or {}).get('conversation_id') or '').strip()
    if not conversation_id:
        return _mazda_progress_from_messages(intake, [])
    data = letta_get(
        f'/v1/conversations/{quote(conversation_id, safe="")}/messages?limit=200',
        # This runs while rendering the scanner report.  Letta being down must
        # not leave the iframe blank for most of its 30-second refresh cycle.
        timeout=3)
    messages = (
        data if isinstance(data, list)
        else (data or {}).get('messages', (data or {}).get('results', [])))
    return _mazda_progress_from_messages(intake, messages)


def build_recent_intake_html(intake):
    """Synthetic recent-report page for an intake whose document has no
    report.html (the normal case for scanner scans — they store expenses in
    MySQL but never generate a report file). Mirrors the Receipt Only page:
    a #verified-transactions table of the intake's expenses with the same
    embedded category-picker dialog, so recategorize / view-receipt work
    exactly like on a real report.

    This function's one job is to gather the intake's data. What that data
    *means* belongs to finance.intake_report_model, and how it looks belongs
    to finance.intake_report_page."""
    from html import escape as _esc
    label = intake.get('label') or ''
    dispatched_at = intake.get('dispatched_at')
    when = ''
    if dispatched_at:
        when = datetime.fromtimestamp(float(dispatched_at)).strftime('%Y-%m-%d %H:%M')
    reported = intake.get('reported_at')
    intake_status = str(intake.get('status') or 'processing').lower()
    duplicate_ids = {
        int(i) for i in (intake.get('duplicate_expense_ids') or [])
        if str(i).isdigit()
    }

    rows, row_error = [], None
    try:
        rows = _fetch_expenses_by_ids(intake.get('expense_ids') or [])
        rows, promoted_duplicate_ids = collapse_check_evidence_rows(
            rows, duplicate_ids)
        duplicate_ids |= promoted_duplicate_ids
    except Exception as exc:
        row_error = str(exc)

    pdf_path, receipt_path = _associated_source_paths(rows)
    if intake.get('kind') == 'pdf':
        # Rule 2: the currently-processed document IS the PDF — it's the
        # source regardless of what (date, amount) matching finds elsewhere.
        pdf_display = '<b>this.</b>'
    else:
        pdf_display = _esc(pdf_path) if pdf_path else META_EMPTY
    scanned_statement_path, moms_ledger_path = _associated_evidence_paths(rows)
    # Resolve the durable archive copy once: it is the ONLY scan-image path the
    # report is allowed to print. The intake's own image_path is a temporary
    # staging location, so showing it advertises a path that will not exist
    # tomorrow (and leaks the staging tree) — the file name still appears as
    # "Most Recent Document", which is the part a reader can act on.
    archive_path = _recent_intake_archive_path(
        intake, rows, receipt_path=receipt_path)
    # The scanned statement is its own evidence slot, but for statement intakes
    # it resolves to the same archived copy — print it only when it adds a path
    # the reader cannot already see.
    if archive_path and (
            scanned_statement_path == archive_path
            or archive_path == _statement_archive_path(
                rows, vendor_key=(rows[0].get('vendor_key') if rows else ''))):
        # For a statement these are two names for one page: scanned_statement_url
        # holds the raw scanner filename the DB happened to record, archive_path
        # the canonically-named copy actually filed. Printing both offers the
        # reader a stale path beside the real one.
        scanned_statement_path = ''

    def _path_field(path):
        return _esc(path) if path else META_EMPTY

    meta_fields = [
        ('Document Type', _esc(_document_type_label(
            intake.get('doc_kind'), intake.get('vendor')))),
        ('Month Range', _esc(_format_month_range(rows))),
        ('Associated PDF', pdf_display),
        ('Associated Receipt', _path_field(receipt_path)),
        ('Associated Scanned Statement', _path_field(scanned_statement_path)),
        ('Archived Scan Image', _path_field(archive_path)),
        ('Associated Mom’s Ledger', _path_field(moms_ledger_path)),
    ]

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
    # Refresh while we're still waiting on Mazda's STEP 8 report-back.
    terminal = intake_status in _TERMINAL_INTAKE_STATUSES
    working = ('' if (reported or terminal)
               else intake_report_page.mazda_working_html(
                   mazda_intake_progress(intake)))
    # Unconditional since 2026-08-19. It used to appear only on a
    # needs_human_review intake -- i.e. only while Mazda was switched off --
    # so turning her back on took the review dialog away with her. The two are
    # separate questions: the switch decides who READS the next document, this
    # form is where a human CHECKS and corrects whatever was read, and that is
    # worth having in either mode. Save All still only inserts, so on a
    # document Mazda already filed it is the way to add an expense she missed;
    # correcting one she got wrong is Edit Expense's job, in the same dialog.
    presentation_rows_list = intake_report_model.presentation_rows(
        rows, duplicate_ids,
        stored=intake.get('stored'), parsed=intake.get('parsed'))
    source_descriptions = {}
    doc_kind = str(intake.get('doc_kind') or '').lower()
    if doc_kind in ('statement', 'bank_statement'):
        source_descriptions = intake_report_model.recover_statement_source_descriptions(
            f"{intake.get('image_path')}.statement.json"
            if intake.get('image_path') else '',
            presentation_rows_list,
        )
    elif doc_kind == 'receipt':
        receipt_token = hashlib.sha256(
            str(intake.get('image_path') or '').encode('utf-8')).hexdigest()[:12]
        source_descriptions = intake_report_model.recover_receipt_source_descriptions(
            f'/tmp/mazda_receipt_{receipt_token}.json'
            if intake.get('image_path') else '',
            presentation_rows_list,
        )
    presentation_rows_list = intake_report_model.apply_source_descriptions(
        presentation_rows_list, source_descriptions)
    presentation_rows_list = intake_report_model.apply_canonical_vendor_keys(
        presentation_rows_list,
        lambda description: manual_entry.resolve_vendor_match(
            description).get('vendor_key'),
    )
    # Mazda's own findings (whatever STEP 8 already stored for this document)
    # seed the review dialog instead of leaving it blank -- an auto-scan used
    # to only ever populate Verified Transactions, so checking/correcting what
    # she read meant re-running Mazda Fill by hand. resolve_vendor resolves
    # each row's *canonical* vendor_key (manual_entry.resolve_vendor_match)
    # so the dialog's vendor dropdown preselects a known merchant even though
    # the DB's own vendor_key column can hold a one-off, transaction-specific
    # slug rather than the reusable key the dropdown lists.
    stored_items = intake_report_model.stored_findings(
        presentation_rows_list,
        resolve_vendor=lambda description: manual_entry.resolve_vendor_match(
            description).get('vendor_key'),
        guess_vendor=vendor_lookup.guess_vendor_key,
        vendor_is_known=vendor_lookup.vendor_is_known)
    manual_entry_html = intake_report_page.manual_entry_form_html(
        intake.get('image_path'), intake.get('conversation_id'), scanner_key,
        mazda_mode=_MAZDA_MODE_SERVICE.current(), stored_items=stored_items)
    # Unconditional, unlike the form above. Save All inserts, so it belongs
    # only to a scan nobody has typed in yet; Edit Expense corrects a row that
    # is already stored, so gating it on the same status made it unreachable
    # at exactly the moment it was needed.
    expense_edit_html = intake_report_page.expense_edit_panel_html()
    return intake_report_page.render_intake_report(
        headline=intake_report_model.display_document_name(
            archive_path, intake.get('document') or 'document'),
        subtitle=(f'{label} — ' if label else '') + f'dispatched {when}',
        meta_fields=meta_fields,
        status_text=intake_report_model.status_sentence(
            intake, rows, row_error=row_error,
            status_detail=intake.get('status_detail')),
        status_tone=intake_report_model.status_tone(
            intake_status, reported, rows),
        table_html=intake_report_page.transactions_table_html(
            presentation_rows_list,
            source_document_url=source_document_url,
            empty_note=intake_report_model.empty_table_note(
                intake_status, reported)),
        working_html=working,
        expense_edit_html=expense_edit_html,
        archive_path=archive_path,
        auto_refresh=not (rows or reported or terminal),
        extra_css=('\n' + _receipt_only_cat_css() + '\n' + click_css + '\n'
                   + picker_css + '\n'),
        picker_html=picker_html,
        manual_entry_html=manual_entry_html,
    )


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
    return _embed_report_html(recent['url'], recent['file'])


def _embed_report_html(report_url, report_file):
    """Return a current picker report with a <base href> for dashboard use."""
    # Existing reports are static artifacts. Refresh the replaceable picker
    # block in memory so scanner tabs receive the current UI without requiring
    # every archived report to be regenerated on disk.
    html = _report_html_with_current_picker(report_file)
    base_href = report_url.rsplit('/', 1)[0] + '/'
    base_tag = f'<base href="{base_href}">'
    m = re.search(r'<head[^>]*>', html, re.I)
    if m:
        return html[:m.end()] + base_tag + html[m.end():]
    return base_tag + html


def _scanner_statement_report(scanner_key, intake):
    """Prefer the canonical archived statement report for one scanner intake.

    When a statement scan already has a real archived report.html that contains
    one of this intake's expense ids, serve that report directly instead of the
    synthetic intake page. This keeps the scanner tab aligned with the verified
    canonical artifact and avoids collapsing a statement down to whatever subset
    of ids happened to be forwarded in the intake callback.
    """
    if not isinstance(intake, dict):
        return None
    doc_kind = str(intake.get('doc_kind') or '').strip().lower()
    if doc_kind not in {'statement', 'bank_statement', 'tax_document'}:
        return None
    expense_ids = []
    for source in (intake.get('expense_ids') or [],
                   intake.get('duplicate_expense_ids') or [],
                   intake.get('scanned_statement_attached') or []):
        for value in source:
            try:
                expense_ids.append(int(value))
            except (TypeError, ValueError):
                continue
    if not expense_ids:
        return None
    seen = set()
    for expense_id in expense_ids:
        if expense_id in seen:
            continue
        seen.add(expense_id)
        found = _find_matching_report_row('', '', expense_id=expense_id)
        if not found:
            continue
        report_file = _report_file_for_url(found.report_path)
        if report_file:
            return {'url': found.report_path, 'file': report_file, 'expense_id': expense_id}
    return None


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
    canonical = _scanner_statement_report(scanner_key, intake)
    if canonical:
        return _embed_report_html(canonical['url'], canonical['file'])
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
    reprocess hit the actual file on disk.

    The dialog now posts location.search too (the scanner report needs it to say
    WHICH scanner), so every synthetic page is matched on its path alone and
    answers without its query string."""
    base = str(report_path or '').split('?', 1)[0]
    if base == RECENT_REPORT_PATH:
        recent = resolve_recent_report()
        if recent and recent.get('mode') == 'report':
            return recent['url']
        # Intake mode (or nothing yet): no report.html backs the page — return
        # '' so recategorize does its search-every-report / DB-only fallback,
        # exactly like the New Records dialog.
        return ''
    if base == SCANNER_REPORT_PATH:
        # Scanner reports are always synthetic DB-backed pages. There is no
        # report.html to recolor, so an empty path intentionally selects
        # recategorize_expense's search/static-row-or-DB-only success path.
        return ''
    if base == RECEIPT_ONLY_REPORT_PATH:
        # Synthetic too, but its own code path keys off this exact constant.
        return base
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


# _update_report_row_color moved to finance/recategorize.py, with the two
# functions that are its only callers. The URL->file mapping it needs stays
# here, so it is passed in.


def _rol_get_connection():
    """get_connection() from the rol_finances receipt_parsing_tools tree."""
    import sys as _sys
    if RECEIPT_PARSING_TOOLS not in _sys.path:
        _sys.path.insert(0, RECEIPT_PARSING_TOOLS)
    from app.db import get_connection  # type: ignore
    return get_connection()


_category_taxonomy = None
_category_taxonomy_lock = threading.Lock()


def _get_category_taxonomy():
    """Composition root for the category tree.

    The DB is authoritative; LEGACY_TAXONOMY is the fallback so a database blip
    degrades the Set Category dialog to the old hardcoded behaviour instead of
    emptying it. Migration 002 backfilled the presentation columns to reproduce
    those same maps, so this returns identical answers to the four dicts above
    for every id they covered — verified against all 169 categories and 892
    categorised expenses by migrations/verify_taxonomy_equivalence.py.
    """
    global _category_taxonomy
    with _category_taxonomy_lock:
        if _category_taxonomy is None:
            # Late-bound connection: resolve the module attribute per call so a
            # test (or a reconnect) that replaces _rol_get_connection is honoured
            # instead of being frozen in at first use.
            _category_taxonomy = FallbackCategoryTaxonomy(
                MySqlCategoryTaxonomy(lambda: _rol_get_connection()),
                LEGACY_TAXONOMY,
            )
    return _category_taxonomy


def _vendor_prefix(id_light):
    """Strip the trailing _MM_DD_YY_<amount> from an id_light to get its vendor part."""
    import re as _re
    return _re.sub(r'_\d{2}_\d{2}_\d{2}_\d+_\d+$', '', id_light or '')


# ── ROL Finance: setting a row's category, and taking it back ────────────────
# recategorize_expense, undo_recategorize_expense, the report-row repaint and
# the undo journal's composition root moved to finance/recategorize.py. They are
# one gesture that has to land in two places which can disagree -- the expenses
# row and the cat-* class in a static report.html -- plus the journal that
# reverses both by the same matching rules.
#
# What stays here (the DB connection, the taxonomy, the two category-name
# resolvers, the report-row search, the URL->file mapping) is handed over per
# call in a Collaborators bundle rather than imported back. That is what keeps
# `monkeypatch.setattr(server, '_rol_get_connection', ...)` reaching the code
# that actually runs.
#
# _update_report_row_color, _record_category_undo, _undo_category_action,
# _get_category_undo_service and CATEGORY_UNDO_JOURNAL are deliberately NOT
# re-exported: nothing here calls them any more, and a re-export is a second
# binding that a test can patch while the real one keeps running
# (tests/test_recategorize.py asserts they are absent).
from finance import recategorize as _recategorize  # noqa: E402


def _recategorize_deps():
    """Resolve this module's half of the category cluster, at call time.

    Every entry is looked up when the call happens, not when this module is
    imported, so replacing any of them on `server` is honoured.
    """
    return _recategorize.Collaborators(
        get_connection=lambda: _rol_get_connection(),
        resolve_reporting_category=_resolve_reporting_category,
        css_class_for_report_name=_css_class_for_report_name,
        find_matching_report_row=_find_matching_report_row,
        report_file_for_url=_report_file_for_url,
        vendor_prefix=_vendor_prefix,
        category_taxonomy=_get_category_taxonomy,
        receipt_only_report_path=RECEIPT_ONLY_REPORT_PATH,
    )


def recategorize_expense(date_str, signed_amount, vendor_key, reporting_category,
                         description='', report_path='', expense_id=None):
    """Persist a user's category pick for one Verified-Transactions row."""
    return _recategorize.recategorize_expense(
        date_str, signed_amount, vendor_key, reporting_category,
        description, report_path, expense_id, deps=_recategorize_deps())


def undo_recategorize_expense(token):
    """Undo one tokenized category write without overwriting a newer choice."""
    return _recategorize.undo_recategorize_expense(
        token, deps=_recategorize_deps())


# Moved to finance/vendor_review.py -- list_vendor_keys, list_pending_vendor_review,
# set_receipt_vendor, and the PendingVendorReviewRow model. get_connection,
# receipt_url_for_path and _vendor_category_lookup are this module's, so the
# composition roots below inject them as late-bound lambdas rather than letting
# the moved code import them back -- a test replacing server._vendor_category_lookup
# (to fake a vendor_category.yaml) is honoured only because of the late binding.
from finance.vendor_review import (
    list_vendor_keys as _list_vendor_keys,
    list_pending_vendor_review as _list_pending_vendor_review,
    set_receipt_vendor as _set_receipt_vendor,
)

_vendor_category_lookup = vendor_lookup.vendor_category_lookup


def list_vendor_keys():
    return _list_vendor_keys(lambda: _vendor_category_lookup())


def list_pending_vendor_review():
    return _list_pending_vendor_review(
        lambda: _rol_get_connection(), lambda fp: _receipt_url_for_path(fp))


def set_receipt_vendor(expense_id, vendor_key):
    return _set_receipt_vendor(
        lambda: _rol_get_connection(), lambda: _vendor_category_lookup(),
        expense_id, vendor_key)


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
# The two scanners moved to hardware/scanners.py as typed `ScannerSpec`s, and
# `SCANNERS` is now a derived view of them — same keys, same nested dicts, same
# order. The specs cross-check what the dict never could: that `namelike` and
# `driver_match` actually describe the `device` the script drives (otherwise the
# Diagnostics tab probes one scanner while scans come off the other), that
# `output` is a bare filename before it is joined to SCAN_TOOLS_DIR, and that no
# two scanners share an `output` (which would show the Freezer's page the
# Window's last scan).
#
# Imported here because server.py's own scan paths, hardware/scanner_diagnostics
# and tests/ all still name `SCANNERS` through `server`.
from hardware.scanners import SCANNERS  # noqa: E402

# Finding a WSL_INTEROP socket that actually relays to Windows moved to
# hardware/wsl_interop.py -- it is not scanner logic, and the printer repair
# needs it too. Re-exported under the historical names: the scan paths below
# and tests/test_server.py both reach it through `server`.
from hardware.wsl_interop import (  # noqa: E402
    _interop_works,
    _wsl_interop_socket,
)

# The DeskJet queue repair moved to hardware/printer.py: 220 lines of Windows
# PowerShell and LEDM status parsing that never touch this module's state. The
# constants are re-exported because the scanner dialogs and tests name them
# through `server`.
from hardware.printer import (  # noqa: E402
    DESKJET_BLOCKING_STATUS,
    DESKJET_PRINTER_IP,
    DESKJET_PRINTER_NAME,
    DESKJET_PRINTER_PORT,
    DESKJET_PRINT_ONLY_STATUS,
    DESKJET_STATUS_URL,
    read_deskjet_device_status,
)
from hardware.printer import fix_deskjet_printer as _fix_deskjet_printer  # noqa: E402
from hardware.wsl_interop import WINDOWS_POWERSHELL as _WINDOWS_POWERSHELL  # noqa: E402


def fix_deskjet_printer(runner=subprocess.run, device_status=None):
    """Composition root for the DeskJet repair: this module's interop lookup.

    The lambda is the point. Handing over `_wsl_interop_socket` itself would
    freeze whichever function object existed at import time, and six tests
    replace `server._wsl_interop_socket` before calling this -- going through
    the module global on every call keeps them honoured.
    """
    return _fix_deskjet_printer(
        lambda: _wsl_interop_socket(), runner=runner, device_status=device_status)


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


# Reading a scan script's outcome, and judging whether the page has anything on
# it, moved to hardware/scan_result.py. Both are pure and neither touches this
# module's state; the optional Pillow import went with them, so nothing else
# here has to know the blank-scan gate exists.
from hardware.scan_result import (  # noqa: E402
    _busiest_tile_spread,
    _scan_output_ready,
    classify_scan_result,
    inspect_scan_image_quality,
)


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
    uses_airscan = bool(cfg.get('airscan_device'))
    interop = _wsl_interop_socket()
    if not interop and not uses_airscan:
        return {'status': 'error',
                'error': 'No usable WSL interop socket — open a WSL session so the '
                         'service can launch the scanner.'}
    scan_env = os.environ.copy()
    if interop:
        scan_env['WSL_INTEROP'] = interop
    with _SCAN_LOCK:
        if not uses_airscan:
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
            if not uses_airscan:
                _reap_stale_scans(scan_env)
            return {'status': 'error',
                    'error': f'Scan timed out after {SCAN_TIMEOUT_SEC}s '
                             '(scanner not responding).'}
        except Exception as exc:  # noqa: BLE001 — surface launch failures to the UI
            return {'status': 'error', 'error': f'Failed to start scan: {exc}'}
    log = ((proc.stdout or '') + (proc.stderr or '')).strip()
    img = os.path.join(SCAN_TOOLS_DIR, cfg['output'])
    result = classify_scan_result(proc.returncode, log, _scan_output_ready(img))
    if result['status'] == 'ready':
        # Cache-bust so the browser reloads the freshly scanned image each time.
        result['image_url'] = (
            f'{SCANNER_IMAGE_URL_PREFIX}?scanner={key}&t={int(time.time())}')
    return result


# ── Scanner workflow diagnostics (the health LEDs) ──────────────────────────
# The probes and the 210-line pure map from probe results to LED rows live in
# hardware/scanner_diagnostics.py. What stays here is the composition root
# below: it owns SCANNERS, the scan lock and the interop lookup, and hands the
# results over. Re-exported under the historical names for tests and callers.
from hardware.scanner_diagnostics import (  # noqa: E402
    SCANNER_DIAG_LOCK_WAIT_SEC,
    SCANNER_DIAG_TIMEOUT_SEC,
    _airscan_ready,
    _diag_check,
    _run_scanner_diag_ps,
    build_scanner_diagnostics,
)


def scanner_diagnostics(key):
    """Read-only health snapshot of one scanner's whole workflow (the LEDs).

    Never starts a WIA transfer. The Windows probe briefly waits for
    `_SCAN_LOCK` so switching from Freezer to Window does not make the two
    diagnostic requests manufacture a false "scan in progress" warning. A real
    scan keeps the lock beyond this small wait, in which case the WIA checks are
    still skipped rather than interfering with its transfer.
    """
    if key not in SCANNERS:
        return {'scanner': key, 'checks': [], 'overall': 'bad',
                'error': f'Unknown scanner: {key}'}
    airscan_ready = _airscan_ready(SCANNERS[key])
    interop = _wsl_interop_socket()
    ps_data = None
    if interop and not airscan_ready:
        acquired = _SCAN_LOCK.acquire(timeout=SCANNER_DIAG_LOCK_WAIT_SEC)
        try:
            ps_data = _run_scanner_diag_ps(
                SCANNERS[key], interop, SCAN_TOOLS_DIR,
                skip_wia=not acquired)
        finally:
            if acquired:
                _SCAN_LOCK.release()
    device_status = read_deskjet_device_status() if key == 'freezer' else None
    return build_scanner_diagnostics(
        key, bool(interop), ps_data, device_status, airscan_ready=airscan_ready)


MAZDA_AGENT_ID = 'agent-6b536cf4-ec88-4290-b595-fed21d14bd8e'

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
    if not _scan_output_ready(local_image_path):
        print('[scan→mazda] Refusing to stage a missing or empty scan output')
        return None
    # Scanner output names are reusable (window_scan.jpg / scan_freezer.jpg), while a
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


# ── Execution mode (human-only decision gate) ──────────────────────────────
# MAZDA_DECISION_MODE gates whether a scan/PDF dispatch may construct Mazda
# and the Trainer at all. This is the single fork point for every LLM call
# the intake pipeline can make: every deeper LLM call (categorizer, vision,
# parser selection) only happens INSIDE Mazda's own agent turn, so never
# starting that turn blocks all of them at once — there is no way to reach
# in and intercept a call three layers inside her reasoning.
#
# The fork itself, the scan dispatch it guards and the record it writes when
# it declines now live in intake/mazda_dispatch.py; the mode vocabulary and
# its env-var parser live beside the operator's switch in intake/mazda_mode.py.
# What is left here is the composition root: the process-wide default, the
# operator's store, and the collaborators mazda_dispatch is handed per call.

# Resolved once at process start, like TRAINER_ENABLED below — an env change
# never alters an already-running process; restart dashboard-server.service
# to pick up a new value (in-flight/pending runs are unaffected either way).
EXECUTION_MODE = resolve_execution_mode()

#: Where an operator's choice of mode outlives this process. Beside the other
#: small operator preferences (~/.mazda/model_stats_muted.json).
MAZDA_MODE_FILE = os.path.expanduser('~/.mazda/mazda_mode.json')

# The switch on the intake dialog writes here; dispatch_or_block reads here.
# EXECUTION_MODE is handed over as a callable, not a value, so it stays the
# live default -- the env var still decides everything on a box where nobody
# has ever touched the switch, and the test suite's monkeypatch of
# EXECUTION_MODE keeps working.
_MAZDA_MODE_SERVICE = MazdaModeService(
    JsonFileMazdaModeStore(MAZDA_MODE_FILE),
    default_mode=lambda: EXECUTION_MODE,
)


def current_execution_mode():
    """The mode in force *right now* -- operator's switch, else EXECUTION_MODE.

    Every dispatch decision goes through this rather than reading
    EXECUTION_MODE directly, so flipping the switch takes effect on the next
    scanned document instead of the next restart.
    """
    return _MAZDA_MODE_SERVICE.mode()


def mazda_mode_status():
    """GET /api/mazda-mode: what the intake dialog's switch should show."""
    return _MAZDA_MODE_SERVICE.current().to_http()


def set_mazda_mode(data):
    """POST /api/mazda-mode: move the switch, or say why the body was refused."""
    return _MAZDA_MODE_SERVICE.set_from_http(data)


def _mazda_dispatch_deps():
    """Rebuilt per call, never captured.

    current_execution_mode is a bound *function*, so a monkeypatched
    EXECUTION_MODE or a live flip of the operator's switch is read at the
    moment the fork asks, not at import. watch_intake is the Trainer's --
    it stays in this file with the escalation service it wraps.
    """
    return mazda_dispatch.Collaborators(
        current_mode=current_execution_mode,
        watch_intake=_watch_intake_for_problems,
        merge_status=merge_recent_intake_status,
        observe_callback=_observe_intake_callback,
        letta_get=letta_get,
    )


def _dispatch_mazda_or_block(document_path, label, facade, conversation_id,
                             dispatched_at, mazda_thread_target, mazda_thread_args):
    """The one fork point between Mazda's LLM turn and human-only blocking.

    Thin wrapper: both intake entry points and the Mazda-mode tests reach it
    through `server`. The decision lives in intake/mazda_dispatch.py.
    """
    return mazda_dispatch.dispatch_or_block(
        _mazda_dispatch_deps(), document_path, label, facade, conversation_id,
        dispatched_at, mazda_thread_target, mazda_thread_args)


def _notify_mazda_of_scan_and_record_failure(
        scan_image_path, scanner_name, facade_result=None,
        conversation_id=None, dispatched_at=None):
    """Dispatch a scan and make a transport failure visible in its report.

    Kept as a wrapper because it is handed to _dispatch_mazda_or_block as the
    scan path's thread target.
    """
    return mazda_dispatch.notify_mazda_of_scan_and_record_failure(
        _mazda_dispatch_deps(), scan_image_path, scanner_name, facade_result,
        conversation_id, dispatched_at)


# ── Mazda Trainer ────────────────────────────────────────────────────────────
# Normal intake runs without a Trainer. Callback evidence or a missing callback
# summons one through the typed escalation policy in intake/trainer_escalation.
TRAINER_SCRIPT = os.path.join(HERE, 'trainer', 'run_mazda_trainer.mjs')
TRAINER_RUNNER = os.environ.get(
    'MAZDA_TRAINER_RUNNER', os.path.expanduser('~/.bun/bin/bun'))
TRAINER_ENABLED = os.environ.get(
    'MAZDA_TRAINER_ENABLED', '1').lower() not in ('0', 'false', 'no')
TRAINER_CALLBACK_TIMEOUT_SECONDS = float(os.environ.get(
    'MAZDA_TRAINER_CALLBACK_TIMEOUT_SECONDS', '900'))


def _build_trainer_escalation_service():
    if not TRAINER_ENABLED:
        return NullTrainerEscalationService()
    return ProblemOnlyTrainerEscalationService(
        notifier=DetachedTrainerNotifier(TRAINER_RUNNER, TRAINER_SCRIPT),
        scheduler=ThreadingDeadlineScheduler(),
        callback_timeout_seconds=TRAINER_CALLBACK_TIMEOUT_SECONDS,
        recorder=CallbackTrainerEscalationRecorder(merge_recent_intake_event),
    )


_trainer_escalation_service = _build_trainer_escalation_service()


def _recover_trainer_escalations():
    return recover_pending_trainer_watches(
        _read_recent_pointer_file(), _trainer_escalation_service)


def _watch_intake_for_problems(scan_path, scanner_name, facade_result,
                               conversation_id, dispatched_at):
    return _trainer_escalation_service.watch(TrainerLaunchRequest(
        scan_path=scan_path,
        scanner_name=scanner_name,
        facade_result=dict(facade_result or {}),
        conversation_id=conversation_id,
        dispatched_at=float(dispatched_at),
    ))


def _observe_intake_callback(payload):
    callback = IntakeCallback.from_mapping(payload)
    if callback is None:
        return None
    return _trainer_escalation_service.observe(callback)


def _notify_mazda_of_pdf(file_path, label=None, conversation_id=None,
                         dispatched_at=None, facade_result=None):
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


def _may_retry_terminal_scan(previous, content_sha256):
    """Retry-policy Strategy for a byte-identical scanner document.

    A successful or active intake owns its fingerprint.  A terminal failure
    does not: operators must be able to retry the same legitimate page after
    its infrastructure or orchestration failure is repaired.
    """
    if not previous or previous.get('content_sha256') != content_sha256:
        return True
    return str(previous.get('status') or '').lower() in {'fail', 'stalled'}


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
        if (content_sha256 and
                not _may_retry_terminal_scan(previous, content_sha256)):
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
    return intake_is_in_progress(
        get_scanner_intake(key), max_age_seconds=max_age_seconds)


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
    if result.get('empty_output'):
        # Nothing was dispatched, so no STEP 8 callback is ever coming. Record
        # the failure against this scanner ourselves -- same reason as the
        # blank-page rejection in process_scanned_document.
        record_recent_intake(
            os.path.join(SCAN_TOOLS_DIR, (SCANNERS.get(key) or {}).get('output', '')),
            (SCANNERS.get(key) or {}).get('name'),
            status='fail', status_detail=result.get('error') or '')
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
    if _scanner_intake_in_progress(key):
        return {
            'status': 'intake_busy',
            'ok': False,
            'error': ('The previous document from this scanner is still being '
                      'verified. Wait for intake completion or a problem-triggered '
                      'Trainer verdict before scanning another.'),
        }
    with _scanner_runtime_status_lock:
        return dict(_scanner_runtime_status.get(key, {'status': 'idle', 'ok': True}))


def clear_scanner_verification_lock(key):
    """Terminal-out one scanner's stuck intake lock without changing finance data."""
    if key not in SCANNERS:
        return {'ok': False, 'error': f'Unknown scanner: {key}'}
    intake = get_scanner_intake(key)
    if not intake or not _scanner_intake_in_progress(key):
        return {'ok': True, 'cleared': False,
                'message': 'No active verification lock was found.'}
    update = {
        'conversation_id': intake.get('conversation_id'),
        'document_path': intake.get('image_path'),
        'dispatched_at': intake.get('dispatched_at'),
        'status': 'stalled',
        'detail': ('Verification lock cleared manually from the scanner view; '
                   'the scan and financial records were left unchanged.'),
    }
    if not merge_recent_intake_status(update):
        return {'ok': False, 'error': 'The active verification lock could not be matched.'}
    with _scanner_runtime_status_lock:
        _scanner_runtime_status[key] = {'status': 'idle', 'ok': True}
    return {'ok': True, 'cleared': True, 'status': 'idle'}


# ── Document intake pipeline (the "Process Document" action) ────────────────
# When a scan finishes, the dashboard fires POST /api/process-document. The
# cheapest reliable tool runs FIRST — the deterministic intake facade
# (mazda_intake.py: classify + parse) — and its result is rendered inline within
# seconds. The deeper, agentic stages (investigate → categorize → store) are
# Mazda's job; they are dispatched fire-and-forget (NO polling) via the existing
# _notify_mazda_of_scan thread. Governing rule: cheapest reliable tool first;
# LLM only when confidence < 0.90 (the facade enforces that threshold itself).
from paths import ROL_FINANCES_DIR  # noqa: E402
MAZDA_INTAKE_FACADE = os.path.join(ROL_FINANCES_DIR, 'tools', 'mazda_intake.py')
MAZDA_INTAKE_PYTHON = os.path.join(ROL_FINANCES_DIR, '.venv', 'bin', 'python3')
INTAKE_FACADE_TIMEOUT_SEC = 120
STATEMENT_PARSE_SCRIPT = os.path.join(
    ROL_FINANCES_DIR, 'tools', 'receipt_scanning_tools', 'parse_statement_scan.py')
STATEMENT_PREFLIGHT_TIMEOUT_SEC = 180

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


def _statement_last4(value):
    text = str(value or '').strip()
    match = re.search(r'(?:^|\D)(\d{4})$', text)
    if match:
        return match.group(1)
    # Some statements print the complete account number and vision returns it
    # despite the parser contract asking for the final four. Six or more plain
    # digits are unambiguously a full account number; retain its final four.
    # Deliberately do not truncate five-digit values: malformed five-digit Amex
    # workbook cells are a known trap and must continue to fail closed.
    if re.fullmatch(r'\d{6,}', text):
        return text[-4:]
    return None


def _default_statement_account_directory():
    """Build the workbook-backed last-four resolver without a hard import."""
    _ensure_sys_path(ROL_FINANCES_DIR)
    from tools.receipt_scanning_tools.known_accounts import KnownCardsWorkbook
    return KnownCardsWorkbook()


def _complete_statement_transactions(rows):
    """Keep only rows carrying a valid date, description, and numeric amount."""
    complete = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        description = ' '.join(str(row.get('description') or '').split())
        try:
            datetime.strptime(str(row.get('date') or ''), '%Y-%m-%d')
            amount = float(row['amount'])
        except (KeyError, TypeError, ValueError):
            continue
        normalized = dict(row)
        normalized.update(description=description, amount=amount)
        if description:
            complete.append(normalized)
    return complete


def _statement_records(parsed):
    """Normalize parse_statement_scan.py's output to a list of statement dicts.

    The script grew a multi-statement envelope on 2026-07-22 (one scanned page
    can hold two cards): {'statements': [{bank_name, account_number,
    transactions, ...}, ...]}. It previously put those fields at the top level.
    Both shapes are accepted here so the preflight keeps working whichever
    version of the script is deployed — reading only the old flat keys against
    the new envelope silently yielded no bank, no last4 and no transactions,
    which rejected every statement scan before it could be dispatched.
    """
    if not isinstance(parsed, dict):
        return []
    statements = parsed.get('statements')
    if isinstance(statements, list):
        return [s for s in statements if isinstance(s, dict)]
    if any(parsed.get(key) is not None
           for key in ('bank_name', 'account_number', 'transactions')):
        return [parsed]
    return []


def _statement_records_summary(statements):
    """Human-readable 'Chase 1234, Amex 5678' for a multi-statement rejection."""
    labels = []
    for statement in statements:
        bank = ' '.join(str(statement.get('bank_name') or '').split())
        last4 = _statement_last4(statement.get('account_number'))
        labels.append(' '.join(part for part in (bank, last4) if part)
                      or 'unidentified account')
    return ', '.join(labels)


def run_statement_preflight(
        image_path, facade_result, metadata=None, account_directory=None,
        engine='auto'):
    """Extract and validate statement metadata before dispatch or storage.

    `engine`: 'auto' (default, unchanged behavior) is parse_statement_scan.py's
    own full Gemini/Codex/ChatGPT/OpenAI fallback chain, used for every
    automatic Mazda dispatch. 'gemini-only'/'haiku-only' name one provider with
    no fallback -- the dashboard's "Read with Gemini"/"Read with Haiku"
    buttons, where an operator who chose a provider must get exactly that one,
    not a silent fallback to a different one on failure.
    """
    if (facade_result or {}).get('doc_kind') not in ('statement', 'bank_statement'):
        return None
    metadata = metadata if isinstance(metadata, dict) else {}
    command = [MAZDA_INTAKE_PYTHON, STATEMENT_PARSE_SCRIPT, image_path]
    bank_override = ' '.join(str(metadata.get('bank_name') or '').split())
    last4_override = _statement_last4(metadata.get('account_last4'))
    if bank_override:
        command.extend(['--bank-name', bank_override])
    if last4_override:
        command.extend(['--account-last4', last4_override])
    if engine and engine != 'auto':
        command.extend(['--engine', engine])
    try:
        proc = subprocess.run(
            command, cwd=ROL_FINANCES_DIR, capture_output=True, text=True,
            timeout=STATEMENT_PREFLIGHT_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'rejected': True,
                'error': 'statement extraction timed out before storage'}
    except Exception as exc:
        return {'ok': False, 'rejected': True,
                'error': f'statement extraction failed before storage: {exc}'}
    output = (proc.stdout or '').strip()
    try:
        json_start = output.find('{')
        if json_start < 0:
            raise ValueError('no JSON object')
        parsed = json.loads(output[json_start:])
    except (ValueError, json.JSONDecodeError):
        detail = (proc.stderr or output or f'exit {proc.returncode}')[:300]
        return {'ok': False, 'rejected': True,
                'error': f'statement extraction returned no JSON: {detail}'}
    if not parsed.get('ok'):
        return {'ok': False, 'rejected': True,
                'error': parsed.get('error') or 'statement extraction failed'}

    statements = _statement_records(parsed)
    if len(statements) > 1:
        # The parser can split one scanned page into several accounts, but every
        # stage after this point — the --bank-name/--account-last4 flags in
        # build_mazda_scan_message, the single per-scanner intake record, the
        # store script — describes ONE account. Attributing two accounts'
        # transactions to statements[0] would file real money under the wrong
        # card silently, so halt and ask for one statement per pass instead.
        return {
            'ok': False, 'rejected': True, 'needs_statement_metadata': False,
            'error': ('Statement rejected: this scan holds '
                      f'{len(statements)} separate statements '
                      f'({_statement_records_summary(statements)}). Storage '
                      'handles one account per scan — rescan them one at a '
                      'time.'),
        }
    statement = statements[0] if statements else {}
    parsed_bank_name = ' '.join(
        str(statement.get('bank_name') or '').split())
    facade_issuer = ' '.join(
        str((facade_result or {}).get('vendor') or '').split())
    if facade_issuer.lower() in ('unknown', 'none', 'null'):
        facade_issuer = ''
    bank_name = bank_override or parsed_bank_name or facade_issuer
    statement_last4 = _statement_last4(statement.get('account_number'))
    account_last4 = last4_override or statement_last4
    last4_source = 'operator' if last4_override else (
        'statement' if account_last4 else 'unknown')
    workbook_ambiguous_last4 = []
    workbook_matched_names = []
    # The primary branded letterhead identifies the account family more safely
    # than OCR of marked-over digits.  Always try that identity even when vision
    # emitted four digits; a unique workbook row is authoritative.  If there is
    # no branded identity, retain the older missing-last4 lookup by bank name.
    lookup_candidates = []
    if not last4_override and facade_issuer:
        lookup_candidates.append(facade_issuer)
    if not account_last4 and bank_name and bank_name not in lookup_candidates:
        lookup_candidates.append(bank_name)
    lookup = None
    lookup_name = ''
    for candidate in lookup_candidates:
        try:
            candidate_lookup = (
                account_directory or _default_statement_account_directory()
            ).lookup_last4(candidate)
        except Exception:
            candidate_lookup = None
        if not candidate_lookup:
            continue
        candidate_last4 = _statement_last4(
            getattr(candidate_lookup, 'last4', None))
        candidate_ambiguity = list(
            getattr(candidate_lookup, 'ambiguous_last4', ()) or ())
        if candidate_last4 or candidate_ambiguity:
            lookup = candidate_lookup
            lookup_name = candidate
            break
    if lookup:
        workbook_last4 = _statement_last4(getattr(lookup, 'last4', None))
        workbook_ambiguous_last4 = list(
            getattr(lookup, 'ambiguous_last4', ()) or ())
        workbook_matched_names = list(
            getattr(lookup, 'matched_names', ()) or ())
        if workbook_last4:
            account_last4 = workbook_last4
            last4_source = 'known_cards_workbook'
            if lookup_name == facade_issuer:
                bank_name = facade_issuer
        elif workbook_ambiguous_last4:
            account_last4 = None
            last4_source = 'unknown'
    transactions = _complete_statement_transactions(statement.get('transactions'))
    if not transactions:
        return {
            'ok': False, 'rejected': True, 'needs_statement_metadata': False,
            'error': ('Statement rejected: no complete transaction with date, '
                      'vendor/description, and amount was found.'),
        }
    missing = []
    if not bank_name:
        missing.append('bank_name')
    if not account_last4:
        missing.append('account_last4')
    result = dict(parsed)
    result.update({
        'bank_name': bank_name or None,
        'account_last4': account_last4,
        'account_number': account_last4,
        'transactions': transactions,
        'transaction_count': len(transactions),
        'last4_source': last4_source,
        'workbook_ambiguous_last4': workbook_ambiguous_last4,
        'workbook_matched_names': workbook_matched_names,
    })
    if missing:
        ambiguity = (
            ' Candidates in the known-cards workbook: '
            + ', '.join(workbook_ambiguous_last4) + '.'
            if workbook_ambiguous_last4 else '')
        result.update({
            'ok': False,
            'needs_statement_metadata': True,
            'missing_fields': missing,
            'error': (
                'Statement needs bank name and account last four before storage.'
                + ambiguity),
        })
    return result


def _statement_preflight_payload(image_path, preflight):
    """Return the exact validated parser envelope Mazda must store.

    Preserve the original per-statement rows (including unreadable rows) so the
    downstream validator can quarantine them. The top-level ``transactions``
    list is only the complete-row summary used by preflight.
    """
    source_statements = preflight.get('statements')
    source = (
        source_statements[0]
        if isinstance(source_statements, list) and source_statements
        and isinstance(source_statements[0], dict)
        else {})
    rows = source.get('transactions')
    if not isinstance(rows, list):
        rows = preflight.get('transactions') or []
    rows = [dict(row) for row in rows if isinstance(row, dict)]
    statement = dict(source)
    statement.update({
        'bank_name': preflight.get('bank_name'),
        'account_number': preflight.get('account_last4'),
        'transaction_count': len(rows),
        'unreadable_count': sum(
            1 for row in rows if row.get('unreadable')),
        'transactions': rows,
    })
    return {
        'ok': True,
        'doc_kind': 'statement',
        'source_image': image_path,
        'statement_count': 1,
        'statements': [statement],
    }


def _write_statement_preflight_payload(image_path, preflight):
    """Write a validated statement envelope beside Mazda's immutable scan."""
    payload_path = image_path + '.statement.json'
    try:
        with open(payload_path, 'w', encoding='utf-8') as handle:
            json.dump(_statement_preflight_payload(image_path, preflight), handle)
    except OSError:
        return ''
    return payload_path


#: doc_kind values run_statement_preflight() will actually act on -- kept in
#: sync with its own `(facade_result or {}).get('doc_kind') not in (...)`
#: check so an operator's override can only ever route into that same branch,
#: never invent a doc_kind the rest of the pipeline doesn't understand.
STATEMENT_DOC_KINDS = ('statement', 'bank_statement')


def _human_override_facade(doc_kind):
    """A synthetic facade result for doc_kind_override, standing in for
    run_intake_facade()'s real (paid, vision-based) classify call.

    The operator has already looked at the document -- the manual-entry
    form's "Show Image" button exists for exactly this -- and knows it isn't
    a receipt. Re-deriving that with a Gemini vision call would spend a token
    MAZDA_DECISION_MODE=human_only exists specifically to avoid (see
    finance/manual_entry.py's module docstring). `parsed` stays None just
    like a real statement classification: run_statement_preflight() is the
    thing that actually reads the document's contents, via its own
    STATEMENT_PARSE_SCRIPT call, which is unavoidable -- a statement's
    several transactions have to be read somehow -- but skipping the
    classify step still saves one full vision call per document.
    """
    return {
        'ok': True, 'error': None, 'doc_kind': doc_kind,
        'routing_key': f'{doc_kind}.human_override', 'vendor': None,
        'confidence': 1.0, 'classification_method': 'human_override',
        'recommended_action': 'auto', 'parsed': None,
    }


# Composition root for the statement-breakup path: which concrete satisfies
# each port is decided here and nowhere else. The adapters themselves live in
# finance/statement_dashboard_adapters.py, built from these functions alone.
_STATEMENT_BREAKUP_SERVICE = StatementBreakupService(
    PreflightStatementExtractor(CallableStatementPreflight(
        run_statement_preflight,
        _statement_preflight_payload,
        _human_override_facade,
    )),
    ScriptStatementStore(),
    CallbackStatementIntakeRecorder(
        merge_recent_intake_event, _invalidate_receipt_index),
)


# Composition root for "Mazda Fill" -- the manual-entry form's one reading
# button. Same arrangement as the statement service above: which concrete
# satisfies each port is decided here and nowhere else.
#
# The classifier is the SAME deterministic facade the automatic pipeline runs
# first (run_intake_facade -> mazda_intake.py), so "which reader does this page
# want" is answered by the tool that already answers it for Mazda, not by a
# local OCR heuristic and not by asking the operator to eyeball it.
_MAZDA_FILL_SERVICE = MazdaFillService(
    CallableDocumentClassifier(
        lambda image_path: (run_intake_facade(image_path) or {}).get('doc_kind')),
    CallableReceiptReader(
        lambda image_path, model: manual_entry.preview_receipt_parse(
            image_path, engine=model, category_namer=taxonomy_category_namer())),
    _STATEMENT_BREAKUP_SERVICE,
    statement_doc_kinds=STATEMENT_DOC_KINDS,
)


def mazda_fill_document(data):
    """POST /api/mazda-fill: read one scanned page with a cheap model.

    Semi-automatic on purpose. Mazda's own classify+read tools run, and the
    answer lands in the form for a human to check and Save -- nothing is
    stored here. That is the whole difference between this and letting
    MAZDA_DECISION_MODE=auto file the document unattended.
    """
    try:
        request = MazdaFillRequest.from_http(data)
    except (ValidationError, ValueError) as exc:
        return {'ok': False, 'error': str(exc)}
    return _MAZDA_FILL_SERVICE.fill(request).to_http()


def break_up_statement_document(data):
    """POST /api/manual-statement-breakup: the "Break Up Document" button.

    A receipt carries one expense and every fill button asks the receipt
    parser, so a statement page holding five transactions filled a single row
    and left the form's Prev/Next navigation nothing to walk. This runs the
    statement parser instead — the same preflight the automatic pipeline runs —
    and answers with one row per transaction.
    """
    try:
        request = StatementBreakupRequest.from_http(data)
    except (ValidationError, ValueError) as exc:
        return {'ok': False, 'error': str(exc)}
    return _STATEMENT_BREAKUP_SERVICE.break_up(request).to_http()


def submit_manual_statement_entry(data):
    """POST /api/manual-statement-entry: Save All, in statement mode.

    Stores the corrected rows through store_statement_transactions.py — the
    same tool Mazda's STATEMENT BRANCH runs, so duplicate detection, the
    credit/payment split (a "PAYMENT - THANK YOU" line is not an expense),
    vendor resolution to NEEDS_VENDOR_KEY, and the scanned-statement archive
    all apply unchanged. Nothing here reimplements any of that.
    """
    try:
        request = StatementStoreRequest.from_http(data)
    except (ValidationError, ValueError) as exc:
        return {'ok': False, 'error': str(exc)}
    return _STATEMENT_BREAKUP_SERVICE.store(request).to_http()


def process_scanned_document(
        key, org_id=1, engine='gemini', statement_metadata=None,
        doc_kind_override=None):
    """Orchestrate the Process Document action for one scanner's latest image.

    1. Resolve the scanner's output image.
    2. Run the deterministic facade (classify + parse) for the inline result
       -- or, when `doc_kind_override` names a statement kind, skip that paid
       classify call and use the operator's own assertion instead (see
       _human_override_facade).
    3. Dispatch Mazda fire-and-forget for investigate → categorize → store.
    No polling: the deeper stages run in Mazda's own time and surface in her
    own agent transcript, not here.
    """
    cfg = SCANNERS.get(key)
    if not cfg:
        return {'ok': False, 'error': f'Unknown scanner: {key}', 'stages': []}
    image_path = os.path.join(SCAN_TOOLS_DIR, cfg.get('output', ''))
    if _SCAN_LOCK.locked():
        return {
            'ok': False,
            'error': 'The scanner is still scanning. Processing will start when the image is complete.',
            'stage_error': 'Scanner transfer still in progress.',
            'scanner': key,
            'image_path': image_path,
            'mazda_dispatched': False,
            'trainer_dispatched': False,
            'stages': [],
        }
    if not _scan_output_ready(image_path):
        return {
            'ok': False,
            'error': 'The scanner did not produce a usable image. Please scan the document again.',
            'stage_error': 'The scanner output image is missing or empty.',
            'scanner': key,
            'image_path': image_path,
            'mazda_dispatched': False,
            'trainer_dispatched': False,
            'stages': [],
        }
    image_quality = inspect_scan_image_quality(image_path)
    if not image_quality.get('ok'):
        # Before the facade, before vision health, before Mazda: a page with
        # nothing on it cannot become an expense, and every stage past here
        # costs either an API call or an agent's turn. Recorded as this
        # scanner's own last intake so the rejection is visible on its tab --
        # otherwise a failed capture reads as a stuck scanner still showing
        # the previous document.
        reason = image_quality.get('reason') or 'The scan is not readable.'
        record_recent_intake(image_path, cfg.get('name'), status='fail',
                             status_detail=reason)
        return {
            'ok': False,
            'error': reason,
            'stage_error': reason,
            'scanner': key,
            'image_path': image_path,
            'image_quality': image_quality,
            'mazda_dispatched': False,
            'trainer_dispatched': False,
            'stages': [],
        }
    if doc_kind_override is not None:
        if doc_kind_override not in STATEMENT_DOC_KINDS:
            return {
                'ok': False,
                'error': f'Unsupported doc_kind_override: {doc_kind_override}',
                'scanner': key, 'image_path': image_path,
                'mazda_dispatched': False, 'trainer_dispatched': False,
                'stages': [],
            }
        facade = _human_override_facade(doc_kind_override)
    else:
        facade = run_intake_facade(image_path, org_id=org_id, engine=engine)
    mazda_dispatched = False
    trainer_dispatched = False
    stage_error = None
    conversation_id = None
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
    statement_preflight = run_statement_preflight(
        image_path, facade, metadata=statement_metadata)
    if statement_preflight is not None:
        if not statement_preflight.get('ok'):
            result = build_pipeline_result(facade, mazda_dispatched=False)
            result['trainer_dispatched'] = False
            result['scanner'] = key
            result['image_path'] = image_path
            result['stage_error'] = statement_preflight.get('error')
            result['needs_statement_metadata'] = bool(
                statement_preflight.get('needs_statement_metadata'))
            result['statement_rejected'] = bool(statement_preflight.get('rejected'))
            result['missing_fields'] = statement_preflight.get('missing_fields', [])
            result['statement_metadata'] = {
                'bank_name': statement_preflight.get('bank_name'),
                'account_last4': statement_preflight.get('account_last4'),
            }
            return result
        facade = dict(facade)
        facade['statement_preflight'] = statement_preflight
        facade['vendor'] = statement_preflight['bank_name']
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
        remote_image_path = _stage_scan_for_mazda(image_path)
        if remote_image_path:
            if facade.get('statement_preflight'):
                payload_path = _write_statement_preflight_payload(
                    remote_image_path, facade['statement_preflight'])
                if payload_path:
                    facade = dict(facade)
                    facade['statement_preflight'] = dict(
                        facade['statement_preflight'], payload_path=payload_path)
            conversation_id = _create_mazda_conversation()
            if conversation_id:
                dispatched_at = time.time()
                # Persist first: a fast transport failure in the worker must
                # have an exact intake record to mark terminal.
                record_recent_intake(
                    remote_image_path, cfg.get('name', key), kind='scan',
                    facade=facade, conversation_id=conversation_id,
                    dispatched_at=dispatched_at,
                    content_sha256=content_sha256)
                mazda_dispatched = _dispatch_mazda_or_block(
                    remote_image_path, cfg.get('name', key), facade,
                    conversation_id, dispatched_at,
                    _notify_mazda_of_scan_and_record_failure,
                    (remote_image_path, cfg.get('name', key), facade,
                     conversation_id, dispatched_at))
                if not mazda_dispatched:
                    stage_error = HUMAN_ONLY_MODE_STAGE_MESSAGE
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
    result['execution_mode'] = current_execution_mode()
    if conversation_id:
        result['conversation_id'] = conversation_id
    if stage_error:
        result['stage_error'] = stage_error
    result['scanner'] = key
    result['image_path'] = image_path
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
    record_recent_intake(real, doc_label, kind='pdf', facade=facade,
                         conversation_id=conversation_id,
                         dispatched_at=dispatched_at)
    # PDFs already live inside ROL_FINANCES_DIR (enforced above), so no staging
    # is needed — executor_run on this box reads them directly. This also
    # covers reprocess_report, which delegates here.
    mazda_dispatched = _dispatch_mazda_or_block(
        real, f'PDF intake ({doc_label})', facade, conversation_id, dispatched_at,
        _notify_mazda_of_pdf,
        (real, doc_label, conversation_id, dispatched_at, facade))
    result = build_pipeline_result(facade, mazda_dispatched)
    result['trainer_dispatched'] = False
    result['execution_mode'] = current_execution_mode()
    result['file_path'] = real
    result['label'] = doc_label
    result['conversation_id'] = conversation_id
    if not mazda_dispatched:
        result['stage_error'] = HUMAN_ONLY_MODE_STAGE_MESSAGE
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
        'archive_paths': data.get('archive_paths') or [],
        'archive_years': data.get('archive_years') or [],
        # Preserve exact dispatch identity.  Reusable scanner filenames are
        # insufficient routing keys when an older conversation reports late.
        'conversation_id': data.get('conversation_id', ''),
        'dispatched_at': data.get('dispatched_at'),
    }
    escalation = _observe_intake_callback(event)
    if escalation and escalation.summon_required:
        event['trainer_dispatched'] = escalation.summoned
        event['trainer_escalation_reason'] = escalation.reason
        event['status'] = 'processing' if escalation.summoned else 'fail'
        event['status_detail'] = (
            f'Trainer summoned: {escalation.reason}'
            if escalation.summoned
            else f'Trainer launch failed: {escalation.reason}'
        )
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
    from finance.receipt_filename import parse_receipt_filename
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
                match = parse_receipt_filename(fn)
                if match:
                    by_da.setdefault(match.index_key(), []).append(fp)
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


def _resolve_expense_receipt_path(date_str, amount_str, receipt_url):
    """Resolve a receipt only for an expense that owns a non-empty receipt_url.

    Stored receipt_url values are not always byte-for-byte file paths, so after
    trying the URL directly we retain the established date/amount filename
    fallback. The non-empty URL guard is what prevents a receipt from leaking
    onto a different or receipt-less expense: a bare (date, amount) collision
    is common (e.g. two same-day purchases of the same round amount), and only
    an expense that is itself known to own a receipt (non-empty receipt_url)
    is allowed to use that weaker match as a second attempt.
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
    """Return the expense matching a report row using the recategorization rules.

    Direct expense_id lookups must return that exact row, including LINE_ITEM
    children. Date/amount lookups intentionally remain parent-biased so report-row
    recategorization does not ambiguously land on an itemized sibling.
    """
    optional_columns = (
        'id_light', 'document_url', 'scanned_statement_url', 'moms_ledger',
        'notes', 'expense_role', 'parent_expense_id',
    )
    schema = ShowColumnsProbe().read(cur, optional_columns)
    select_sql = schema.select_clause(
        ('id', 'description', 'receipt_url', 'expense_date', 'amount'),
        optional_columns,
        quote='`',
    )
    role_filter = (
        " AND `expense_role` <> 'LINE_ITEM'" if schema.has('expense_role') else ''
    )
    if expense_id not in (None, ''):
        try:
            eid = int(expense_id)
        except (TypeError, ValueError):
            return None
        cur.execute(f"SELECT {select_sql} FROM expenses WHERE id=%s", (eid,))
        rows = cur.fetchall()
        return rows[0] if rows else None
    cur.execute(
        f"SELECT {select_sql} FROM expenses WHERE expense_date=%s AND amount=%s"
        f"{role_filter}", (date_str, amount_str)
    )
    return _select_matching_expense(cur.fetchall(), vendor_key, description)


def _lookup_expense_row(date_str, signed_amount, vendor_key, description='',
                        expense_id=None):
    amt = _norm_amount(signed_amount)
    if amt is None and expense_id in (None, ''):
        return None
    with _rol_get_connection() as cnx:
        with cnx.cursor() as cur:
            return _matching_expense(
                cur, date_str, amt, vendor_key, description, expense_id)


_DOCUMENT_PLACEHOLDERS = {'null', 'none', 'undefined', 'n/a', 'na', '#'}
_VIEWABLE_DOCUMENT_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tif', '.tiff', '.pdf',
    '.xlsx', '.xlsm',
}
SUPPORTING_DOCUMENT_URL_PREFIX = '/supporting-document'
SUPPORTING_DOCUMENT_ANNOTATION_CACHE = os.path.join(
    HERE, '.cache', 'document-annotations')
_supporting_document_annotation_service = None
_supporting_document_annotation_lock = threading.Lock()


def _get_supporting_document_annotation_service(
) -> IExpenseDocumentAnnotationService:
    """Composition root for non-destructive supporting-document highlighting."""
    global _supporting_document_annotation_service
    with _supporting_document_annotation_lock:
        if _supporting_document_annotation_service is None:
            _supporting_document_annotation_service = (
                build_document_annotation_service(
                    SUPPORTING_DOCUMENT_ANNOTATION_CACHE)
            )
    return _supporting_document_annotation_service


def _expense_annotation_evidence(chosen, document_type=''):
    related_document_path = ''
    if document_type == 'moms_ledger':
        related_document_path = (
            _resolve_local_supporting_document(
                chosen.get('document_url'), 'source') or ''
        )
    return ExpenseEvidence(
        expense_id=int(chosen['id']),
        expense_date=str(chosen.get('expense_date') or ''),
        amount=str(chosen.get('amount') or ''),
        description=str(chosen.get('description') or ''),
        vendor_key=_vendor_prefix(chosen.get('id_light')),
        related_document_path=related_document_path,
    )


def _prepare_supporting_document_view(chosen, source_path, document_type=''):
    """Ask the interface-backed service for an annotated, cached copy."""
    return _get_supporting_document_annotation_service().prepare(
        source_path, _expense_annotation_evidence(chosen, document_type))


def _annotation_job_key(chosen, source_path, document_type=''):
    """Identify annotation work, including source revisions and row evidence."""
    try:
        stat = os.stat(source_path)
        revision = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        revision = (None, None)
    evidence = _expense_annotation_evidence(chosen, document_type)
    return (os.path.abspath(source_path), revision, evidence, document_type)


_annotation_proxy = BackgroundResultProxy(
    loader=_prepare_supporting_document_view, name='document-annotation')


def _background_annotation_result(chosen, source_path, document_type=''):
    key = _annotation_job_key(chosen, source_path, document_type)
    return _annotation_proxy.get(
        key, dict(chosen), source_path, document_type, default=None)


def _usable_document_reference(value):
    value = str(value or '').strip()
    if not value or value.lower() in _DOCUMENT_PLACEHOLDERS:
        return False
    parsed = urlparse(value)
    if parsed.scheme and parsed.scheme not in {'http', 'https'}:
        return False
    if parsed.scheme in {'http', 'https'} and not parsed.netloc:
        return False
    return True


def _supporting_document_roots():
    """Directories a stored document reference is allowed to resolve inside."""
    return [
        os.path.abspath(os.path.expanduser('~/rol_finances/readable_documents')),
        os.path.abspath(os.path.expanduser(
            '~/rol_finances/tools/receipt_scanning_tools/incoming_scans')),
    ]


def _resolve_local_supporting_document(reference, document_type):
    if not _usable_document_reference(reference):
        return None
    if document_type == 'receipt':
        resolved = _resolve_receipt_url_path(reference)
        if resolved:
            return resolved
        # A scan attached to an *existing* row (the receipt turned out to
        # duplicate a statement line already in the DB) keeps the intake
        # staging path it was scanned to — it was never filed into the
        # receipts tree, so the receipt index cannot see it. Fall through to
        # the generic allowed-roots resolution rather than dropping the
        # View Receipt button for a receipt that is plainly on disk.
    raw = unquote(str(reference).split('#', 1)[0].strip())
    candidates = [raw] if os.path.isabs(raw) else [
        os.path.join(os.path.expanduser('~/rol_finances'), raw),
        os.path.join(READABLE_DOCS_BASE, raw),
    ]
    allowed_roots = _supporting_document_roots()
    for candidate in candidates:
        candidate = os.path.abspath(candidate)
        if any(os.path.commonpath([candidate, root]) == root for root in allowed_roots):
            if os.path.isfile(candidate):
                return candidate
    return None


def _viewable_supporting_document(reference, resolved_path=None):
    """Accept only formats the protected document viewer can render."""
    candidate = resolved_path
    if not candidate:
        candidate = unquote(urlparse(str(reference or '')).path)
    return os.path.splitext(candidate)[1].lower() in _VIEWABLE_DOCUMENT_EXTENSIONS


def _intake_source_document(intake):
    """The scan image an intake dispatch was built from, or ''.

    Only the immutable staged path recorded with the intake counts. The
    scanner's own output file (`scan_freezer.jpg`) is reused by every later
    scan, so falling back to it would offer a *different* document under the
    label "View Source Document".
    """
    path = str((intake or {}).get('image_path') or '').strip()
    if path and _resolve_local_supporting_document(path, 'source'):
        return path
    return ''


def _report_source_document_reference(report_path):
    """The document the report page holding this row was built from.

    Month reports live next to their downloaded statement file, which
    `_source_document_path` finds by scanning the report directory. Scanner
    reports and Recent Report intake pages are synthetic DB-backed pages: their
    paper scan belongs exclusively to `scanned_statement_url`, never to the
    downloaded-source slot.
    """
    return _supporting_document_pages().source_document_reference(
        report_path, _source_document_path
    )


def server_intake_page_lookup():
    """Composition root for IIntakePageLookup: this module's intake state.

    The lambdas are the point. Handing over the function objects would freeze
    whichever ones existed at wiring time, and `_supporting_document_pages`
    caches its resolver for the process lifetime; going through the module
    global on every call keeps a test that replaces `resolve_recent_report` or
    `get_scanner_intake` honoured, which is what the class did before it moved
    to finance/supporting_documents.py.
    """
    return CallableIntakePageLookup(
        lambda: resolve_recent_report(),
        lambda scanner_key: get_scanner_intake(scanner_key),
        lambda intake: _intake_source_document(intake),
    )


def _supporting_document_pages():
    """Composition point for the page resolver (built once, on first use)."""
    global _SUPPORTING_DOCUMENT_PAGES
    if _SUPPORTING_DOCUMENT_PAGES is None:
        _SUPPORTING_DOCUMENT_PAGES = SupportingDocumentPageResolver(
            server_intake_page_lookup(), REPORT_PAGE_ROUTES
        )
    return _SUPPORTING_DOCUMENT_PAGES


def _report_scanned_statement_reference(report_path):
    """The paper scan a scanner/recent-intake page can offer for its rows."""
    return _supporting_document_pages().scanned_statement_reference(report_path)


def _slot_reference(chosen, kind, report_path=''):
    """The reference to offer for one supporting-document slot."""
    slot = SUPPORTING_DOCUMENT_CATALOG.slot_for_kind(kind)
    if slot is None:
        return ''
    if kind == 'source':
        return _source_document_reference(chosen, report_path)
    return slot_reference(
        chosen, slot, report_path,
        normalize=normalize_supporting_document_reference,
        page_scan=_report_scanned_statement_reference,
    )


def _source_document_reference(chosen, report_path=''):
    """The source-document reference to offer for one expense row.

    The stored `document_url` wins, but only while it still resolves. A scan
    image that disappears after storage (2026-07-29: a concurrent agent's
    `git add -A` swept two in-flight scans off disk) otherwise left the dialog
    with no View Source Document button at all, even on a scanner report that
    knows exactly which image it came from.
    """
    chosen = chosen or {}
    reference = chosen.get('document_url') or ''
    reference = str(reference).strip()
    receipt_reference = str(chosen.get('receipt_url') or '').strip()
    if should_suppress_source_document(
            reference,
            receipt_reference,
            resolve_local_path=lambda ref: _resolve_local_supporting_document(
                ref, 'source'
            ) or _resolve_local_supporting_document(ref, 'receipt')):
        return ''
    scanned_statement_reference = str(
        chosen.get('scanned_statement_url') or '').strip()
    if not scanned_statement_reference:
        scanned_statement_reference = _report_scanned_statement_reference(report_path)

    # Resolve the effective source candidate before comparing it with the
    # scanned statement.  The old order only compared the stored
    # ``document_url``; when that field was empty, the report-directory
    # fallback could resolve to the exact same JPG and expose two buttons for
    # one document.
    source_reference = reference
    if not (_usable_document_reference(source_reference) and (
            urlparse(source_reference).scheme in {'http', 'https'}
            or _resolve_local_supporting_document(source_reference, 'source'))):
        source_reference = _report_source_document_reference(report_path) or ''

    if not source_reference:
        # Scanner and Recent-Report intake pages are synthetic - they have no
        # report.html of their own, so _report_source_document_reference always
        # comes back empty for them (see SupportingDocumentPageResolver). But
        # the row's own (date, amount) may still match an existing month
        # report's transaction row - the exact match _associated_source_paths
        # already uses to print "Associated PDF" on the intake page header.
        # Reuse it here instead of leaving a real downloaded statement
        # undiscoverable just because this row surfaced via a scan.
        match = _find_matching_report_row(
            str(chosen.get('expense_date') or ''),
            str(chosen.get('amount') or ''))
        if match:
            source_reference = _source_document_path(match.report_path) or ''

    if references_same_underlying_document(
            source_reference,
            scanned_statement_reference,
            resolve_local_path=lambda ref: (
                _resolve_local_supporting_document(ref, 'source')
                or _resolve_local_supporting_document(ref, 'scanned_statement')
            )):
        return ''
    if _usable_document_reference(source_reference) and (
            urlparse(source_reference).scheme in {'http', 'https'}
            or _resolve_local_supporting_document(source_reference, 'source')):
        return source_reference
    # A stale stored path is not evidence.  In particular, never return a
    # missing scanner image as a downloaded source document; the scanner page's
    # paper copy is resolved through the separate scanned-statement slot.
    return ''


def _supporting_document_descriptors(chosen, report_path=''):
    return [
        item.model_dump()
        for item in _supporting_document_service().descriptors(
            chosen, report_path
        )
    ]


def _supporting_document_service() -> ISupportingDocumentService:
    """Composition root for the supporting-document application boundary."""
    global _SUPPORTING_DOCUMENT_SERVICE
    if _SUPPORTING_DOCUMENT_SERVICE is None:
        _SUPPORTING_DOCUMENT_SERVICE = SupportingDocumentService(
            SupportingDocumentPorts(
                lookup_expense=lambda *args, **kwargs: _lookup_expense_row(
                    *args, **kwargs
                ),
                normalize_amount=lambda value: _norm_amount(value),
                catalog=SUPPORTING_DOCUMENT_CATALOG,
                normalize_reference=lambda value: normalize_supporting_document_reference(value),
                usable_reference=lambda value: _usable_document_reference(value),
                resolve_local=lambda reference, kind: _resolve_local_supporting_document(
                    reference, kind
                ),
                viewable=lambda reference, path=None: _viewable_supporting_document(
                    reference, path
                ),
                source_reference=lambda chosen, path: _source_document_reference(
                    chosen, path
                ),
                reference_for=lambda chosen, kind, report_path: _slot_reference(
                    chosen, kind, report_path
                ),
                prepare_view=lambda chosen, path, kind: _prepare_supporting_document_view(
                    chosen, path, kind
                ),
                background_prepare_view=lambda chosen, path, kind: _background_annotation_result(
                    chosen, path, kind
                ),
                document_url_prefix=SUPPORTING_DOCUMENT_URL_PREFIX,
            )
        )
    return _SUPPORTING_DOCUMENT_SERVICE


def lookup_supporting_documents(date_str, signed_amount, vendor_key,
                                description='', report_path='', expense_id=None):
    request = SupportingDocumentRequest(
        date=date_str, signed_amount=signed_amount, vendor_key=vendor_key,
        description=description, expense_id=expense_id, report_path=report_path,
    )
    return _supporting_document_service().lookup(
        request, descriptor_builder=_supporting_document_descriptors
    ).model_dump()


def open_supporting_document(date_str, signed_amount, vendor_key, document_type,
                             description='', expense_id=None, report_path='',
                             wait_for_highlight=True):
    request = SupportingDocumentRequest(
        date=date_str, signed_amount=signed_amount, vendor_key=vendor_key,
        document_type=document_type, description=description,
        expense_id=expense_id, report_path=report_path,
        wait_for_highlight=wait_for_highlight,
    )
    return _supporting_document_service().open(request).model_dump()


def _supporting_document_path_for_expense(
        expense_id, document_type, report_path=''):
    return _supporting_document_service().path_for_expense(
        int(expense_id), document_type, report_path
    )


def _supporting_document_view_for_expense(
        expense_id, document_type, report_path=''):
    return _supporting_document_service().view_for_expense(
        int(expense_id), document_type, report_path
    )



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
        def preferred_source(candidate_directory):
            preferred = []
            if not os.path.isdir(candidate_directory):
                return ''
            for name in os.listdir(candidate_directory):
                fp = os.path.join(candidate_directory, name)
                ext = os.path.splitext(name)[1].lower()
                if (os.path.isfile(fp)
                        and ext in _VIEWABLE_DOCUMENT_EXTENSIONS):
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
        split = _split_report_url(raw)
        if split:
            _base, rel = split
            report_directory = os.path.dirname(rel)
            for month_key in ROL_FINANCES_REPORTS_MONTHS:
                candidate_directory = os.path.join(
                    _rol_reports_base_dir(month_key), report_directory)
                if os.path.abspath(candidate_directory) == os.path.abspath(directory):
                    continue
                source = preferred_source(candidate_directory)
                if source:
                    return source
        if os.path.isfile(report_file):
            return report_file
    return receipt_path or ''


def _report_source_document_view(report_path):
    """Return a browser-viewable copy of the document behind a report."""
    source_path = _source_document_path(report_path)
    if not source_path or not os.path.isfile(source_path):
        return ''
    ext = os.path.splitext(source_path)[1].lower()
    if ext not in _VIEWABLE_DOCUMENT_EXTENSIONS:
        return ''
    if ext in {'.xlsx', '.xlsm'}:
        cache_key = hashlib.sha256(source_path.encode('utf-8')).hexdigest()[:16]
        browser_path = os.path.join(
            SUPPORTING_DOCUMENT_ANNOTATION_CACHE,
            f'{cache_key}-{os.path.basename(source_path)}.html',
        )
        return render_excel_for_browser(source_path, browser_path)
    return source_path


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

    document_reference = (
        (chosen.get('document_url') or '').strip() if chosen else '')
    resolved_document = (
        _resolve_local_supporting_document(document_reference, 'source')
        if document_reference else None)
    if (not resolved_document and document_reference
            and urlparse(document_reference).scheme in {'http', 'https'}
            and _viewable_supporting_document(document_reference)):
        resolved_document = document_reference
    metadata = {
        'expense_id': chosen['id'] if chosen else '',
        'receipt_url': '',
        'receipt_path': '',
        'notes': (chosen.get('notes') or '') if chosen else '',
        'machine_origin': _document_machine_origin(),
        # Ask Mazda must use the expense's database-backed source association.
        # The report directory is only a legacy fallback for old rows.
        'source_document_path': (
            resolved_document or _source_document_path(report_path)),
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
        source_document_path=(
            resolved_document or _source_document_path(report_path, fp)),
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


def scanned_statements_present(rows):
    """Same shape/contract as receipts_present, for the SCANNED_STATEMENT slot.

    Drives a row marker distinct from the receipt corner: a row backed by a
    scan of a printed statement EG has physically reviewed, independent of
    whether it also has a receipt or the bank's own downloaded source."""
    expense_map = {}
    try:
        with _rol_get_connection() as cnx:
            with cnx.cursor() as cur:
                cur.execute(
                    "SELECT id, expense_date, amount, id_light, description, "
                    "scanned_statement_url FROM expenses"
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
            ref = (chosen.get('scanned_statement_url') or '').strip() if chosen else ''
            present = bool(
                ref and _resolve_local_supporting_document(ref, 'scanned_statement'))
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
# Membership requires an ACTUAL receipt file to resolve (via _resolve_expense_receipt_path —
# the same test that drives the red "has-receipt" corner marker), NOT merely a
# non-empty expenses.receipt_url: ~48 rows carry a receipt_url whose file is missing
# on disk (the known data gap) and must be excluded so every row shown has a receipt
# (and a marker). This also catches rows whose receipt_url is blank but whose receipt
# file is still found by (date, amount).
def _reporting_category_for_id(category_id, parent_of=None):
    """Walk a leaf category_id up its parent chain to a reporting-bucket name.

    Delegates to ICategoryTaxonomy, which sources the same walk from the DB's
    is_report_category / report_category_id columns. `parent_of` is retained
    for call-site compatibility and ignored: the taxonomy carries the parentage
    itself, so callers no longer need to pre-load the tree.
    """
    return _get_category_taxonomy().label_for(category_id)


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
                "       e.category_id, e.receipt_url, e.document_url, "
                "       e.moms_ledger, e.expense_role "
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
            'cat_class': _css_class_for_report_name(rep),
            'receipt_url': r.get('receipt_url'),
            'document_url': r.get('document_url'),
            'moms_ledger': r.get('moms_ledger'),
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
    Set Category dialog. Sourced from ICategoryTaxonomy — i.e. from the
    `categories` table — so a category added by a migration shows up without a
    code change. Previously this iterated REPORTING_CATEGORY_CLASS, which meant
    new buckets (e.g. Money Movement, 402) were invisible no matter how many
    times the service was restarted.

    /api/recategorize-expense resolves picks through the same taxonomy, so the
    picker still cannot offer a category the writer would reject.
    """
    cats = []
    for node in _get_category_taxonomy().selectable_report_categories():
        cats.append({
            'name': node.label,
            'cls': node.css_class or 'cat-uncategorized',
            'bg': node.report_bg or '#BFBFBF',
            'fg': node.report_fg or '#000000',
            'excluded': bool(node.excluded_from_nonprofit_totals),
        })
    # "Uncategorized" is a sentinel, not a row: picking it clears category_id.
    # Only append it when the taxonomy did not already supply it — LEGACY_TAXONOMY
    # (the offline fallback) lists it as selectable, and appending unconditionally
    # showed it twice in the dialog whenever the DB was unreachable.
    if not any(c['name'] == 'Uncategorized' for c in cats):
        cats.append({'name': 'Uncategorized', 'cls': 'cat-uncategorized',
                     'bg': '#BFBFBF', 'fg': '#000000', 'excluded': False})
    return cats


def _report_category_node_by_name(name, selectable_only=True):
    """Resolve a report/dialog label back to its category node.

    selectable_only=False also finds buckets the dialog does not offer — notably
    'Uncategorized' (node 1), which reports use as a label but which must never
    appear as a choice.
    """
    wanted = str(name or '').strip()
    taxonomy = _get_category_taxonomy()
    nodes = (taxonomy.selectable_report_categories() if selectable_only
             else [n for n in taxonomy.all_nodes() if n.is_report_category])
    for node in nodes:
        if node.label == wanted:
            return node
    return None


def _css_class_for_report_name(name):
    """The cat-* class for a reporting-bucket label, from the categories table.

    Reports bake this class into each <tr> on disk, so it must stay stable for
    existing buckets and must exist for new ones (a bucket with no class would
    render unstyled).
    """
    node = _report_category_node_by_name(name, selectable_only=False)
    if node is not None and node.css_class:
        return node.css_class
    return REPORTING_CATEGORY_CLASS.get(name, 'cat-uncategorized')


def _resolve_reporting_category(name):
    """(target_category_id, css_class) for a dialog pick, or (None, None) if the
    name is not a selectable report category. 'Uncategorized' clears the id."""
    if str(name or '').strip() == 'Uncategorized':
        return None, 'cat-uncategorized'
    node = _report_category_node_by_name(name)
    if node is None:
        # Fall back to the legacy maps so a stale client (or a report.html
        # injected before this change) keeps working.
        if name in REPORTING_CATEGORY_DB_MAP:
            return (REPORTING_CATEGORY_DB_MAP[name],
                    REPORTING_CATEGORY_CLASS.get(name, 'cat-uncategorized'))
        return None, None
    return node.id, (node.css_class or 'cat-uncategorized')


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
                "       category_id, receipt_url, document_url, moms_ledger, "
                "       created_at, notes "
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
            'receipt_url': r.get('receipt_url') or '',
            'document_url': r.get('document_url') or '',
            'moms_ledger': r.get('moms_ledger') or '',
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


def _ensure_sys_path(*dirs):
    """Insert each directory into sys.path once, if not already present.

    rol_finances scripts import as `tools.python_tasks....` (absolute,
    rooted at ROL_FINANCES_DIR) rather than relative to whatever directory
    actually holds the file being imported, so a caller reaching into one of
    its submodules needs BOTH dirs on sys.path: ROL_FINANCES_DIR for the
    `tools` package root, and the submodule's own directory to resolve the
    top-level `import_module('some_file')` call itself. Getting only one of
    the two is exactly what made _picker_module 500 on every report.html —
    VERIFICATION_LIB alone resolved `restructure_verified_transactions` but
    left its own `from tools.python_tasks...` import with nowhere to find
    `tools`. sys.path mutation is process-global and was previously
    duplicated ad hoc per call site (see _default_statement_account_
    directory); this is the one place that needs to get the set right.
    """
    for d in dirs:
        if d not in sys.path:
            sys.path.insert(0, d)


def _picker_module():
    """Import restructure_verified_transactions from VERIFICATION_LIB, which
    itself does `from tools.python_tasks.verification_lib... import ...` —
    hence needing ROL_FINANCES_DIR on sys.path too. See _ensure_sys_path."""
    import importlib
    _ensure_sys_path(ROL_FINANCES_DIR, VERIFICATION_LIB)
    return importlib.import_module('restructure_verified_transactions')


def _receipt_only_picker_assets():
    """The category-picker dialog markup/CSS reused verbatim from the report.html
    injector, so the Receipt Only tab behaves identically to Verified Transactions.

    CATEGORY_PICKER_HTML is a TEMPLATE — its category list and row colours are
    placeholders. Returning it raw shipped `var CATS = []` to the browser, which
    left the dialog with no categories to render. Always render it through
    render_picker_block() with this process's category list.
    """
    assets = render_assets(_picker_module(), _rol_finance_categories())
    return assets.css, assets.html, assets.clickable_row_css


def _report_html_with_current_picker(report_file):
    """Refresh only the picker assets in memory; never rewrite row categories."""
    rv = _picker_module()
    with open(report_file, encoding='utf-8', errors='ignore') as handle:
        # Pass the categories in: the injector would otherwise HTTP-fetch them
        # from this very server, from inside one of its own request handlers.
        return rv.add_category_picker(handle.read(), _rol_finance_categories())


def _receipt_only_cat_css():
    return category_row_css(_rol_finance_categories())


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
                _esc(str(r['id']), quote=True),
                _esc(str(r['vendor_key']), quote=True),
                _esc(str(r['description']), quote=True),
                _esc(str(r['amount']), quote=True),
                _esc(str(r['date']), quote=True),
                _esc(str(r['description'])), _esc(str(r['amount'])), _esc(str(r['date'])),
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
        + '  </style></head><body>\n'
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


# Letta API base URL — override with LETTA_BASE_URL env var; defined in hosts.py
# beside the SSH destinations, and re-exported here under its historical name.
from hosts import LETTA_BASE_URL  # noqa: E402

# Model handles selectable per-agent from Input Options. Keep this curated list
# aligned with the ChatGPT OAuth catalog advertised by the live Letta server.
AGENT_MODEL_OPTIONS = [
    'chatgpt-plus-pro/gpt-5.6-sol',
    'chatgpt-plus-pro/gpt-5.6-luna',
    'chatgpt-plus-pro/gpt-5.6-terra',
    'claude-pro-max/claude-haiku-4-5-20251001',
    'claude-pro-max/claude-sonnet-5',
    'claude-pro-max/claude-opus-5',
]

_LETTA_GATEWAY: ILettaGateway = UrllibLettaGateway(LETTA_BASE_URL)
_AGENT_MODEL_OPTIONS_SERVICE = AgentModelOptionsService(
    _LETTA_GATEWAY,
    AGENT_MODEL_OPTIONS,
)

# The edge-tts voice catalogue moved to agents/registry.py as typed
# `VoiceOption`s. An id that is not a real edge-tts voice does not fail when it
# is picked — it fails later, at speech time, on a background thread.
from agents.registry import AGENT_VOICE_OPTIONS  # noqa: E402

AGENT_VOICE_METADATA_KEY = 'dashboard_voice'

def agent_model_options(current_handle):
    """Compatibility shim for callers that still consume a plain list."""
    return list(select_model_options(current_handle, tuple(AGENT_MODEL_OPTIONS)))

def agent_model_payload(letta_id, service=None, pending_provider=''):
    """Compatibility shim while model reads move behind ILettaGateway.

    `pending_provider` is the dashboard's *not-yet-saved* Token-dropdown
    value -- when given, the Model dropdown is filtered to THAT provider's
    family instead of the agent's live one, so picking a token pre-narrows
    the model list before the account PATCH round-trip finishes."""
    model_service = service or _AGENT_MODEL_OPTIONS_SERVICE
    family = OAUTH_PROVIDER_ACCOUNTS.get(pending_provider, {}).get('family', '')
    prefix = FAMILY_MODEL_PREFIX.get(family, '') if family else ''
    return model_service.get_options(letta_id, family_prefix=prefix).to_http()

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

# The agent roster moved to agents/registry.py as typed `LettaAgentSpec`s, and
# `LETTA_AGENTS` is a derived view of them. Add a new Letta agent there.
#
# The move found a live defect. The literal listed Shelia TWICE, identically.
# build_agent_list() iterates the roster as a list, so /api/agents served 21
# tiles for 20 agents and Agent Management rendered two identical Shelia cards
# — verified against the live dashboard before the fix. AGENT_CARDS carried the
# same duplicate as a repeated dict key, where Python silently kept the last,
# which is why the card text looked right and hid the roster bug. The registry
# now refuses a roster with a repeated name or Letta id.
#
# CHATGPT_PLUS_PRO / CLAUDE_PRO_MAX come back because this module's provider
# probes and startup banner name them; the two tool lists travelled entirely.
from agents.registry import (  # noqa: E402
    CHATGPT_PLUS_PRO,
    CLAUDE_PRO_MAX,
    LETTA_AGENTS,
)

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


# The Agent Card copy moved to agents/registry.py as typed `AgentCard`s.
# A card missing a key used to render as a blank panel rather than an error.
from agents.registry import AGENT_CARDS  # noqa: E402


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

def tts_cache_path(text, voice):
    """Compatibility export for the extracted voice synthesis service."""
    return synthesis_cache_path(TTS_CACHE_DIR, text, voice)


def synthesize_speech(text, voice=None, runner=subprocess.run):
    """Compatibility adapter for the extracted server-rewrite voice service."""
    return EdgeTtsSynthesizer(
        binary_path=EDGE_TTS_BIN,
        default_voice=EDGE_TTS_VOICE,
        cache_dir=TTS_CACHE_DIR,
        timeout_sec=EDGE_TTS_TIMEOUT_SEC,
        max_text_len=TTS_MAX_TEXT_LEN,
        runner=runner,
    ).synthesize(text, voice)

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
from hosts import LETTA_DOCKER_HOST  # noqa: E402
LETTA_REMOTE_LOG_PULL_SCRIPT = '~/server_tools/pull_letta_server_logs.sh'
LETTA_REMOTE_LOG_CACHE = '/tmp/letta_server_remote.log'
LETTA_REMOTE_LOG_PULL_INTERVAL = 30   # seconds between SSH pulls
LETTA_REMOTE_LOG_LOOKBACK = 300       # seconds of history to seed the cache with on first pull
LETTA_REMOTE_LOG_CACHE_MAX_LINES = 4000  # trim threshold so /tmp doesn't grow unbounded

# ── Server Management registry ────────────────────────────────────────────────
# The fifteen tiles moved to servers/registry.py as typed `ServerSpec`s, and
# `SERVERS` is now a derived view of them — same list, same dicts, same per-entry
# key order, so `cfg.get('health_url')` and friends answer exactly as before.
#
# What the specs check that 159 lines of dict literal never could: that `check`
# names a probe HEALTH_CHECKS actually defines (a typo used to render as a red
# tile reading "unknown check: ..."), that `depends_on` points at a real server,
# that a `log_file` is absolute, that no two tiles share a key or a name, and —
# the shape that matters most — that a server declares exactly ONE active probe.
# server_health() resolves `check` before `health_url`, so an entry carrying both
# advertised a health URL on /api/servers that was never pinged.
#
# A factory rather than a literal because four entries interpolate values this
# composition root owns: PORT, the two startup logs, and the Letta log cache.
from servers.registry import build_server_specs as _build_server_specs  # noqa: E402
from servers.registry import as_configs as _server_configs  # noqa: E402

SERVER_SPECS = _build_server_specs(
    port=PORT,
    letta_base_url=LETTA_BASE_URL,
    letta_docker_host=LETTA_DOCKER_HOST,
    letta_remote_log_cache=LETTA_REMOTE_LOG_CACHE,
    executor_startup_log=EXECUTOR_STARTUP_LOG,
    logger_api_startup_log=LOGGER_API_STARTUP_LOG,
)
SERVERS = _server_configs(SERVER_SPECS)

# SSH_CONNECTIONS, SSH_CONNECT_TIMEOUT, SSH_HEALTH_POLL_INTERVAL,
# SSH_HEALTH_FAIL_THRESHOLD and SSH_LOG_TAIL moved to monitoring/ssh_checks.py
# with the probes that are the only things that read them. The roster and the
# poll interval come back because the startup banner counts one and prints the
# other; the rest is read from the owning module, including by its tests.
from monitoring.ssh_checks import (  # noqa: E402
    SSH_CONNECTIONS,
    SSH_HEALTH_POLL_INTERVAL,
    _ssh_poll_loop,
)

# ── Server lifecycle clocks and log-file reading ─────────────────────────────
# The "starting" grace window and the "down for 54m / stale" clock moved to
# monitoring/server_lifecycle.py -- they are one state machine seen from two
# sides, and both need only a server key, never SERVERS or a probe. Tailing,
# age formatting, the log-mtime-as-probe fallback and the detail panel's row
# builder moved to monitoring/log_files.py.
#
# Only the names this module or a `srv.` route still calls are pulled back in;
# everything else is read from its owning module, including by its tests
# (tests/test_server_lifecycle.py, tests/test_log_files.py). `_starting_servers`
# and `_starting_lock` are the exception -- imported by identity, because
# tests/test_server.py's `_clear_starting()` resets the one real registry
# through `server`, and a rebind would silently give it a second empty one.
from monitoring import log_files, server_lifecycle  # noqa: E402
from monitoring.server_lifecycle import (  # noqa: E402
    _starting_servers,
    _starting_lock,
    mark_server_starting,
    is_server_starting,
)
from monitoring.log_files import trim_log_cache as _trim_log_cache  # noqa: E402


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


def deploy_dashboard():
    """Keyboard-free deploy: fast-forward the checked-out branch and self-restart.

    This is the resilience path — the whole point is that the system is never
    "dead in the water" waiting for a human at a keyboard. The dashboard runs in
    the real `systemd --user` session, so it can `git pull` the live checkout and
    restart itself, which a sandboxed executor (or Frita over Tailscale) cannot do
    directly. It only ever fast-forwards the branch that is ALREADY checked out —
    nothing to specify, no way to land on the wrong branch, no auth to lose.

    Fails loud (standing rule): a non-fast-forwardable pull or any git error is
    reported back and the restart is SKIPPED, so a broken or dirty tree is never
    activated. Only a clean fast-forward proceeds to restart_dashboard_server()."""
    def _git(*args):
        return subprocess.run(
            ['git', '-C', REPO_ROOT, *args],
            capture_output=True, text=True, timeout=120)
    try:
        branch = _git('rev-parse', '--abbrev-ref', 'HEAD').stdout.strip()
        before = _git('rev-parse', '--short', 'HEAD').stdout.strip()
        fetch = _git('fetch', 'origin', branch)
        if fetch.returncode != 0:
            return {'ok': False, 'text': f'git fetch origin {branch} failed — '
                                         f'tree NOT restarted:\n{fetch.stderr.strip()}'}
        pull = _git('pull', '--ff-only', 'origin', branch)
        if pull.returncode != 0:
            return {'ok': False, 'text': f'git pull --ff-only origin {branch} failed — '
                                         f'tree NOT restarted (fix the working tree first):\n'
                                         f'{pull.stderr.strip() or pull.stdout.strip()}'}
        after = _git('rev-parse', '--short', 'HEAD').stdout.strip()
    except FileNotFoundError:
        return {'ok': False, 'text': 'git not found — cannot deploy on this host.'}
    except subprocess.TimeoutExpired:
        return {'ok': False, 'text': 'git operation timed out — tree NOT restarted.'}
    except Exception as e:
        return {'ok': False, 'text': f'deploy error — tree NOT restarted: {e}'}

    restart = restart_dashboard_server()
    moved = 'already up to date' if before == after else f'{before} -> {after}'
    return {'ok': restart.get('ok', False),
            'text': f'Deployed {branch} ({moved}). ' + restart.get('text', '')}


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


# ── The Win10 box: reachability, containers, dockerd, and reviving it ────────
# win10_node_health, restart_win10_node, win10_container_states,
# container_status_for, ensure_win10_docker and win10_docker_ok moved to
# monitoring/win10_node.py, taking all thirteen of their WIN10_* constants and
# _win10_* caches and locks with them. The Win10 WSL node hosts Letta, the
# Frita SDK executor and the Logger API, so its reachability is the root cause
# the other three hang off (blocked_by) instead of showing three separate reds.
#
# The names below are imported back because they are all still called -- from
# HEALTH_CHECKS, from server_status_kind, and from http_app/get_routes.py via
# `srv`. restart_win10_node is the one exception: it writes to RESTART_LOG,
# which stays here because every other restart handler writes to it too, so the
# log is injected per call instead (see _win10_node_deps below).
from monitoring import win10_node as _win10_node  # noqa: E402
from monitoring.win10_node import (  # noqa: E402
    ensure_win10_docker,
    win10_docker_ok,
    win10_node_health,
)


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


def _win10_node_deps():
    """Resolve this module's half of the Win10 cluster, at call time.

    Only the restart log, which every restart handler here appends to. Looked
    up per call so replacing either name on `server` is honoured.
    """
    return _win10_node.Collaborators(
        log_restart=_log_restart,
        restart_log_path=RESTART_LOG,
    )


def restart_win10_node():
    """Revive the Win10 WSL node from the still-online Windows side."""
    return _win10_node.restart_win10_node(deps=_win10_node_deps())


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
    # The background failover poller has already asked the standby account
    # whether a swap would even help; show that verdict instead of promising a
    # Restart that can't work (both accounts capped, standby needing re-auth…).
    note = chatgpt_failover.last_failover_note()
    remedy = (f'auto-failover: {note}' if note
              else 'Restart swaps to the standby account token')
    return {'ok': False, 'hard': True,  # a restart click can't revive a dead token by itself
            'text': f'{CHATGPT_PLUS_PRO} token UNUSABLE — {probe["text"]} — Mazda + fleet '
                    f'cannot run a single LLM step (dispatches fail HTTP 401); '
                    f'{remedy}'}


def restart_chatgpt_provider():
    """'Restart' for the provider tile = swap the chatgpt-plus-pro row to the
    standby account token on the Letta box (same script auto-failover uses).
    Only helps when the standby token is alive — the tile stays red otherwise."""
    _log_restart('chatgpt-provider: swap provider token to standby')
    ok, note = chatgpt_failover.run_failover_swap()
    if not ok:
        return {'ok': False, 'text': f'token swap failed — {note}'}
    try:
        _poll_chatgpt_provider_once()  # refresh the fleet's send-errors now, not in 90s
    except Exception:
        pass
    return {'ok': True, 'text': f'provider token swapped to standby — {note}'}


def set_chatgpt_provider_account(source):
    """Install a SPECIFIC account's token as the live chatgpt-plus-pro
    provider row (unlike restart_chatgpt_provider, which only ping-pongs to
    whatever the standby happens to hold). Returns ChatGptProviderAccountStatus."""
    strategy = PROVIDER_ACCOUNT_SOURCES.get(source)
    if strategy is None:
        status = get_chatgpt_provider_account_status()
        return status.model_copy(update={'ran': True, 'ok': False,
                                          'text': f'unknown account source: {source!r}', 'source': source})
    _log_restart(f'chatgpt-provider: set to {strategy.label}')
    ok, note = strategy.install()
    if ok:
        try:
            _poll_chatgpt_provider_once()  # refresh the fleet's send-errors now, not in 90s
        except Exception:
            pass
    status = get_chatgpt_provider_account_status()
    return status.model_copy(update={'ran': True, 'ok': ok, 'text': note, 'source': source})


def get_chatgpt_provider_account_status():
    """Current live-row account + the accounts it can be swapped to."""
    try:
        creds, _ptype = _fetch_provider_oauth_creds(CHATGPT_PLUS_PRO)
    except Exception:
        creds = None
    return chatgpt_provider_account_status(creds)


def start_browser_server():
    """Start browser_server.py on the Win10 box (100.80.49.10) over SSH if not already
    running. Requires Flask, undetected-chromedriver, and Chrome logged into chatgpt.com
    there — this dashboard host has no display for Chrome itself."""
    _log_restart('browser-server: starting browser_server.py on Win10 box (:5001)')
    try:
        urllib.request.urlopen('http://100.80.49.10:5001/health', timeout=3)
        return {'ok': True, 'text': 'browser_server already running on 100.80.49.10:5001'}
    except Exception:
        pass

    cmd = (
        "cd ~/letta-code/browser_tools && "
        "kill $(cat /tmp/browser_server.pid 2>/dev/null) 2>/dev/null; sleep 1; "
        "source .venv/bin/activate 2>/dev/null && "
        "BROWSER_SERVER_HOST=0.0.0.0 nohup python3 browser_server.py "
        ">/tmp/browser_server.log 2>&1 & echo $! > /tmp/browser_server.pid"
    )
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=10', 'adamsl@100.80.49.10', cmd],
            capture_output=True, text=True, timeout=20,
        )
    except Exception as e:
        return {'ok': False, 'text': f'SSH to Win10 box failed: {e}'}

    time.sleep(4)
    try:
        urllib.request.urlopen('http://100.80.49.10:5001/health', timeout=5)
        return {'ok': True, 'text': 'browser_server started on 100.80.49.10:5001 '
                                     '(Chrome launches lazily on first relay message)'}
    except Exception as e:
        return {'ok': False, 'text': f'browser_server did not come up after start attempt: {e} '
                                      f'(stderr: {result.stderr[-300:] if result.stderr else ""})'}


# The Restart buttons. `RestartCommand` (servers/restart.py) pairs a key with
# the callable that services it, so a key and its handler stop being two facts;
# `RESTART_HANDLERS` and `RESTARTABLE_KEYS` are derived views of the registry.
#
# The handlers stay here: they are behaviour bound to this module's own state,
# and moving them is round 23's job. What the registry adds today is the check
# nothing was making — that every Server Management tile HAS a command. A tile
# with none renders without a Restart button, which reads as a design choice
# rather than a missing registration, and breaks this dashboard's standing
# promise that the user never needs the command line.
from servers.restart import RestartCommand, RestartRegistry  # noqa: E402

RESTART_REGISTRY = RestartRegistry([
    RestartCommand(key='win10-node', handler=restart_win10_node,
                   note='revive WSL node via the Windows host'),
    RestartCommand(key='executor', handler=start_executor_server,
                   note='script frees the port + relaunches'),
    RestartCommand(key='mcp-proxy', handler=start_executor_server,
                   note='mcp-proxy :8789 is part of that script'),
    RestartCommand(key='dashboard', handler=restart_dashboard_server),
    RestartCommand(key='logger-api', handler=start_logger_api,
                   note='idempotent self-healing compose up'),
    RestartCommand(key='frita-executor', handler=restart_frita_executor,
                   note='docker recovery + idempotent deploy'),
    RestartCommand(key='browser-server', handler=start_browser_server,
                   note='browser automation for relay_message_to_chatgpt'),
    RestartCommand(
        key='lettabot',
        handler=lambda: _restart_user_unit('lettabot', 'lettabot.service')),
    RestartCommand(
        key='thought-bridge',
        handler=lambda: _restart_user_unit('thought-bridge',
                                           'thought-bridge.service')),
    RestartCommand(
        key='mazda-tools-mcp',
        handler=lambda: _restart_user_unit('mazda-tools-mcp',
                                           'mazda-tools-mcp.service')),
    RestartCommand(
        key='letta',
        handler=lambda: _restart_remote(
            'letta',
            'docker restart letta-server 2>&1 | tail -3 || '
            '(cd ~/letta-src && docker compose restart 2>&1 | tail -3)')),
    RestartCommand(
        key='dashboard-proxy',
        handler=lambda: _restart_remote(
            'dashboard-proxy',
            'systemctl --user restart dashboard-proxy.service 2>&1 | tail -3 || '
            'echo "no dashboard-proxy.service — start mechanism unknown, '
            'please configure"')),
    RestartCommand(key='document-vision', handler=restart_document_vision),
    RestartCommand(key='mazda-categorizer-llm',
                   handler=lambda: restart_mazda_categorizer_llm()),
    # Its tile was retired on 2026-08-19; the handler is kept deliberately, so
    # the registry covers the tiles rather than equalling them.
    RestartCommand(key='chatgpt-provider', handler=restart_chatgpt_provider,
                   note='swap provider row to standby token'),
])
RESTART_REGISTRY.check_covers(s['key'] for s in SERVERS)

RESTART_HANDLERS = RESTART_REGISTRY.as_handler_map()
RESTARTABLE_KEYS = RESTART_REGISTRY.keys


def restart_server(key):
    """Dispatch a restart for any Server Management entry. Returns {ok, text}."""
    return RESTART_REGISTRY.dispatch(key)


# ── Remote Letta server log pulling (SSH) ─────────────────────────────────────
# The Letta server itself is Docker-on-Win10 — there's nothing to tail locally,
# so a background thread (started in `__main__`) periodically SSHes in and
# appends new lines to LETTA_REMOTE_LOG_CACHE, which the "letta" SERVERS entry
# points its `log_file` at. Everything downstream (server_log_rows, tail_lines,
# the /api/server-logs route) treats it exactly like any other tailed log.

_letta_log_pull_lock = threading.Lock()
_letta_log_pull_since = None  # ISO8601 UTC ('...Z'); seeded with a lookback window on first pull


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

def letta_messages(
    agent_id: str,
    limit: int = 200,
    gateway: ILettaGateway | None = None,
) -> list[dict[str, object]]:
    """Fetch all message types for an agent from the Letta API.

    Backs the Messages/Thoughts/Tool Calls tabs. Uses a longer-than-default
    timeout because the Letta box is currently only reachable over a Tailscale
    DERP relay (no direct connection to this box), which regularly takes
    10-20s round trip — the 6s default was cutting the request off before the
    reply arrived, so these tabs showed empty ("no messages recorded yet")
    even though the agent had messages. 25s keeps this under the browser's
    30s fetch abort while giving the slow relay path room to finish.
    """
    message_gateway = gateway or _LETTA_GATEWAY
    return [
        message.to_legacy()
        for message in message_gateway.get_agent_messages(
            agent_id,
            limit=limit,
            timeout=25,
        )
    ]

# ── The three agent tabs: Thoughts, Messages, Tool Calls ─────────────────────
# letta_thoughts, cached_thoughts, letta_convo and letta_toolcalls moved to
# agents/message_views.py, together with the thoughts proxy, the age window and
# the timestamp parsing they share. They are three readings of one message
# stream and are expected to agree about which messages exist.
#
# What stays here -- letta_messages (the gateway shim), letta_get (the raw
# Letta GET) and _msg_age_seconds (which the agent-activity poller also uses)
# -- is handed over per call in a Collaborators bundle rather than imported
# back, so monkeypatch.setattr(server, 'letta_messages', ...) reaches the code
# that actually runs.
#
# letta_thoughts, _msg_date, _letta_conversation_messages, _thoughts_proxy and
# MESSAGES_MAX_AGE_SECONDS are deliberately NOT re-exported: nothing here calls
# them any more, and a re-export is a second binding a test can patch while the
# real one keeps running (tests/test_message_views.py asserts they are absent).
from agents import message_views as _message_views  # noqa: E402


def _message_view_deps():
    """Resolve this module's half of the agent-tabs cluster, at call time.

    Every entry is looked up when the call happens, not when this module is
    imported, so replacing any of them on `server` is honoured.
    """
    return _message_views.Collaborators(
        letta_messages=letta_messages,
        letta_get=letta_get,
        msg_age_seconds=_msg_age_seconds,
    )


def cached_thoughts(agent_id, conversation_id=''):
    """Non-blocking Thoughts-tab rows for one agent."""
    return _message_views.cached_thoughts(
        agent_id, conversation_id, deps=_message_view_deps())


def letta_convo(agent_id):
    """Messages-tab rows for one agent."""
    return _message_views.letta_convo(agent_id, deps=_message_view_deps())


def letta_toolcalls(agent_id):
    """Tool Calls-tab rows for one agent."""
    return _message_views.letta_toolcalls(agent_id, deps=_message_view_deps())


def _within_max_age(m, now):
    """True if a row is recent enough for the Messages tab. Also applied to the
    local Claude Code log, which has no Letta agent behind it."""
    return _message_views.within_max_age(m, now, deps=_message_view_deps())


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

# The Claude-SDK executor probes moved to health/frita.py: the ghost-stack
# detection on :8797, the separate work-route probe, and the credential
# re-push that lets a health *check* fix the one condition it can. None of it
# reads this module's state. Re-exported under the historical names -- the
# agent health sweep and the Server Management tab both name them via `srv`.
from health.frita import (  # noqa: E402
    FRITA_CREDS_SYNC_SCRIPT, FRITA_EXEC_GHOST_URL, FRITA_EXEC_GOOD_URL,
    FRITA_EXEC_WORK_URL, _probe_claude_sdk_endpoint, _probe_sdk_status,
    claude_sdk_account_payload, claude_sdk_token_status,
    _resync_frita_creds, frita_executor_health,
)




# ── Document Vision health (classify_scan.py's 3-tier fallback) ─────────────
# Both this tile and the Categorizer tile moved to health/document_vision.py.
# They read the same shared event log but own different chains and different
# remedies, which is exactly why they live together and are documented apart.
# `classify_failure` went to health/failures.py -- five checks call it, so it
# belongs beside none of them. Re-exported under the historical names.
from health.document_vision import (  # noqa: E402
    DOCUMENT_VISION_HALT_MESSAGE, MAZDA_PROVIDER_HEALTH_PATH,
    MAZDA_PROVIDER_HEALTH_WINDOW_SECONDS, ROL_FINANCES_ENV_PATH,
    VISION_PROVIDER_PREFIX, _jwt_claims, _read_env_var,
    document_vision_health, mazda_categorizer_fallback_health,
    provider_belongs_to_vision, restart_mazda_categorizer_llm,
    split_provider_health_state, unresolved_fallbacks,
    vision_provider_fallbacks,
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
# Moved to health/poller.py -- HealthPoller (the cache + lock), HealthCacheEntry
# (the debounce record, Pydantic so a malformed entry fails loud instead of a
# silent KeyError deep in a background thread), and the module constants.
# SERVERS and server_health are this module's, so they're injected rather than
# imported back, keeping the poller's own tests independent of live config.
from health.poller import (
    HealthPoller,
    HEALTH_POLL_INTERVAL,
    HEALTH_CHECK_TIMEOUT,
    HEALTH_FAIL_THRESHOLD,
)

_health_poller = HealthPoller()


def _poll_all_health_once():
    _health_poller.poll_all_once(SERVERS, server_health)


def _health_poll_loop():
    """Composition root for the background health poller: this module's
    SERVERS and server_health.

    Both are passed as late-bound callables so a test that replaces
    `server.SERVERS` or `server.server_health` is still honoured by a poller
    thread that started before the replacement -- see
    tests/test_health_poller.py::TestThePatchTargetTrap for why this matters.
    """
    _health_poller.poll_loop(lambda: SERVERS,
                              lambda cfg, timeout=None: server_health(cfg, timeout=timeout))


def cached_server_health(cfg):
    return _health_poller.cached(cfg, server_health)


# The SSH/Tailscale connection checks moved to monitoring/ssh_checks.py -- the
# roster, both probes, the debounced health cache and the per-connection log
# tail. Nothing there needs a collaborator from this file, so nothing is
# injected; the names below are imported back only because the routes and the
# startup banner still call them.

# LOG_ACTIVITY_WINDOW, _format_age, log_activity_health and tail_lines moved to
# monitoring/log_files.py (imported above). server_log_rows moved with them, but
# needs the two health collaborators that live here, so they are passed in at
# call time -- which is also what keeps
# `monkeypatch.setattr(server, 'cached_server_health', ...)` working.

def server_log_rows(cfg, q=''):
    """Build {status, rows} for a server. rows carry a stable 'seq' line key."""
    return log_files.server_log_rows(
        cfg, q,
        health_reader=cached_server_health,
        status_kind=server_status_kind,
        starting_window=server_lifecycle)


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
# agent every sweep — dozens of full-context model calls per awake-hour, and
# the canary's history grew with every ping/reply pair, so each probe got more
# expensive AND burned the very quota it was watching. Replaced with a
# ZERO-TOKEN probe: read the provider's own OAuth token from the Letta API
# (on this self-hosted server /v1/providers/ returns api_key_enc as plaintext
# token JSON) and ask the account's usage endpoint directly — the same
# endpoint Model Stats uses, but with the PROVIDER's token, so it still works
# after an Adam↔mom token swap. Extend PROVIDER_USAGE_PROBES to cover new
# provider types; no agent is ever messaged.


from monitoring import chatgpt_failover, provider_usage  # noqa: E402
from monitoring.provider_usage import (  # noqa: E402
    PROVIDER_USAGE_PROBES,
    fetch_provider_oauth_creds as _fetch_provider_oauth_creds,
)

# The zero-token provider quota probes moved to monitoring/provider_usage.py:
# the fleet lookup, the provider-token read, the two vendor probes and the two
# classifiers are one pipeline, and the classifiers are now typed -- an
# unrecognised usage body used to classify as "plenty of headroom", which is
# the verdict chatgpt_failover.maybe_failover consults. Only the agent roster stays
# here, injected per call.

def _provider_usage_deps():
    """Rebuilt per call so monkeypatching server.LETTA_AGENTS / get_letta_id works."""
    return provider_usage.Collaborators(agents=LETTA_AGENTS, get_letta_id=get_letta_id)


def _provider_agent_ids(provider_name):
    return provider_usage.provider_agent_ids(provider_name, deps=_provider_usage_deps())


# ── Per-agent OAuth account assignment (Model Stats "Agent Assignments" tab) ─
# Each Letta provider row is a single account's token; per-agent "which token"
# is really "which provider row" for the agent's model family. Two families
# (claude / chatgpt) x two humans (eg / mom) = the four real provider rows
# created 2026-08-21 when Mazda's fleet moved off the single shared
# claude-pro-max row (see mazda_categorizer_provider_fallback memory lineage).
OAUTH_PROVIDER_ACCOUNTS = {
    'claude-pro-max-eg':    {'account': 'eg',  'label': 'eg1972@gmail.com',     'family': 'claude'},
    'claude-pro-max':       {'account': 'mom', 'label': 'rbarnesrol@gmail.com', 'family': 'claude'},
    'chatgpt-plus-pro':     {'account': 'eg',  'label': 'eg1972@gmail.com',     'family': 'chatgpt'},
    'chatgpt-plus-pro-mom': {'account': 'mom', 'label': 'rbarnesrol@aol.com',   'family': 'chatgpt'},
}
# family → the AGENT_MODEL_OPTIONS prefix that carries that family's models,
# used to pick a starting model when the Token dropdown jumps an agent to a
# provider in a *different* family (its current model id has no meaning there).
FAMILY_MODEL_PREFIX = {'claude': 'claude-pro-max', 'chatgpt': 'chatgpt-plus-pro'}


def _default_model_id_for_family(family):
    prefix = FAMILY_MODEL_PREFIX.get(family, '') + '/'
    handle = next((h for h in AGENT_MODEL_OPTIONS if h.startswith(prefix)), None)
    return handle.partition('/')[2] if handle else ''

_weekly_remaining_cache = {}
_weekly_remaining_cache_lock = threading.Lock()
WEEKLY_REMAINING_CACHE_TTL = 60  # seconds; keeps the tab's poll from re-hitting 4 usage APIs every refresh


def _weekly_percent_remaining(provider_name):
    """100 - the 7-day/weekly window's used_percent for a provider's live
    token, via the same zero-token usage probes as the health system (never
    an LLM call). None on any failure -- caller renders that as unknown, not 0%."""
    now = time.time()
    with _weekly_remaining_cache_lock:
        cached = _weekly_remaining_cache.get(provider_name)
        if cached and now - cached[1] < WEEKLY_REMAINING_CACHE_TTL:
            return cached[0]

    creds, provider_type = _fetch_provider_oauth_creds(provider_name)
    remaining = None
    if creds:
        try:
            if provider_type in ('anthropic', 'anthropic_oauth'):
                token = creds.get('access_token') or (creds.get('claudeAiOauth') or {}).get('accessToken') or ''
                req = urllib.request.Request(
                    'https://api.anthropic.com/api/oauth/usage',
                    headers={'Authorization': 'Bearer ' + token,
                             'anthropic-beta': 'oauth-2025-04-20', 'User-Agent': 'claude-code/2.0.32'})
                with urllib.request.urlopen(req, timeout=15) as r:
                    usage = json.loads(r.read().decode())
                used = float((usage.get('seven_day') or {}).get('utilization') or 0)
                remaining = round(100 - used, 1)
            elif provider_type == 'chatgpt_oauth':
                req = urllib.request.Request(
                    'https://chatgpt.com/backend-api/wham/usage',
                    headers={'Authorization': 'Bearer ' + (creds.get('access_token') or ''),
                             'ChatGPT-Account-Id': creds.get('account_id', ''),
                             'OpenAI-Beta': 'codex-1', 'originator': 'codex_cli_rs', 'User-Agent': 'codex'})
                with urllib.request.urlopen(req, timeout=15) as r:
                    usage = json.loads(r.read().decode())
                rl = usage.get('rate_limit') or {}
                # The weekly window isn't reliably "secondary_window" -- its
                # position shifts (see monitoring/provider_usage.py's
                # codex_window_label and its 2026-08-19 note:
                # primary_window was the 7-day window with no secondary at
                # all). Pick whichever window's own limit_window_seconds is
                # actually ~7 days, not a fixed key.
                w = None
                for key in ('primary_window', 'secondary_window'):
                    candidate = rl.get(key)
                    if isinstance(candidate, dict) and abs((candidate.get('limit_window_seconds') or 0) - 604800) < 3600:
                        w = candidate
                        break
                used = float((w or {}).get('used_percent') or 0)
                remaining = round(100 - used, 1)
        except Exception:
            remaining = None

    with _weekly_remaining_cache_lock:
        _weekly_remaining_cache[provider_name] = (remaining, now)
    return remaining


def agent_oauth_account_payload(letta_id, pending_model=''):
    """GET contract for the per-agent Token dropdown: every OAuth account
    across BOTH families (an agent can be repointed at any of the four --
    picking one outside its current family also jumps its model family, see
    patch_agent_oauth_account), plus which provider row is live right now.

    `pending_model` is the dashboard's *not-yet-saved* model-dropdown value
    (a full handle like 'chatgpt-plus-pro/gpt-5.6-luna') -- when given, its
    provider is treated as "current" instead of the agent's live llm_config,
    so a model-family switch shows the right token pre-selected before the
    model PATCH round-trip finishes."""
    cur = letta_get(f'/v1/agents/{letta_id}', timeout=15) or {}
    live_provider = ((cur.get('llm_config') or {}).get('provider_name')) or ''
    pending_provider = pending_model.partition('/')[0] if pending_model else ''
    current = pending_provider if pending_provider in OAUTH_PROVIDER_ACCOUNTS else (
        live_provider if live_provider in OAUTH_PROVIDER_ACCOUNTS else '')
    options = [
        {'provider': provider, 'account': meta['account'], 'label': meta['label']}
        for provider, meta in OAUTH_PROVIDER_ACCOUNTS.items()
    ]
    return {'ok': True, 'current': current, 'options': options}


def patch_agent_oauth_account(agent_id, provider):
    """POST handler body: repoint an agent at a different provider row (any
    of the four -- same family or not). Same-family switches keep the
    current model id; a cross-family switch has no equivalent model id to
    carry over, so it starts that family's default model (see
    _default_model_id_for_family) -- the caller resyncs its Model dropdown
    from the returned `model` handle."""
    lid = letta_id_for(agent_id)
    if not lid:
        return {'ok': False, 'error': 'not a Letta agent'}
    target_info = OAUTH_PROVIDER_ACCOUNTS.get(provider)
    if not target_info:
        return {'ok': False, 'error': f'unknown provider {provider!r}'}
    cur = letta_get(f'/v1/agents/{lid}', timeout=15) or {}
    llm = cur.get('llm_config') or {}
    cur_provider = llm.get('provider_name') or ''
    cur_info = OAUTH_PROVIDER_ACCOUNTS.get(cur_provider)
    if cur_info and cur_info['family'] == target_info['family']:
        model_id = llm.get('model') or ''
    else:
        model_id = _default_model_id_for_family(target_info['family'])
    new_handle = f'{provider}/{model_id}'
    req = urllib.request.Request(
        f'{LETTA_BASE_URL}/v1/agents/{lid}',
        data=json.dumps({'model': new_handle}).encode(),
        headers={'Content-Type': 'application/json'},
        method='PATCH',
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read().decode())
    resolved_handle = (resp.get('llm_config') or {}).get('handle') or new_handle
    return {'ok': True, 'account': target_info['account'], 'provider': provider, 'model': resolved_handle}


_model_stats_agents_cache = {'value': None, 'ts': 0.0}
_model_stats_agents_cache_lock = threading.Lock()
MODEL_STATS_AGENTS_CACHE_TTL = 20  # seconds; one bulk /v1/agents/ fetch backs every row


def model_stats_agents_payload(force_refresh=False):
    """One row per LETTA_AGENTS entry for the Agent Assignments tab: current
    model, current OAuth account label, and that account's weekly-remaining %."""
    now = time.time()
    if not force_refresh:
        with _model_stats_agents_cache_lock:
            cached = _model_stats_agents_cache.get('value')
            if cached is not None and now - _model_stats_agents_cache.get('ts', 0.0) < MODEL_STATS_AGENTS_CACHE_TTL:
                return cached

    req = urllib.request.Request(f'{LETTA_BASE_URL}/v1/agents/?limit=200')
    with urllib.request.urlopen(req, timeout=20) as r:
        all_agents = json.loads(r.read().decode())
    by_id = {a['id']: a for a in all_agents}

    rows = []
    referenced_providers = set()
    for cfg in LETTA_AGENTS:
        real_id = get_letta_id(cfg)
        agent_data = by_id.get(real_id) if real_id else None
        llm = (agent_data or {}).get('llm_config') or {}
        provider = llm.get('provider_name') or ''
        model_id = llm.get('model') or ''
        info = OAUTH_PROVIDER_ACCOUNTS.get(provider)
        if provider:
            referenced_providers.add(provider)
        rows.append({
            'id': real_id or f'unknown-{cfg["name"].lower()}',
            'name': cfg['name'],
            'model': model_id,
            'account': info['account'] if info else '',
            'account_label': info['label'] if info else (provider or 'unknown'),
            'weekly_percent_remaining': _weekly_percent_remaining(provider) if provider else None,
        })

    # Accounts (e.g. rbarnesrol@aol.com / chatgpt-plus-pro-mom) that exist in
    # OAUTH_PROVIDER_ACCOUNTS but back no current agent's provider would
    # otherwise never appear on this tab -- surface them read-only so an
    # unused token's expiry is still visible.
    rows.extend(build_unassigned_account_rows(
        OAUTH_PROVIDER_ACCOUNTS, referenced_providers, _weekly_percent_remaining))

    # Mazda's run_claude_code_sdk tool is not a Letta agent, but it runs the
    # work that makes her minions useful and authenticates with its own mounted
    # Claude OAuth credential. Keep it in this list so an expired executor
    # token cannot hide behind healthy Letta-agent rows. This probe is
    # read-only and does not submit a Claude job or trigger auto-repair.
    sdk_account = claude_sdk_account_payload()
    sdk_option = next(
        (item for item in sdk_account.get('options', [])
         if item.get('account') == sdk_account.get('current')),
        {},
    )
    rows.append(build_claude_sdk_assignment(
        claude_sdk_token_status(), now=time.time(),
        account=sdk_account.get('current', ''),
        account_label=sdk_option.get('label', 'Executor OAuth token')))

    with _model_stats_agents_cache_lock:
        _model_stats_agents_cache['value'] = rows
        _model_stats_agents_cache['ts'] = now
    return rows


# ── ChatGPT provider auto-failover ────────────────────────────────────────────
# The whole state machine -- poll, detect a rate limit, heal a stale standby
# token, decide, swap, re-probe -- moved to monitoring/chatgpt_failover.py.
# It is one loop with one decision in it, and the parked standby bundle is now
# typed: a bundle that had lost its `account_id` used to switch OFF the guard
# that stops a heal parking a DIFFERENT account's refresh token, destroying
# the only copy of the real one.
#
# Three things stay here and are injected per sweep: the agent roster lookup
# and the two send-error writers, which belong to Agent Management's cache.
CHATGPT_PROVIDER_POLL_INTERVAL = chatgpt_failover.CHATGPT_PROVIDER_POLL_INTERVAL


def _chatgpt_failover_deps():
    """Rebuilt per sweep so monkeypatching the server-side names is honoured."""
    return chatgpt_failover.Collaborators(
        provider_agent_ids=_provider_agent_ids,
        record_send_error=record_agent_send_error,
        clear_send_error=clear_agent_send_error)


def _poll_chatgpt_provider_once(provider_name=CHATGPT_PLUS_PRO):
    return chatgpt_failover.poll_provider_once(provider_name,
                                               deps=_chatgpt_failover_deps())


def _chatgpt_provider_poll_loop():
    chatgpt_failover.poll_loop(_poll_chatgpt_provider_once)


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
# The whole of this moved into model_stats/: `sources.py` (the typed registry),
# `windows.py` (UsageWindow + the labelling), `reader.py` (the three provider
# branches), `last_good.py` (surviving a throttle) and `usage_history.py` (the
# burn-rate bar and the leak detector). None of it touched this module's state.
# Re-exported under the historical names: routes reach these through `srv`, and
# tests/test_server.py names several of them through `server`.
from model_stats.extractors import (  # noqa: E402
    _CLAUDE_EXTRACT_PY, _CODEX_EXTRACT_PY,
    _GEMINI_FLASH_FILL_EXTRACT_PY, _run_extractor,
)
from model_stats.last_good import (  # noqa: E402
    MODEL_STATS_LAST_GOOD_FILE, _restore_model_stats_last_good,
    _save_model_stats_last_good,
)
from model_stats.reader import (  # noqa: E402
    MODEL_STATS_CACHE_TTL, _fill_extractor_failure, _fill_rate_limited,
    _model_stats_cache, _model_stats_uncached, model_stats,
)
from model_stats.sources import ModelStatSource, R46_SSH_HOST  # noqa: E402
from model_stats.assignments import (  # noqa: E402
    build_claude_sdk_assignment,
    build_unassigned_account_rows,
)
from model_stats.usage_history import (  # noqa: E402
    LEAK_BUCKET_MINUTES, LEAK_LOOKBACK_MINUTES, LEAK_MIN_RISE_PCT,
    LEAK_MIN_RISING_BUCKETS, MODEL_USAGE_HISTORY_FILE,
    MODEL_USAGE_HISTORY_KEEP_MINUTES, MODEL_USAGE_SAMPLE_INTERVAL,
    RATE_BAR_FULL_SCALE_MULTIPLE, RATE_WARN_BURN_MULTIPLE,
    RATE_WINDOW_MINUTES, LeakVerdict, UsageRate, _attach_usage_metrics,
    _record_usage_sample, compute_usage_rate, detect_slow_leak,
)
from model_stats.usage_history import (  # noqa: E402
    _model_usage_sample_loop as _run_model_usage_sample_loop,
)
from model_stats.windows import UsageWindow, _human_reset  # noqa: E402


def _model_usage_sample_loop():
    """Composition root for the background usage sampler.

    The sampler needs a reading; the reader needs the sampler's recorder. The
    cycle is broken by injection, and the lambda keeps the binding late so a
    test that replaces `server.model_stats` is still honoured by a sampler
    thread that started before it.
    """
    return _run_model_usage_sample_loop(lambda key: model_stats(key))


# ── Web Terminal (Input Options → Terminal) ──────────────────────────────────
# A browser xterm.js panel connects to GET /api/terminal (WebSocket) and gets a
# full login shell in a pty on this box; when ?agent=<letta-id> is present the
# shell opens inside a letta-code session for that agent.
#
# What used to be one section here was three unrelated things, now three
# modules: http_app/websocket.py (the hand-rolled RFC 6455 framing, because the
# server stays stdlib-only), terminal/pty_session.py (spawning the shell and
# reaping the whole pty *session*, which is the only way to catch letta-code
# after it detaches), and letta_code/runner.py (the headless one-turn runner,
# which never touches a pty and only lived here by accident).
#
# Wire protocol, unchanged: client→server text frames carry JSON
# {"t":"i","d":<keys>} for input and {"t":"r","c":cols,"r":rows} for resize;
# server→client frames are binary raw pty bytes -- binary, not text, because a
# pty read can split a UTF-8 sequence mid-character and browsers kill the
# socket on an invalid text frame.
from letta_code.runner import (  # noqa: E402
    _letta_code_command, validate_letta_code_prompt,
)
from letta_code.runner import run_letta_code_message as _run_letta_code_message  # noqa: E402
from terminal.pty_session import _session_pids  # noqa: E402


def run_letta_code_message(agent_id, prompt, timeout=900, conversation_id=None):
    """Composition root for the headless runner: this module's id resolver.

    The lambda keeps the binding late. Handing `letta_id_for` over directly
    would freeze whichever function object existed at import time, and the
    tests that replace `server.letta_id_for` -- along with the agent-registry
    cache it reads -- would stop being honoured.
    """
    return _run_letta_code_message(
        agent_id, prompt, lambda aid: letta_id_for(aid),
        timeout=timeout, conversation_id=conversation_id)


# ── PC Monitor (per-machine RAM / disk / network) ─────────────────────────────
# Moved wholesale to monitoring/pc_metrics.py: one shell snippet run on the
# target, and pure code turning its output into three bars. It reads none of
# this module's state. Re-exported under the historical names because the
# routes reach `pc_metrics` and `PC_MONITORS` through `srv`.
from monitoring.pc_metrics import (  # noqa: E402
    PC_ALERT_THRESHOLDS, PC_METRICS_CACHE_TTL, PC_NET_CAPACITY_MBPS,
    PcMetric, PcMonitor, build_pc_metrics, parse_pc_metrics_output,
    pc_metrics_collector_command,
)


# ── HTTP Handler ──────────────────────────────────────────────────────────────

# ---------------------------------------------------------------------------
# HTTP layer
#
# DashboardHandler and ReusableHTTPServer used to live here (~1,380 lines).
# They now live in the `http_app` package, which reaches back into this module
# as `srv.<name>` — late binding, so runtime rebinds and test monkeypatches on
# `server` are still visible to the routes. That import has to happen at the
# *tail* of this file: every name the routes touch must already be defined.
# ---------------------------------------------------------------------------
sys.modules.setdefault('server', sys.modules[__name__])

from http_app import BackgroundTask, ServerConfig, serve   # noqa: E402
from http_app.handler import DashboardHandler              # noqa: E402
from http_app.runtime import ReusableHTTPServer            # noqa: E402


def startup_tasks():
    """The daemon threads the dashboard boots with, each with its banner line."""
    return [
        BackgroundTask(
            label='letta-log-pull',
            target=_letta_remote_log_pull_loop,
            banner=(f'Pulling Letta server logs over SSH from {LETTA_DOCKER_HOST} every '
                    f'{LETTA_REMOTE_LOG_PULL_INTERVAL}s -> {LETTA_REMOTE_LOG_CACHE}')),
        # Pre-warm the agent-list cache so the first /api/agents after a restart
        # doesn't block the browser on the slow (~12-30s) Letta roster fetch.
        BackgroundTask(
            label='agent-list-prewarm',
            target=build_agent_list,
            banner='Pre-warming /api/agents cache in the background'),
        BackgroundTask(
            label='health-poll',
            target=_health_poll_loop,
            banner=(f'Polling server health every {HEALTH_POLL_INTERVAL}s '
                    f'(timeout={HEALTH_CHECK_TIMEOUT}s, fail-threshold={HEALTH_FAIL_THRESHOLD})')),
        BackgroundTask(
            label='ssh-poll',
            target=_ssh_poll_loop,
            banner=(f'Polling {len(SSH_CONNECTIONS)} SSH connections every '
                    f'{SSH_HEALTH_POLL_INTERVAL}s')),
        BackgroundTask(
            label='chatgpt-provider-poll',
            target=_chatgpt_provider_poll_loop,
            banner=(f'Polling chatgpt-plus-pro provider health every '
                    f'{CHATGPT_PROVIDER_POLL_INTERVAL}s '
                    f'({len(_provider_agent_ids(CHATGPT_PLUS_PRO))} Suzuki-fleet agents; the whole '
                    f'Mazda fleet ({len(_provider_agent_ids(CLAUDE_PRO_MAX))} agents) is now on '
                    f'{CLAUDE_PRO_MAX})')),
        BackgroundTask(
            label='model-usage-sample',
            target=_model_usage_sample_loop,
            banner=(f'Sampling model usage every {MODEL_USAGE_SAMPLE_INTERVAL}s '
                    f'(rate warn \u2265{RATE_WARN_BURN_MULTIPLE}x sustainable; leak: '
                    f'{LEAK_MIN_RISING_BUCKETS}\u00d7{LEAK_BUCKET_MINUTES}m rising of '
                    f'{LEAK_LOOKBACK_MINUTES}m)')),
    ]


def startup_banners():
    """One-shot lines printed before the pollers start."""
    recovered = _recover_trainer_escalations()
    return [
        f'Letta API: {LETTA_BASE_URL}',
        f'Recovered {recovered} pending Trainer escalation watches',
    ]


if __name__ == '__main__':
    serve(DashboardHandler,
          ServerConfig(port=int(os.environ.get('PORT', 8765))),
          tasks=startup_tasks(),
          banners=startup_banners())
