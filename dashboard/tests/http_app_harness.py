"""Shared harness: a real DashboardHandler on a real socket, with the service
layer stubbed out.

Why a live server rather than a fake handler object: the point of these tests is
to survive the route-registry refactor, so they must assert on what a *browser*
observes (status code, headers, body) and know nothing about how the handler
dispatches internally. A test that pokes at `do_GET`'s if/elif ladder would be
worthless the moment that ladder becomes a registry.

Why the service layer is stubbed: these routes restart systemd units, SSH to
other machines, drive scanners and talk to the live Letta API. `srv` resolves
names at call time, so monkeypatching `server` is enough to make all of that
inert — which is also a standing proof that the late-binding handle works.
"""
import http.client
import importlib
import inspect
import json
import os as _os
import threading
import urllib.error

import server
from http_app.handler import DashboardHandler
from http_app.runtime import ReusableHTTPServer

# Names on `server` that must survive stubbing: Pydantic request models and
# validation classes the routes construct, plus submodules they reach through.
DO_NOT_STUB = {
    'ChatGptProviderSwapRequest', 'CodexSyncRequest', 'CodexSyncToggleRequest',
    'ModelStatsMuteRequest', 'NoteEditRequest', 'PartialVoiceCommand',
    'ValidationError', 'taxonomy_category_namer',
}


class RecordedCall(dict):
    """A stub's return value: an empty dict, so callers can .get()/iterate it."""


class FakeModel:
    """Stands in for a Pydantic result object a route calls .model_dump() on."""

    def __init__(self, payload=None):
        self._payload = payload if payload is not None else {'ok': True}

    def model_dump(self, mode=None):
        return dict(self._payload)

    def model_dump_json(self):
        return json.dumps(self._payload)


class FakeStrategy:
    """Stands in for the receptionist / note-command strategy objects."""

    def __init__(self, result=None, wrap_model=False):
        self._result = result if result is not None else {'ok': True}
        self._wrap_model = wrap_model
        self.calls = []

    def evaluate(self, *args, **kwargs):
        self.calls.append(('evaluate', args, kwargs))
        return dict(self._result)

    def assess(self, *args, **kwargs):
        self.calls.append(('assess', args, kwargs))
        return FakeModel(self._result)

    def classify(self, *args, **kwargs):
        self.calls.append(('classify', args, kwargs))
        return dict(self._result)


def default_returns():
    """Return shapes the routes genuinely destructure.

    A blanket `{}` stub is enough for most of the 95 routes, but a handful
    immediately call .model_dump() on the result, unpack a tuple, or reach for a
    strategy method. Those are contracts between a route and its service, so
    they are spelled out here rather than papered over.
    """
    import server as _server
    an_existing_file = _os.path.join(_server.HERE, 'dashboard.html')
    return {
        # (down_for, stale) — unpacked directly by /api/server-health
        'track_down_duration': lambda *a, **k: (0, False),
        # Pydantic results the routes serialise with .model_dump()
        'codex_sync_status': lambda *a, **k: FakeModel({'ok': True, 'sources': []}),
        'run_codex_sync_now': lambda *a, **k: FakeModel({'ok': True}),
        'toggle_codex_sync': lambda *a, **k: FakeModel({'ok': True}),
        'get_chatgpt_provider_account_status': lambda *a, **k: FakeModel({'ok': True}),
        'set_chatgpt_provider_account': lambda *a, **k: FakeModel({'ok': True}),
        # Strategy objects
        'build_receptionist_strategy': lambda *a, **k: FakeStrategy(),
        'note_command_service': lambda *a, **k: FakeStrategy(),
        # Routes that serve a file and 404 when the lookup comes back empty
        '_report_source_document_view': lambda *a, **k: an_existing_file,
    }


#: What the route ladders call that does not live in server.py.
#:
#: Round 12 pointed the ladders at the module that owns each name, so
#: monkeypatching `server` no longer makes those calls inert — and an unstubbed
#: one here means a route test SSHes to another box, drives a scanner, or runs
#: whisper. Each entry is `module path -> the names that module owns`, and the
#: stub is recorded under the bare name, so `stubbed.called('pc_metrics')` reads
#: the same whichever side of the move it is written on.
#:
#: Add to this whenever a round converts an `srv.` name to a direct import. The
#: symptom of forgetting is not a red test — it is a green one that took 30
#: seconds and touched the network.
DIRECT_SERVICES = {
    'agent_thoughts': ('message_text',),
    'codex_sync_status': ('codex_sync_status', 'run_codex_sync_now',
                          'toggle_codex_sync'),
    'document_annotation': ('render_excel_for_browser',),
    'health.failures': ('classify_failure',),
    'health.frita': ('claude_sdk_account_payload', 'set_claude_sdk_account'),
    'model_stats.reader': ('model_stats',),
    'model_stats_mute': ('apply_mute_overlay', 'set_muted'),
    'monitoring.log_files': ('log_activity_health',),
    'monitoring.pc_metrics': ('pc_metrics',),
    'monitoring.server_lifecycle': ('clear_server_starting',
                                    'track_down_duration'),
    'monitoring.ssh_checks': ('cached_ssh_health', 'connection_log_rows',
                              'get_ssh_connection', 'run_manual_test'),
    'monitoring.win10_node': ('container_status_for', 'win10_container_states'),
    'voice.note_factory': ('note_command_service',),
    'voice.pipeline': ('build_pipeline', 'handle_voice_upload'),
    'voice.receptionist': ('build_receptionist_strategy',),
}


class ServiceRecorder:
    """Replaces every server.py *function* with a recording no-op."""

    def __init__(self):
        self.calls = []

    #: modules the routes reach into wholesale (manual_entry.foo(), and the
    #: statement-review verbs) rather than by a name-at-a-time import
    SUBMODULES = ('finance.manual_entry', 'statement_review')

    def install(self, monkeypatch, returns=None):
        merged = default_returns()
        merged.update(returns or {})
        returns = merged
        self._install_submodules(monkeypatch, returns)
        self._install_direct_services(monkeypatch, returns)
        for name in dir(server):
            if name in DO_NOT_STUB or name.startswith('__'):
                continue
            obj = getattr(server, name, None)
            # Functions only: classes, modules, locks, dicts and lists are data
            # the routes merely read, and replacing them changes route meaning.
            if not inspect.isfunction(obj):
                continue
            monkeypatch.setattr(server, name, self._stub(name, returns))
        for name, value in returns.items():
            if not inspect.isfunction(getattr(server, name, None)):
                monkeypatch.setattr(server, name, value, raising=False)

    def _install_submodules(self, monkeypatch, returns):
        """Routes call manual_entry.foo() / statement_review.foo(); real I/O too."""
        for path in self.SUBMODULES:
            module = importlib.import_module(path)
            short = path.rsplit('.', 1)[-1]
            for attr in dir(module):
                if attr.startswith('__'):
                    continue
                if inspect.isfunction(getattr(module, attr, None)):
                    key = f'{short}.{attr}'
                    monkeypatch.setattr(module, attr, self._stub(key, returns))

    def _install_direct_services(self, monkeypatch, returns):
        """Stub the owning module for every name the ladders import directly."""
        for path, names in DIRECT_SERVICES.items():
            module = importlib.import_module(path)
            for attr in names:
                if not inspect.isfunction(getattr(module, attr, None)):
                    continue
                monkeypatch.setattr(module, attr, self._stub(attr, returns))

    def _stub(self, name, returns):
        def stub(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            result = returns.get(name, RecordedCall())
            return result(*args, **kwargs) if callable(result) else result
        stub.__name__ = f'stub_{name}'
        return stub

    def names(self):
        return [c[0] for c in self.calls]

    def called(self, name):
        return name in self.names()

    def args_for(self, name):
        return next((a for n, a, _ in self.calls if n == name), None)

    def kwargs_for(self, name):
        return next((k for n, _, k in self.calls if n == name), None)


class DashboardClient:
    """Minimal HTTP client bound to a live handler instance."""

    def __init__(self, port):
        self.port = port

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
        try:
            payload = None
            hdrs = dict(headers or {})
            if body is not None:
                payload = body if isinstance(body, (bytes, str)) else json.dumps(body)
                if isinstance(payload, str):
                    payload = payload.encode('utf-8')
                hdrs.setdefault('Content-Type', 'application/json')
            conn.request(method, path, body=payload, headers=hdrs)
            resp = conn.getresponse()
            return Response(resp.status, dict(resp.getheaders()), resp.read())
        finally:
            conn.close()

    def get(self, path, **kw):
        return self.request('GET', path, **kw)

    def post(self, path, body=None, **kw):
        return self.request('POST', path, body=body if body is not None else {}, **kw)


class Response:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self.body = body

    @property
    def text(self):
        return self.body.decode('utf-8', 'replace')

    @property
    def json(self):
        return json.loads(self.text)

    def __repr__(self):
        return f'<Response {self.status} {self.body[:80]!r}>'


def start_server():
    """Bind an ephemeral port and serve DashboardHandler on a daemon thread."""
    httpd = ReusableHTTPServer(('127.0.0.1', 0), DashboardHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread, httpd.server_address[1]


class FakeHTTPResponse:
    """Stands in for urlopen's context manager in the routes that PATCH Letta."""

    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self, *a):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeUrllib:
    """Replaces post_routes' `urllib`, keeping the real exception classes.

    The routes catch urllib.error.HTTPError by identity, so the fake must reuse
    the real module for `.error` while intercepting `.request.urlopen`.
    """

    error = urllib.error

    def __init__(self, payload=None, raises=None):
        self.calls = []
        self.request = _FakeRequestModule(self, payload, raises)


class _FakeRequestModule:
    def __init__(self, parent, payload, raises):
        self._parent = parent
        self._payload = payload if payload is not None else {}
        self._raises = raises

    def Request(self, url, data=None, headers=None, method=None):
        record = {'url': url, 'data': data, 'headers': headers, 'method': method}
        self._parent.calls.append(record)
        return record

    def urlopen(self, req, timeout=None):
        if self._raises is not None:
            raise self._raises
        return FakeHTTPResponse(self._payload)
