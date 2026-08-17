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
from typing import Optional

from pydantic import field_validator

from finance.expense_fields import ExpenseFieldRules
from finance.vendor_lookup import vendor_category_lookup
from statement_review import RF_PYPATH, RF_VENV_PY

PARSE_AND_CATEGORIZE_SCRIPT = os.path.expanduser(
    '~/rol_finances/tools/receipt_scanning_tools/receipt_parsing_tools/'
    'parse_and_categorize.py')
MANUAL_ENTRY_TIMEOUT_SEC = 90
#: Preview-only engines the "Prefill from OCR" (local, zero-token) and
#: "Gemini Flash Fill" (gemini-only, free-tier) buttons may request.
#: Deliberately excludes "auto"/"gemini" (parse_and_categorize.py's CLI
#: quirk: "gemini" is an alias for the FULL auto chain, including the
#: chatgpt-oauth/openai paid tiers on Gemini failure -- not a Gemini-only
#: mode) and "chatgpt-oauth"/"openai" outright, so a preview request can
#: never reach a paid tier no matter what a caller passes.
PREVIEW_ENGINES = frozenset({'local', 'gemini-only'})


class ManualReceiptEntry(ExpenseFieldRules):
    """One human-entered receipt line item.

    The merchant/date/amount rules come from ExpenseFieldRules -- the same
    three checks statement_review.py's apply_corrections() applies to a parsed
    row, and the same ones finance/expense_edit_model.ExpenseEdit applies to a
    correction -- so a hand-typed insert and a later edit can never disagree
    about what a valid field looks like. Only the fields specific to *storing a
    new document* live here.
    """

    image_path: str
    category_id: Optional[int] = None
    org_id: int = 1

    @field_validator('image_path')
    @classmethod
    def _image_path_non_empty(cls, value):
        if not value.strip():
            raise ValueError('image_path is required')
        return value


def build_preview_command(image_path: str, engine: str = 'local') -> list[str]:
    """Pure builder for a read-only OCR/AI preview -- no --save, no I/O here.

    `engine` must be one of PREVIEW_ENGINES: 'local' (the zero-token OCR
    pass parse_and_categorize.py always runs before applying overrides) or
    'gemini-only' (a real Gemini-only tier, falling back to local on
    failure -- never chatgpt-oauth/openai). Raises ValueError on anything
    else, so a preview request can never be turned into a paid-tier call.
    """
    if engine not in PREVIEW_ENGINES:
        raise ValueError(f'unsupported preview engine: {engine!r}')
    return [RF_VENV_PY, PARSE_AND_CATEGORIZE_SCRIPT,
            '--file', image_path, '--engine', engine, '--json']


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


def _document_text(payload: dict) -> str:
    """The document's raw OCR text, if the parse payload carried any.

    parse_and_categorize.py puts it at meta.raw_text. It is passed to the
    vendor lookup purely to disambiguate a merchant name that matches more
    than one stored vendor -- a DTE bill names its own account number, which
    is what says whether it is the house's or the church's.
    """
    meta = payload.get('meta') or {}
    if not isinstance(meta, dict):
        return ''
    text = meta.get('raw_text')
    return text if isinstance(text, str) else ''


def _reporting_label(category_id, category_namer, fallback: str | None):
    """A category name the form's dropdown can actually select.

    VendorCategoryLookup answers in categories_tree.txt's *leaf* vocabulary
    ("Housing Gas Bill"); the dropdown is built from the taxonomy's *reporting
    bucket* labels ("Housing Payment & Upkeep"). Handing the form a leaf name
    silently did nothing -- a <select> ignores a value matching no option --
    so a perfectly resolved vendor still left Category blank with no error
    anywhere (found 2026-08-17). Translating through ICategoryNamer is what
    makes "found the vendor" also mean "guessed the category".

    Falls back to the leaf name only when no namer was injected (offline
    tests): callers that want a selectable label always pass one.
    """
    if category_namer is None or category_id is None:
        return fallback
    try:
        return category_namer.name_for(category_id) or None
    except Exception:
        # Same fail-soft posture as the rest of prefill -- a taxonomy blip
        # leaves the dropdown for the operator, it never breaks the read.
        return None


def _resolve_vendor_match(merchant_name: str | None, lookup_fn=None,
                          document_text: str = '',
                          category_namer=None) -> dict:
    """Best-effort vendor_key/category lookup for an OCR'd merchant name, so
    the form can preselect the vendor dropdown (and its category) instead of
    only filling the free-text merchant field. A lookup failure here must
    never break OCR prefill -- same fail-soft posture as OCR itself -- so
    any exception just means "no match", not an error surfaced to the form.

    When the name matches several stored vendors that disagree about the
    category, nothing is prefilled and `vendor_candidates` comes back for the
    operator to choose from -- see vendor_disambiguation.py for why guessing
    one was a real defect ("DTE Energy" -> the house's 0544 account or the
    church's 0020 account, resolved by vendor_category.yaml ordering).

    `lookup_fn` mirrors `preview_receipt_parse`'s `runner` injection point --
    tests pass a fake so they don't depend on the real vendor_category.yaml.
    """
    blank = {'vendor_key': None, 'category_name': None,
             'vendor_ambiguous': False, 'vendor_candidates': []}
    # `.strip()`: a whitespace-only name is truthy in Python, so without it the
    # lookup was called with "   " and relied on _slugify to shrug it off.
    if not (merchant_name or '').strip():
        return blank
    try:
        match = (lookup_fn or vendor_category_lookup)().find_vendor_match(
            merchant_name, document_text=document_text)
    except Exception:
        return blank
    return {
        'vendor_key': match.vendor_key,
        'category_name': _reporting_label(
            getattr(match, 'category_id', None), category_namer,
            match.category_name),
        'vendor_ambiguous': bool(getattr(match, 'ambiguous', False)),
        'vendor_candidates': [
            {'vendor_key': c.vendor_key,
             'category_name': _reporting_label(
                 getattr(c, 'category_id', None), category_namer,
                 c.category_name)}
            for c in getattr(match, 'candidates', []) or []
        ],
    }


def preview_receipt_parse(image_path: str, engine: str = 'local', runner=None,
                           vendor_lookup_fn=None, category_namer=None):
    """Run a read-only parse pass so the form can prefill instead of
    starting blank. Returns (ok, payload). ok=False just means the form
    stays blank -- this is a convenience, never a requirement.

    `engine='local'` (default) keeps the zero-LLM/vision-call guarantee
    documented at module level. `engine='gemini-only'` is the dashboard's
    opt-in "Gemini Flash Fill" button -- see PREVIEW_ENGINES/
    build_preview_command for why it can't reach a paid tier even on
    failure.
    """
    try:
        command = build_preview_command(image_path, engine)
    except ValueError as exc:
        return False, {'error': str(exc)}
    result = (runner or _run_parse_and_categorize)(command)
    if result.get('returncode') != 0:
        return False, {'error': result.get('stderr') or 'preview failed'}
    report = result.get('report') or {}
    if not report:
        return False, {'error': 'could not parse OCR output'}
    prefill = _extract_prefill(report)
    # Every field can legitimately come back None now that the local OCR
    # fallback leaves unreadable fields blank instead of guessing (today's
    # date, a $0.00 total) -- that's a real "couldn't read this" result,
    # not a successful prefill with nothing in it.
    if not any(prefill.values()):
        return False, {'error': 'OCR could not read any fields from this document', **prefill}
    prefill.update(_resolve_vendor_match(
        prefill.get('merchant_name'), vendor_lookup_fn,
        document_text=_document_text(report),
        category_namer=category_namer))
    return True, prefill
