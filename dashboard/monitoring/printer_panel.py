"""The Printer tab: EG's printers, the default, recent print jobs, a test page and cancel.

Everything goes through agent_blocks' `adws/adw_printer.py`, the same ADW the
ChatGPT bridge worker runs, so the dashboard never prints by itself and never
imports printer code. Its last stdout line is `PRINTER_RESULT {json}`.

* `printer_payload()` runs `discover`: Windows printers, the default and the
  latest jobs from the registry. It reads only -- no driver installs, no
  settings changes, nothing printed -- and is cached for 30 s, since asking
  Windows costs a few seconds of PowerShell.
* `start_test_print()` prints the one fixed test page, and only when the body
  says `{"confirm": true}` and printing is switched on
  (`~/.config/startrek_printer/enabled`). There is no way to send text from
  here. It answers with the job id straight away; the print runs on.
* `start_document_print()` prints an already-stored file (a note's PDF
  attachment, so far) instead of the fixed test page. Same `{"confirm": true}`
  and switch rule, plus an explicit `printer_id` -- this machine has no
  Windows default printer, so one is never guessed. The file itself is
  resolved by an injected `resolve(data) -> (path, title)`, so this module
  never has to import notes_attachments.
* `cancel_job()` asks the ADW to cancel one job by id.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import threading
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict

AGENT_BLOCKS = Path(os.path.expanduser('~/agent_blocks'))
UV = Path(os.path.expanduser('~/.local/bin/uv'))
ADW = AGENT_BLOCKS / 'adws' / 'adw_printer.py'
ENABLED_FLAG = Path(os.path.expanduser('~/.config/startrek_printer/enabled'))
MARKER = 'PRINTER_RESULT '
JOB_ID = re.compile(r'[A-Za-z0-9_\-]{6,80}')
CACHE_SECONDS = 30.0
READ_TIMEOUT = 120          # discover / cancel; the first uv run may resolve packages
PRINT_TIMEOUT = 1800        # the ADW's own monitor stops well before this

_cache: dict = {'at': 0.0, 'payload': None}
_lock = threading.Lock()


class PrinterPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')

    enabled: bool
    ok: bool
    error: str = ''
    printers: list[dict] = []
    default: str | None = None
    documents: int = 0
    recent: list[dict] = []
    checked_at: float = 0.0


def result_line(stdout: str) -> dict | None:
    """The ADW's answer: its last `PRINTER_RESULT` line, parsed. Pure."""
    for line in reversed(stdout.splitlines()):
        if line.startswith(MARKER):
            try:
                data = json.loads(line[len(MARKER):])
            except ValueError:
                return None
            return data if isinstance(data, dict) else None
    return None


def _run(args: list[str], stdin: str = '', timeout: int = READ_TIMEOUT) -> dict:
    try:
        done = subprocess.run([str(UV), 'run', '--quiet', str(ADW), *args], input=stdin,
                              capture_output=True, text=True, timeout=timeout, cwd=str(AGENT_BLOCKS))
    except FileNotFoundError:
        return {'error': 'uv or the printer ADW is missing on this machine'}
    except subprocess.TimeoutExpired:
        return {'error': f'the printer ADW did not answer within {timeout} s'}
    return result_line(done.stdout) or {'error': 'the printer ADW gave no result line'}


def build_payload(answer: dict, enabled: bool, now: float) -> PrinterPayload:
    """Shape a `discover` answer for the page. Outbox documents are only counted, never named. Pure."""
    if 'error' in answer:
        return PrinterPayload(enabled=enabled, ok=False, error=str(answer['error'])[:300], checked_at=now)
    return PrinterPayload(enabled=enabled, ok=True, printers=list(answer.get('printers') or []),
                          default=answer.get('default'), documents=len(answer.get('documents') or []),
                          recent=list(answer.get('recent') or []), checked_at=now)


def printer_payload(refresh: bool = False) -> dict:
    with _lock:
        now = time.time()
        if refresh or _cache['payload'] is None or now - _cache['at'] > CACHE_SECONDS:
            _cache['payload'] = build_payload(_run(['discover']), ENABLED_FLAG.exists(), now).model_dump()
            _cache['at'] = now
        return _cache['payload']


def _forget() -> None:
    with _lock:
        _cache['at'] = 0.0


def new_job_id() -> str:
    return 'd_' + secrets.token_hex(12)


def start_test_print(data: dict, launch=None) -> dict:
    """Start the fixed test page. `launch(job_id)` is injected by tests; it defaults to a background thread."""
    if data.get('confirm') is not True:
        return {'ok': False, 'message': 'Printing needs {"confirm": true}; nothing was printed.'}
    if not ENABLED_FLAG.exists():
        return {'ok': False, 'message': 'Printing is switched off on this computer; nothing was printed.'}
    job_id = new_job_id()
    (launch or _launch_test_page)(job_id)
    _forget()
    return {'ok': True, 'job_id': job_id,
            'message': 'Test page handed to the printer workflow. Its status shows below; '
                       'leaving the Windows queue is not proof that paper came out.'}


def _launch_test_page(job_id: str) -> None:
    def work() -> None:
        _run(['print', '--job-id', job_id], stdin='{"kind": "test_page"}', timeout=PRINT_TIMEOUT)
        _forget()
    threading.Thread(target=work, name=f'print-{job_id}', daemon=True).start()


def start_document_print(data: dict, resolve, launch=None) -> dict:
    """Print an already-stored file -- so far, a note's PDF attachment -- rather than the fixed test
    page. `resolve(data) -> (path, title)` is injected so this module never imports notes_attachments;
    it raises `LookupError` for anything this module should refuse (a bad id, a damaged file, a note
    that is not found), and that message is returned to the caller unchanged. `launch(job_id, stdin)`
    is injected the same way as the test page's; it defaults to a background thread.

    `printer_id` is required, not defaulted: this machine has no Windows default printer, so guessing
    one would either fail silently or print on whichever queue happened to answer first.
    """
    if data.get('confirm') is not True:
        return {'ok': False, 'message': 'Printing needs {"confirm": true}; nothing was printed.'}
    if not ENABLED_FLAG.exists():
        return {'ok': False, 'message': 'Printing is switched off on this computer; nothing was printed.'}
    printer_id = data.get('printer_id')
    if not isinstance(printer_id, str) or not printer_id.strip():
        return {'ok': False, 'message': 'A printer_id is required; this computer has no default printer.'}
    try:
        path, title = resolve(data)
    except LookupError as exc:
        return {'ok': False, 'message': str(exc)}
    job_id = new_job_id()
    stdin = json.dumps({'kind': 'document_file', 'path': path, 'title': title, 'printer_id': printer_id})
    (launch or _launch_document)(job_id, stdin)
    _forget()
    return {'ok': True, 'job_id': job_id,
            'message': f'"{title}" handed to the printer workflow on {printer_id}. Its status shows '
                       'below; leaving the Windows queue is not proof that paper came out.'}


def _launch_document(job_id: str, stdin: str) -> None:
    def work() -> None:
        _run(['print', '--job-id', job_id], stdin=stdin, timeout=PRINT_TIMEOUT)
        _forget()
    threading.Thread(target=work, name=f'print-{job_id}', daemon=True).start()


def cancel_job(data: dict) -> dict:
    job_id = data.get('job_id')
    if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id):
        return {'ok': False, 'message': 'A valid job_id is required.'}
    answer = _run(['cancel', '--job-id', job_id])
    _forget()
    if 'error' in answer:
        return {'ok': False, 'message': str(answer['error'])[:300]}
    return {'ok': True, 'job': answer.get('job'), 'message': f"Job {job_id}: {answer.get('job', {}).get('state')}"}
