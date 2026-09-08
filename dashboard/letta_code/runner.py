"""Running one Letta Code turn headlessly, and what may be sent to it.

Not terminal code, despite having lived beside it: nothing here touches a pty.
A caller hands over an agent id and a prompt, and gets back the single JSON
result of one turn.

Two decisions in here are worth knowing about before changing anything.

*Permission mode.* A headless run has nobody to answer an approval prompt, so
the CLI auto-DENIES anything gated. Without a raised mode the agent can read
and reason but every Edit and Write silently fails -- and then reports work it
was never allowed to do. `acceptEdits` auto-allows the edit tools and Bash and
nothing further; deliberately narrower than `--yolo`, which a web-reachable
endpoint has no business handing out.

*Conversation identity.* Headless mode starts a fresh conversation per call by
default, to dodge 409 "conversation busy" races -- which means the agent
remembers nothing of the previous turn. A caller that wants continuity must
pass back the `conversation_id` a prior call returned.

`letta_id_for` is injected rather than imported: it resolves against the
server's agent registry, and importing that here would be a cycle.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess

from hosts import LETTA_BASE_URL
from letta_ids import _TERMINAL_ID_RE
from paths import LETTA_CODE_BUN, REPO_ROOT

_LETTA_CODE_MAX_PROMPT_CHARS = 20000
_LETTA_CODE_FORBIDDEN_INPUT_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


class ConversationBusyError(RuntimeError):
    """Another request is already being processed for this conversation.

    Expected/benign -- happens when a follow-up is sent before the previous
    turn's reply has come back. Callers should surface this as a clear,
    short message rather than the generic Letta Code failure path.
    """


def validate_letta_code_prompt(value):
    """Accept message text while rejecting terminal-control traffic."""
    if not isinstance(value, str):
        raise ValueError('message must be text')
    value = value.replace('\r\n', '\n').replace('\r', '\n')
    if not value.strip():
        raise ValueError('message is empty')
    if len(value) > _LETTA_CODE_MAX_PROMPT_CHARS:
        raise ValueError(f'message is too long (maximum {_LETTA_CODE_MAX_PROMPT_CHARS} characters)')
    if _LETTA_CODE_FORBIDDEN_INPUT_RE.search(value):
        raise ValueError('message contains unsupported control characters')
    return value


def _letta_code_command():
    """Return a service-safe command prefix for this checkout's CLI.

    dashboard-server.service has a deliberately small PATH and the repo may not
    have a built letta.js yet. Prefer the canonical TypeScript dev entry point
    through Bun, using its stable user install path, then fall back to a linked
    or built CLI when needed.
    """
    bun = LETTA_CODE_BUN if os.path.isfile(LETTA_CODE_BUN) else shutil.which('bun')
    if bun:
        return [bun, 'run', 'dev', '--']
    letta = shutil.which('letta')
    if letta:
        return [letta]
    built = os.path.join(REPO_ROOT, 'letta.js')
    if os.path.isfile(built):
        return [built]
    raise FileNotFoundError(
        'Letta Code runtime not found (expected ~/.bun/bin/bun, PATH letta, '
        f'or {built})')


def run_letta_code_message(agent_id, prompt, letta_id_for,
                           timeout=1770, conversation_id=None):
    """Run one Letta Code turn and expose only its final JSON result.

    Without `conversation_id`, headless mode's default behavior creates a
    brand-new conversation on every call (to avoid 409 "conversation busy"
    races), so the agent has no memory of the previous turn. Callers that
    want a running conversation must pass back the `run.conversation_id`
    a prior call returned; the CLI's `--conversation` resumes it instead of
    starting over. `--conversation` derives the agent from the conversation
    itself, so it is mutually exclusive with `--agent`.
    """
    lid = letta_id_for(agent_id)
    if not lid or not _TERMINAL_ID_RE.fullmatch(lid):
        raise ValueError('invalid Letta agent id')
    clean_prompt = validate_letta_code_prompt(prompt)
    command = _letta_code_command()
    # `bun run dev` expands to a package script that invokes `bun` once more.
    # Preserve the resolved runtime directory for that nested command even
    # under dashboard-server.service's intentionally minimal PATH.
    runtime_path = os.path.dirname(command[0])
    child_path = os.environ.get('PATH', '')
    if runtime_path:
        child_path = runtime_path + (os.pathsep + child_path if child_path else '')
    if conversation_id and not _TERMINAL_ID_RE.fullmatch(conversation_id):
        raise ValueError('invalid Letta conversation id')
    session_args = (
        ['--conversation', conversation_id] if conversation_id
        else ['--agent', lid]
    )
    # Headless runs have nobody to answer an approval prompt, so the CLI
    # auto-DENIES anything gated ("Tool requires approval (headless mode)").
    # Without a raised mode the agent can read and reason but every Edit/Write
    # silently fails, and she reports work she was never allowed to do.
    # acceptEdits auto-allows the edit tools + Bash and nothing else - narrower
    # than --yolo/bypassPermissions, which this web-reachable endpoint should
    # not hand out.
    # `bun run dev` forks a further `bun ... run src/index.ts` child rather
    # than exec'ing into it, so a plain subprocess.run(timeout=...) only
    # kills that outer wrapper on timeout -- the real worker underneath
    # survives as an orphan, reparented to init, and keeps running (still
    # holding the Letta conversation "busy") indefinitely. Confirmed live
    # 2026-09-08: a timed-out run's worker was still going 30+ minutes after
    # the dashboard had already told the caller it timed out, CONFLICT-ing
    # every later message into that same conversation. start_new_session=True
    # puts the whole tree in its own process group so a timeout can reap all
    # of it with killpg, not just the one PID subprocess.run knows about.
    proc = subprocess.Popen(
        [*command, *session_args, '--prompt', clean_prompt,
         '--output-format', 'json', '--memfs-startup', 'skip',
         '--permission-mode', 'acceptEdits'],
        cwd=REPO_ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True,
        env={**os.environ, 'PATH': child_path, 'LETTA_BASE_URL': LETTA_BASE_URL},
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.communicate()  # reap the group; this run is being abandoned
        raise
    if proc.returncode != 0:
        detail = (stderr or stdout or 'Letta Code failed').strip()
        # A second message sent into a conversation while the first is still
        # running (e.g. a follow-up typed before the previous reply lands)
        # gets this exact CONFLICT from the Letta server. It is not a real
        # failure, but the raw CLI output around it is dominated by unrelated
        # skill-listing noise -- `detail[-1000:]` below keeps the true error
        # near its end, and the dashboard's HTTP error unwrap then shows only
        # the first 120 chars of THAT, which lands back on the noise instead
        # of the one sentence that actually explains what happened. Replace
        # it with a clean, specific message instead of raising the raw dump.
        if 'CONFLICT' in detail and 'currently being processed for this conversation' in detail:
            raise ConversationBusyError(
                "Mazda is still working on your previous message in this "
                'conversation. Wait for that reply, then try again.')
        raise RuntimeError(detail[-1000:])
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError('Letta Code returned invalid JSON') from exc
    result = payload.get('result')
    if not isinstance(result, str) or not result.strip():
        raise RuntimeError('Mazda returned no answer')
    return {'ok': True, 'reply': result, 'run': {
        'agent_id': payload.get('agent_id'),
        'conversation_id': payload.get('conversation_id'),
    }}
