"""Backing logic for the Scanner screen's statement-review dialog.

When `store_statement_transactions.py` refuses a statement it parks the image in
`readable_documents/bank_statements/_needs_review/` next to a JSON sidecar that
carries everything needed to run it again -- the parsed rows, the statement
total, which rows were unreadable, and a suggested amount where subtraction can
determine one. This module turns those sidecars into review items for the
dashboard and applies a human's answers by re-running the store command.

Two kinds of item, matching the two ways a statement can be refused:

* ``workbook``    -- the account's last four digits could not be resolved. The
  human adds a row to Known_Credit_Cards_and_Banks.xlsx and presses OK; we just
  re-run, because the workbook is re-read on every lookup. If it still cannot be
  resolved the item simply comes back, which is the "dialog pops up again"
  behavior EG asked for.
* ``amounts``     -- one or more rows are unreadable. The human confirms or
  overrides the suggested amount for each, and we re-run with those filled in.

Nothing here guesses. A suggestion is only ever offered when exactly one amount
is missing and the printed total makes it arithmetic; the human still has to
accept it.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile

NEEDS_REVIEW_DIRNAME = '_needs_review'
DEFAULT_ARCHIVE_ROOT = os.path.expanduser(
    '~/rol_finances/readable_documents/bank_statements'
)
STORE_SCRIPT = os.path.expanduser(
    '~/rol_finances/tools/receipt_scanning_tools/store_statement_transactions.py'
)
RF_VENV_PY = '/home/adamsl/rol_finances/.venv/bin/python3'
RF_PYPATH = '/home/adamsl/rol_finances'
RESOLVE_TIMEOUT_SEC = 180


def needs_review_dir(archive_root=None):
    return os.path.join(archive_root or DEFAULT_ARCHIVE_ROOT, NEEDS_REVIEW_DIRNAME)


def _kind(packet):
    return 'workbook' if packet.get('needs_workbook_entry') else 'amounts'


def build_review_item(sidecar_path, packet):
    """Shape one sidecar into what the dialog renders. Pure."""
    rows = []
    for row in packet.get('row_errors') or []:
        rows.append({
            'index': row.get('index'),
            'date': row.get('date'),
            'description': row.get('description'),
            'missing': row.get('missing') or [],
            'suggested_amount': row.get('suggested_amount'),
        })
    return {
        'id': os.path.basename(sidecar_path),
        'kind': _kind(packet),
        'bank_name': packet.get('bank_name'),
        'account_last4': packet.get('account_last4'),
        'statement_total': packet.get('statement_total'),
        'workbook_ambiguous_last4': packet.get('workbook_ambiguous_last4') or [],
        'reason': packet.get('reason'),
        'quarantined_at': packet.get('quarantined_at'),
        'source_file': packet.get('source_file'),
        'rows': rows,
        'message': review_message(packet),
    }


def review_message(packet):
    """The human-facing sentence for this item, in EG's own phrasing."""
    if _kind(packet) == 'workbook':
        bank = packet.get('bank_name') or 'this account'
        ambiguous = packet.get('workbook_ambiguous_last4') or []
        if ambiguous:
            return (
                f"There are several cards on file for {bank} "
                f"({', '.join(ambiguous)}). I can't tell which one this "
                f"statement belongs to. Please make the row for this card "
                f"unambiguous in Known_Credit_Cards_and_Banks.xlsx, then press OK."
            )
        return (
            f"I don't have {bank} in Known_Credit_Cards_and_Banks.xlsx, so I "
            f"don't know the last 4 digits for its filename. Please add a row "
            f"for this card, then press OK."
        )

    parts = []
    for row in packet.get('row_errors') or []:
        where = row.get('description') or 'an unlabeled row'
        when = row.get('date') or 'an unreadable date'
        suggested = row.get('suggested_amount')
        line = f"I can't read the expense for {where} on {when}."
        if suggested is not None:
            line += (
                f" My guess is ${suggested:,.2f}. Please enter a different "
                f"number if you can read the garbled number."
            )
        else:
            line += " Please enter the expense number."
        parts.append(line)
    return ' '.join(parts)


def list_reviews(archive_root=None):
    """Every pending sidecar, newest first."""
    directory = needs_review_dir(archive_root)
    items = []
    try:
        names = sorted(os.listdir(directory), reverse=True)
    except OSError:
        return items
    for name in names:
        if not name.endswith('.json'):
            continue
        path = os.path.join(directory, name)
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                packet = json.load(handle)
        except (OSError, ValueError):
            continue
        items.append(build_review_item(path, packet))
    return items


def apply_amounts(packet, amounts):
    """Return the packet's transactions with human-supplied amounts filled in.

    ``amounts`` maps row index -> value. Pure, so the substitution is testable
    without touching the filesystem or the store script.
    """
    transactions = [dict(row) for row in packet.get('transactions') or []]
    for raw_index, raw_value in (amounts or {}).items():
        try:
            index = int(raw_index)
            value = float(raw_value)
        except (TypeError, ValueError):
            raise ValueError(f'invalid amount for row {raw_index!r}')
        if not 0 <= index < len(transactions):
            raise ValueError(f'row {index} is not in this statement')
        # Statement purchases are negative by the parser's convention; a human
        # typing "4.50" means a $4.50 charge, so keep the sign the row already
        # had rather than flipping it to a credit.
        transactions[index]['amount'] = -abs(value)
        transactions[index].pop('unreadable', None)
    return transactions


def resolve_review(review_id, amounts=None, archive_root=None, runner=None):
    """Re-run the store for one quarantined statement.

    Returns ``(ok, payload)``. On success the sidecar and its parked image are
    removed, so the item disappears from the dialog; on failure both stay put
    and the caller re-renders the item (the "pops up again" path).
    """
    directory = needs_review_dir(archive_root)
    sidecar = os.path.join(directory, os.path.basename(review_id))
    if not sidecar.startswith(directory) or not os.path.isfile(sidecar):
        return False, {'error': f'no pending review named {review_id!r}'}

    with open(sidecar, 'r', encoding='utf-8') as handle:
        packet = json.load(handle)

    try:
        transactions = apply_amounts(packet, amounts)
    except ValueError as exc:
        return False, {'error': str(exc)}

    parse_payload = {
        'ok': True,
        'bank_name': packet.get('bank_name'),
        'account_number': packet.get('account_last4'),
        'statement_total': packet.get('statement_total'),
        'transactions': transactions,
    }
    source_file = packet.get('source_file')
    handle = tempfile.NamedTemporaryFile(
        'w', suffix='.json', prefix='statement_retry_', delete=False, encoding='utf-8'
    )
    try:
        json.dump(parse_payload, handle)
        handle.close()
        command = [
            RF_VENV_PY, STORE_SCRIPT,
            '-f', handle.name,
            '--source-file', source_file or '',
            '--archive-root', packet.get('archive_root') or (
                archive_root or DEFAULT_ARCHIVE_ROOT),
        ]
        if packet.get('env_path'):
            command += ['--env-path', packet['env_path']]
        result = (runner or _run_store)(command)
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass

    report = result.get('report') or {}
    if result.get('returncode') != 0 or not report.get('ok', False):
        # Still not storable — leave it queued so the dialog comes back.
        return False, {
            'error': report.get('error') or result.get('stderr') or 'store failed',
            'report': report,
            'item': build_review_item(sidecar, packet),
        }

    for path in (sidecar, os.path.splitext(sidecar)[0]):
        try:
            os.unlink(path)
        except OSError:
            pass
    return True, {'report': report}


def _run_store(command):
    env = dict(os.environ, PYTHONPATH=RF_PYPATH)
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=RESOLVE_TIMEOUT_SEC, env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {'returncode': 1, 'stderr': f'{type(exc).__name__}: {exc}', 'report': {}}
    try:
        report = json.loads(completed.stdout or '{}')
    except ValueError:
        report = {}
    return {
        'returncode': completed.returncode,
        'stderr': completed.stderr,
        'report': report,
    }
