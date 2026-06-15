#!/usr/bin/env python3
"""
Dashboard SPA server.
Serves dashboard.html and proxies agent data from the Letta API.
Run: python3 server.py   (from /home/adamsl/letta-code/dashboard/)
Then open: http://localhost:8765/
"""
import json
import os
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from collections import deque
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote

from voice.pipeline import build_pipeline, handle_voice_upload

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)

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
ROL_FINANCES_REPORTS_BASE = os.path.expanduser(
    '~/rol_finances/readable_documents/bank_statements/january')
ROL_FINANCES_REPORTS_URL_PREFIX = '/rol_finances_reports'
ROL_FINANCE_REPORTS = [
    {'key': 'amex-61006',        'label': 'Amex 61006',         'dir': 'amex_personal_january_25'},
    {'key': 'fnbo-4851',         'label': 'FNBO 4851',          'dir': 'january_fnbo_2025_account_4851'},
    {'key': 'amex-personal-year','label': 'Amex Personal Year', 'dir': 'amex_personal_whole_2025'},
    {'key': 'bank-5938-pdf1',    'label': 'Bank 5938 PDF 1',    'dir': 'december_january_personal_bank_statement'},
    {'key': 'bank-6285-pdf1',    'label': 'Bank 6285 PDF 1',    'dir': 'non_profit_rol_Statement_december_january_6285'},
    {'key': 'bank-6285-pdf2',    'label': 'Bank 6285 PDF 2',    'dir': 'business_january_february_6285'},
    {'key': 'jetblue-pdf1',      'label': 'Jet Blue PDF 1',     'dir': 'jet_blue__december_january_12_26_25_to_01_23_25'},
    {'key': 'jetblue-pdf2',      'label': 'Jet Blue PDF 2',     'dir': 'jet_blue_january_february_01_27_to_02_25_25'},
    {'key': 'platinum-year',     'label': 'Platinum Year',      'dir': 'platinum_business_credit_card_for_the_year'},
    {'key': 'diners-club-0587',  'label': 'Diners Club 0587',   'dir': 'diners_club__january_25_statements-MONTHLY-0587'},
]

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


def _report_file_for_url(report_path):
    """Map a /rol_finances_reports/<dir>/report.html URL path to its file on disk."""
    prefix = ROL_FINANCES_REPORTS_URL_PREFIX + '/'
    if not report_path or not report_path.startswith(prefix):
        return None
    rel = report_path[len(prefix):]
    fp = os.path.abspath(os.path.join(ROL_FINANCES_REPORTS_BASE, rel))
    base = os.path.abspath(ROL_FINANCES_REPORTS_BASE)
    if os.path.commonpath([fp, base]) == base and os.path.isfile(fp):
        return fp
    return None


def _update_report_row_color(report_path, vendor_key, date_str, amount_str, new_cls):
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
    if not vk:
        return False

    def attempt(require_date, require_amount):
        """Rewrite the first vendor-matching row that also meets the given criteria."""
        state = {'done': False}

        def repl(m):
            open_tag, inner = m.group(1), m.group(2)
            if state['done'] or ('data-vendor-key="%s"' % vk) not in open_tag:
                return m.group(0)
            if require_date and d and ('>%s<' % d) not in inner:
                return m.group(0)
            if require_amount and a and ('>%s<' % a) not in inner:
                return m.group(0)
            new_open = _re.sub(r'\bcat-[a-z0-9-]+\b', new_cls, open_tag, count=1)
            if new_open == open_tag:  # row had no cat-* class yet
                if 'class="' in new_open:
                    new_open = new_open.replace('class="', 'class="%s ' % new_cls, 1)
                else:
                    new_open = ' class="%s"%s' % (new_cls, new_open)
            state['done'] = True
            return '<tr%s>%s</tr>' % (new_open, inner)

        out = _re.sub(r'<tr([^>]*)>(.*?)</tr>', repl, html, flags=_re.S)
        return out if state['done'] else None

    # Prefer the tightest match (vendor+date+amount), then loosen — always vendor-gated.
    for require_date, require_amount in ((True, True), (True, False), (False, True)):
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


def recategorize_expense(date_str, signed_amount, vendor_key, reporting_category, description='', report_path=''):
    """Persist a user's category pick for one Verified-Transactions row.

    Matches the row to an expenses row by (expense_date, abs(amount)) — the only
    reliable join, since report vendor_keys diverge from the DB id_light vendor part
    (e.g. 'circle_k_09828_cirst' vs 'circle_k_09828'). When that date/amount is shared
    by several expenses, disambiguates by vendor_key prefix then exact description.
    """
    from decimal import Decimal, InvalidOperation
    if reporting_category not in REPORTING_CATEGORY_DB_MAP:
        return {'ok': False, 'error': f'Unknown category: {reporting_category}'}
    target_id = REPORTING_CATEGORY_DB_MAP[reporting_category]

    raw_amt = str(signed_amount or '').replace('$', '').replace(',', '').strip()
    try:
        amt = abs(Decimal(raw_amt))
    except (InvalidOperation, ValueError):
        return {'ok': False, 'error': f'Bad amount: {signed_amount!r}'}

    try:
        with _rol_get_connection() as cnx:
            with cnx.cursor() as cur:
                cur.execute(
                    "SELECT id, id_light, description, category_id "
                    "FROM expenses WHERE expense_date=%s AND amount=%s",
                    (date_str, str(amt)),
                )
                rows = cur.fetchall()
                if not rows:
                    return {'ok': False,
                            'error': 'No matching expense in DB for that date/amount (bank-only row).'}

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

                cur.execute("UPDATE expenses SET category_id=%s WHERE id=%s",
                            (target_id, chosen['id']))
    except Exception as e:
        return {'ok': False, 'error': f'DB error: {e}'}

    # Persist the color into the static report.html so it survives a refresh.
    file_updated = False
    try:
        new_cls = REPORTING_CATEGORY_CLASS.get(reporting_category)
        if new_cls:
            # Match the file by the RAW displayed amount the client sent (e.g. "-$150.00",
            # "+$10.00", "296.41") — NOT the normalized abs value used for the DB lookup,
            # which would only match plain rows like "10.25".
            file_updated = _update_report_row_color(
                report_path, vendor_key, date_str, signed_amount, new_cls)
    except Exception:
        file_updated = False

    return {
        'ok': True,
        'expense_id': chosen['id'],
        'previous_category_id': chosen.get('category_id'),
        'category_id': target_id,
        'reporting_category': reporting_category,
        'file_updated': file_updated,
    }


# Letta API base URL — override with LETTA_BASE_URL env var
LETTA_BASE_URL = os.environ.get('LETTA_BASE_URL', 'http://100.80.49.10:8283').rstrip('/')

# Agents that are wired to the Letta API automatically.
# Add any new Letta agent here: { 'name': '...', 'id': '<real-letta-agent-id>' }
# Set 'id' to None to auto-discover by name from the Letta agent list.
LETTA_AGENTS = [
    {'name': 'Scissari', 'id': 'agent-5955b0c2-7922-4ffe-9e43-b116053b80fa'},
    {'name': 'Frita',    'id': 'agent-881a883f-edd0-4963-bf67-6ef178b8f018'},
    {'name': 'Hailey',   'id': 'agent-2b4f760c-e22a-4b6a-9c8d-0ace7b9bac03'},
    {'name': 'Cesare',   'id': None},
    {'name': 'Jeri',     'id': None},
    {'name': 'Mazda',    'id': None},
    {'name': 'Mazda Router', 'id': 'agent-bc561f63-a5bd-4192-806e-58d92593da2b'},
    {'name': 'Mazda Parser', 'id': 'agent-a5063757-46c7-4054-a07d-2b1263db43a8'},
    {'name': 'Mazda Vendor Identity', 'id': 'agent-acd624ac-17f2-4a74-aa34-78036cac4d66'},
    {'name': 'Mazda Receipt Linker', 'id': 'agent-9a14f800-d848-4914-bfd4-53ab62bc177b'},
    {'name': 'Mazda Categorization', 'id': 'agent-c429ff25-c8af-4f1a-a6f1-6d48307e2874'},
]

# Cache of name→id resolved from the Letta API
_letta_id_cache = {}
_letta_id_cache_lock = threading.Lock()
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
    'Cesare': {
        'identity': 'Cesare',
        'role': 'Specialized collaborative agent used in the broader multi-agent workflow.',
        'responsibilities': [
            'Handle assigned subtasks in coordinated agent workflows',
            'Contribute focused execution where routed',
        ],
        'tools': [
            'Agent messaging and task execution flows',
        ],
        'memory_summary': 'Operates as part of the shared agent network with context continuity when connected.',
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
        'key': 'letta',
        'name': 'Letta Server',
        'health_url': f'{LETTA_BASE_URL}/v1/health/',
        'log_file': LETTA_REMOTE_LOG_CACHE,
        'note': f'Letta API ({LETTA_BASE_URL}) — logs pulled periodically over SSH from '
                f'{LETTA_DOCKER_HOST} (Docker container on the Win10 box)',
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
        'health_url': 'http://100.80.49.10:8797/health',
        'note': 'Frita\'s win10_run tool backend — Docker container on Win10 box '
                '(internal :8787, published :8797); restart via "Start" button',
    },
    {
        'key': 'mazda-tools-mcp',
        'name': 'Mazda Tools MCP',
        'tcp_check': ('127.0.0.1', 8791),
        'note': 'mcp-proxy for Mazda\'s Letta tools (mazda-tools-mcp.service, :8791) — '
                'if down, Mazda\'s tool calls silently fail',
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
]

SSH_CONNECT_TIMEOUT = 6          # seconds given to `ssh` to connect + run the check command
SSH_HEALTH_POLL_INTERVAL = 30    # background poll cadence
SSH_LOG_TAIL = 50                # how many past connection-test results to keep per connection

SERVER_LOG_TAIL = 300   # how many trailing log lines to expose

# Track servers that are currently starting (for a limited time).
_starting_servers = {}  # { key: timestamp_when_started }
_starting_lock = threading.Lock()


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
    with _letta_id_cache_lock:
        if name in _letta_id_cache:
            return _letta_id_cache[name]
    data = letta_get('/v1/agents')
    if not data:
        return None
    agents = data if isinstance(data, list) else data.get('agents', [])
    with _letta_id_cache_lock:
        for a in agents:
            _letta_id_cache[a['name']] = a['id']
        return _letta_id_cache.get(name)

def get_letta_id(agent_cfg):
    """Return the real Letta agent ID for an agent config dict."""
    if agent_cfg.get('id'):
        return agent_cfg['id']
    return _resolve_letta_id(agent_cfg['name'])

def letta_messages(agent_id, limit=200):
    """Fetch all message types for an agent from the Letta API."""
    data = letta_get(f'/v1/agents/{agent_id}/messages?limit={limit}')
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

def server_health(cfg, timeout=None):
    """Ping a server's health_url or tcp_check. Returns {ok, text} (or None if neither set).

    tcp_check: (host, port) — used for MCP proxies and other non-HTTP servers that
    only need a TCP connection test (no HTTP response to parse)."""
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
        if not (cfg.get('health_url') or cfg.get('tcp_check')):
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
    if not (cfg.get('health_url') or cfg.get('tcp_check')):
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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
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


def tailscale_test(cfg, timeout=SSH_CONNECT_TIMEOUT):
    """Check a Tailscale peer's online status by scanning `tailscale status`.

    For devices with no sshd (e.g. phones) — "down" here means the device
    isn't connected to the tailnet, so any tailnet-only URL is unreachable
    from it."""
    try:
        result = subprocess.run(['tailscale', 'status'], capture_output=True, text=True, timeout=timeout)
        for line in result.stdout.splitlines():
            if line.split()[:1] == [cfg['host']]:
                if 'offline' in line:
                    return {'ok': False, 'text': line.strip()}
                return {'ok': True, 'text': line.strip()}
        return {'ok': False, 'text': f"{cfg['host']} not found in tailscale status"}
    except subprocess.TimeoutExpired:
        return {'ok': False, 'text': f'tailscale status timed out after {timeout}s'}
    except Exception as e:
        return {'ok': False, 'text': f'tailscale status failed: {e}'}


def connection_test(cfg, timeout=SSH_CONNECT_TIMEOUT):
    """Dispatch to the right health check based on cfg['check'] (default 'ssh')."""
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
            _ssh_health_cache[cfg['key']] = h
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        _record_ssh_log(cfg['key'], f"[{ts}] {'OK' if h['ok'] else 'FAIL'} — {h['text']}")


def _ssh_poll_loop():
    """Background daemon thread body: keep the SSH connection cache fresh."""
    while True:
        _poll_all_ssh_once()
        time.sleep(SSH_HEALTH_POLL_INTERVAL)


def cached_ssh_health(cfg):
    """Debounced SSH health result for cfg from the background poll loop.

    Falls back to a synchronous (slow) probe on first access, before the
    background loop has populated the cache."""
    with _ssh_health_lock:
        h = _ssh_health_cache.get(cfg['key'])
    if h is not None:
        return h
    h = connection_test(cfg)
    with _ssh_health_lock:
        _ssh_health_cache[cfg['key']] = h
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
    health = cached_server_health(cfg)
    if health is not None and health.get('ok'):
        clear_server_starting(cfg['key'])
        out['status'] = health
    elif is_server_starting(cfg['key']):
        out['status'] = {'ok': False, 'text': 'STARTING... — server startup in progress'}
    elif health is not None:
        out['status'] = health
    else:
        # No health_url to ping — fall back to "is it still writing logs?".
        log_health = log_activity_health(cfg)
        if log_health is not None:
            out['status'] = log_health

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


def build_agent_list(force_refresh=False):
    """Return the agent list for /api/agents, combining Letta agents + Claude."""
    now = time.time()
    if not force_refresh:
        with _agent_list_cache_lock:
            cached = _agent_list_cache.get('value')
            if cached is not None and now - _agent_list_cache.get('ts', 0.0) < AGENT_LIST_CACHE_TTL:
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


# ── HTTP Handler ──────────────────────────────────────────────────────────────

class DashboardHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        agent_id = query.get('agent', [''])[0]

        if path == '/api/code-status':
            return self.json_response(get_code_status())

        if path == '/api/agents':
            return self.json_response(build_agent_list(force_refresh=query.get('refresh', ['0'])[0] == '1'))

        if path == '/api/agent-activity':
            return self.json_response(agent_activity_status())

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
                {'key': s['key'], 'name': s['name'], 'note': s.get('note', '')}
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
            }
            for cfg in SERVERS:
                has_active_check = cfg.get('health_url') or cfg.get('tcp_check')
                status = None
                if has_active_check:
                    # A real "up" always wins — flip green as soon as the server
                    # actually answers, rather than waiting out the "starting" window.
                    h = cached_server_health(cfg)
                    if h.get('ok'):
                        clear_server_starting(cfg['key'])
                        status = 'up'
                    elif is_server_starting(cfg['key']):
                        status = 'starting'
                    else:
                        status = 'down'
                elif cfg.get('log_file'):
                    log_health = log_activity_health(cfg)
                    status = 'up' if (log_health and log_health.get('ok')) else 'down'

                if status is not None:
                    result['servers'].append({
                        'key': cfg['key'],
                        'name': cfg['name'],
                        'status': status,
                    })
                    if status == 'down':
                        result['any_down'] = True
                        result['all_up'] = False
            return self.json_response(result)

        if path == '/api/rol-finance-reports':
            result = []
            for r in ROL_FINANCE_REPORTS:
                report_file = os.path.join(ROL_FINANCES_REPORTS_BASE, r['dir'], 'report.html')
                exists = os.path.isfile(report_file)
                result.append({
                    'key': r['key'],
                    'label': r['label'],
                    'exists': exists,
                    'url': f'{ROL_FINANCES_REPORTS_URL_PREFIX}/{r["dir"]}/report.html' if exists else None,
                })
            return self.json_response(result)

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
            h = connection_test(cfg, timeout=8)
            with _ssh_health_lock:
                _ssh_health_cache[key] = h
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            _record_ssh_log(key, f"[{ts}] {'OK' if h['ok'] else 'FAIL'} — {h['text']} (manual test)")
            return self.json_response(h)

        if path == '/' or path == '':
            return self.serve_file(os.path.join(HERE, 'dashboard.html'), 'text/html')

        if path == ROL_FINANCES_PLAN_PATH:
            return self.serve_file(ROL_FINANCES_PLAN_FILE, 'text/html')

        if path.startswith(ROL_FINANCES_REPORTS_URL_PREFIX + '/'):
            rel = path[len(ROL_FINANCES_REPORTS_URL_PREFIX) + 1:]
            fp = os.path.abspath(os.path.join(ROL_FINANCES_REPORTS_BASE, rel))
            base = os.path.abspath(ROL_FINANCES_REPORTS_BASE)
            if os.path.commonpath([fp, base]) == base and os.path.isfile(fp):
                return self.serve_file(fp, 'text/html')
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

                return self.json_response({'ok': False, 'text': f'Unknown action: {action} for {server}'})
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)

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
                        return self.json_response({'replies': replies or [{'type': 'assistant_message', 'text': '(no reply)'}]})
                    except Exception as e:
                        return self.json_response({'replies': [{'type': 'error', 'text': str(e)}]})
                return self.json_response({'replies': [{'type': 'assistant_message', 'text': f'[stub] {agent_id} got: {text}'}]})
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
                data.get('report_path', ''),
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
                }.get(ext, 'application/octet-stream')
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(content))
            self._send_no_cache_headers()
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)

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
    threading.Thread(target=_health_poll_loop, daemon=True).start()
    print(f'Polling server health every {HEALTH_POLL_INTERVAL}s '
          f'(timeout={HEALTH_CHECK_TIMEOUT}s, fail-threshold={HEALTH_FAIL_THRESHOLD})')
    threading.Thread(target=_ssh_poll_loop, daemon=True).start()
    print(f'Polling {len(SSH_CONNECTIONS)} SSH connections every {SSH_HEALTH_POLL_INTERVAL}s')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
