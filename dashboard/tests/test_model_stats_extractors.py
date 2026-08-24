"""The three usage extractors: 220 lines of Python that nothing was checking.

These programs run on the machine being measured, reached over SSH or run
locally, and are carried there as string literals. Nothing imports them, so
`bun run lint`, pytest collection and the interpreter itself all skip straight
past them -- a stray colon or an unbalanced quote in the Codex extractor would
first show up as a grey card on the dashboard, with no traceback anywhere,
because `_run_extractor` turns every failure into `{'error': ...}` by design.

So these tests compile all three and pin the contract they share: exactly one
JSON object on stdout, an `error` key rather than a crash, and no writes to the
machine being measured. Two of them are then actually executed against a fake
home directory, which is the only way to find out whether they parse what they
claim to parse.
"""
import ast
import builtins
import datetime
import json
import os
import subprocess
import sys

import pytest
from zoneinfo import ZoneInfo

import server
from model_stats import extractors


SCRIPTS = {
    'codex': extractors._CODEX_EXTRACT_PY,
    'claude': extractors._CLAUDE_EXTRACT_PY,
    'gemini': extractors._GEMINI_FLASH_FILL_EXTRACT_PY,
}


def run_script(source, home, env=None, timeout=20):
    """Execute one extractor with HOME pointed at a fixture directory."""
    environ = dict(os.environ)
    environ['HOME'] = str(home)
    environ.update(env or {})
    proc = subprocess.run([sys.executable, '-'], input=source, env=environ,
                          capture_output=True, text=True, timeout=timeout)
    return proc


class TestTheyAreValidPython:
    """The check the interpreter never gets to make."""

    @pytest.mark.parametrize('name', sorted(SCRIPTS))
    def test_it_compiles(self, name):
        compile(SCRIPTS[name], f'<{name}>', 'exec')

    @pytest.mark.parametrize('name', sorted(SCRIPTS))
    def test_every_name_it_uses_is_imported_or_defined(self, name):
        """A missing `import time` only surfaces on the unlucky code path."""
        tree = ast.parse(SCRIPTS[name])
        bound = set(dir(builtins))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                bound |= {(a.asname or a.name).split('.')[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                bound |= {a.asname or a.name for a in node.names}
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                bound.add(getattr(node, 'name', '<lambda>'))
                args = node.args
                bound |= {a.arg for a in
                          args.posonlyargs + args.args + args.kwonlyargs}
                if args.vararg:
                    bound.add(args.vararg.arg)
                if args.kwarg:
                    bound.add(args.kwarg.arg)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                bound.add(node.id)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                bound.add(node.name)
        used = {n.id for n in ast.walk(tree)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        assert used <= bound, f'undefined in {name}: {sorted(used - bound)}'

    @pytest.mark.parametrize('name', sorted(SCRIPTS))
    def test_it_ends_by_printing_json(self, name):
        """One JSON blob on stdout is the entire wire protocol."""
        tree = ast.parse(SCRIPTS[name])
        last = tree.body[-1]
        assert isinstance(last, ast.Expr)
        assert ast.unparse(last).startswith('print(json.dumps(')

    @pytest.mark.parametrize('name', sorted(SCRIPTS))
    def test_every_print_it_makes_is_the_json_payload(self, name):
        """The Claude extractor has an early-exit path, so "one print" is not
        the rule -- "every print is the payload" is. A stray debug print would
        become the line _run_extractor parses and silently replace the reading.
        """
        prints = [n for n in ast.walk(ast.parse(SCRIPTS[name]))
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == 'print']
        assert prints
        for call in prints:
            assert ast.unparse(call).startswith('print(json.dumps(')

    def test_the_claude_early_exit_stops_rather_than_printing_twice(self):
        """Two JSON lines and _run_extractor would parse the wrong one."""
        source = SCRIPTS['claude']
        early = [ln for ln in source.split('\n') if 'print(json.dumps' in ln]
        assert len(early) == 2, 'update this test if the paths changed'
        assert 'SystemExit' in early[0], 'the early path must not fall through'

    @pytest.mark.parametrize('name', sorted(SCRIPTS))
    def test_it_never_deletes_anything(self, name):
        """These read a live account belonging to a person, over SSH."""
        for forbidden in ('os.remove', 'os.unlink', 'shutil.rmtree', 'os.rmdir',
                          'os.truncate'):
            assert forbidden not in SCRIPTS[name], f'{name}: {forbidden}'

    @pytest.mark.parametrize('name, target', [
        ('codex', 'AUTH'), ('claude', 'CRED'),
    ])
    def test_the_only_file_it_writes_is_the_credential_it_refreshed(self, name, target):
        """These two do write, deliberately: refreshing an OAuth token yields a
        new one, and dropping it would force a re-auth on the next reading.
        Pinned because a write to anything *else* on mom's machine, from a
        panel that only claims to report usage, would be a genuine surprise.
        """
        writes = [ast.unparse(n) for n in ast.walk(ast.parse(SCRIPTS[name]))
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == 'open' and len(n.args) > 1]
        assert writes == [f"open({target}, 'w')"]

    def test_the_gemini_extractor_writes_nothing_at_all(self):
        """It only counts lines in a log another process wrote."""
        writes = [n for n in ast.walk(ast.parse(SCRIPTS['gemini']))
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == 'open' and len(n.args) > 1]
        assert writes == []

    @pytest.mark.parametrize('name', sorted(SCRIPTS))
    def test_it_targets_the_running_users_home(self, name):
        """Hard-coded /home/adamsl would measure the wrong account on R46."""
        assert '/home/adamsl' not in SCRIPTS[name]
        assert 'expanduser' in SCRIPTS[name]


class TestTheyFailSoft:
    """A missing CLI is 'not configured', never a traceback."""

    @pytest.mark.parametrize('name', sorted(SCRIPTS))
    def test_an_empty_home_still_yields_one_json_line(self, name, tmp_path):
        proc = run_script(SCRIPTS[name], tmp_path)
        assert proc.returncode == 0, proc.stderr
        lines = proc.stdout.strip().splitlines()
        assert len(lines) == 1, f'stdout must carry one blob, got {lines}'
        assert isinstance(json.loads(lines[0]), dict)

    @pytest.mark.parametrize('name', sorted(SCRIPTS))
    def test_an_empty_home_reports_not_configured_rather_than_usage(self, name, tmp_path):
        payload = json.loads(
            run_script(SCRIPTS[name], tmp_path).stdout.strip().splitlines()[-1])
        assert payload.get('configured') is not True

    @pytest.mark.parametrize('name', sorted(SCRIPTS))
    def test_garbage_config_files_do_not_crash_it(self, name, tmp_path):
        """Half-written JSON is a real state; a torn credentials file is common."""
        for sub, fname in (('.codex', 'auth.json'), ('.codex', 'config.toml'),
                           ('.claude', '.credentials.json'),
                           ('.claude', 'stats-cache.json'),
                           ('.gemini', 'receipt_api_usage.log')):
            d = tmp_path / sub
            d.mkdir(exist_ok=True)
            (d / fname).write_text('{not json at all\x00\n\xff')
        proc = run_script(SCRIPTS[name], tmp_path)
        assert proc.returncode == 0, proc.stderr
        json.loads(proc.stdout.strip().splitlines()[-1])

    @pytest.mark.parametrize('name', sorted(SCRIPTS))
    def test_a_directory_where_a_file_belongs_does_not_crash_it(self, name, tmp_path):
        for sub, fname in (('.codex', 'auth.json'), ('.claude', '.credentials.json'),
                           ('.gemini', 'receipt_api_usage.log')):
            (tmp_path / sub / fname).mkdir(parents=True, exist_ok=True)
        proc = run_script(SCRIPTS[name], tmp_path)
        assert proc.returncode == 0, proc.stderr
        json.loads(proc.stdout.strip().splitlines()[-1])


class TestGeminiFlashFill:
    """Counts real API calls out of a local log; the limit is a local estimate.

    Nothing here is Google-reported. There is no usage endpoint for a bare API
    key, so "used" is a count of lines parse_and_categorize.py wrote and
    "limit" is a number this box was configured with -- which is exactly why
    the card's detail text says so, and why these tests pin the counting rules
    rather than trusting the number.
    """

    def payload(self, tmp_path, rows=(), limit=None, key='test-key'):
        gemini = tmp_path / '.gemini'
        gemini.mkdir(exist_ok=True)
        (gemini / 'receipt_api_usage.log').write_text(
            ''.join(r if isinstance(r, str) else json.dumps(r) + '\n'
                    for r in rows))
        env = {}
        if key is not None:
            env['GEMINI_API_KEY'] = key
        if limit is not None:
            env['GEMINI_FLASH_FILL_DAILY_LIMIT'] = limit
        proc = run_script(extractors._GEMINI_FLASH_FILL_EXTRACT_PY, tmp_path, env)
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def at(self, when):
        return {'ts': when.timestamp(), 'model': 'gemini-2.5-flash'}

    def test_no_key_is_not_configured_and_says_where_to_put_one(self, tmp_path):
        out = self.payload(tmp_path, key=None)
        assert out['configured'] is False
        assert 'rol_finances/.env' in out['error']

    def test_a_key_in_the_environment_counts_as_configured(self, tmp_path):
        assert self.payload(tmp_path)['configured'] is True

    def test_a_key_only_in_the_dotenv_file_is_found(self, tmp_path):
        """The scanner tools read it from there, not from the environment."""
        env_dir = tmp_path / 'rol_finances'
        env_dir.mkdir()
        (env_dir / '.env').write_text('OTHER=1\nGEMINI_API_KEY="from-dotenv"\n')
        assert self.payload(tmp_path, key=None)['configured'] is True

    def test_no_log_means_zero_used_not_an_error(self, tmp_path):
        gemini = tmp_path / '.gemini'
        gemini.mkdir()
        proc = run_script(extractors._GEMINI_FLASH_FILL_EXTRACT_PY, tmp_path,
                          {'GEMINI_API_KEY': 'k'})
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        assert out['used'] == 0
        assert out['error'] is None

    def test_the_default_limit_is_the_published_free_tier(self, tmp_path):
        assert self.payload(tmp_path)['limit'] == 250

    def test_the_limit_is_overridable_because_it_is_only_an_estimate(self, tmp_path):
        assert self.payload(tmp_path, limit='40')['limit'] == 40

    def test_todays_calls_are_counted(self, tmp_path):
        now = datetime.datetime.now()
        rows = [self.at(now - datetime.timedelta(minutes=n)) for n in range(5)]
        assert self.payload(tmp_path, rows)['used'] == 5

    def test_yesterdays_calls_are_not(self, tmp_path):
        """A daily cap that never rolled over would keep the card permanently red."""
        now = datetime.datetime.now().replace(hour=12)
        rows = [self.at(now - datetime.timedelta(days=1))] * 9
        rows.append(self.at(now))
        assert self.payload(tmp_path, rows)['used'] == 1

    def test_tomorrows_clock_skew_is_not_counted_either(self, tmp_path):
        now = datetime.datetime.now().replace(hour=12)
        rows = [self.at(now + datetime.timedelta(days=1)), self.at(now)]
        assert self.payload(tmp_path, rows)['used'] == 1

    def test_blank_and_malformed_lines_are_skipped_not_counted(self, tmp_path):
        now = datetime.datetime.now()
        rows = ['\n', '   \n', 'not json\n', '{"no_ts": 1}\n', '{"ts": null}\n',
                self.at(now)]
        assert self.payload(tmp_path, rows)['used'] == 1

    def test_a_truncated_final_line_does_not_lose_the_whole_count(self, tmp_path):
        """The log is appended to live; a read can land mid-write."""
        now = datetime.datetime.now()
        rows = [self.at(now), self.at(now), '{"ts": 17203']
        assert self.payload(tmp_path, rows)['used'] == 2

    def test_it_reports_a_reset_at_midnight_pacific(self, tmp_path):
        """Same convention as every other Google per-day cap on this card."""
        resets_at = self.payload(tmp_path)['resets_at']
        assert resets_at is not None
        moment = datetime.datetime.fromisoformat(resets_at)
        pacific = moment.astimezone(ZoneInfo('America/Los_Angeles'))
        assert (pacific.hour, pacific.minute) == (0, 0)
        assert moment > datetime.datetime.now(datetime.timezone.utc)


class TestRunExtractor:
    """Pipes a script somewhere and parses the one line it prints."""

    def test_a_local_run_uses_this_interpreter_on_stdin(self, monkeypatch):
        seen = {}
        def run(cmd, **kwargs):
            seen['cmd'] = cmd
            seen['kwargs'] = kwargs
            return subprocess.CompletedProcess(cmd, 0, '{"ok": true}', '')
        monkeypatch.setattr(extractors.subprocess, 'run', run)
        assert extractors._run_extractor('print(1)', None) == {'ok': True}
        assert seen['cmd'] == [sys.executable, '-']
        assert seen['kwargs']['input'] == 'print(1)'

    def test_a_remote_run_feeds_the_script_over_ssh_stdin(self, monkeypatch):
        """Not `-c`: a remote shell mangles a multi-line argument."""
        seen = {}
        monkeypatch.setattr(extractors.subprocess, 'run',
                            lambda cmd, **kw: seen.update(cmd=cmd, kw=kw)
                            or subprocess.CompletedProcess(cmd, 0, '{}', ''))
        extractors._run_extractor('print(1)', 'adamsl@10.0.0.1')
        assert seen['cmd'][-2:] == ['python3', '-']
        assert '-c' not in seen['cmd']
        assert seen['kw']['input'] == 'print(1)'

    def test_ssh_never_blocks_on_a_password_prompt(self, monkeypatch):
        """BatchMode: an unreachable R46 must time out, not hang the request."""
        seen = {}
        monkeypatch.setattr(extractors.subprocess, 'run',
                            lambda cmd, **kw: seen.update(cmd=cmd)
                            or subprocess.CompletedProcess(cmd, 0, '{}', ''))
        extractors._run_extractor('print(1)', 'adamsl@10.0.0.1')
        assert 'BatchMode=yes' in seen['cmd']
        assert 'ConnectTimeout=8' in seen['cmd']

    def test_only_the_last_stdout_line_is_parsed(self, monkeypatch):
        """SSH banners and warnings arrive ahead of the payload."""
        monkeypatch.setattr(extractors.subprocess, 'run',
                            lambda cmd, **kw: subprocess.CompletedProcess(
                                cmd, 0, 'Welcome to Ubuntu\nnoise\n{"used": 3}\n', ''))
        assert extractors._run_extractor('x', 'host') == {'used': 3}

    @pytest.mark.parametrize('stdout, stderr', [
        ('', 'ssh: connect to host port 22: No route to host'),
        ('   \n', 'permission denied'),
        ('not json', ''),
    ])
    def test_every_failure_becomes_an_error_key(self, monkeypatch, stdout, stderr):
        monkeypatch.setattr(extractors.subprocess, 'run',
                            lambda cmd, **kw: subprocess.CompletedProcess(
                                cmd, 1, stdout, stderr))
        assert 'error' in extractors._run_extractor('x', 'host')

    def test_a_stderr_message_is_surfaced_and_capped(self, monkeypatch):
        monkeypatch.setattr(extractors.subprocess, 'run',
                            lambda cmd, **kw: subprocess.CompletedProcess(
                                cmd, 255, '', 'E' * 900))
        assert len(extractors._run_extractor('x', 'host')['error']) == 200

    def test_a_timeout_is_an_error_not_an_exception(self, monkeypatch):
        def boom(cmd, **kw):
            raise subprocess.TimeoutExpired(cmd='ssh', timeout=18)
        monkeypatch.setattr(extractors.subprocess, 'run', boom)
        assert 'error' in extractors._run_extractor('x', 'host')

    def test_the_timeout_is_honoured(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(extractors.subprocess, 'run',
                            lambda cmd, **kw: seen.update(kw)
                            or subprocess.CompletedProcess(cmd, 0, '{}', ''))
        extractors._run_extractor('x', None, timeout=35)
        assert seen['timeout'] == 35


class TestServerReExport:
    def test_the_scripts_no_longer_live_in_server(self):
        assert extractors._run_extractor.__module__ == 'model_stats.extractors'
        assert server._run_extractor is extractors._run_extractor

    @pytest.mark.parametrize('name', sorted(SCRIPTS))
    def test_each_script_is_reachable_under_its_historical_name(self, name):
        attr = {'codex': '_CODEX_EXTRACT_PY', 'claude': '_CLAUDE_EXTRACT_PY',
                'gemini': '_GEMINI_FLASH_FILL_EXTRACT_PY'}[name]
        assert getattr(server, attr) is SCRIPTS[name]

    def test_every_configured_source_has_a_kind_the_dashboard_handles(self):
        assert {s.kind for s in server.MODEL_STAT_SOURCES.values()} == {
            'codex', 'claude', 'gemini'}
