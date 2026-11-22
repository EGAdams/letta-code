"""Strategy for actually invoking an agent on a remediation prompt.

Three strategies, tried in order by ``default_runner()``:

1. ``REMEDIATION_ADW_SCRIPT``, if set and present on disk, switches to a scoped
   subprocess adapter shaped like receptionist_work/adw_runner.py's
   FinanceAdwRunner: one named script, a request/result JSON file, a bounded
   timeout -- never a shell string built from alert text.
2. Otherwise, if this host already has a Bridge client token
   (``~/.config/agent_bridge/client_token``), ``BridgeRestRemediationRunner``
   posts the prompt straight to the real Bridge REST task queue -- the same
   queue docs/adw-supervisor.md's read-only monitor polls, now with a write
   path, gated on the *client* token the Bridge issues for this workspace
   (never the worker token).
3. Otherwise ``UnwiredRemediationRunner`` honestly reports that nothing was
   executed -- the same posture monitoring/model_registry.py takes by
   refusing to claim a model is "available" without a real check.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

DEFAULT_TIMEOUT_SECONDS = 120

#: The Bridge's own REST task queue -- fixed and allowlisted, never read from
#: the environment, so a remediation dispatch can't be redirected to another host.
BRIDGE_BASE_URL = 'https://bridge.americansjewelry.com/api/agent-bridge/v1'
BRIDGE_TOKEN_PATH = Path(os.path.expanduser('~/.config/agent_bridge/client_token'))
BRIDGE_TIMEOUT_SECONDS = 20
#: The only agent, workspace and operation this runner is allowed to request --
#: Bridge policy enforces this server-side too, but there is no reason to ask
#: for anything else from here.
BRIDGE_AGENT = 'claude-sonnet'
BRIDGE_WORKSPACE = 'letta_code'
BRIDGE_OPERATION = 'implement'
BRIDGE_APPROVAL_MODE = 'workspace_write'
BRIDGE_SCHEMA_VERSION = '1.0'
BRIDGE_TASK_TYPE = 'agent_task'
#: Matches Bridge's own task_id shape, e.g. "t_" + 24 hex chars.
BRIDGE_TASK_ID_RE = re.compile(r'^t_[0-9a-f]{24}$')
#: Matches the pydantic bound already enforced on the dispatch request
#: (remediation_dispatch.RemediationDispatchRequest.prompt); re-checked here so
#: this runner is safe to call directly, not just through that one caller.
BRIDGE_PROMPT_MAX_LENGTH = 20000
#: HostGator's mod_security answers 406 Not Acceptable to urllib's default
#: "Python-urllib/3.x" User-Agent, so every Bridge request names this client.
BRIDGE_USER_AGENT = 'letta-dashboard-remediation/1.0'
#: The only states a task can still leave -- the gateway's own TaskState
#: rule (AgentTaskTools::terminal): anything else is final.
BRIDGE_PENDING_STATES = frozenset({'queued', 'running'})
BRIDGE_SUMMARY_MAX_LENGTH = 1500


@dataclass(frozen=True)
class RemediationOutcome:
    ok: bool
    task_id: str | None
    status: str
    error: str | None = None
    detail: str = ''


@dataclass(frozen=True)
class RemediationStatus:
    ok: bool
    task_id: str
    state: str
    terminal: bool
    succeeded: bool | None = None
    summary: str = ''
    error: str | None = None
    detail: str = ''


class IRemediationRunner(Protocol):
    def run(self, alert_key: str, model_id: str, prompt: str) -> RemediationOutcome: ...


class IRemediationStatusReader(Protocol):
    def status(self, task_id: str) -> RemediationStatus: ...


class UnwiredRemediationRunner:
    """Honest default: no ADW script and no Bridge client token are configured on this host."""

    def run(self, alert_key: str, model_id: str, prompt: str) -> RemediationOutcome:
        return RemediationOutcome(
            ok=False, task_id=None, status='unsupported', error='dispatch_unsupported',
            detail='no remediation ADW script is configured (set REMEDIATION_ADW_SCRIPT) and no '
                   f'Bridge client token was found at {BRIDGE_TOKEN_PATH}; nothing was executed',
        )


class ScopedAdwRemediationRunner:
    """Invokes exactly one named script with a request/result JSON file, never a shell string.

    ``root`` is the ``uv run`` working directory, i.e. which project's venv/deps get
    picked up. It defaults to the configured script's own parent directory -- the
    checkout that owns it (e.g. ``~/agent_blocks``, the way FinanceAdwRunner and
    adw_bridge_poll_settings.py already run against their own checkout) -- never
    this dashboard's REPO_ROOT, which has no reason to share a venv with a script
    living elsewhere.
    """

    def __init__(self, script: Path, root: Path | None = None, timeout: float = DEFAULT_TIMEOUT_SECONDS):
        self.script = script
        self.root = root if root is not None else script.parent
        self.timeout = timeout

    def run(self, alert_key: str, model_id: str, prompt: str) -> RemediationOutcome:
        uv = shutil.which('uv') or str(Path.home() / '.local/bin/uv')
        task_id = f'remediate-{uuid.uuid4().hex[:12]}'
        with tempfile.TemporaryDirectory(prefix='remediation-adw-') as directory:
            request_path = Path(directory) / 'request.json'
            result_path = Path(directory) / 'result.json'
            request_path.write_text(json.dumps({
                'alert_key': alert_key, 'model_id': model_id, 'prompt': prompt, 'task_id': task_id,
            }))
            command = [uv, 'run', str(self.script), '--request-file', str(request_path),
                       '--result-file', str(result_path)]
            try:
                completed = subprocess.run(command, cwd=self.root, capture_output=True, text=True,
                                           timeout=self.timeout, env={**os.environ, 'PYTHONUNBUFFERED': '1'})
            except (OSError, subprocess.TimeoutExpired) as exc:
                return RemediationOutcome(ok=False, task_id=task_id, status='failed',
                                          error='runner_failed', detail=f'{type(exc).__name__}: {exc}')
            if not result_path.is_file():
                detail = (completed.stderr or completed.stdout)[-1500:]
                return RemediationOutcome(ok=False, task_id=task_id, status='failed',
                                          error='no_result', detail=detail or 'the script produced no result file')
            try:
                result = json.loads(result_path.read_text())
            except ValueError:
                return RemediationOutcome(ok=False, task_id=task_id, status='failed',
                                          error='invalid_result', detail='the script result file was not valid JSON')
            return RemediationOutcome(
                ok=bool(result.get('ok')), task_id=str(result.get('task_id') or task_id),
                status=str(result.get('status') or ('queued' if result.get('ok') else 'failed')),
                error=None if result.get('ok') else str(result.get('error') or 'remediation_failed'),
                detail=str(result.get('detail') or ''))


class BridgeRestRemediationRunner:
    """Dispatches one task to the real Bridge REST queue over HTTPS (stdlib
    urllib, never a shell), authenticated with the *client* token Bridge
    issues for this workspace -- never the worker token. The agent,
    workspace and operation are fixed constants, not request input: this
    runner either asks for exactly the one task Bridge policy already grants
    this deployment, or it refuses and says why -- it never silently
    substitutes a different model just because one was requested.
    """

    def __init__(self, token_path: Path | None = None, base_url: str | None = None,
                 timeout: float = BRIDGE_TIMEOUT_SECONDS):
        # Resolved against the module globals at call time (not bound as a
        # parameter default) so tests can monkeypatch BRIDGE_TOKEN_PATH/BRIDGE_BASE_URL
        # and have default_runner() pick it up.
        self.token_path = token_path if token_path is not None else BRIDGE_TOKEN_PATH
        self.base_url = base_url if base_url is not None else BRIDGE_BASE_URL
        self.timeout = timeout

    def _token(self) -> str | None:
        try:
            token = self.token_path.read_text(encoding='utf-8').strip()
        except OSError:
            return None
        return token or None

    def run(self, alert_key: str, model_id: str, prompt: str) -> RemediationOutcome:
        if model_id != BRIDGE_AGENT:
            return RemediationOutcome(
                ok=False, task_id=None, status='unsupported', error='model_not_supported',
                detail=f'the Bridge REST runner only dispatches "{BRIDGE_AGENT}"; '
                       f'"{model_id}" is not wired to it')
        if len(prompt) > BRIDGE_PROMPT_MAX_LENGTH:
            return RemediationOutcome(
                ok=False, task_id=None, status='rejected', error='prompt_too_long',
                detail=f'prompt exceeds {BRIDGE_PROMPT_MAX_LENGTH} characters')
        token = self._token()
        if not token:
            return RemediationOutcome(
                ok=False, task_id=None, status='unsupported', error='bridge_token_missing',
                detail=f'no Bridge client token at {self.token_path}; nothing was dispatched')

        body = json.dumps({
            'schema_version': BRIDGE_SCHEMA_VERSION,
            'task_type': BRIDGE_TASK_TYPE,
            'agent': BRIDGE_AGENT,
            'workspace': BRIDGE_WORKSPACE,
            'operation': BRIDGE_OPERATION,
            'approval_mode': BRIDGE_APPROVAL_MODE,
            'prompt': prompt,
            'idempotency_key': alert_key,
        }).encode('utf-8')
        request = urllib.request.Request(
            f'{self.base_url}/tasks', data=body, method='POST',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json',
                     'User-Agent': BRIDGE_USER_AGENT})
        del token  # never referenced again -- not logged, not echoed in any error below

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            return RemediationOutcome(ok=False, task_id=None, status='failed', error='bridge_http_error',
                                      detail=f'Bridge rejected the task request (HTTP {exc.code})')
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            return RemediationOutcome(ok=False, task_id=None, status='failed', error='bridge_unreachable',
                                      detail=f'could not reach the Bridge task queue: {type(exc).__name__}')

        try:
            result = json.loads(raw)
        except ValueError:
            return RemediationOutcome(ok=False, task_id=None, status='failed', error='invalid_bridge_response',
                                      detail='the Bridge task queue returned a response that was not valid JSON')
        task_id = result.get('task_id') if isinstance(result, dict) else None
        state = result.get('state') if isinstance(result, dict) else None
        if not isinstance(task_id, str) or not BRIDGE_TASK_ID_RE.match(task_id) \
                or not isinstance(state, str) or not state:
            return RemediationOutcome(ok=False, task_id=None, status='failed', error='invalid_bridge_response',
                                      detail='the Bridge task queue response did not contain a recognizable task_id/state')
        return RemediationOutcome(ok=True, task_id=task_id, status=state, detail='')

    def _get(self, path: str) -> dict | None:
        """One authenticated GET; None on any transport, HTTP or JSON failure."""
        token = self._token()
        if not token:
            return None
        request = urllib.request.Request(
            f'{self.base_url}{path}', method='GET',
            headers={'Authorization': f'Bearer {token}', 'User-Agent': BRIDGE_USER_AGENT})
        del token
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read())
        except (urllib.error.URLError, OSError, TimeoutError, ValueError):
            return None
        return result if isinstance(result, dict) else None

    def status(self, task_id: str) -> RemediationStatus:
        """Reads a task this client submitted. The Bridge answers 404 for anyone
        else's task, so the client token is the only scope needed."""
        if not BRIDGE_TASK_ID_RE.match(task_id or ''):
            return RemediationStatus(ok=False, task_id=task_id, state='unknown', terminal=False,
                                     error='invalid_task_id', detail='not a Bridge task id')
        task = self._get(f'/tasks/{task_id}')
        state = task.get('state') if task else None
        if not isinstance(state, str) or not state:
            return RemediationStatus(ok=False, task_id=task_id, state='unknown', terminal=False,
                                     error='bridge_status_unavailable',
                                     detail='could not read the task state from the Bridge')
        if state in BRIDGE_PENDING_STATES:
            return RemediationStatus(ok=True, task_id=task_id, state=state, terminal=False)
        result = self._get(f'/tasks/{task_id}/result') or {}
        succeeded = bool(result.get('ok')) if result.get('ready') else state == 'succeeded'
        summary = result.get('summary') if isinstance(result.get('summary'), str) else ''
        last_error = next((v for v in (result.get('last_error'), task.get('last_error'))
                           if isinstance(v, str) and v), '')
        return RemediationStatus(ok=True, task_id=task_id, state=state, terminal=True,
                                 succeeded=succeeded and state == 'succeeded',
                                 summary=summary[:BRIDGE_SUMMARY_MAX_LENGTH],
                                 detail=last_error[:BRIDGE_SUMMARY_MAX_LENGTH])


def default_runner() -> IRemediationRunner:
    """The one place that names this host's remediation ADW script or Bridge token, if any."""
    configured = os.environ.get('REMEDIATION_ADW_SCRIPT', '')
    if configured and Path(configured).is_file():
        return ScopedAdwRemediationRunner(Path(configured))
    bridge = BridgeRestRemediationRunner()
    if bridge.token_path.is_file():
        return bridge
    return UnwiredRemediationRunner()
