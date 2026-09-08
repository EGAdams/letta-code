"""The headless Letta Code runner, and the guard on what reaches it.

This endpoint is reachable from a browser and ends in a subprocess, so the two
things pinned hardest here are the input validator and the argv the runner
builds. Neither is exercised by anything else: the CLI is never actually
invoked in tests, so a wrong flag would be discovered on the live box.

The other thing pinned is the injection seam. `letta_id_for` resolves against
the server's agent registry, which the runner cannot import without a cycle, so
server.py wraps it in a lambda at its composition root. If that ever becomes an
eager binding, the tests that replace `server.letta_id_for` keep passing while
the runner talks to whatever agent the registry held at import time.
"""
import json
import subprocess

import pytest

import server
from letta_code import runner


class FakePopen:
    """Stands in for subprocess.Popen. The runner uses Popen (not
    subprocess.run) so a timeout can killpg() the whole process group --
    `bun run dev` forks a further worker rather than exec'ing into it, and a
    plain subprocess.run(timeout=...) only ever kills that outer wrapper."""

    _next_pid = 9000

    def __init__(self, argv, stdout='', stderr='', returncode=0,
                 raise_timeout=False, **kwargs):
        self.args = argv
        self.kwargs = kwargs
        FakePopen._next_pid += 1
        self.pid = FakePopen._next_pid
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self._raise_timeout = raise_timeout
        self.communicate_calls = []

    def communicate(self, timeout=None):
        self.communicate_calls.append(timeout)
        if self._raise_timeout and len(self.communicate_calls) == 1:
            raise subprocess.TimeoutExpired(cmd=self.args, timeout=timeout)
        return self._stdout, self._stderr


def ok_payload(reply='done', conversation_id='conv-1'):
    return json.dumps({'result': reply, 'conversation_id': conversation_id})


@pytest.fixture
def spy(monkeypatch):
    """Capture the argv and kwargs the runner would have executed."""
    seen = {}

    def fake_popen(argv, **kwargs):
        seen['argv'] = argv
        seen['kwargs'] = kwargs
        real_kwargs = {k: v for k, v in kwargs.items() if k not in ('stdout', 'stderr')}
        proc = FakePopen(argv, stdout=ok_payload(), **real_kwargs)
        seen['proc'] = proc
        return proc

    monkeypatch.setattr(runner.subprocess, 'Popen', fake_popen)
    monkeypatch.setattr(runner, '_letta_code_command', lambda: ['/bun', 'run', 'dev', '--'])
    return seen


AGENT = 'agent-6b536cf4-ec88-4290-b595-fed21d14bd8e'


class TestThePromptGuard:
    def test_ordinary_text_passes(self):
        assert runner.validate_letta_code_prompt('hello Mazda') == 'hello Mazda'

    def test_carriage_returns_are_normalised(self):
        """A CR left in the string submits the line early once it reaches a
        terminal, which turns half a message into a command."""
        assert runner.validate_letta_code_prompt('a\r\nb\rc') == 'a\nb\nc'

    def test_a_tab_is_kept_because_it_is_ordinary_text(self):
        assert runner.validate_letta_code_prompt('a\tb') == 'a\tb'

    @pytest.mark.parametrize('text', [
        '\x00', 'a\x1bb', 'a\x07b', 'a\x7fb', 'a\x0cb', 'a\x0bb'])
    def test_terminal_control_characters_are_rejected(self, text):
        with pytest.raises(ValueError, match='control characters'):
            runner.validate_letta_code_prompt(text)

    @pytest.mark.parametrize('text', ['\x0b', '\x0c'])
    def test_a_message_that_is_only_a_form_feed_is_refused_as_empty(self, text):
        """These are both control characters and whitespace to str.strip(), so
        the emptiness check reaches them first. Rejected either way -- pinned
        because the *message* differs, and a caller reading 'is empty' should
        not conclude the control-character guard let it through."""
        with pytest.raises(ValueError, match='empty'):
            runner.validate_letta_code_prompt(text)

    @pytest.mark.parametrize('text', ['', '   ', '\n\n', '\t'])
    def test_an_empty_message_is_rejected_rather_than_sent(self, text):
        with pytest.raises(ValueError, match='empty'):
            runner.validate_letta_code_prompt(text)

    def test_a_non_string_is_rejected(self):
        """The body is JSON, so this can be a list, a number, or None."""
        with pytest.raises(ValueError, match='must be text'):
            runner.validate_letta_code_prompt(['hello'])

    def test_a_message_at_the_limit_is_accepted(self):
        text = 'x' * runner._LETTA_CODE_MAX_PROMPT_CHARS
        assert runner.validate_letta_code_prompt(text) == text

    def test_a_message_past_the_limit_is_refused_with_the_number_in_it(self):
        with pytest.raises(ValueError, match='20000'):
            runner.validate_letta_code_prompt(
                'x' * (runner._LETTA_CODE_MAX_PROMPT_CHARS + 1))


class TestTheAgentIdGuard:
    @pytest.mark.parametrize('hostile', [
        'a b', 'a;b', 'a$(id)', 'a`id`', 'a|b', 'a&b', "a'b", 'a"b',
        'a\\b', '../a', 'a\nb'])
    def test_a_hostile_id_never_reaches_the_subprocess(self, hostile, spy):
        with pytest.raises(ValueError, match='invalid Letta agent id'):
            runner.run_letta_code_message(hostile, 'hi', lambda a: a)
        assert 'argv' not in spy

    def test_an_unresolvable_agent_is_refused(self, spy):
        with pytest.raises(ValueError, match='invalid Letta agent id'):
            runner.run_letta_code_message('nobody', 'hi', lambda a: None)
        assert 'argv' not in spy

    @pytest.mark.parametrize('hostile', ['c v', 'c;v', 'c$(id)', '../c'])
    def test_a_hostile_conversation_id_is_refused_too(self, hostile, spy):
        with pytest.raises(ValueError, match='invalid Letta conversation id'):
            runner.run_letta_code_message(
                AGENT, 'hi', lambda a: a, conversation_id=hostile)
        assert 'argv' not in spy

    def test_the_guard_is_the_shared_pattern(self):
        """One definition, in letta_ids.py, because the terminal upgrade path
        types the same id into a shell."""
        from letta_ids import TERMINAL_ID_RE
        assert runner._TERMINAL_ID_RE is TERMINAL_ID_RE


class TestTheCommandItBuilds:
    def test_a_fresh_call_names_the_agent(self, spy):
        runner.run_letta_code_message(AGENT, 'hi', lambda a: a)
        assert '--agent' in spy['argv'] and AGENT in spy['argv']

    def test_resuming_names_the_conversation_and_not_the_agent(self, spy):
        """`--conversation` derives the agent from the conversation itself, so
        the two flags are mutually exclusive -- passing both is an error from
        the CLI, not a preference."""
        runner.run_letta_code_message(
            AGENT, 'hi', lambda a: a, conversation_id='conv-abc')
        assert '--conversation' in spy['argv'] and 'conv-abc' in spy['argv']
        assert '--agent' not in spy['argv']

    def test_it_runs_with_accept_edits_and_not_bypass(self, spy):
        """Without a raised mode a headless run auto-DENIES every gated tool,
        so the agent reads and reasons and then reports edits it was never
        allowed to make. bypassPermissions is the other failure: this endpoint
        is web-reachable and must not hand out a yolo shell.

        Asserted on the argv rather than the source, so the comment explaining
        why bypassPermissions is absent cannot satisfy the test.
        """
        runner.run_letta_code_message(AGENT, 'hi', lambda a: a)
        argv = spy['argv']
        assert argv[argv.index('--permission-mode') + 1] == 'acceptEdits'
        assert not {'--yolo', 'bypassPermissions', '--dangerously-skip-permissions'} & set(argv)

    def test_it_asks_for_json_output(self, spy):
        runner.run_letta_code_message(AGENT, 'hi', lambda a: a)
        argv = spy['argv']
        assert argv[argv.index('--output-format') + 1] == 'json'

    def test_the_prompt_reaches_the_cli_normalised(self, spy):
        runner.run_letta_code_message(AGENT, 'a\r\nb', lambda a: a)
        argv = spy['argv']
        assert argv[argv.index('--prompt') + 1] == 'a\nb'

    def test_it_runs_from_the_checkout_root(self, spy):
        from paths import REPO_ROOT
        runner.run_letta_code_message(AGENT, 'hi', lambda a: a)
        assert spy['kwargs']['cwd'] == REPO_ROOT

    def test_the_runtime_directory_is_prepended_to_the_child_path(self, spy):
        """dashboard-server.service has a deliberately minimal PATH, and
        `bun run dev` invokes `bun` a second time from inside the package
        script. Without this the nested call finds nothing."""
        runner.run_letta_code_message(AGENT, 'hi', lambda a: a)
        assert spy['kwargs']['env']['PATH'].startswith('/')

    def test_the_letta_base_url_is_passed_through(self, spy):
        from hosts import LETTA_BASE_URL
        runner.run_letta_code_message(AGENT, 'hi', lambda a: a)
        assert spy['kwargs']['env']['LETTA_BASE_URL'] == LETTA_BASE_URL

    def test_the_timeout_is_honoured(self, spy):
        runner.run_letta_code_message(AGENT, 'hi', lambda a: a, timeout=42)
        assert spy['proc'].communicate_calls == [42]

    def test_a_fresh_process_group_is_started(self, spy):
        """So a timeout can killpg() the whole tree instead of leaving the
        real worker behind as an orphan (see the module docstring above the
        Popen call)."""
        runner.run_letta_code_message(AGENT, 'hi', lambda a: a)
        assert spy['kwargs']['start_new_session'] is True

    def test_timeout_kills_the_whole_process_group_not_just_the_wrapper(
            self, monkeypatch):
        """`bun run dev` forks a further worker rather than exec'ing into it,
        so killing only the direct child (plain subprocess.run(timeout=...))
        leaves that worker running as an orphan -- still holding the Letta
        conversation "busy" -- indefinitely. Confirmed live 2026-09-08: an
        orphaned worker was still running 30+ minutes after its request had
        already been reported back to the caller as timed out."""
        monkeypatch.setattr(runner, '_letta_code_command', lambda: ['/bun'])
        proc = FakePopen(['/bun'], raise_timeout=True)
        monkeypatch.setattr(runner.subprocess, 'Popen', lambda *a, **k: proc)
        killed = []
        monkeypatch.setattr(runner.os, 'getpgid', lambda pid: pid * 10)
        monkeypatch.setattr(runner.os, 'killpg',
                            lambda pgid, sig: killed.append((pgid, sig)))
        with pytest.raises(runner.subprocess.TimeoutExpired):
            runner.run_letta_code_message(AGENT, 'hi', lambda a: a, timeout=5)
        assert killed == [(proc.pid * 10, runner.signal.SIGKILL)]


class TestWhatItReturns:
    def test_only_the_final_result_is_exposed(self, monkeypatch):
        """The CLI's JSON also carries the whole turn. Passing that through
        would put tool calls and file contents on a web response."""
        monkeypatch.setattr(runner, '_letta_code_command', lambda: ['/bun'])
        monkeypatch.setattr(runner.subprocess, 'Popen', lambda *a, **k: FakePopen(
            a[0], stdout=json.dumps({'result': 'the answer', 'conversation_id': 'conv-9',
                               'messages': [{'secret': 'internal'}]})))
        out = runner.run_letta_code_message(AGENT, 'hi', lambda a: a)
        assert out['run']['conversation_id'] == 'conv-9'
        assert 'the answer' in json.dumps(out)
        assert 'internal' not in json.dumps(out)

    def test_a_nonzero_exit_raises_with_the_tail_of_the_error(self, monkeypatch):
        monkeypatch.setattr(runner, '_letta_code_command', lambda: ['/bun'])
        monkeypatch.setattr(runner.subprocess, 'Popen', lambda *a, **k: FakePopen(
            a[0], stderr='x' * 3000 + 'THE REAL CAUSE', returncode=1))
        with pytest.raises(RuntimeError) as exc:
            runner.run_letta_code_message(AGENT, 'hi', lambda a: a)
        assert 'THE REAL CAUSE' in str(exc.value)
        assert len(str(exc.value)) <= 1000

    def test_a_conversation_busy_conflict_gets_a_clean_message_not_the_raw_dump(
            self, monkeypatch):
        """Sending a follow-up before the previous turn's reply lands hits
        this exact CONFLICT from the Letta server. It is expected/benign, but
        the raw CLI stderr around it is dominated by unrelated skill-listing
        noise that the dashboard's client-side error unwrap (first 120 chars)
        would show instead of the one sentence that actually explains it --
        this must surface as a clean message, not that dump. Reproduces the
        real failure logged 2026-09-08 17:54 (curl'd against a live server)."""
        monkeypatch.setattr(runner, '_letta_code_command', lambda: ['/bun'])
        raw = (
            'skills/spotify-player/SKILL.md), spreadsheet, state-change-debugger, '
            'syncing-memory-filesystem, transcribe, visual-identity, working-in-parallel\n'
            'Error: CONFLICT: Cannot send a new message: Another request '
            '(run_id=run-70b829fd) is currently being processed for this '
            'conversation. Please wait for it to complete.\n'
            'View agent: agent-6b536cf4 (run: run-70b829fd)\n'
            'error: script "dev" exited with code 1'
        )
        monkeypatch.setattr(runner.subprocess, 'Popen', lambda *a, **k: FakePopen(
            a[0], stderr=raw, returncode=1))
        with pytest.raises(runner.ConversationBusyError) as exc:
            runner.run_letta_code_message(AGENT, 'hi', lambda a: a, conversation_id='conv-9')
        assert 'still working on your previous message' in str(exc.value)
        assert 'spotify-player' not in str(exc.value)

    def test_unparseable_output_is_named_rather_than_leaking_a_decode_error(
            self, monkeypatch):
        monkeypatch.setattr(runner, '_letta_code_command', lambda: ['/bun'])
        monkeypatch.setattr(runner.subprocess, 'Popen',
                            lambda *a, **k: FakePopen(a[0], stdout='not json'))
        with pytest.raises(RuntimeError, match='invalid JSON'):
            runner.run_letta_code_message(AGENT, 'hi', lambda a: a)


class TestFindingTheCli:
    def test_the_bun_user_install_path_wins_when_it_exists(self, monkeypatch):
        monkeypatch.setattr(runner, 'LETTA_CODE_BUN', '/home/test/.bun/bin/bun')
        monkeypatch.setattr(runner.os.path, 'isfile', lambda p: p == '/home/test/.bun/bin/bun')
        assert runner._letta_code_command() == ['/home/test/.bun/bin/bun', 'run', 'dev', '--']

    def test_it_falls_back_to_a_linked_cli(self, monkeypatch):
        monkeypatch.setattr(runner, 'LETTA_CODE_BUN', '/missing/bun')
        monkeypatch.setattr(runner.os.path, 'isfile', lambda p: False)
        monkeypatch.setattr(runner.shutil, 'which',
                            lambda n: '/usr/local/bin/letta' if n == 'letta' else None)
        assert runner._letta_code_command() == ['/usr/local/bin/letta']

    def test_with_nothing_installed_it_says_where_it_looked(self, monkeypatch):
        monkeypatch.setattr(runner, 'LETTA_CODE_BUN', '/missing/bun')
        monkeypatch.setattr(runner.os.path, 'isfile', lambda p: False)
        monkeypatch.setattr(runner.shutil, 'which', lambda n: None)
        with pytest.raises(FileNotFoundError, match='letta.js'):
            runner._letta_code_command()


class TestTheCompositionRoot:
    def test_server_resolves_the_id_lookup_at_call_time(self, monkeypatch):
        """The lambda is the point. An eager binding would freeze whichever
        `letta_id_for` existed at import, and the registry it reads is a cache
        that tests and the running server both replace."""
        monkeypatch.setattr(runner, '_letta_code_command', lambda: ['/bun'])
        monkeypatch.setattr(runner.subprocess, 'Popen',
                            lambda *a, **k: FakePopen(a[0], stdout=ok_payload()))
        seen = []
        monkeypatch.setattr(server, 'letta_id_for',
                            lambda aid: seen.append(aid) or AGENT)
        server.run_letta_code_message('some-alias', 'hi')
        assert seen == ['some-alias']

    @pytest.mark.parametrize('name', [
        'validate_letta_code_prompt', '_letta_code_command'])
    def test_the_historical_name_still_resolves(self, name):
        assert getattr(server, name) is getattr(runner, name)
