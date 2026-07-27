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
from datetime import date
from urllib.parse import quote

NEEDS_REVIEW_DIRNAME = '_needs_review'
DEFAULT_ARCHIVE_ROOT = os.path.expanduser(
    '~/rol_finances/readable_documents/bank_statements'
)
STORE_SCRIPT = os.path.expanduser(
    '~/rol_finances/tools/receipt_scanning_tools/store_statement_transactions.py'
)
ANNOTATION_SCRIPT = os.path.expanduser(
    '~/rol_finances/tools/receipt_scanning_tools/apply_statement_annotations.py'
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
    review_id = os.path.basename(sidecar_path)
    document_path = (
        sidecar_path[:-len('.json')]
        if sidecar_path.endswith('.json')
        else sidecar_path
    )
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
        'id': review_id,
        'kind': _kind(packet),
        'bank_name': packet.get('bank_name'),
        'account_last4': packet.get('account_last4'),
        'statement_total': packet.get('statement_total'),
        'workbook_ambiguous_last4': packet.get('workbook_ambiguous_last4') or [],
        'reason': packet.get('reason'),
        'quarantined_at': packet.get('quarantined_at'),
        'source_file': packet.get('source_file'),
        'document_path': document_path,
        'document_url': (
            '/api/statement-review-document?id='
            + quote(review_id, safe='')
        ),
        # Ask Mazda receives the complete retry packet, not a lossy summary.
        # This is the same data the store retry will use after the human acts.
        'document_context': {
            'pending_review_id': review_id,
            'quarantined_document_path': document_path,
            **packet,
        },
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

    row_errors = packet.get('row_errors') or []
    # store_statement_transactions.py already tries the clean archived PDF for
    # this account/period before quarantining anything (see RowGapResolver) --
    # reaching here with a long list means that lookup found nothing, not that
    # nobody tried. Enumerating every row anyway is what produced a wall of a
    # dozen near-identical questions; past a couple of genuine gaps, ask once.
    if len(row_errors) > 2:
        bank = packet.get('bank_name') or 'this account'
        return (
            f"{len(row_errors)} transactions on this {bank} statement still "
            f"have an unreadable date, description, or amount after checking "
            f"the archived clean statement PDF for this account and period. "
            f"Please open the document and fill in what you can read, or "
            f"attach the correct statement PDF if one isn't archived yet."
        )

    parts = []
    for row in row_errors:
        where = row.get('description') or 'an unlabeled row'
        when = row.get('date') or 'an unreadable date'
        missing = set(row.get('missing') or [])
        suggested = row.get('suggested_amount')
        if missing == {'date'}:
            line = (
                f"The transaction date is unreadable for {where}. "
                f"Please enter the transaction date."
            )
        elif missing == {'description'}:
            line = (
                f"The transaction description is unreadable for the row on {when}. "
                f"Please enter the merchant or description."
            )
        else:
            line = f"I can't read the expense for {where} on {when}."
        if 'amount' in missing and suggested is not None:
            line += (
                f" My guess is ${suggested:,.2f}. Please enter a different "
                f"number if you can read the garbled number."
            )
        elif 'amount' in missing:
            line += " Please enter the expense amount."
        extra = missing - {'amount', 'date', 'description'}
        if extra:
            line += f" Please correct: {', '.join(sorted(extra))}."
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


def review_document_path(review_id, archive_root=None):
    """Resolve one queued review id to its quarantined document.

    The id must name a current JSON sidecar directly inside ``_needs_review``.
    Serving only the sibling document keeps the dashboard endpoint from
    becoming an arbitrary local-file reader.
    """
    if not isinstance(review_id, str) or not review_id.endswith('.json'):
        return ''
    if os.path.basename(review_id) != review_id:
        return ''
    directory = os.path.abspath(needs_review_dir(archive_root))
    sidecar = os.path.abspath(os.path.join(directory, review_id))
    try:
        if os.path.commonpath([sidecar, directory]) != directory:
            return ''
    except ValueError:
        return ''
    document = sidecar[:-len('.json')]
    if not os.path.isfile(sidecar) or not os.path.isfile(document):
        return ''
    return document


def apply_corrections(packet, corrections):
    """Fill missing transaction fields from the review dialog.

    ``corrections`` maps row index -> ``{field: value}``. Only the three fields
    the statement validator understands are accepted. The operation is pure so
    the substitution is testable without touching the filesystem or store.
    """
    transactions = [dict(row) for row in packet.get('transactions') or []]
    for raw_index, fields in (corrections or {}).items():
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            raise ValueError(f'invalid row index {raw_index!r}')
        if not 0 <= index < len(transactions):
            raise ValueError(f'row {index} is not in this statement')
        if not isinstance(fields, dict):
            raise ValueError(f'invalid corrections for row {index}')
        row = transactions[index]
        for field, raw_value in fields.items():
            if field == 'amount':
                try:
                    value = float(raw_value)
                except (TypeError, ValueError):
                    raise ValueError(f'invalid amount for row {index}')
                if value <= 0:
                    raise ValueError(f'invalid amount for row {index}')
                # Statement purchases are negative by the parser's convention;
                # a human typing "4.50" means a $4.50 charge. Preserve a known
                # credit sign, otherwise default an unreadable amount to charge.
                existing = row.get('amount')
                row['amount'] = abs(value) if isinstance(
                    existing, (int, float)) and existing > 0 else -abs(value)
            elif field == 'date':
                value = str(raw_value or '').strip()
                try:
                    date.fromisoformat(value)
                except ValueError:
                    raise ValueError(f'invalid date for row {index}')
                row['date'] = value
            elif field == 'description':
                value = ' '.join(str(raw_value or '').split())
                if not value:
                    raise ValueError(f'invalid description for row {index}')
                row['description'] = value
            else:
                raise ValueError(f'unsupported field {field!r} for row {index}')
        if row.get('date') and row.get('description') and isinstance(
                row.get('amount'), (int, float)):
            row.pop('unreadable', None)
    return transactions


def apply_amounts(packet, amounts):
    """Backward-compatible amount-only wrapper used by older callers/tests."""
    return apply_corrections(
        packet,
        {index: {'amount': value} for index, value in (amounts or {}).items()},
    )


def resolve_review(review_id, corrections=None, amounts=None, archive_root=None,
                   runner=None, annotation_runner=None):
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
        if corrections is None:
            corrections = {
                index: {'amount': value}
                for index, value in (amounts or {}).items()
            }
        transactions = apply_corrections(packet, corrections)
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
            'error': (
                report.get('error')
                or result.get('stderr')
                or result.get('stdout')
                or 'store failed'
            ),
            'report': report,
            'item': build_review_item(sidecar, packet),
        }

    expense_ids = []
    for raw_id in (
            list(report.get('expense_ids') or [])
            + list(report.get('duplicate_expense_ids') or [])):
        try:
            expense_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if expense_id not in expense_ids:
            expense_ids.append(expense_id)
    if expense_ids:
        annotation_command = [
            RF_VENV_PY,
            ANNOTATION_SCRIPT,
            '--image',
            source_file or '',
            '--expense-ids',
            ','.join(str(expense_id) for expense_id in expense_ids),
        ]
        if packet.get('env_path'):
            annotation_command += ['--env-path', packet['env_path']]
        annotation_result = (annotation_runner or _run_store)(annotation_command)
        annotation_report = annotation_result.get('report') or {}
        if (annotation_result.get('returncode') != 0
                or not annotation_report.get('ok', False)):
            problems = annotation_report.get('problems') or []
            error = (
                '; '.join(str(problem) for problem in problems)
                or annotation_result.get('stderr')
                or annotation_result.get('stdout')
                or 'handwritten category step failed'
            )
            return False, {
                'error': error,
                'report': report,
                'item': build_review_item(sidecar, packet),
            }
        report['annotations'] = annotation_report

    # A failed retry can leave another timestamped packet for the same immutable
    # staged scan. Once storage is confirmed, clear every packet for that source
    # so an older copy cannot immediately reopen as though it were new work.
    source_file = packet.get('source_file')
    for name in os.listdir(directory):
        if not name.endswith('.json'):
            continue
        candidate = os.path.join(directory, name)
        try:
            with open(candidate, 'r', encoding='utf-8') as handle:
                same_source = json.load(handle).get('source_file') == source_file
        except (OSError, ValueError):
            same_source = False
        if not same_source:
            continue
        for path in (candidate, os.path.splitext(candidate)[0]):
            try:
                os.unlink(path)
            except OSError:
                pass
    return True, {'report': report}


def _parse_report_output(stdout):
    """Extract the store's JSON object even if a dependency printed first."""
    text = stdout or ''
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != '{':
            continue
        try:
            value, _end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {}


def _run_store(command):
    env = dict(os.environ, PYTHONPATH=RF_PYPATH)
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=RESOLVE_TIMEOUT_SEC, env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {'returncode': 1, 'stderr': f'{type(exc).__name__}: {exc}', 'report': {}}
    report = _parse_report_output(completed.stdout)
    return {
        'returncode': completed.returncode,
        'stderr': completed.stderr,
        'stdout': completed.stdout,
        'report': report,
    }
