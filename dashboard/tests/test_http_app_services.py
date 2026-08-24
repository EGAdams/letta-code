"""The `srv` late-binding handle — the load-bearing trick in the HTTP layer.

Two properties have to hold or the refactor silently breaks things:

1. No import cycle. server.py imports http_app from its tail, so a route mixin
   must never `import server` at module scope.
2. Late binding. `from server import foo` would snapshot 180-odd names at import
   time, which would quietly neuter every `monkeypatch.setattr(server, ...)` in
   this suite — the failure mode being tests that keep passing while testing
   a stale function.
"""
import ast
import subprocess
import sys
import textwrap

import pytest

import server
from http_app import services as srv


class TestLateBinding:
    def test_reads_a_current_value_from_server(self):
        assert srv.LETTA_BASE_URL == server.LETTA_BASE_URL

    def test_sees_a_rebind_that_happens_after_import(self, monkeypatch):
        monkeypatch.setattr(server, 'LETTA_BASE_URL', 'http://rebound:1234')
        assert srv.LETTA_BASE_URL == 'http://rebound:1234'

    def test_monkeypatched_functions_are_visible(self, monkeypatch):
        monkeypatch.setattr(server, 'get_code_status', lambda: {'sentinel': True})
        assert srv.get_code_status() == {'sentinel': True}

    def test_the_rebind_is_undone_with_the_monkeypatch(self, monkeypatch):
        original = server.LETTA_BASE_URL
        monkeypatch.setattr(server, 'LETTA_BASE_URL', 'http://temporary')
        monkeypatch.undo()
        assert srv.LETTA_BASE_URL == original

    def test_resolution_happens_per_access_not_once(self, monkeypatch):
        monkeypatch.setattr(server, 'LETTA_BASE_URL', 'http://first')
        first = srv.LETTA_BASE_URL
        monkeypatch.setattr(server, 'LETTA_BASE_URL', 'http://second')
        assert (first, srv.LETTA_BASE_URL) == ('http://first', 'http://second')

    def test_modules_reached_through_server_still_work(self):
        # Routes call things like srv.manual_entry.<fn> and srv.statement_review.<fn>.
        assert srv.manual_entry is server.manual_entry
        assert srv.statement_review is server.statement_review

    def test_mutable_module_state_is_shared_not_copied(self):
        # e.g. srv._scan_dispatch_claims must be the *same* dict server mutates.
        assert srv._scan_dispatch_claims is server._scan_dispatch_claims


class TestMissingNames:
    def test_an_unknown_name_raises_attribute_error(self):
        with pytest.raises(AttributeError):
            srv.definitely_not_a_dashboard_service

    def test_the_error_says_where_to_look(self):
        """A typo'd service name during the refactor should name the file to fix."""
        with pytest.raises(AttributeError, match=r'server\.py defines no'):
            srv.definitely_not_a_dashboard_service

    def test_the_missing_name_is_in_the_message(self):
        with pytest.raises(AttributeError, match='hopefully_absent'):
            srv.hopefully_absent

    def test_a_name_added_to_server_later_resolves(self, monkeypatch):
        monkeypatch.setattr(server, 'brand_new_service', lambda: 'hi', raising=False)
        assert srv.brand_new_service() == 'hi'


class TestNoImportCycle:
    """Each mixin must import cleanly *first*, with `server` not yet loaded."""

    @pytest.mark.parametrize('module', [
        'http_app.services',
        'http_app.models',
        'http_app.runtime',
        'http_app.transport',
        'http_app.terminal_ws',
        'http_app.get_routes',
        'http_app.post_routes',
        'http_app.handler',
        'http_app',
    ])
    def test_importing_it_before_server_does_not_deadlock(self, module):
        code = f'import {module}; print("ok")'
        out = subprocess.run([sys.executable, '-c', code], cwd='.',
                             capture_output=True, text=True, timeout=180)
        assert out.returncode == 0, out.stderr[-2000:]
        assert 'ok' in out.stdout

    def test_server_first_then_handler_also_works(self):
        code = 'import server; from http_app.handler import DashboardHandler; print("ok")'
        out = subprocess.run([sys.executable, '-c', code], cwd='.',
                             capture_output=True, text=True, timeout=180)
        assert out.returncode == 0, out.stderr[-2000:]

    def test_no_mixin_imports_server_at_module_scope(self):
        """The rule that keeps the cycle impossible — enforced, not just documented."""
        offenders = []
        for name in ('transport', 'terminal_ws', 'get_routes', 'post_routes',
                     'handler', 'runtime', 'models', '__init__'):
            tree = ast.parse(open(f'http_app/{name}.py').read())
            for node in tree.body:            # module scope only
                if isinstance(node, ast.Import):
                    if any(a.name == 'server' for a in node.names):
                        offenders.append(name)
                if isinstance(node, ast.ImportFrom) and node.module == 'server':
                    offenders.append(name)
        assert offenders == [], f'module-scope `import server` in: {offenders}'
