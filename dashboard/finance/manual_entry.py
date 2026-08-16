"""Manual receipt entry for MAZDA_DECISION_MODE=human_only.

When Mazda never runs, a scanned receipt has no parsed data at all -- there is
no packet to correct, unlike statement_review.py's quarantine flow. This
module lets an operator type the fields by hand and store the expense through
the exact same tool Mazda's own intake pipeline uses
(receipt_parsing_tools/parse_and_categorize.py --save), so duplicate
detection, near-duplicate receipt-linking, and the NEEDS_VENDOR_KEY fallback
all apply unchanged -- nothing here reimplements that logic.

``--engine local`` is load-bearing: it is the only engine value that never
attempts a real LLM/vision call (parse_and_categorize.py's _parse_receipt()
skips its provider-tier loop entirely for "local"), which is what makes this
safe to use while MAZDA_DECISION_MODE=human_only is trying to spend zero
tokens.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from statement_review import RF_PYPATH, RF_VENV_PY

PARSE_AND_CATEGORIZE_SCRIPT = os.path.expanduser(
    '~/rol_finances/tools/receipt_scanning_tools/receipt_parsing_tools/'
    'parse_and_categorize.py')
MANUAL_ENTRY_TIMEOUT_SEC = 90


class ManualReceiptEntry(BaseModel):
    """One human-entered receipt line item.

    Validation mirrors statement_review.py's apply_corrections(): non-empty
    merchant, ISO date, positive amount -- the same three fields, the same
    rules, applied here instead of to an existing parsed row.
    """
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True)

    image_path: str
    merchant_name: str
    transaction_date: str
    total_amount: float
    category_id: Optional[int] = None
    org_id: int = 1

    @field_validator('image_path')
    @classmethod
    def _image_path_non_empty(cls, value):
        if not value.strip():
            raise ValueError('image_path is required')
        return value

    @field_validator('merchant_name')
    @classmethod
    def _merchant_non_empty(cls, value):
        cleaned = ' '.join(value.split())
        if not cleaned:
            raise ValueError('merchant_name is required')
        return cleaned

    @field_validator('transaction_date')
    @classmethod
    def _date_is_iso(cls, value):
        date.fromisoformat(value)
        return value

    @field_validator('total_amount')
    @classmethod
    def _amount_is_positive(cls, value):
        if value <= 0:
            raise ValueError('total_amount must be positive')
        return value


def build_preview_command(image_path: str) -> list[str]:
    """Pure builder for a read-only OCR preview -- no --save, no I/O here.

    Same --engine local as the save command: this is the local-OCR pass
    parse_and_categorize.py always runs before applying overrides, run here
    on its own with --json so the form can prefill from it instead of
    starting blank.
    """
    return [RF_VENV_PY, PARSE_AND_CATEGORIZE_SCRIPT,
            '--file', image_path, '--engine', 'local', '--json']


def build_save_command(entry: ManualReceiptEntry) -> list[str]:
    """Pure builder for the parse_and_categorize.py argv -- no I/O, unit-tested."""
    cmd = [
        RF_VENV_PY, PARSE_AND_CATEGORIZE_SCRIPT,
        '--file', entry.image_path,
        '--engine', 'local',
        '--no-pick',
        '--save',
        '--merchant-name-override', entry.merchant_name,
        '--transaction-date-override', entry.transaction_date,
        '--total-amount-override', str(entry.total_amount),
        '--org-id', str(entry.org_id),
    ]
    if entry.category_id is not None:
        cmd += ['--category-id', str(entry.category_id)]
    return cmd


def _extract_json_result(stdout, required_key=None):
    """The LAST top-level JSON object in stdout, optionally requiring a key.

    parse_and_categorize.py's real result is always the final thing printed
    to stdout before exit -- but a dependency import warning, a deprecation
    notice, or (2026-08-16, confirmed via repro) a receipt-metadata debug
    dict can land on stdout *earlier* in the same run. A first-match scan
    (the approach statement_review.py's _parse_report_output uses for the
    cleaner store_statement_transactions.py output) grabbed that earlier,
    unrelated dict and reported a successful save as a failure. Scanning
    every candidate and keeping the last one -- filtered to one carrying
    `required_key` when given, since only the true result carries 'success'
    -- can't be fooled by incidental JSON-shaped output ahead of it.
    """
    decoder = json.JSONDecoder()
    text = stdout or ''
    best = None
    index, length = 0, len(text)
    while index < length:
        if text[index] != '{':
            index += 1
            continue
        try:
            value, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            index += 1
            continue
        # Jump past the whole object just consumed -- otherwise a nested
        # `{` inside it (e.g. {"ok": true, "party": {...}}) would be
        # rescanned as its own, unrelated top-level candidate.
        index += max(end, 1)
        if isinstance(value, dict) and (required_key is None or required_key in value):
            best = value
    return best or {}


def _run_parse_and_categorize(command, required_key=None):
    env = dict(os.environ, PYTHONPATH=RF_PYPATH)
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=MANUAL_ENTRY_TIMEOUT_SEC, env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {'returncode': 1, 'stderr': f'{type(exc).__name__}: {exc}', 'report': {}}
    return {
        'returncode': completed.returncode,
        'stderr': completed.stderr,
        'stdout': completed.stdout,
        'report': _extract_json_result(completed.stdout, required_key),
    }


def submit_manual_receipt_entry(entry: ManualReceiptEntry, runner=None):
    """Store one manually-entered receipt. Returns (ok, payload)."""
    run = runner or (lambda cmd: _run_parse_and_categorize(cmd, required_key='success'))
    result = run(build_save_command(entry))
    report = result.get('report') or {}
    if result.get('returncode') != 0 or not report.get('success', False):
        return False, {
            'error': (report.get('error') or result.get('stderr')
                      or result.get('stdout') or 'store failed'),
            'report': report,
        }
    return True, {'report': report}


def _extract_prefill(payload: dict) -> dict:
    """Best-effort fields from a --json parse payload, for the form to
    prefill. A None value means OCR didn't find that field -- the human
    types it in, exactly as if this preview step were skipped entirely.
    """
    party = payload.get('party') or {}
    totals = payload.get('totals') or {}
    return {
        'merchant_name': party.get('merchant_name') or None,
        'transaction_date': payload.get('transaction_date') or None,
        'total_amount': totals.get('total_amount'),
    }


def preview_receipt_parse(image_path: str, runner=None):
    """Run the local-OCR-only pass so the form can prefill instead of
    starting blank. Returns (ok, payload). ok=False just means the form
    stays blank -- OCR here is a convenience, never a requirement: the same
    --engine local guarantee (zero LLM/vision calls) applies as for save.
    """
    result = (runner or _run_parse_and_categorize)(build_preview_command(image_path))
    if result.get('returncode') != 0:
        return False, {'error': result.get('stderr') or 'preview failed'}
    report = result.get('report') or {}
    if not report:
        return False, {'error': 'could not parse OCR output'}
    return True, _extract_prefill(report)
