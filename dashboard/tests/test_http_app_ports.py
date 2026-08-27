"""Round 12: the port mechanism, and the death of the free `srv` name.

Three things are pinned here, in rising order of how expensive they are to get
wrong:

1. `current_ports()` hands the routes the *real* collaborators (rule 4).
2. It resolves them *per call*. Cache the bundle at import and every
   `monkeypatch.setattr(server, ...)` in this suite silently starts lying —
   the tests keep passing while testing a function nobody runs.
3. The names round 12 dropped stay dropped, and the `srv.` count in
   `http_app/` never goes back up.

Point 3 is the one that decays without a test. Every earlier round paid a
re-export tax: move a function out of `server.py`, and the route still says
`srv.the_name`, so the name has to stay behind as an import. Forty-seven of
those had accumulated by round 11 — names `server.py` defined nothing for and
merely held. Round 15 adding two `srv.` calls back would quietly restart the
meter, and nothing else in the suite would notice.
"""
import ast
import glob
import os
import re

import pytest

import server
from http_app import ports
from http_app.registry import Ports, current_ports


# ── the mechanism ───────────────────────────────────────────────────────────

class TestProductionWiresTheRealObjects:
    """Rule 4: prove the container hands over the real thing, not that the
    bundle merely has the right number of fields."""

    def test_the_scanner_port_reaches_the_real_scanner_functions(self):
        port = current_ports().scanner
        assert port.status('window') == server.scanner_status('window')
        assert port.image_url_prefix == server.SCANNER_IMAGE_URL_PREFIX

    def test_image_path_joins_the_real_scan_directory(self):
        expected = os.path.join(
            server.SCAN_TOOLS_DIR, server.SCANNERS['window']['output'])
        assert current_ports().scanner.image_path('window') == expected

    def test_an_unknown_scanner_has_no_image_path(self):
        """The route turns None into a 404. A path built from a missing spec
        would be `SCAN_TOOLS_DIR/None` — a file that never exists, which is a
        404 too, but by accident and with a traceback's worth of noise first."""
        assert current_ports().scanner.image_path('atari-2600') is None

    def test_the_bundle_is_frozen(self):
        """A route that could rebind a port would be a service locator with
        extra steps."""
        with pytest.raises(Exception):
            current_ports().scanner = object()


class TestResolvedPerCall:
    """The late binding the whole HTTP test suite rests on."""

    def test_a_rebound_server_function_is_seen_by_the_next_call(self, monkeypatch):
        monkeypatch.setattr(server, 'scanner_status', lambda key: {'sentinel': key})
        assert current_ports().scanner.status('freezer') == {'sentinel': 'freezer'}

    def test_a_port_built_before_the_rebind_still_sees_it(self, monkeypatch):
        """Constructed early, called late — the case a route hits when it holds
        the bundle across a few lines of a handler."""
        port = current_ports().scanner
        monkeypatch.setattr(server, 'run_scanner', lambda key: {'late': True})
        assert port.run('window') == {'late': True}

    def test_each_call_builds_a_fresh_bundle(self):
        assert current_ports() is not current_ports()

    def test_the_registry_never_captures_the_server_module(self):
        """`import server` at module scope in http_app is a cycle (server.py
        imports http_app from its own tail) *and* a snapshot. The one legal
        reach is inside a function."""
        tree = ast.parse(open('http_app/registry.py').read())
        for node in tree.body:
            assert not (isinstance(node, ast.Import)
                        and any(a.name == 'server' for a in node.names))
            assert not (isinstance(node, ast.ImportFrom) and node.module == 'server')


class TestThePortVocabulary:
    """Fourteen ports, no fifteenth. A grab-bag `MiscPort` is `srv` renamed."""

    def test_every_declared_port_is_a_protocol(self):
        declared = [v for k, v in vars(ports).items()
                    if k.endswith('Port') and isinstance(v, type)]
        assert len(declared) == 14
        for port in declared:
            assert getattr(port, '_is_protocol', False), f'{port.__name__} is not a Protocol'

    def test_the_bundle_only_carries_ports_that_are_populated(self):
        """A field per *populated* port. An empty adapter built per request for
        a port nobody calls yet would answer no question.

        Round 12 populated `scanner`; round 13 added the config halves of
        `reports`, `servers` and `agents`. The remaining ten are declared in
        ports.py and stay out of the bundle until the round that fills them.
        """
        assert set(Ports.__dataclass_fields__) == {
            'scanner', 'reports', 'servers', 'agents'}


# ── the tax that must not come back ─────────────────────────────────────────

#: The 38 names round 12 deleted from server.py: names it imported but never
#: itself used, held only so a route could say `srv.<name>`. Nine more of the
#: 47 free names stayed, because server.py genuinely calls them (HERE,
#: LETTA_BASE_URL, REPO_ROOT, SSH_CONNECTIONS, ValidationError, manual_entry,
#: model_stats, render_excel_for_browser, claude_sdk_account_payload) — the
#: routes stopped reaching through `server` for those too, but the import is
#: doing real work, so it is not a re-export.
DROPPED = [
    'ChatGptProviderSwapRequest', 'CodexSyncRequest', 'CodexSyncToggleRequest',
    'MODEL_STAT_SOURCES', 'ModelStatsMuteRequest', 'NoteEditRequest',
    'PC_MONITORS', 'PartialVoiceCommand', 'WIN10_CONTAINERS',
    '_TERMINAL_ID_RE', '_msg_text', '_terminal_reap', '_terminal_spawn_shell',
    'apply_mute_overlay', 'build_pipeline', 'build_receptionist_strategy',
    'cached_ssh_health', 'classify_failure', 'clear_server_starting',
    'codex_sync_status', 'connection_log_rows', 'container_status_for',
    'get_ssh_connection', 'handle_voice_upload', 'log_activity_health',
    'note_command_service', 'pc_metrics', 'run_codex_sync_now',
    'run_manual_ssh_test', 'set_claude_sdk_account', 'set_muted',
    'statement_review', 'toggle_codex_sync', 'track_down_duration',
    'win10_container_states', 'ws_accept_key', 'ws_encode_frame',
    'ws_read_frame',
]


@pytest.mark.parametrize('name', DROPPED)
def test_a_dropped_re_export_cannot_creep_back(name):
    """Rule 6. A re-export is a second binding: code that closed over the
    owning module's global keeps running while `monkeypatch.setattr(server,
    name, ...)` lands on the copy — a test that passes while testing nothing.
    """
    assert not hasattr(server, name), (
        f'server.{name} is back. If a route needs it, that is a port method; '
        f'if server.py needs it, say so here and move it off this list.')


def _srv_references():
    """Every `srv.<name>` in the HTTP layer, as (file, name) pairs.

    Counted from source rather than from the imported modules because the point
    is the *text* the next round writes, not what it resolves to.
    """
    found = []
    for path in sorted(glob.glob('http_app/*.py')):
        if path.endswith('services.py'):
            continue          # its own docstring is the usage example
        src = open(path).read()
        found += [(path, m) for m in re.findall(r'\bsrv\.([A-Za-z_]\w*)', src)]
    return found


#: Measured at the end of round 13, down from round 12's 147 / 116 and round
#: 11's 220 / 167. These are ceilings, not targets: every later round should
#: push them down as it converts its own port. A rise means someone reached for
#: a free name instead of adding a port method — rule 13, and a failing build.
#:
#: Round 13 lowered them by eight names: the config it moved out
#: (SERVERS, RESTARTABLE_KEYS, LETTA_AGENTS, ROL_FINANCES_REPORTS_MONTHS,
#: ROL_FINANCES_REPORTS_DEFAULT_MONTH, ROL_FINANCES_REPORTS_URL_PREFIX,
#: _rol_finance_reports_for_month) plus get_letta_id, which left with the
#: receptionist lookup that was its only caller in the ladder.
#:
#: It also absorbed a rise it did not cause: a parallel feature added
#: `srv._resolve_expense_receipt_path` in e96ace55 without lowering anything,
#: which had this file failing on arrival. That name belongs to DocumentPort
#: and leaves in round 20.
SRV_SITE_CEILING = 134
SRV_NAME_CEILING = 109


class TestTheSrvCountOnlyEverFalls:
    def test_no_new_srv_call_sites(self):
        sites = _srv_references()
        assert len(sites) <= SRV_SITE_CEILING, (
            f'{len(sites)} `srv.` sites, ceiling {SRV_SITE_CEILING}. Round 12 '
            f'exists to make this number fall. Add a port method instead, then '
            f'lower the ceiling.')

    def test_no_new_srv_names(self):
        names = {n for _, n in _srv_references()}
        assert len(names) <= SRV_NAME_CEILING, (
            f'{len(names)} distinct `srv.` names, ceiling {SRV_NAME_CEILING}.')

    def test_the_ceiling_is_kept_honest(self):
        """A ceiling nobody lowers becomes a lie the next round inherits. If
        this fails, the count fell — edit the two constants down."""
        sites = _srv_references()
        names = {n for _, n in sites}
        assert (len(sites), len(names)) == (SRV_SITE_CEILING, SRV_NAME_CEILING), (
            'the `srv.` count moved; update SRV_SITE_CEILING/SRV_NAME_CEILING '
            f'to ({len(sites)}, {len(names)})')

    def test_the_scanner_tab_no_longer_reaches_through_srv(self):
        """Round 12's worked example, asserted where it can regress."""
        scanner_names = {
            'SCANNERS', 'SCAN_TOOLS_DIR', 'SCANNER_IMAGE_URL_PREFIX',
            'run_scanner', 'scanner_status', 'scanner_diagnostics',
            'clear_scanner_verification_lock', 'fix_deskjet_printer',
        }
        assert scanner_names & {n for _, n in _srv_references()} == set()

    def test_the_config_round_13_moved_no_longer_reaches_through_srv(self):
        """Round 13's own conversions, asserted where they can regress."""
        config_names = {
            'SERVERS', 'RESTARTABLE_KEYS', 'LETTA_AGENTS', 'get_letta_id',
            'ROL_FINANCES_REPORTS_MONTHS', 'ROL_FINANCES_REPORTS_DEFAULT_MONTH',
            'ROL_FINANCES_REPORTS_URL_PREFIX', '_rol_finance_reports_for_month',
        }
        assert config_names & {n for _, n in _srv_references()} == set()


def test_the_registry_is_the_only_http_app_module_that_names_server():
    """`services.py` is the old locator and `registry.py` is the new one. Any
    third module reaching for `server` means the seam leaked."""
    offenders = []
    for path in sorted(glob.glob('http_app/*.py')):
        if os.path.basename(path) in ('services.py', 'registry.py'):
            continue
        if re.search(r'''\bsys\.modules\[['"]server['"]\]|import_module\(['"]server['"]\)''',
                     open(path).read()):
            offenders.append(path)
    assert offenders == []


def test_registry_and_ports_import_before_server_exists():
    """Same cycle rule as every other mixin: server.py imports http_app from
    its own tail, so neither of these may pull `server` in at import."""
    import subprocess
    import sys
    out = subprocess.run(
        [sys.executable, '-c',
         'import http_app.ports, http_app.registry, sys; '
         'assert "server" not in sys.modules; print("ok")'],
        cwd='.', capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, out.stderr[-2000:]
    assert 'ok' in out.stdout


def test_registry_is_not_imported_into_server():
    """The dependency points one way. server.py builds nothing here yet, and
    when it does (the container, round 23 onward) it will hand objects *to*
    the registry, not import it."""
    assert 'registry' not in {
        (a.asname or a.name).split('.')[-1]
        for node in ast.parse(open('server.py').read()).body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for a in node.names}
