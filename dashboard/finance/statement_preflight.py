"""Extracting and validating statement metadata before dispatch or storage.

``run_statement_preflight`` is the one place that turns
``parse_statement_scan.py``'s raw JSON into something dispatch/storage can
trust: it resolves the bank name and last-four digits (operator override, the
parser's own read, or the known-cards workbook, in that priority), rejects a
scan that actually holds more than one account, and drops any transaction
missing a date/description/amount rather than passing a half-read row
downstream. The five module-private helpers below exist only to serve it and
travel with it for that reason -- none of them is called from anywhere else
in the codebase.

Fully self-contained: unlike the intake-folding and document-processing
extractions beside it, nothing here reaches back into server.py's mutable
state, so there is no ``Collaborators`` bundle to build.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime

from paths import ROL_FINANCES_DIR

MAZDA_INTAKE_PYTHON = f'{ROL_FINANCES_DIR}/.venv/bin/python3'
STATEMENT_PARSE_SCRIPT = (
    f'{ROL_FINANCES_DIR}/tools/receipt_scanning_tools/parse_statement_scan.py')
STATEMENT_PREFLIGHT_TIMEOUT_SEC = 180


def _statement_last4(value):
    text = str(value or '').strip()
    match = re.search(r'(?:^|\D)(\d{4})$', text)
    if match:
        return match.group(1)
    # Some statements print the complete account number and vision returns it
    # despite the parser contract asking for the final four. Six or more plain
    # digits are unambiguously a full account number; retain its final four.
    # Deliberately do not truncate five-digit values: malformed five-digit Amex
    # workbook cells are a known trap and must continue to fail closed.
    if re.fullmatch(r'\d{6,}', text):
        return text[-4:]
    return None


def _default_statement_account_directory():
    """Build the workbook-backed last-four resolver without a hard import."""
    if ROL_FINANCES_DIR not in sys.path:
        sys.path.insert(0, ROL_FINANCES_DIR)
    from tools.receipt_scanning_tools.known_accounts import KnownCardsWorkbook
    return KnownCardsWorkbook()


def _complete_statement_transactions(rows):
    """Keep only rows carrying a valid date, description, and numeric amount."""
    complete = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        description = ' '.join(str(row.get('description') or '').split())
        try:
            datetime.strptime(str(row.get('date') or ''), '%Y-%m-%d')
            amount = float(row['amount'])
        except (KeyError, TypeError, ValueError):
            continue
        normalized = dict(row)
        normalized.update(description=description, amount=amount)
        if description:
            complete.append(normalized)
    return complete


def _statement_records(parsed):
    """Normalize parse_statement_scan.py's output to a list of statement dicts.

    The script grew a multi-statement envelope on 2026-07-22 (one scanned page
    can hold two cards): {'statements': [{bank_name, account_number,
    transactions, ...}, ...]}. It previously put those fields at the top level.
    Both shapes are accepted here so the preflight keeps working whichever
    version of the script is deployed -- reading only the old flat keys against
    the new envelope silently yielded no bank, no last4 and no transactions,
    which rejected every statement scan before it could be dispatched.
    """
    if not isinstance(parsed, dict):
        return []
    statements = parsed.get('statements')
    if isinstance(statements, list):
        return [s for s in statements if isinstance(s, dict)]
    if any(parsed.get(key) is not None
           for key in ('bank_name', 'account_number', 'transactions')):
        return [parsed]
    return []


def _statement_records_summary(statements):
    """Human-readable 'Chase 1234, Amex 5678' for a multi-statement rejection."""
    labels = []
    for statement in statements:
        bank = ' '.join(str(statement.get('bank_name') or '').split())
        last4 = _statement_last4(statement.get('account_number'))
        labels.append(' '.join(part for part in (bank, last4) if part)
                      or 'unidentified account')
    return ', '.join(labels)


def run_statement_preflight(
        image_path, facade_result, metadata=None, account_directory=None,
        engine='auto', rol_finances_dir=ROL_FINANCES_DIR):
    """Extract and validate statement metadata before dispatch or storage.

    `engine`: 'auto' (default, unchanged behavior) is parse_statement_scan.py's
    own full Gemini/Codex/ChatGPT/OpenAI fallback chain, used for every
    automatic Mazda dispatch. 'gemini-only'/'haiku-only' name one provider with
    no fallback -- the dashboard's "Read with Gemini"/"Read with Haiku"
    buttons, where an operator who chose a provider must get exactly that one,
    not a silent fallback to a different one on failure.
    """
    if (facade_result or {}).get('doc_kind') not in ('statement', 'bank_statement'):
        return None
    metadata = metadata if isinstance(metadata, dict) else {}
    command = [MAZDA_INTAKE_PYTHON, STATEMENT_PARSE_SCRIPT, image_path]
    bank_override = ' '.join(str(metadata.get('bank_name') or '').split())
    last4_override = _statement_last4(metadata.get('account_last4'))
    if bank_override:
        command.extend(['--bank-name', bank_override])
    if last4_override:
        command.extend(['--account-last4', last4_override])
    if engine and engine != 'auto':
        command.extend(['--engine', engine])
    try:
        proc = subprocess.run(
            command, cwd=rol_finances_dir, capture_output=True, text=True,
            timeout=STATEMENT_PREFLIGHT_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'rejected': True,
                'error': 'statement extraction timed out before storage'}
    except Exception as exc:
        return {'ok': False, 'rejected': True,
                'error': f'statement extraction failed before storage: {exc}'}
    output = (proc.stdout or '').strip()
    try:
        json_start = output.find('{')
        if json_start < 0:
            raise ValueError('no JSON object')
        parsed = json.loads(output[json_start:])
    except (ValueError, json.JSONDecodeError):
        detail = (proc.stderr or output or f'exit {proc.returncode}')[:300]
        return {'ok': False, 'rejected': True,
                'error': f'statement extraction returned no JSON: {detail}'}
    if not parsed.get('ok'):
        return {'ok': False, 'rejected': True,
                'error': parsed.get('error') or 'statement extraction failed'}

    statements = _statement_records(parsed)
    if len(statements) > 1:
        # The parser can split one scanned page into several accounts, but every
        # stage after this point -- the --bank-name/--account-last4 flags in
        # build_mazda_scan_message, the single per-scanner intake record, the
        # store script -- describes ONE account. Attributing two accounts'
        # transactions to statements[0] would file real money under the wrong
        # card silently, so halt and ask for one statement per pass instead.
        return {
            'ok': False, 'rejected': True, 'needs_statement_metadata': False,
            'error': ('Statement rejected: this scan holds '
                      f'{len(statements)} separate statements '
                      f'({_statement_records_summary(statements)}). Storage '
                      'handles one account per scan -- rescan them one at a '
                      'time.'),
        }
    statement = statements[0] if statements else {}
    parsed_bank_name = ' '.join(
        str(statement.get('bank_name') or '').split())
    facade_issuer = ' '.join(
        str((facade_result or {}).get('vendor') or '').split())
    if facade_issuer.lower() in ('unknown', 'none', 'null'):
        facade_issuer = ''
    bank_name = bank_override or parsed_bank_name or facade_issuer
    statement_last4 = _statement_last4(statement.get('account_number'))
    account_last4 = last4_override or statement_last4
    last4_source = 'operator' if last4_override else (
        'statement' if account_last4 else 'unknown')
    workbook_ambiguous_last4 = []
    workbook_matched_names = []
    # The primary branded letterhead identifies the account family more safely
    # than OCR of marked-over digits.  Always try that identity even when vision
    # emitted four digits; a unique workbook row is authoritative.  If there is
    # no branded identity, retain the older missing-last4 lookup by bank name.
    lookup_candidates = []
    if not last4_override and facade_issuer:
        lookup_candidates.append(facade_issuer)
    if not account_last4 and bank_name and bank_name not in lookup_candidates:
        lookup_candidates.append(bank_name)
    lookup = None
    lookup_name = ''
    for candidate in lookup_candidates:
        try:
            candidate_lookup = (
                account_directory or _default_statement_account_directory()
            ).lookup_last4(candidate)
        except Exception:
            candidate_lookup = None
        if not candidate_lookup:
            continue
        candidate_last4 = _statement_last4(
            getattr(candidate_lookup, 'last4', None))
        candidate_ambiguity = list(
            getattr(candidate_lookup, 'ambiguous_last4', ()) or ())
        if candidate_last4 or candidate_ambiguity:
            lookup = candidate_lookup
            lookup_name = candidate
            break
    if lookup:
        workbook_last4 = _statement_last4(getattr(lookup, 'last4', None))
        workbook_ambiguous_last4 = list(
            getattr(lookup, 'ambiguous_last4', ()) or ())
        workbook_matched_names = list(
            getattr(lookup, 'matched_names', ()) or ())
        if workbook_last4:
            account_last4 = workbook_last4
            last4_source = 'known_cards_workbook'
            if lookup_name == facade_issuer:
                bank_name = facade_issuer
        elif workbook_ambiguous_last4:
            account_last4 = None
            last4_source = 'unknown'
    transactions = _complete_statement_transactions(statement.get('transactions'))
    if not transactions:
        return {
            'ok': False, 'rejected': True, 'needs_statement_metadata': False,
            'error': ('Statement rejected: no complete transaction with date, '
                      'vendor/description, and amount was found.'),
        }
    missing = []
    if not bank_name:
        missing.append('bank_name')
    if not account_last4:
        missing.append('account_last4')
    result = dict(parsed)
    result.update({
        'bank_name': bank_name or None,
        'account_last4': account_last4,
        'account_number': account_last4,
        'transactions': transactions,
        'transaction_count': len(transactions),
        'last4_source': last4_source,
        'workbook_ambiguous_last4': workbook_ambiguous_last4,
        'workbook_matched_names': workbook_matched_names,
    })
    if missing:
        ambiguity = (
            ' Candidates in the known-cards workbook: '
            + ', '.join(workbook_ambiguous_last4) + '.'
            if workbook_ambiguous_last4 else '')
        result.update({
            'ok': False,
            'needs_statement_metadata': True,
            'missing_fields': missing,
            'error': (
                'Statement needs bank name and account last four before storage.'
                + ambiguity),
        })
    return result
