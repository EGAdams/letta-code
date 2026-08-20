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
from finance.statement_heuristic import looks_like_multiple_transactions
from finance.vendor_lookup import vendor_category_lookup
from statement_review import RF_PYPATH, RF_VENV_PY

PARSE_AND_CATEGORIZE_SCRIPT = os.path.expanduser(
    '~/rol_finances/tools/receipt_scanning_tools/receipt_parsing_tools/'
    'parse_and_categorize.py')
MANUAL_ENTRY_TIMEOUT_SEC = 90
#: Preview-only engines a read of one document may request: 'local' (the
#: zero-token OCR pass, no longer offered by any button -- see
#: finance/mazda_fill.py) plus the three single-provider, no-fallback models
#: the Mazda Fill dropdown offers. Each names ONE subscription this house
#: already pays a flat fee for: Gemini's free tier, Claude Haiku through this
#: box's Claude Code OAuth session (never an ANTHROPIC_API_KEY, see
#: claude_oauth_client.py), and the ChatGPT/Codex subscription through the
#: installed Codex CLI.
#:
#: Deliberately excludes "auto"/"gemini" (parse_and_categorize.py's CLI quirk:
#: "gemini" is an alias for the FULL auto chain, including the paid tiers on
#: Gemini failure -- not a Gemini-only mode) and "openai" outright, so a
#: preview request can never reach a metered tier no matter what a caller
#: passes. "chatgpt-oauth" is likewise left off: it is the same subscription
#: as 'codex-only' reached through a different endpoint and a different
#: default model, and offering both would mean two dropdown entries that read
#: the same page with two different models.
PREVIEW_ENGINES = frozenset({'local', 'gemini-only', 'haiku-only', 'codex-only'})

#: What parse_and_categorize.py stamps meta.model_name with when every named
#: engine failed and free local OCR answered in its place.
LOCAL_FALLBACK_MODEL_NAME = 'local-fallback'


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
    pass parse_and_categorize.py always runs before applying overrides),
    'gemini-only' (a real Gemini-only tier, falling back to local on
    failure -- never chatgpt-oauth/openai), or 'haiku-only' (Claude Haiku via
    this box's Claude Code subscription OAuth session, falling back to local
    on failure -- never a metered ANTHROPIC_API_KEY). Raises ValueError on
    anything else, so a preview request can never be turned into a paid-tier
    call.
    """
    if engine not in PREVIEW_ENGINES:
        raise ValueError(f'unsupported preview engine: {engine!r}')
    return [RF_VENV_PY, PARSE_AND_CATEGORIZE_SCRIPT,
            '--file', image_path, '--engine', engine, '--json']


def build_save_command(entry: ManualReceiptEntry) -> list[str]:
    """Pure builder for the parse_and_categorize.py argv -- no I/O, unit-tested."""
    # The two free-text values use `--opt=value` rather than `--opt value`:
    # argparse refuses a separate value beginning with a dash ("-Kroger" is
    # read as an unknown option, and the save fails), while the equals form is
    # always taken as the value. The remaining options carry validated numbers
    # and ISO dates, which cannot start with a dash.
    cmd = [
        RF_VENV_PY, PARSE_AND_CATEGORIZE_SCRIPT,
        f'--file={entry.image_path}',
        '--engine', 'local',
        '--no-pick',
        '--save',
        f'--merchant-name-override={entry.merchant_name}',
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


def _engine_failure_of(report: dict) -> dict:
    """The chosen model's own account of why it did not fill the form.

    parse_and_categorize.py stamps this onto the local-fallback report when a
    model ANSWERED and still could not give the page a receipt's identity (see
    receipt_engine.py's ReceiptShapeMismatch). Absent for a 429/503/missing
    key, because those mean nobody read the document. Passing it through
    unchanged is what lets MazdaFillService re-read the page as a statement
    instead of handing back an empty form -- and what lets the operator read
    "found no transaction date" instead of a quota error from an unrelated
    model further down the ladder.
    """
    meta = report.get('meta')
    failure = meta.get('engine_failure') if isinstance(meta, dict) else None
    return failure if isinstance(failure, dict) else {}


def _answered_by_local_fallback(payload: dict, engine: str) -> bool:
    """Did free OCR answer a question that was asked of a named model?

    parse_and_categorize.py falls back to local OCR whenever the engine it was
    given fails, and returns that result as a normal success. For the auto
    chain that is right. For a named model it is not: the operator picked
    Gemini/Haiku/Codex, and a quota-exhausted account (verified 2026-08-19:
    both Codex accounts, one out of weekly usage and one with a dead refresh
    token) would otherwise fill the form with OCR's guess under that model's
    name. On the DTE gas bill that guess is the merchant "Account Number".

    Reporting it as the failure it is costs the operator nothing -- they can
    pick the other model, or type three fields -- and is the difference
    between "Mazda read this" and "something read this".
    """
    if engine == 'local':
        return False
    meta = payload.get('meta') or {}
    if not isinstance(meta, dict):
        return False
    return meta.get('model_name') == LOCAL_FALLBACK_MODEL_NAME


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


def _engine_failure_detail(stderr: str | None, engine: str) -> str | None:
    """Pull the AI engine's own failure line out of parse_and_categorize.py's
    stderr, when a non-local engine returned a blank prefill.

    _parse_receipt() always falls back to the zero-token local parser on any
    AI-engine exception, so an auth failure (a malformed API key, say) and an
    unreadable photo both dead-end at the same generic "OCR could not read
    any fields" result -- the operator saw a wrong key and a scan of an empty
    table produce an identical error and has no way to tell "rotate the key"
    from "rescan the receipt" apart. The engine's own tier function already
    prints one line naming the real cause before it falls back; surfacing
    that line closes the gap without changing the always-fall-back behavior
    itself (a token key going bad must never block receipt intake).
    """
    if engine == 'local' or not stderr:
        return None
    for line in stderr.splitlines():
        lowered = line.lower()
        if 'parsing failed' in lowered or 'not available' in lowered or 'not set' in lowered:
            return line.strip()
    return None


def preview_receipt_parse(image_path: str, engine: str = 'local', runner=None,
                           vendor_lookup_fn=None, category_namer=None):
    """Run a read-only parse pass so the form can prefill instead of
    starting blank. Returns (ok, payload). ok=False just means the form
    stays blank -- this is a convenience, never a requirement.

    `engine='local'` (default) keeps the zero-LLM/vision-call guarantee
    documented at module level. `engine='gemini-only'` is the dashboard's
    opt-in "Gemini Flash Fill" button and `engine='haiku-only'` is the
    "Fill with Haiku" button -- see PREVIEW_ENGINES/build_preview_command for
    why neither can reach a paid tier even on failure.
    """
    try:
        command = build_preview_command(image_path, engine)
    except ValueError as exc:
        return False, {'error': str(exc)}
    result = (runner or _run_parse_and_categorize)(command)
    if result.get('returncode') != 0:
        return False, {'error': result.get('stderr') or 'preview failed'}
    report = result.get('report')
    # isinstance, not truthiness. A reader that returned a bare string, a list,
    # or an error page is not an empty report -- it is a report we cannot read,
    # and every line below assumes a mapping. Letting one through raised
    # AttributeError on this error path, turning "the model didn't answer" into
    # a 500. Found by property_tests/test_boundary_readers_fail_safe.py.
    if not isinstance(report, dict) or not report:
        return False, {'error': 'could not parse OCR output'}
    # Deliberately BEFORE _extract_prefill: an OCR guess must not reach the
    # form's fields wearing the chosen model's name.
    if _answered_by_local_fallback(report, engine):
        engine_failure = _engine_failure_of(report)
        # The model's own sentence when it has one -- it answered, and said
        # something specific and useful. The generic wording below is for the
        # case where nobody looked at the document at all.
        # "did not answer" would be a lie for half of these. Verified live
        # 2026-08-19: haiku-only spent 4,071 input tokens on a window scan and
        # replied with output that was not valid JSON at all -- it answered,
        # just uselessly. A 429 and a garbled reply reach this line by the same
        # route, so the wording has to be true of both.
        error = engine_failure.get('message') or (
            f'{engine} did not return a usable reading of this document '
            '(local OCR is not used to fill this form). Try the other model, '
            'or type the fields in.')
        failed = {
            'error': error,
            'possible_statement': looks_like_multiple_transactions(
                _document_text(report)),
        }
        if engine_failure:
            failed['engine_failure'] = engine_failure
        return False, failed
    prefill = _extract_prefill(report)
    # Computed unconditionally, success or failure: a page that reads as a
    # statement's transaction table is worth flagging even when none of the
    # three receipt-shaped fields below happened to come back readable.
    possible_statement = looks_like_multiple_transactions(_document_text(report))
    # Every field can legitimately come back None now that the local OCR
    # fallback leaves unreadable fields blank instead of guessing (today's
    # date, a $0.00 total) -- that's a real "couldn't read this" result,
    # not a successful prefill with nothing in it.
    if not any(prefill.values()):
        error = 'OCR could not read any fields from this document'
        detail = _engine_failure_detail(result.get('stderr'), engine)
        if detail:
            error = f'{error} ({detail})'
        return False, {'error': error, 'possible_statement': possible_statement, **prefill}
    prefill.update(_resolve_vendor_match(
        prefill.get('merchant_name'), vendor_lookup_fn,
        document_text=_document_text(report),
        category_namer=category_namer))
    prefill['possible_statement'] = possible_statement
    return True, prefill
