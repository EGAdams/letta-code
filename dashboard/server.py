#!/usr/bin/env python3
"""
Dashboard SPA server.
Serves dashboard.html and proxies agent data from the Letta API.
Run: python3 server.py   (from /home/adamsl/letta-code/dashboard/)
Then open: http://localhost:8765/
"""
import json
import os
import threading
import urllib.request
import urllib.error
from datetime import datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)

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
]

# Cache of name→id resolved from the Letta API
_letta_id_cache = {}
_letta_id_cache_lock = threading.Lock()

# Claude Code log files (persistent, local)
CLAUDE_LOG_FILE = os.path.join(HERE, 'claude_messages.json')
CLAUDE_TOOL_LOG_FILE = os.path.join(HERE, 'claude_toolcalls.json')
_claude_log_lock = threading.Lock()
_claude_tool_log_lock = threading.Lock()

# Voice transcripts (raw whisper vs. cleaned) — for diagnosing mishears.
VOICE_LOG_FILE = os.path.join(HERE, 'voice_transcripts.json')
_voice_log_lock = threading.Lock()


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


# ── Agent registry ────────────────────────────────────────────────────────────

def build_agent_list():
    """Return the agent list for /api/agents, combining Letta agents + Claude."""
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
            return self.json_response(build_agent_list())

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

        if path == '/' or path == '':
            return self.serve_file(os.path.join(HERE, 'dashboard.html'), 'text/html')

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
                        with urllib.request.urlopen(req, timeout=30) as r:
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
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
