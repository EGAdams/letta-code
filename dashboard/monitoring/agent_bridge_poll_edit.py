"""Save the Poll Settings tab's edits: hand them to the worker's own ADW.

The dashboard does not decide what is allowed. It checks only the shape (the
seven known keys, numbers or the hours object), then runs
`adws/adw_bridge_poll_settings.py` in agent_blocks, which validates against
the worker's `PollSettings`, backs up and writes `poll_settings.json`, restarts
`agent-bridge-worker.service`, and answers with one JSON line. Its answer is
passed back as it is.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

AGENT_BLOCKS = Path(os.path.expanduser('~/agent_blocks'))
PYTHON = AGENT_BLOCKS / 'lancedb_memory' / '.venv' / 'bin' / 'python'
ADW = AGENT_BLOCKS / 'adws' / 'adw_bridge_poll_settings.py'
TIMEOUT_SECONDS = 90        # the ADW waits up to 30 s for the restarted worker's first check


class ActiveHoursEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')

    start_hour: int
    end_hour: int


class PollSettingsEdit(BaseModel):
    """Shape only; the limits live in the worker."""

    model_config = ConfigDict(extra='forbid')

    idle_seconds: float
    burst_seconds: float
    burst_window_seconds: float
    slow_down_seconds: float
    error_base_seconds: float
    error_max_seconds: float
    active_hours: ActiveHoursEdit | None = None


def _refused(message: str, problems: list | None = None) -> dict:
    return {'ok': False, 'message': message, 'problems': problems or []}


def last_json_line(stdout: str) -> dict | None:
    """The ADW's answer is its last line that parses as a JSON object. Pure."""
    for line in reversed(stdout.strip().splitlines()):
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if isinstance(data, dict):
            return data
    return None


def save_poll_settings(body: dict) -> dict:
    try:
        edit = PollSettingsEdit.model_validate(body)
    except ValidationError as error:
        problems = [{'field': str(e['loc'][0]) if e['loc'] else '', 'message': e['msg']}
                    for e in error.errors()]
        return _refused('Those settings were not saved.', problems)
    try:
        done = subprocess.run([str(PYTHON), str(ADW)], cwd=str(AGENT_BLOCKS),
                              input=edit.model_dump_json(), capture_output=True, text=True,
                              timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return _refused('The save took too long to confirm. Reload the tab to see what happened.')
    except OSError as error:
        return _refused(f'Could not run the settings ADW: {error}')
    answer = last_json_line(done.stdout)
    if answer is None:
        tail = (done.stderr or '').strip().splitlines()[-1:] or ['no output']
        return _refused(f'The settings ADW gave no answer (exit {done.returncode}): {tail[0][:200]}')
    return answer
