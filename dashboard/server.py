#!/usr/bin/env python3
"""
Dashboard SPA server.
Serves dashboard.html and proxies agent data from the Letta API.
Run: python3 server.py   (from /home/adamsl/letta-code/dashboard/)
Then open: http://localhost:8765/
"""
import json
import glob
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections import deque
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote, unquote

from agents.letta_gateway import ILettaGateway
from agents.model_options import AgentModelOptionsService, select_model_options
from agents.urllib_letta_gateway import UrllibLettaGateway

from pydantic import ValidationError

from voice.synthesis import EdgeTtsSynthesizer, cache_path as synthesis_cache_path
from category_taxonomy import FallbackCategoryTaxonomy, MySqlCategoryTaxonomy
from chatgpt_provider_accounts import CODEX_PRIMARY_AUTH_JSON, PROVIDER_ACCOUNT_SOURCES
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
from supporting_document_service import normalize_supporting_document_reference
from supporting_document_slots import SUPPORTING_DOCUMENT_CATALOG
from finance.report_verdict import (
    AuditorReportVerdictSource,
    IReportVerdictSource,
    NullReportVerdictSource,
    worst_status,
)
from finance.expense_edit_audit import (
    AuditedExpenseEditCommand,
    CallableExpenseEditCommand,
    DEFAULT_EXPENSE_EDIT_AUDIT_PATH,
    JsonlExpenseEditAuditLog,
)
from finance.http_coercion import as_float
from finance.category_naming import ICategoryNamer, TaxonomyCategoryNamer
from finance.expense_edit_repository import MySqlExpenseRecordRepository
from finance.expense_report_sync import StaticExpenseReportSynchronizer
from finance.receipt_relocation import FilesystemReceiptFileRelocator
from finance.receipt_destination import CanonicalReceiptDestinationPolicy
from finance.report_page import ReportPageRoutes
from finance import (archive_path, intake_report_model, intake_report_page,
                     manual_entry, vendor_lookup)
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
from intake.recent_intake_routing import ExactRecentIntakeEventRouter
from finance.statement_dashboard_adapters import (
    CallableStatementPreflight,
    CallbackStatementIntakeRecorder,
)
from finance.statement_extraction_adapter import PreflightStatementExtractor
from finance.focused_receipt_reader import FocusedReceiptReader
from finance.receipt_read_contracts import (
    ReceiptReadIntent,
    ReceiptReadRequest,
)
from finance.receipt_read_service import (
    CallableDocumentClassifier,
    CallableForensicReceiptReader,
    FocusedReceiptReadStrategy,
    ForensicReceiptReadStrategy,
    ReceiptReadService,
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
    cards = ROL_FINANCE_REPORTS if month_key == ROL_FINANCES_REPORTS_DEFAULT_MONTH else [
        r for r in ROL_FINANCE_REPORTS if not r.get('all_year')
    ]
    return [
        r for r in cards
        if r.get('only_month') is None or r.get('only_month') == month_key
    ]


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
from paths import ROL_FINANCES_DIR  # noqa: E402
VERIFICATION_LIB = os.path.expanduser(
    '~/rol_finances/tools/python_tasks/verification_lib')


# Second opinion on every report tab. The badge inside a report is written by
# whoever generated it, so on its own it lets a report that copied another
# statement's numbers show green; the auditor reads the PDF sitting next to the
# report and can only ever downgrade the badge. Wired here (composition root)
# so tests can inject NullReportVerdictSource and judge badge parsing alone.
REPORT_VERDICT_SOURCE: IReportVerdictSource = AuditorReportVerdictSource(
    lib_dir=VERIFICATION_LIB,
    rol_root=ROL_FINANCES_DIR,
    logger=lambda message: print(f'[report-verdict] {message}', flush=True),
)


def _classify_report_badge(report_file):
    """The status a report claims for itself, read from its hero badge:
    'pass' (green, finished), 'review' (yellow, work in progress — e.g.
    "REVIEW NEEDED"), or 'fail' (red — explicit failure). Falls back to
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


def _classify_report_status(report_file, verdict_source=None):
    """Classify a report.html's overall verification status as 'pass', 'review'
    or 'fail', reconciling what the report claims with what the auditor finds.

    The two are combined by taking the worse of them, so the auditor can turn a
    self-declared PASS red but never promotes a report its own author flagged.
    When no independent verdict is available (auditor missing, or it crashed)
    the badge stands alone — an absent second opinion is not evidence."""
    badge = _classify_report_badge(report_file)
    if badge == 'fail':
        return badge
    source = REPORT_VERDICT_SOURCE if verdict_source is None else verdict_source
    return worst_status(badge, source.verdict(report_file)) or badge


from finance import report_attention as _report_attention  # noqa: E402


def _auditor_attention_detail(report_file, verdict_source=None):
    return _report_attention.auditor_attention_detail(
        report_file, REPORT_VERDICT_SOURCE if verdict_source is None else verdict_source)


def _extract_report_attention_detail(report_file, verdict_source=None):
    return _report_attention.extract_report_attention_detail(
        report_file, REPORT_VERDICT_SOURCE if verdict_source is None else verdict_source)


def _extract_report_failure_detail(report_file):
    """Backward-compatible name for existing callers and tests."""
    return _extract_report_attention_detail(report_file)


def _rol_reports_base_dir(month_key):
    """Base dir for a month key, e.g. 'feb-2025' -> .../bank_statements/february."""
    sub = ROL_FINANCES_REPORTS_MONTHS.get(
        month_key, ROL_FINANCES_REPORTS_MONTHS[ROL_FINANCES_REPORTS_DEFAULT_MONTH])
    return os.path.join(ROL_FINANCES_REPORTS_PARENT, sub)


from finance import recent_reports_index as _recent_reports_index  # noqa: E402


def _recent_reports_index_deps():
    return _recent_reports_index.Collaborators(
        reports_months=ROL_FINANCES_REPORTS_MONTHS,
        reports_url_prefix=ROL_FINANCES_REPORTS_URL_PREFIX,
        rol_reports_base_dir=_rol_reports_base_dir,
        rol_finance_reports_for_month=_rol_finance_reports_for_month,
        classify_report_status=_classify_report_status,
    )


def _month_broken_report_label(month_key):
    return _recent_reports_index.month_broken_report_label(
        _recent_reports_index_deps(), month_key)


def _rol_finance_recent_reports(limit=5):
    return _recent_reports_index.rol_finance_recent_reports(
        _recent_reports_index_deps(), limit=limit)


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


from intake import recent_report_store as _recent_report_store  # noqa: E402


def _recent_report_store_deps():
    return _recent_report_store.Collaborators(
        pointer_file=RECENT_REPORT_POINTER_FILE,
        lock=_recent_report_lock,
        report_file_for_url=_report_file_for_url,
        rol_finance_recent_reports=_rol_finance_recent_reports,
        current_execution_mode=current_execution_mode,
        fold_event_into_intake=_fold_event_into_intake,
        recent_intake_event_router=_recent_intake_event_router,
        merge_recent_intake_event=merge_recent_intake_event,
    )


def _read_recent_pointer_file():
    return _recent_report_store.read_recent_pointer_file(_recent_report_store_deps())


def _write_recent_pointer_file(data):
    return _recent_report_store.write_recent_pointer_file(_recent_report_store_deps(), data)


def set_recent_report_pointer(report_path):
    return _recent_report_store.set_recent_report_pointer(
        _recent_report_store_deps(), report_path)


def intake_state_token():
    return _recent_report_store.intake_state_token(_recent_report_store_deps())


def record_recent_intake(image_path, label, kind='scan', facade=None,
                         conversation_id=None, dispatched_at=None,
                         content_sha256=None, status='processing',
                         status_detail=''):
    """Record an intake dispatch (scan or PDF). See
    intake/recent_report_store.py."""
    return _recent_report_store.record_recent_intake(
        _recent_report_store_deps(), image_path, label, kind=kind, facade=facade,
        conversation_id=conversation_id, dispatched_at=dispatched_at,
        content_sha256=content_sha256, status=status, status_detail=status_detail)


from intake import intake_folding as _intake_folding  # noqa: E402


def _intake_folding_deps():
    """Rebuilt per call, never captured -- see intake/intake_folding.py's
    module docstring for why `duplicate_event_rows` and
    `resolve_duplicate_expense_ids` route back through this module's own
    names instead of calling their real implementation directly."""
    return _intake_folding.Collaborators(
        get_connection=_rol_get_connection,
        duplicate_event_rows=_duplicate_event_rows,
        resolve_duplicate_expense_ids=_resolve_duplicate_expense_ids,
    )


def _duplicate_event_rows(ids):
    return _intake_folding.duplicate_event_rows(_intake_folding_deps(), ids)


def _fold_event_into_intake(intake, event):
    """Fold one STEP 8 event's fields into one intake record, in place.
    The merge rule lives in intake/intake_folding.py."""
    return _intake_folding.fold_event_into_intake(
        _intake_folding_deps(), intake, event)


_recent_intake_event_router = ExactRecentIntakeEventRouter()


def merge_recent_intake_event(event):
    """Fold a STEP 8 /api/expense-stored event into every intake record it
    belongs to. See intake/recent_report_store.py."""
    return _recent_report_store.merge_recent_intake_event(
        _recent_report_store_deps(), event)


def merge_statement_review_result(payload):
    """Publish a successful review retry through the normal report event path."""
    return _recent_report_store.merge_statement_review_result(
        _recent_report_store_deps(), payload)


def merge_recent_intake_status(update):
    """Apply a Trainer terminal status to the exact dispatched intake. See
    intake/recent_report_store.py."""
    return _recent_report_store.merge_recent_intake_status(
        _recent_report_store_deps(), update)


def record_intake_status(data):
    """Dashboard endpoint used by the Trainer runner after writing its report."""
    return _recent_report_store.record_intake_status(
        _recent_report_store_deps(), data)


from finance import manual_receipt_intake as _manual_receipt_intake  # noqa: E402


def _manual_receipt_intake_deps():
    return _manual_receipt_intake.Collaborators(
        resolve_reporting_category=_resolve_reporting_category,
        invalidate_receipt_index=_invalidate_receipt_index,
        merge_recent_intake_event=merge_recent_intake_event,
        get_expense_edit_repository=_get_expense_edit_repository,
        synchronize_recent_report_image=_synchronize_recent_report_image,
        vendor_prefix=_vendor_prefix,
    )


def submit_manual_receipt_entry(data):
    """POST /api/manual-receipt-entry: the needs_human_review form's Save
    button. See finance/manual_receipt_intake.py."""
    return _manual_receipt_intake.submit_manual_receipt_entry(
        _manual_receipt_intake_deps(), data)


from finance import manual_expense_intake as _manual_expense_intake  # noqa: E402


def _manual_expense_intake_deps():
    return _manual_expense_intake.Collaborators(
        resolve_reporting_category=_resolve_reporting_category,
        get_expense_edit_repository=_get_expense_edit_repository,
    )


def submit_manual_expense_entry(data):
    """POST /api/add-expense-entry: the Add Expense page's Save All button.
    See finance/manual_expense_intake.py."""
    return _manual_expense_intake.submit_manual_expense_entry(
        _manual_expense_intake_deps(), data)


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
_expense_edit_audit_log = JsonlExpenseEditAuditLog(os.environ.get(
    'EXPENSE_EDIT_AUDIT_LOG', DEFAULT_EXPENSE_EDIT_AUDIT_PATH))


def _get_expense_edit_repository():
    """Composition root for the Edit Expense search/update boundary."""
    global _expense_edit_repository
    with _expense_edit_repository_lock:
        if _expense_edit_repository is None:
            _expense_edit_repository = MySqlExpenseRecordRepository(
                lambda: _rol_get_connection(), taxonomy_category_namer(),
                relocator=FilesystemReceiptFileRelocator(
                    resolve_path=_resolve_receipt_url_path,
                    destination_policy=RECEIPT_DESTINATION_POLICY))
    return _expense_edit_repository


from finance import receipt_reference_sync as _receipt_reference_sync  # noqa: E402


def _update_recent_receipt_references(expense_ids, path, old_path=''):
    return _receipt_reference_sync.update_recent_receipt_references(
        _receipt_reference_sync.Collaborators(get_connection=_rol_get_connection),
        expense_ids, path, old_path)


def _synchronize_recent_report_image(expense_id, **changes):
    """Composition boundary for the archived-image naming policy."""
    try:
        with _recent_report_lock:
            return RecentReportImageSynchronizer(
                read_pointer=_read_recent_pointer_file,
                write_pointer=_write_recent_pointer_file,
                fetch_rows=_fetch_expenses_by_ids,
                update_references=_update_recent_receipt_references,
                destination_policy=RECEIPT_DESTINATION_POLICY,
            ).synchronize(expense_id, **changes)
    except Exception as exc:  # noqa: BLE001 - the expense write already landed
        return {
            'renamed': False,
            'warning': f'Expense saved, but its image could not be renamed: '
                       f'{type(exc).__name__}: {exc}',
        }


from finance import expense_commands as _expense_commands  # noqa: E402


def _expense_commands_deps():
    return _expense_commands.Collaborators(
        get_expense_edit_repository=_get_expense_edit_repository,
        invalidate_receipt_index=_invalidate_receipt_index,
        synchronize_recent_report_image=_synchronize_recent_report_image,
        vendor_prefix=_vendor_prefix,
    )


def search_stored_expenses(data, repository=None):
    """POST /api/expense-search: rows behind the Edit Expense button."""
    return _expense_commands.search_stored_expenses(
        _expense_commands_deps(), data, repository=repository)


from finance import expense_edit_service as _expense_edit_service  # noqa: E402


def _expense_edit_service_deps():
    return _expense_edit_service.Collaborators(
        get_expense_edit_repository=_get_expense_edit_repository,
        taxonomy_category_namer=taxonomy_category_namer,
        invalidate_receipt_index=_invalidate_receipt_index,
        synchronize_recent_report_image=_synchronize_recent_report_image,
        vendor_prefix=_vendor_prefix,
        static_expense_report_synchronizer=StaticExpenseReportSynchronizer,
        rol_finances_reports_parent=ROL_FINANCES_REPORTS_PARENT,
    )


def _edit_stored_expense(data, repository=None, namer=None, report_sync=None):
    """Apply one correction; the public command wraps this with auditing."""
    return _expense_edit_service.edit_stored_expense(
        _expense_edit_service_deps(), data, repository=repository, namer=namer,
        report_sync=report_sync)


def edit_stored_expense(data, repository=None, namer=None, report_sync=None,
                        audit_log=None):
    """POST /api/expense-edit: apply and persist one diagnostic audit event."""
    recorder = audit_log if audit_log is not None else _expense_edit_audit_log
    command = AuditedExpenseEditCommand(
        CallableExpenseEditCommand(lambda request: _edit_stored_expense(
            request, repository=repository, namer=namer,
            report_sync=report_sync)),
        recorder,
    )
    return command.execute(data)


def delete_stored_expense(data, repository=None):
    """POST /api/expense-delete: remove one stored row."""
    return _expense_commands.delete_stored_expense(
        _expense_commands_deps(), data, repository=repository)


def add_sales_tax_to_expense(data, repository=None):
    """POST /api/expense-add-tax: put sales tax back on one stored row."""
    return _expense_commands.add_sales_tax_to_expense(
        _expense_commands_deps(), data, repository=repository)


from intake import intake_halt as _intake_halt  # noqa: E402


def _intake_halt_deps():
    return _intake_halt.Collaborators(halt_file=INTAKE_HALT_FILE, lock=_intake_halt_lock)


def record_intake_halt(data):
    """Persist a fail-loud intake halt so the dashboard can raise the alert.
    See intake/intake_halt.py."""
    return _intake_halt.record_intake_halt(_intake_halt_deps(), data)


def read_intake_halt():
    """Current intake-halt state for the front-end poller."""
    return _intake_halt.read_intake_halt(_intake_halt_deps())


def acknowledge_intake_halt():
    """Clear the active halt once a human has seen it (the alert's Acknowledge)."""
    return _intake_halt.acknowledge_intake_halt(_intake_halt_deps())


def _load_recent_report_pointer():
    return _recent_report_store.load_recent_report_pointer(_recent_report_store_deps())


def resolve_recent_report():
    """The most recently processed document. See
    intake/recent_report_store.py."""
    return _recent_report_store.resolve_recent_report(_recent_report_store_deps())


from finance import expense_lookup as _expense_lookup  # noqa: E402


def _expense_lookup_deps():
    return _expense_lookup.Collaborators(
        get_connection=_rol_get_connection,
        reporting_category_for_id=_reporting_category_for_id,
        css_class_for_report_name=_css_class_for_report_name,
    )


def _fetch_expenses_by_ids(ids):
    """Rows for the synthetic recent-intake view. See finance/expense_lookup.py."""
    return _expense_lookup.fetch_expenses_by_ids(_expense_lookup_deps(), ids)


def _resolve_duplicate_expense_ids(expense_date, amount, limit=3):
    """Last-resort recovery for a duplicate-only callback that named no ids.
    See intake/intake_folding.py's resolve_duplicate_expense_ids."""
    return _intake_folding.resolve_duplicate_expense_ids(
        _intake_folding_deps(), expense_date, amount, limit)


from finance import document_association as _document_association  # noqa: E402


def _document_association_deps():
    return _document_association.Collaborators(
        find_matching_report_row=_find_matching_report_row,
        source_document_path=_source_document_path,
        resolve_local_supporting_document=_resolve_local_supporting_document,
        resolve_expense_receipt_path=_resolve_expense_receipt_path,
        report_file_for_url=_report_file_for_url,
        readable_docs_base=READABLE_DOCS_BASE,
        associated_source_paths=_associated_source_paths,
        associated_evidence_paths=_associated_evidence_paths,
        statement_archive_path=_statement_archive_path,
        recent_intake_archive_path=_recent_intake_archive_path,
    )


STATEMENT_INTAKE_DOC_KINDS = _document_association.STATEMENT_INTAKE_DOC_KINDS


def _associated_source_paths(rows):
    return _document_association.associated_source_paths(_document_association_deps(), rows)


def _associated_evidence_paths(rows):
    return _document_association.associated_evidence_paths(_document_association_deps(), rows)


def _rows_are_statement_rows(rows):
    return _document_association.rows_are_statement_rows(rows)


def _statement_archive_path(rows, vendor_key=''):
    return _document_association.statement_archive_path(
        _document_association_deps(), rows, vendor_key=vendor_key)


def _recent_intake_archive_path(intake, rows, receipt_path=''):
    return _document_association.recent_intake_archive_path(
        _document_association_deps(), intake, rows, receipt_path=receipt_path)


def scanner_intake_archive_path(intake, rows):
    return _document_association.scanner_intake_archive_path(
        _document_association_deps(), intake, rows)


# The nine intake steps and the progress-from-messages derivation moved to
# intake/progress.py as typed `MazdaProgressStep`s -- the module asserts
# position == step number, so the indices _mazda_progress_from_messages()
# relies on are guarded by the data they index into.
from intake.progress import mazda_progress_from_messages as _mazda_progress_from_messages  # noqa: E402


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


from finance import intake_report_builder as _intake_report_builder  # noqa: E402
from finance.intake_report_builder import INTAKE_DOCUMENT_URL_PREFIX  # noqa: E402


def _intake_report_builder_deps():
    return _intake_report_builder.Collaborators(
        fetch_expenses_by_ids=_fetch_expenses_by_ids,
        associated_source_paths=_associated_source_paths,
        associated_evidence_paths=_associated_evidence_paths,
        recent_intake_archive_path=_recent_intake_archive_path,
        statement_archive_path=_statement_archive_path,
        receipt_only_picker_assets=_receipt_only_picker_assets,
        receipt_only_cat_css=_receipt_only_cat_css,
        mazda_intake_progress=mazda_intake_progress,
        mazda_mode_current=lambda: _MAZDA_MODE_SERVICE.current(),
    )


def build_recent_intake_html(intake):
    """Synthetic recent-report page for an intake whose document has no
    report.html. See finance/intake_report_builder.py."""
    return _intake_report_builder.build_recent_intake_html(
        _intake_report_builder_deps(), intake)


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
    return _document_association.scanner_statement_report(
        _document_association_deps(), scanner_key, intake)


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


from finance import report_file_lookup as _report_file_lookup  # noqa: E402


def _report_file_lookup_deps():
    return _report_file_lookup.Collaborators(
        reports_url_prefix=ROL_FINANCES_REPORTS_URL_PREFIX,
        reports_months=ROL_FINANCES_REPORTS_MONTHS,
        rol_reports_base_dir=_rol_reports_base_dir,
        reports=ROL_FINANCE_REPORTS,
        recent_report_path=RECENT_REPORT_PATH,
        scanner_report_path=SCANNER_REPORT_PATH,
        receipt_only_report_path=RECEIPT_ONLY_REPORT_PATH,
        resolve_recent_report=resolve_recent_report,
        viewable_document_extensions=_VIEWABLE_DOCUMENT_EXTENSIONS,
        supporting_document_annotation_cache=SUPPORTING_DOCUMENT_ANNOTATION_CACHE,
        render_excel_for_browser=render_excel_for_browser,
        source_document_path=_source_document_path,
    )


def _resolve_report_path_alias(report_path):
    return _report_file_lookup.resolve_report_path_alias(
        _report_file_lookup_deps(), report_path)


def _split_report_url(report_path):
    return _report_file_lookup.split_report_url(_report_file_lookup_deps(), report_path)


def _report_file_for_url(report_path):
    return _report_file_lookup.report_file_for_url(_report_file_lookup_deps(), report_path)


def _iter_existing_report_files():
    return _report_file_lookup.iter_existing_report_files(_report_file_lookup_deps())


def _find_matching_report_row(date_str, amount_str, vendor_key='', expense_id=None):
    return _report_file_lookup.find_matching_report_row(
        _report_file_lookup_deps(), date_str, amount_str, vendor_key=vendor_key,
        expense_id=expense_id)


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
from finance.human_verification import (  # noqa: E402
    HumanVerificationService,
    MySqlHumanVerificationRepository,
)

_human_verification_service = HumanVerificationService(
    MySqlHumanVerificationRepository(lambda: _rol_get_connection()))


def mark_expense_human_verified(request):
    """Persist the review gesture received through CategoryPort."""
    return _human_verification_service.mark_verified(request)


def _decorate_human_verified_rows(report_html):
    """Hydrate static report markers without mutating the report on disk."""
    try:
        return _human_verification_service.decorate_report(report_html)
    except Exception as exc:
        print(f'[human-verification] report hydration failed: {exc}', flush=True)
        return report_html


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
RECEIPT_DESTINATION_POLICY = CanonicalReceiptDestinationPolicy(
    [subtree for _prefix, _serve_base, subtree in RECEIPT_MOUNTS])

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
# INTAKE_DOCUMENT_URL_PREFIX now lives in finance/intake_report_builder.py,
# imported above (near build_recent_intake_html) and re-exported under this
# name for http_app/get_routes.py's `srv.INTAKE_DOCUMENT_URL_PREFIX`.
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
# "device is busy" error we are trying to detect. Manual scans own this lock;
# status requests only observe its ownership and never touch scanner hardware.
_SCAN_LOCK = threading.Lock()
# A real flatbed scan (OfficeJet, 300dpi) takes ~33s; allow headroom but cap it
# so a hung WIA call doesn't tie up the lock indefinitely.
SCAN_TIMEOUT_SEC = 90


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
from hardware import scanner_invoke as _scanner_invoke  # noqa: E402


def _scanner_invoke_deps():
    return _scanner_invoke.Collaborators(
        scanners=SCANNERS,
        scan_tools_dir=SCAN_TOOLS_DIR,
        scan_lock=_SCAN_LOCK,
        scan_timeout_sec=SCAN_TIMEOUT_SEC,
        scanner_image_url_prefix=SCANNER_IMAGE_URL_PREFIX,
        wsl_interop_socket=_wsl_interop_socket,
        scan_output_ready=_scan_output_ready,
    )


def _reap_stale_scans(scan_env):
    return _scanner_invoke.reap_stale_scans(_scanner_invoke_deps(), scan_env)


def _invoke_scanner(key):
    return _scanner_invoke.invoke_scanner(_scanner_invoke_deps(), key)


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


from intake import scan_staging as _scan_staging  # noqa: E402


def _scan_staging_deps():
    return _scan_staging.Collaborators(
        scan_output_ready=_scan_output_ready,
        scan_staging_host=SCAN_STAGING_HOST,
        scan_staging_remote_dir=SCAN_STAGING_REMOTE_DIR,
        letta_base_url=LETTA_BASE_URL,
        mazda_agent_id=MAZDA_AGENT_ID,
    )


def _stage_scan_for_mazda(local_image_path):
    return _scan_staging.stage_scan_for_mazda(_scan_staging_deps(), local_image_path)


def _create_mazda_conversation():
    return _scan_staging.create_mazda_conversation(_scan_staging_deps())


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


from intake import pdf_dispatch as _pdf_dispatch  # noqa: E402


def _notify_mazda_of_pdf(file_path, label=None, conversation_id=None,
                         dispatched_at=None, facade_result=None):
    """Background: send a PDF document to Mazda for intake processing."""
    return _pdf_dispatch.notify_mazda_of_pdf(
        LETTA_BASE_URL, file_path, label=label, conversation_id=conversation_id,
        dispatched_at=dispatched_at, facade_result=facade_result)


from intake import scan_dispatch_claim as _scan_dispatch_claim  # noqa: E402

# Intake-dispatch claim: exactly one Mazda dispatch per (scanner, image file,
# image mtime). Both the server's own post-scan auto-dispatch and the
# frontend's POST /api/process-document funnel through process_scanned_document;
# whichever arrives second sees the claim and skips the dispatch.
_scan_dispatch_claims = {}
_scan_dispatch_claim_lock = threading.Lock()
SCAN_DISPATCH_DEDUP_WINDOW_SEC = _scan_dispatch_claim.SCAN_DISPATCH_DEDUP_WINDOW_SEC


def _scan_dispatch_claim_deps():
    return _scan_dispatch_claim.Collaborators(
        get_scanner_intake=get_scanner_intake,
        claims=_scan_dispatch_claims,
        claims_lock=_scan_dispatch_claim_lock,
        dedup_window_sec=SCAN_DISPATCH_DEDUP_WINDOW_SEC,
    )


def _scan_content_sha256(image_path):
    return _scan_dispatch_claim.scan_content_sha256(image_path)


def _may_retry_terminal_scan(previous, content_sha256):
    return _scan_dispatch_claim.may_retry_terminal_scan(
        _scan_dispatch_claim_deps(), previous, content_sha256)


def _claim_scan_dispatch(key, image_path, content_sha256=None):
    return _scan_dispatch_claim.claim_scan_dispatch(
        _scan_dispatch_claim_deps(), key, image_path, content_sha256=content_sha256)


def _release_scan_dispatch(key, image_path):
    return _scan_dispatch_claim.release_scan_dispatch(
        _scan_dispatch_claim_deps(), key, image_path)


from intake import scanner_control as _scanner_control  # noqa: E402

_scanner_runtime_status = {}
_scanner_runtime_status_lock = threading.Lock()


def _scanner_control_deps():
    return _scanner_control.Collaborators(
        scanners=SCANNERS,
        scan_tools_dir=SCAN_TOOLS_DIR,
        get_scanner_intake=get_scanner_intake,
        scanner_intake_in_progress=_scanner_intake_in_progress,
        invoke_scanner=_invoke_scanner,
        record_recent_intake=record_recent_intake,
        process_scanned_document=process_scanned_document,
        merge_recent_intake_status=merge_recent_intake_status,
        scan_lock=_SCAN_LOCK,
        scanner_runtime_status=_scanner_runtime_status,
        scanner_runtime_status_lock=_scanner_runtime_status_lock,
    )


def _scanner_intake_in_progress(key, max_age_seconds=35 * 60):
    return _scanner_control.scanner_intake_in_progress(
        _scanner_control_deps(), key, max_age_seconds=max_age_seconds)


def run_scanner(key):
    """Manual scan (POST /api/scanner-scan). See intake/scanner_control.py."""
    return _scanner_control.run_scanner(_scanner_control_deps(), key)


def scanner_status(key):
    """Read-only scanner state. Never starts WIA or writes a scan image."""
    return _scanner_control.scanner_status(_scanner_control_deps(), key)


def clear_scanner_verification_lock(key):
    """Terminal-out one scanner's stuck intake lock without changing finance data."""
    return _scanner_control.clear_scanner_verification_lock(_scanner_control_deps(), key)


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
# STATEMENT_PARSE_SCRIPT/STATEMENT_PREFLIGHT_TIMEOUT_SEC now live in
# finance/statement_preflight.py, the only place that used them.

# The pipeline stages the deterministic facade does NOT run — delegated to Mazda.
MAZDA_DELEGATED_STAGES = ('investigate', 'categorize', 'store')


from intake import intake_facade as _intake_facade  # noqa: E402

MAZDA_DELEGATED_STAGES = _intake_facade.MAZDA_DELEGATED_STAGES


def run_intake_facade(image_path, org_id=1, engine='gemini'):
    """Run the deterministic intake facade (classify + parse) on one document.
    See intake/intake_facade.py."""
    deps = _intake_facade.Collaborators(
        mazda_intake_facade=MAZDA_INTAKE_FACADE,
        mazda_intake_python=MAZDA_INTAKE_PYTHON,
        rol_finances_dir=ROL_FINANCES_DIR,
        timeout_sec=INTAKE_FACADE_TIMEOUT_SEC,
    )
    return _intake_facade.run_intake_facade(deps, image_path, org_id=org_id, engine=engine)


def build_pipeline_result(facade, mazda_dispatched):
    return _intake_facade.build_pipeline_result(facade, mazda_dispatched)


from finance import statement_preflight as _statement_preflight  # noqa: E402


def _default_statement_account_directory():
    """Build the workbook-backed last-four resolver without a hard import.

    Kept as a `server.` thin wrapper (tests/test_server.py calls it directly
    to check the real workbook import) even though `run_statement_preflight`
    itself always calls its own module-private copy in
    finance/statement_preflight.py -- every call site that reaches this
    fallback passes `account_directory=` explicitly instead, so the two never
    need to be the same object at runtime."""
    return _statement_preflight._default_statement_account_directory()


def run_statement_preflight(
        image_path, facade_result, metadata=None, account_directory=None,
        engine='auto'):
    """Extract and validate statement metadata before dispatch or storage.
    See finance/statement_preflight.py."""
    return _statement_preflight.run_statement_preflight(
        image_path, facade_result, metadata=metadata,
        account_directory=account_directory, engine=engine)


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
#: never invent a doc_kind the rest of the pipeline doesn't understand. Owned
#: by intake/document_processing.py (the only other reader) and re-exported
#: here.
from intake.document_processing import STATEMENT_DOC_KINDS  # noqa: E402


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


# Composition root for the three manual reading jobs. The browser names the
# intent; this root supplies the interchangeable strategy that performs it.
#
_FOCUSED_RECEIPT_READER = FocusedReceiptReader(taxonomy_category_namer)
_FORENSIC_RECEIPT_STRATEGY = ForensicReceiptReadStrategy(
    CallableDocumentClassifier(
        lambda image_path: (run_intake_facade(image_path) or {}).get('doc_kind')),
    CallableForensicReceiptReader(
        lambda image_path, model: manual_entry.preview_receipt_parse(
            image_path, engine=model, category_namer=taxonomy_category_namer())),
    _STATEMENT_BREAKUP_SERVICE,
    statement_doc_kinds=STATEMENT_DOC_KINDS,
)
_RECEIPT_READ_SERVICE = ReceiptReadService({
    ReceiptReadIntent.CIRCLED_ONLY: FocusedReceiptReadStrategy(
        ReceiptReadIntent.CIRCLED_ONLY, _FOCUSED_RECEIPT_READER),
    ReceiptReadIntent.TOTAL_ONLY: FocusedReceiptReadStrategy(
        ReceiptReadIntent.TOTAL_ONLY, _FOCUSED_RECEIPT_READER),
    ReceiptReadIntent.SEVERAL_EXPENSES: _FORENSIC_RECEIPT_STRATEGY,
})


def read_receipt_document(data):
    """POST /api/receipt-read: run the explicitly requested read strategy.

    Nothing is stored. Circled Only and Total Only use bounded prefill readers;
    Several Expenses alone invokes the storage-grade forensic parser.
    """
    try:
        request = ReceiptReadRequest.from_http(data)
    except (ValidationError, ValueError) as exc:
        return {'ok': False, 'error': str(exc)}
    return _RECEIPT_READ_SERVICE.read(request).to_http()


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


from intake import document_processing as _document_processing  # noqa: E402


def _document_processing_deps():
    """Rebuilt per call, never captured. Several fields (`scanners`,
    `scan_tools_dir`, `document_vision_health`, `inspect_scan_image_quality`,
    `run_statement_preflight`, `run_intake_facade`) have an owning module of
    their own, but route back through this module's bare names anyway --
    tests/test_server.py monkeypatches each of them by its `server.` name to
    drive process_scanned_document through its branches without a real
    scanner, vision provider, or statement parse."""
    return _document_processing.Collaborators(
        scanners=SCANNERS,
        scan_tools_dir=SCAN_TOOLS_DIR,
        scan_locked=lambda: _SCAN_LOCK.locked(),
        record_recent_intake=record_recent_intake,
        human_override_facade=_human_override_facade,
        run_intake_facade=run_intake_facade,
        document_vision_health=document_vision_health,
        inspect_scan_image_quality=inspect_scan_image_quality,
        run_statement_preflight=run_statement_preflight,
        build_pipeline_result=build_pipeline_result,
        scan_content_sha256=_scan_content_sha256,
        claim_scan_dispatch=_claim_scan_dispatch,
        stage_scan_for_mazda=_stage_scan_for_mazda,
        write_statement_preflight_payload=_write_statement_preflight_payload,
        create_mazda_conversation=_create_mazda_conversation,
        dispatch_mazda_or_block=_dispatch_mazda_or_block,
        notify_mazda_of_scan_and_record_failure=_notify_mazda_of_scan_and_record_failure,
        release_scan_dispatch=_release_scan_dispatch,
        current_execution_mode=current_execution_mode,
    )


def process_scanned_document(
        key, org_id=1, engine='gemini', statement_metadata=None,
        doc_kind_override=None):
    """Orchestrate the Process Document action for one scanner's latest
    image. See intake/document_processing.py."""
    return _document_processing.process_scanned_document(
        _document_processing_deps(), key, org_id=org_id, engine=engine,
        statement_metadata=statement_metadata,
        doc_kind_override=doc_kind_override)


from intake import pdf_document_processing as _pdf_document_processing  # noqa: E402


def _pdf_document_processing_deps():
    return _pdf_document_processing.Collaborators(
        rol_finances_dir=ROL_FINANCES_DIR,
        run_intake_facade=run_intake_facade,
        document_vision_health=document_vision_health,
        create_mazda_conversation=_create_mazda_conversation,
        record_recent_intake=record_recent_intake,
        dispatch_mazda_or_block=_dispatch_mazda_or_block,
        notify_mazda_of_pdf=_notify_mazda_of_pdf,
        build_pipeline_result=build_pipeline_result,
        current_execution_mode=current_execution_mode,
        source_document_path=_source_document_path,
        invalidate_receipt_index=_invalidate_receipt_index,
        set_recent_report_pointer=set_recent_report_pointer,
        process_pdf_document=process_pdf_document,
    )


def process_pdf_document(file_path, label=None, org_id=1, engine='gemini'):
    """Orchestrate the Process Document action for an existing PDF file. See
    intake/pdf_document_processing.py."""
    return _pdf_document_processing.process_pdf_document(
        _pdf_document_processing_deps(), file_path, label=label, org_id=org_id,
        engine=engine)


def reprocess_report(report_url):
    """Re-run the full intake pipeline (facade + Mazda) for a report's source
    document. See intake/pdf_document_processing.py."""
    return _pdf_document_processing.reprocess_report(
        _pdf_document_processing_deps(), report_url)


# ── Expense-stored event bus ─────────────────────────────────────────────────
# Mazda calls POST /api/expense-stored after a successful store (STEP 8 in the
# scan message). The dashboard accumulates these lightweight events so the
# Reports tab can poll GET /api/expense-stored-events?since=<unix_ts> and
# reload any open report iframe to pick up newly-linked receipt markers.

_stored_expense_events = deque(maxlen=200)
_stored_expense_lock = threading.Lock()


from intake import expense_stored_callback as _expense_stored_callback  # noqa: E402


def _expense_stored_callback_deps():
    return _expense_stored_callback.Collaborators(
        invalidate_receipt_index=_invalidate_receipt_index,
        observe_intake_callback=_observe_intake_callback,
        merge_recent_intake_event=merge_recent_intake_event,
        set_recent_report_pointer=set_recent_report_pointer,
        stored_expense_lock=_stored_expense_lock,
        stored_expense_events=_stored_expense_events,
    )


def record_stored_expense(data):
    """POST /api/expense-stored: append one document-intake event."""
    return _expense_stored_callback.record_stored_expense(
        _expense_stored_callback_deps(), data)


def get_stored_expense_events(since_ts=0.0):
    """Return events stored after since_ts (unix float). Zero → return all."""
    with _stored_expense_lock:
        events = list(_stored_expense_events)
    return [e for e in events if e['stored_at'] > since_ts]


from finance import receipt_index as _receipt_index_mod  # noqa: E402


def _receipt_index_deps():
    return _receipt_index_mod.Collaborators(
        receipt_mounts=RECEIPT_MOUNTS,
        readable_docs_base=READABLE_DOCS_BASE,
        receipts_url_prefix=ROL_FINANCES_RECEIPTS_URL_PREFIX,
        cache=_RECEIPT_INDEX_CACHE,
        cache_ttl=_RECEIPT_INDEX_TTL,
        vendor_prefix=_vendor_prefix,
        receipt_index=_receipt_index,
        resolve_receipt_url_path=_resolve_receipt_url_path,
    )


def _build_receipt_index():
    return _receipt_index_mod.build_receipt_index(_receipt_index_deps())


def _receipt_index():
    return _receipt_index_mod.receipt_index(_receipt_index_deps())


def _norm_amount(signed_amount):
    return _receipt_index_mod.norm_amount(signed_amount)


def _resolve_receipt_url_path(receipt_url):
    return _receipt_index_mod.resolve_receipt_url_path(_receipt_index_deps(), receipt_url)


def _resolve_expense_receipt_path(date_str, amount_str, receipt_url):
    return _receipt_index_mod.resolve_expense_receipt_path(
        _receipt_index_deps(), date_str, amount_str, receipt_url)


def _receipt_url_for_path(fp):
    return _receipt_index_mod.receipt_url_for_path(_receipt_index_deps(), fp)


def _select_matching_expense(rows, vendor_key, description):
    return _receipt_index_mod.select_matching_expense(
        _receipt_index_deps(), rows, vendor_key, description)


def _matching_expense(cur, date_str, amount_str, vendor_key, description,
                      expense_id=None):
    return _receipt_index_mod.matching_expense(
        _receipt_index_deps(), cur, date_str, amount_str, vendor_key, description,
        expense_id=expense_id)


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
    reference_terms = ()
    if document_type == 'check_image':
        reference_terms = tuple(
            re.findall(
                r'\bcheck\s*#?\s*(\d{3,})\b',
                str(chosen.get('description') or ''), re.I,
            )
        )
    return ExpenseEvidence(
        expense_id=int(chosen['id']),
        expense_date=str(chosen.get('expense_date') or ''),
        amount=str(chosen.get('amount') or ''),
        description=str(chosen.get('description') or ''),
        vendor_key=_vendor_prefix(chosen.get('id_light')),
        related_document_path=related_document_path,
        reference_terms=reference_terms,
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


def _check_image_document_path(report_path):
    """Return the statement's separate cleared-check image PDF, if present."""
    source_path = _source_document_path(report_path)
    if not source_path or not os.path.isfile(source_path):
        return ''
    stem, extension = os.path.splitext(source_path)
    if extension.lower() != '.pdf' or stem.lower().endswith('_images'):
        return ''
    candidate = f'{stem}_images{extension}'
    return candidate if os.path.isfile(candidate) else ''


def _slot_reference(chosen, kind, report_path=''):
    """The reference to offer for one supporting-document slot."""
    slot = SUPPORTING_DOCUMENT_CATALOG.slot_for_kind(kind)
    if slot is None:
        return ''
    if kind == 'check_image':
        chosen = chosen or {}
        if not re.search(
                r'\bcheck\s*#?\s*\d{3,}\b',
                str(chosen.get('description') or ''), re.I):
            return ''
        return _check_image_document_path(report_path)
    if kind == 'source':
        return _source_document_reference(chosen, report_path)
    return slot_reference(
        chosen, slot, report_path,
        normalize=normalize_supporting_document_reference,
        page_scan=_report_scanned_statement_reference,
    )


from finance import source_document_reference as _source_document_reference_mod  # noqa: E402


def _source_document_reference(chosen, report_path=''):
    deps = _source_document_reference_mod.Collaborators(
        resolve_local_supporting_document=_resolve_local_supporting_document,
        report_scanned_statement_reference=_report_scanned_statement_reference,
        usable_document_reference=_usable_document_reference,
        report_source_document_reference=_report_source_document_reference,
        find_matching_report_row=_find_matching_report_row,
        source_document_path=_source_document_path,
    )
    return _source_document_reference_mod.source_document_reference(
        deps, chosen, report_path=report_path)


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
    return _report_file_lookup.source_document_path(
        _report_file_lookup_deps(), report_path, receipt_path)


def _report_source_document_view(report_path):
    return _report_file_lookup.report_source_document_view(
        _report_file_lookup_deps(), report_path)


def _document_machine_origin():
    import socket
    hostname = socket.gethostname().lower()
    return "Mom's machine" if 'rosemary' in hostname else 'Win 11'


from finance import receipt_lookup as _receipt_lookup  # noqa: E402


def _receipt_lookup_deps():
    return _receipt_lookup.Collaborators(
        get_connection=_rol_get_connection,
        norm_amount=_norm_amount,
        matching_expense=_matching_expense,
        resolve_local_supporting_document=_resolve_local_supporting_document,
        viewable_supporting_document=_viewable_supporting_document,
        document_machine_origin=_document_machine_origin,
        source_document_path=_source_document_path,
        resolve_expense_receipt_path=_resolve_expense_receipt_path,
        receipt_url_for_path=_receipt_url_for_path,
    )


def lookup_receipt(date_str, signed_amount, vendor_key, description='', report_path='',
                   expense_id=None):
    """Return receipt and source-document metadata for one report row."""
    return _receipt_lookup.lookup_receipt(
        _receipt_lookup_deps(), date_str, signed_amount, vendor_key,
        description=description, report_path=report_path, expense_id=expense_id)


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


from finance import receipts_present as _receipts_present  # noqa: E402


def _receipts_present_deps():
    return _receipts_present.Collaborators(
        get_connection=_rol_get_connection,
        norm_amount=_norm_amount,
        select_matching_expense=_select_matching_expense,
        resolve_expense_receipt_path=_resolve_expense_receipt_path,
        resolve_local_supporting_document=_resolve_local_supporting_document,
    )


def receipts_present(rows):
    return _receipts_present.receipts_present(_receipts_present_deps(), rows)


def scanned_statements_present(rows):
    return _receipts_present.scanned_statements_present(_receipts_present_deps(), rows)


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
from finance import reporting_category_lookup as _reporting_categories  # noqa: E402


def _reporting_categories_deps():
    return _reporting_categories.Collaborators(
        get_category_taxonomy=_get_category_taxonomy,
        reporting_category_class=REPORTING_CATEGORY_CLASS,
        reporting_category_db_map=REPORTING_CATEGORY_DB_MAP,
    )


def _reporting_category_for_id(category_id, parent_of=None):
    return _reporting_categories.reporting_category_for_id(
        _reporting_categories_deps(), category_id, parent_of=parent_of)


from finance import recent_scans as _recent_scans  # noqa: E402


def _recent_scans_deps():
    return _recent_scans.Collaborators(
        get_connection=_rol_get_connection,
        norm_amount=_norm_amount,
        resolve_expense_receipt_path=_resolve_expense_receipt_path,
        reporting_category_for_id=_reporting_category_for_id,
        css_class_for_report_name=_css_class_for_report_name,
        vendor_prefix=_vendor_prefix,
        month_broken_report_label=_month_broken_report_label,
        reports=ROL_FINANCE_REPORTS,
        month_ranges=ROL_FINANCES_MONTH_RANGES,
        reports_default_month=ROL_FINANCES_REPORTS_DEFAULT_MONTH,
    )


def _fetch_receipt_only_rows(month_key=None):
    return _recent_scans.fetch_receipt_only_rows(_recent_scans_deps(), month_key)


# ── ROL Finance: recently-scanned queue + green/yellow month status ──────────
# A scanned receipt becomes an `expenses` row (created_at auto-set on INSERT), so
# "recently scanned, newest first" is just ORDER BY created_at DESC — no separate
# queue store is needed. An expense has "unfinished business" while it is still
# uncategorized; setting its category (via /api/recategorize-expense) resolves it.
# Uncategorized == category_id NULL, or 1/364 which both resolve to 'Uncategorized'
# in REPORTING_CATEGORY_ANCESTOR_MAP (the same buckets the picker's "Uncategorized"
# choice writes back, i.e. category_id -> None).
_UNCATEGORIZED_CATEGORY_IDS = _recent_scans.UNCATEGORIZED_CATEGORY_IDS


def _is_uncategorized(category_id):
    return _recent_scans.is_uncategorized(category_id)


def _rol_finance_categories():
    return _reporting_categories.rol_finance_categories(_reporting_categories_deps())


def _rol_finance_category_for_ids(category_ids):
    return _reporting_categories.rol_finance_category_for_ids(
        _reporting_categories_deps(), category_ids)


def _report_category_node_by_name(name, selectable_only=True):
    return _reporting_categories.report_category_node_by_name(
        _reporting_categories_deps(), name, selectable_only=selectable_only)


def _css_class_for_report_name(name):
    return _reporting_categories.css_class_for_report_name(_reporting_categories_deps(), name)


def _resolve_reporting_category(name):
    return _reporting_categories.resolve_reporting_category(_reporting_categories_deps(), name)


def _account_number_in_label(label):
    return _reporting_categories.account_number_in_label(label)


def _document_report_for_path(path, month_key=None):
    return _recent_scans.document_report_for_path(_recent_scans_deps(), path, month_key)


def _fetch_recent_scans(limit=5, month_key=None):
    return _recent_scans.fetch_recent_scans(_recent_scans_deps(), limit=limit, month_key=month_key)


def _fetch_month_status():
    return _recent_scans.fetch_month_status(_recent_scans_deps())


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



# Same hide-the-other-sections behavior as
# RolFinanceReportsController.showOnlyVerifiedTransactions() in
# rol-finance-reports-controller.js, ported inline so a report.html opened
# directly (not inside the dashboard's own iframe, e.g. from Mom's SmartMenu)
# can still land on just the Verified Transactions table via ?verified=1.
_VERIFIED_ONLY_SCRIPT = (
    '<script>(function(){'
    'var vt=document.getElementById("verified-transactions");'
    'if(!vt)return;'
    'var keep=vt.closest("section");'
    'if(keep&&keep.parentElement){'
    'for(var i=0;i<keep.parentElement.children.length;i++){'
    'var c=keep.parentElement.children[i];'
    'if(c!==keep&&c.tagName==="SECTION"){c.style.display="none";}'
    '}'
    '}'
    # Mom doesn't need the raw JSON dump either — it's outside the
    # Verified Transactions <section> so the loop above never reaches it.
    'var summaries=document.querySelectorAll("details > summary");'
    'for(var j=0;j<summaries.length;j++){'
    'if(summaries[j].textContent.indexOf("Machine-Readable")!==-1){'
    'summaries[j].parentElement.style.display="none";'
    '}'
    '}'
    '})();</script>'
)


def _report_html_with_current_picker(report_file, verified_only=False):
    """Refresh only the picker assets in memory; never rewrite row categories."""
    rv = _picker_module()
    with open(report_file, encoding='utf-8', errors='ignore') as handle:
        # Pass the categories in: the injector would otherwise HTTP-fetch them
        # from this very server, from inside one of its own request handlers.
        hydrated = _decorate_human_verified_rows(handle.read())
        html = rv.add_category_picker(hydrated, _rol_finance_categories())
    if verified_only:
        html = html.replace('</body>', _VERIFIED_ONLY_SCRIPT + '</body>', 1)
    return html


def _receipt_only_cat_css():
    return category_row_css(_rol_finance_categories())


from finance import receipt_only_report_page as _receipt_only_report_page  # noqa: E402


def build_receipt_only_report_html(month_key=None):
    """A standalone, same-origin report page for receipt-only records. See
    finance/receipt_only_report_page.py."""
    deps = _receipt_only_report_page.Collaborators(
        receipt_only_picker_assets=_receipt_only_picker_assets,
        fetch_receipt_only_rows=_fetch_receipt_only_rows,
        receipt_only_cat_css=_receipt_only_cat_css,
    )
    return _receipt_only_report_page.build_receipt_only_report_html(deps, month_key)


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
from servers.agent_blocks import AgentBlocksServer  # noqa: E402


_AGENT_BLOCKS_SERVER = AgentBlocksServer(
    start_script=os.path.expanduser('~/agent_blocks/spa_documentation/start.sh'),
    startup_log='/tmp/agent_blocks_startup.log',
    mark_starting=mark_server_starting,
)


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


def start_agent_blocks_server():
    """Compatibility adapter for the Server Management restart registry."""
    return _AGENT_BLOCKS_SERVER.start().model_dump()


def ensure_agent_blocks_server():
    """Dashboard startup task: make its embedded Agent Blocks SPA available."""
    return start_agent_blocks_server()


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


def restart_scanner_intake_watchdog():
    """"Restart" for the watchdog tile: there is no process behind it — it
    only reads recent_report.json. Nothing here can revive a dead Trainer run
    or safely decide a stuck intake is done, so this just re-reports current
    status; the actual remedy is fixing whatever killed Trainer (see
    health/scanner_intake_watchdog.py) or "Clear Verification Lock" on the
    affected scanner's own dialog."""
    health = scanner_intake_watchdog_health()
    return {'ok': health['ok'], 'text': health['text']}


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
        with _model_stats_agents_cache_lock:
            _model_stats_agents_cache['value'] = None
        with _weekly_remaining_cache_lock:
            _weekly_remaining_cache.pop(CHATGPT_PLUS_PRO, None)
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
        _ptype = None
    try:
        with open(CODEX_PRIMARY_AUTH_JSON, encoding='utf-8') as fh:
            local_auth = json.load(fh)
    except Exception:
        local_auth = None
    probe_fn = PROVIDER_USAGE_PROBES.get(_ptype)
    probe = probe_fn(creds, timeout=8) if creds and probe_fn else None
    return chatgpt_provider_account_status(
        creds, local_auth=local_auth, probe=probe)


from servers.browser_server import SshBrowserServerLifecycle  # noqa: E402

_BROWSER_SERVER_LIFECYCLE = SshBrowserServerLifecycle(
    remote_host=LETTA_DOCKER_HOST,
    health_url='http://100.80.49.10:5001/health',
    mark_starting=mark_server_starting,
    log_restart=_log_restart,
)


def start_browser_server():
    """Ensure the Win10 browser server's enabled user unit is running."""
    return _BROWSER_SERVER_LIFECYCLE.restart().model_dump()


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
    RestartCommand(key='agent-blocks', handler=start_agent_blocks_server,
                   note='launches start.sh (spa_documentation dev server)'),
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
    RestartCommand(key='scanner-intake-watchdog',
                   handler=lambda: restart_scanner_intake_watchdog()),
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
from health.scanner_intake_watchdog import (  # noqa: E402
    scanner_intake_watchdog_health,
)




# Registry of named check functions usable via a SERVERS entry's 'check' key.
HEALTH_CHECKS = {
    'frita_executor_health': frita_executor_health,
    'win10_node_health': win10_node_health,
    'document_vision_health': document_vision_health,
    'chatgpt_provider_health': chatgpt_provider_health,
    'mazda_categorizer_fallback_health': mazda_categorizer_fallback_health,
    'scanner_intake_watchdog_health': scanner_intake_watchdog_health,
}


from monitoring import server_status as _server_status  # noqa: E402


def _server_status_deps():
    return _server_status.Collaborators(
        health_checks=HEALTH_CHECKS,
        restartable_keys=RESTARTABLE_KEYS,
        is_server_starting=is_server_starting,
        win10_docker_ok=win10_docker_ok,
    )


def server_health(cfg, timeout=None):
    """Ping a server's health_url or tcp_check. See monitoring/server_status.py."""
    return _server_status.server_health(_server_status_deps(), cfg, timeout=timeout)


def compute_server_status(health, *, starting=False, restartable=False,
                          host_unreachable=False, dependency_down=False):
    return _server_status.compute_server_status(
        health, starting=starting, restartable=restartable,
        host_unreachable=host_unreachable, dependency_down=dependency_down)


def server_status_kind(cfg, health):
    """Shared 4-state classification used by both the sidebar tab and the
    detail panel. See monitoring/server_status.py."""
    return _server_status.server_status_kind(_server_status_deps(), cfg, health)


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
from health import claude_sdk_token_rate  # noqa: E402
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

from monitoring import agent_activity as _agent_activity  # noqa: E402


def _agent_activity_deps():
    return _agent_activity.Collaborators(
        letta_agents=LETTA_AGENTS,
        get_letta_id=get_letta_id,
        letta_messages=letta_messages,
        cache=_agent_activity_cache,
        cache_lock=_agent_activity_cache_lock,
        cache_ttl=AGENT_ACTIVITY_CACHE_TTL,
    )


def _msg_age_seconds(m, now):
    return _agent_activity.msg_age_seconds(m, now)


def _agent_activity_one(cfg, now):
    return _agent_activity.agent_activity_one(_agent_activity_deps(), cfg, now)


def agent_activity_status():
    """Return {agent_id: 'active'|'error'|'idle'} for every configured Letta
    agent. See monitoring/agent_activity.py."""
    return _agent_activity.agent_activity_status(_agent_activity_deps())


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


def _claude_provider_for_account(account):
    """The OAUTH_PROVIDER_ACCOUNTS provider whose Claude token belongs to
    ``account`` ('eg' / 'mom'). The SDK executor's dropdown names an account,
    not a provider row, but weekly quota is only readable per provider -- this
    is the join between health/frita.py's CLAUDE_SDK_ACCOUNT_OPTIONS and the
    provider rows the usage probes understand."""
    return next(
        (provider for provider, meta in OAUTH_PROVIDER_ACCOUNTS.items()
         if meta.get('family') == 'claude' and meta.get('account') == account),
        '')


def _default_model_id_for_family(family):
    prefix = FAMILY_MODEL_PREFIX.get(family, '') + '/'
    handle = next((h for h in AGENT_MODEL_OPTIONS if h.startswith(prefix)), None)
    return handle.partition('/')[2] if handle else ''

from model_stats import agents_payload as _agents_payload  # noqa: E402

_weekly_remaining_cache = {}
_weekly_remaining_cache_lock = threading.Lock()
WEEKLY_REMAINING_CACHE_TTL = 60  # seconds; keeps the tab's poll from re-hitting 4 usage APIs every refresh


def _weekly_percent_remaining(provider_name):
    return _agents_payload.weekly_percent_remaining(
        _agents_payload.WeeklyRemainingCollaborators(
            fetch_provider_oauth_creds=_fetch_provider_oauth_creds,
            cache=_weekly_remaining_cache,
            cache_lock=_weekly_remaining_cache_lock,
            cache_ttl=WEEKLY_REMAINING_CACHE_TTL,
        ),
        provider_name)


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
    deps = _agents_payload.Collaborators(
        letta_base_url=LETTA_BASE_URL,
        letta_agents=LETTA_AGENTS,
        get_letta_id=get_letta_id,
        get_chatgpt_provider_account_status=get_chatgpt_provider_account_status,
        oauth_provider_accounts=OAUTH_PROVIDER_ACCOUNTS,
        chatgpt_plus_pro=CHATGPT_PLUS_PRO,
        weekly_percent_remaining=_weekly_percent_remaining,
        claude_sdk_account_payload=claude_sdk_account_payload,
        claude_sdk_token_status=claude_sdk_token_status,
        claude_provider_for_account=_claude_provider_for_account,
        cache=_model_stats_agents_cache,
        cache_lock=_model_stats_agents_cache_lock,
        cache_ttl=MODEL_STATS_AGENTS_CACHE_TTL,
    )
    return _agents_payload.agents_payload(deps, force_refresh=force_refresh)


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


from monitoring import agent_health as _agent_health  # noqa: E402


def _agent_health_deps():
    return _agent_health.Collaborators(
        letta_agents=LETTA_AGENTS,
        get_letta_id=get_letta_id,
        letta_get=letta_get,
        agent_send_errors=_agent_send_errors,
        agent_send_errors_lock=_agent_send_errors_lock,
        probe_claude_sdk_endpoint=_probe_claude_sdk_endpoint,
        frita_exec_work_url=FRITA_EXEC_WORK_URL,
        cache=_agent_health_cache,
        cache_lock=_agent_health_cache_lock,
        cache_ttl=AGENT_HEALTH_CACHE_TTL,
    )


def _uses_claude_sdk(cfg):
    return _agent_health.uses_claude_sdk(cfg)


def agent_health_check(cfg, timeout=15, sdk_status=None):
    return _agent_health.agent_health_check(
        _agent_health_deps(), cfg, timeout=timeout, sdk_status=sdk_status)


def agent_health_status():
    """Return {agent_id: {ok, text, name}} for every agent that declares
    required_tools. See monitoring/agent_health.py."""
    return _agent_health.agent_health_status(_agent_health_deps())


from monitoring import agent_list as _agent_list_mod  # noqa: E402


def _agent_list_deps():
    return _agent_list_mod.Collaborators(
        letta_agents=LETTA_AGENTS,
        get_letta_id=get_letta_id,
        cache=_agent_list_cache,
        cache_lock=_agent_list_cache_lock,
        cache_ttl=AGENT_LIST_CACHE_TTL,
        build_agent_list=build_agent_list,
    )


def build_agent_list(force_refresh=False):
    """Return the agent list for /api/agents, combining Letta agents + Claude.
    See monitoring/agent_list.py."""
    return _agent_list_mod.build_agent_list(_agent_list_deps(), force_refresh=force_refresh)

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


def run_letta_code_message(agent_id, prompt, timeout=1770, conversation_id=None):
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
            label='agent-blocks-autostart',
            target=ensure_agent_blocks_server,
            banner='Ensuring the Agent Blocks documentation server is available'),
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
            label='report-verdict-warm',
            target=_warm_report_verdicts,
            banner='Auditing statement reports once to warm tab verdicts'),
        BackgroundTask(
            label='claude-sdk-token-rate-sample',
            target=claude_sdk_token_rate.SAMPLER.run_forever,
            banner=(f'Sampling Claude Code SDK token usage every '
                    f'{claude_sdk_token_rate.SAMPLER_INTERVAL_SECONDS:.0f}s '
                    f'(the executor keeps no running total)')),
        BackgroundTask(
            label='model-usage-sample',
            target=_model_usage_sample_loop,
            banner=(f'Sampling model usage every {MODEL_USAGE_SAMPLE_INTERVAL}s '
                    f'(rate warn \u2265{RATE_WARN_BURN_MULTIPLE}x sustainable; leak: '
                    f'{LEAK_MIN_RISING_BUCKETS}\u00d7{LEAK_BUCKET_MINUTES}m rising of '
                    f'{LEAK_LOOKBACK_MINUTES}m)')),
    ]


def _warm_report_verdicts():
    """One-shot: audit every report once at boot so the first page load is not
    the slow one. ~0.1s per report, ~5s for the whole tree, then cached until a
    report or its PDF changes. Not a poll loop — it runs once and exits."""
    try:
        reports = sorted(glob.glob(
            os.path.join(ROL_FINANCES_REPORTS_PARENT, '**', 'report.html'),
            recursive=True))
        warmed = REPORT_VERDICT_SOURCE.warm(reports)
        print(f'[report-verdict] warmed {warmed} report verdicts', flush=True)
    except Exception as exc:
        print(f'[report-verdict] warm-up skipped: {exc}', flush=True)


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
