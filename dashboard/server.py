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
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)

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

    fallback_types = {
        'assistant_message': 'assistant',
        'tool_call_message': 'tool',
        'tool_return_message': 'tool',
        'approval_request_message': 'approval',
        'approval_response_message': 'approval',
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

def letta_convo(agent_id):
    msgs = letta_messages(agent_id, limit=200)
    rows = []
    for m in msgs:
        mt = m.get('message_type', '')
        if mt not in ('user_message', 'assistant_message'):
            continue
        text = _msg_text(m)
        if not text.strip():
            continue
        rows.append({
            'date': _msg_date(m),
            'type': mt,
            'text': text[:400],
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
            ts = ts.replace(tzinfo=timezone.utc)
        return (now - ts).total_seconds()
    except Exception:
        return None


def agent_activity_status():
    """Return {agent_id: 'active'|'error'|'idle'} for every configured Letta agent."""
    now = datetime.now(timezone.utc)
    results = {}
    for cfg in LETTA_AGENTS:
        real_id = get_letta_id(cfg)
        dash_id = real_id or f'unknown-{cfg["name"].lower()}'
        if not real_id:
            results[dash_id] = 'idle'
            continue
        msgs = letta_messages(real_id, limit=5)
        if not msgs:
            results[real_id] = 'idle'
            continue
        # Sort ascending so last item is most recent message
        msgs_sorted = sorted(msgs, key=lambda m: str(m.get('created_at') or m.get('date') or ''))
        last = msgs_sorted[-1]
        age = _msg_age_seconds(last, now)
        if age is None or age > 60:
            results[real_id] = 'idle'
            continue
        mt = last.get('message_type', '')
        if mt in ('user_message', 'tool_call_message', 'reasoning_message'):
            results[real_id] = 'active'
        elif mt == 'tool_return_message':
            tr = last.get('tool_return', {})
            if isinstance(tr, dict) and tr.get('status') == 'error':
                results[real_id] = 'error'
            else:
                results[real_id] = 'active'
        else:
            # assistant_message or unknown — agent just finished responding
            results[real_id] = 'idle'
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

        if path == '/api/agents':
            return self.json_response(build_agent_list(force_refresh=query.get('refresh', ['0'])[0] == '1'))

        if path == '/api/agent-activity':
            return self.json_response(agent_activity_status())

        if path == '/api/thoughts':
            if agent_id == 'agent-claude':
                return self.json_response([])   # Claude Code doesn't have thoughts
            lid = letta_id_for(agent_id)
            if lid:
                return self.json_response(letta_thoughts(lid))
            return self.json_response([])

        if path == '/api/messages':
            if agent_id == 'agent-claude':
                return self.json_response(_load_json(CLAUDE_LOG_FILE))
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
                        f'{LETTA_BASE_URL}/v1/agents/{lid}/messages/clear?agent_id={quote(lid, safe="")}',
                        data=b'',
                        method='POST',
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
                        return self.json_response({'replies': replies or [{'type': 'assistant_message', 'text': '(no reply)'}]})
                    except Exception as e:
                        return self.json_response({'replies': [{'type': 'error', 'text': str(e)}]})
                return self.json_response({'replies': [{'type': 'assistant_message', 'text': f'[stub] {agent_id} got: {text}'}]})
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)

        self.send_error(404)

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length).decode('utf-8')

    def _handle_voice(self, raw):
        """Transcribe (whisper.cpp) + clean (Letta agent) an uploaded audio blob.

        Delivery to the main agent is left to the client (it reuses /api/test),
        so this endpoint only ever returns {ok, raw_transcript, cleaned_text}.
        """
        try:
            from voice import build_pipeline, handle_voice_upload
        except Exception as exc:  # voice package missing/broken — fail soft
            return self.json_response({'ok': False, 'error': f'voice unavailable: {exc}'})
        filename = self.headers.get('X-Filename') or 'audio.webm'
        result = handle_voice_upload(build_pipeline(), raw, filename)
        if result.get('ok'):
            _append_json(VOICE_LOG_FILE, _voice_log_lock, {
                'date': datetime.now().isoformat(),
                'raw': result.get('raw_transcript', ''),
                'cleaned': result.get('cleaned_text', ''),
            })
        return self.json_response(result)

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
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
