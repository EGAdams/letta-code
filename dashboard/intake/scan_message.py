"""The intake instruction Mazda receives after a document is scanned.

This is a prompt, not an algorithm. It was 536 lines inside server.py -- one
function nobody could review, in which a stray word silently changes how the
agent files real money. Split here into named sections so a single rule can be
found, read, and tested on its own.

Nothing here does I/O. Every function returns a string, so the whole dispatch
is unit-testable without a scanner, an executor, or a database.

Two branches run end to end:

* **identified** -- the deterministic facade classified the document, so Mazda
  is told not to classify it again. A statement on this branch short-circuits
  to `statement_only_message`, which deliberately *omits* receipt
  investigation and categorization rather than asking Mazda to skip them.
* **unidentified** -- normal for JPEG scans, whose text extraction finds
  nothing. Mazda gets STEP 0 and classifies with vision herself.

Each section builder takes the values it interpolates under the names the
original function used. That kept the split textual, so the prompt this module
emits is byte-identical to the one server.py emitted before it.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex


# Venv python + PYTHONPATH for rol_finances scripts.
#
# Two regressions, two rules, both mandatory on every command we hand Mazda:
#  1. ModuleNotFoundError: No module named 'tools' — Python does not add the cwd
#     to sys.path for a `script.py` invocation, so rol_finances scripts that do
#     `import tools...` need PYTHONPATH=/home/adamsl/rol_finances. (2026-06-28)
#  2. "Command not in allowlist: PYTHONPATH=..." — the executor only strips an
#     inline `PYTHONPATH=...` prefix when the command also contains a shell
#     operator (&&, |, >). A *bare* command (STEP 0 classify) goes straight to
#     the allowlist check with `PYTHONPATH=...` as cmd[0] and is rejected.
#     (2026-06-29 intake run, trace 53.)
# Fix for BOTH: never inline the prefix. Use the full venv python path as the
# executable (it is in the executor allowlist) and pass PYTHONPATH through
# executor_run's own `env` argument, which is applied to the child regardless of
# whether the command takes the shell path. Verified live against pid 1041:8787.
MAZDA_RF_VENV_PY = '/home/adamsl/rol_finances/.venv/bin/python3'
MAZDA_RF_ENV_JSON = '{"PYTHONPATH": "/home/adamsl/rol_finances"}'


def facade_identified(facade_result):
    """Pure predicate: did the deterministic facade actually identify the doc?

    A facade run that merely exits 0 is NOT enough — for JPEG scans the
    text-extraction router returns ``ok: true`` but ``doc_kind: unknown``,
    ``confidence: 0``, ``recommended_action: reject``. Treating that as success
    is the bug that sent Mazda into investigate/categorize with empty data.
    Only return True when the facade produced a usable classification.
    """
    fr = facade_result or {}
    try:
        confidence = float(fr.get('confidence') or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return bool(
        fr.get('ok')
        and (fr.get('doc_kind') or 'unknown') != 'unknown'
        and fr.get('recommended_action') != 'reject'
        and confidence > 0
    )


#: Invariant across every branch: which slot each kind of evidence lands in.
SUPPORTING_DOCUMENT_CONTRACT = (
        'SUPPORTING-DOCUMENT STORAGE CONTRACT — one expense can retain four '
        'independent references. Receipt → receipt_url; statement/source document '
        'downloaded from the bank → document_url; statement scanned from paper '
        '→ scanned_statement_url; Mom’s ledger → moms_ledger. A scanned statement '
        'is derived evidence and MUST NEVER be stored in document_url. Never write a statement path '
        'into receipt_url or a receipt path into document_url. Attach the newly '
        'processed document to the existing matched expense whenever possible and '
        'preserve the other three document fields. An identical existing reference '
        'is an idempotent success (`already_attached`). A different non-empty value '
        'in the same field is a same-type conflict: preserve the original, require '
        'human verification (`NEEDS_DOCUMENT_VERIFICATION`), and never create a '
        'duplicate expense merely to retain the new scan. Documents may arrive in '
        'any order; statement-first/receipt-later and receipt-first/statement-later '
        'must converge on one expense row. Include the association field/status and '
        'preserved-field evidence in trace problems/results and the dashboard callback. '
        'Every available evidence type must be independently viewable from the Set '
        'Category dialog: receipt_url → View Receipt, document_url → View Source '
        'Document, scanned_statement_url → View Scanned Statement, and moms_ledger '
        '→ View Mom’s Ledger. For every new or matched scanned-statement expense, '
        'scanned_statement_url must contain the archived scan reference; the '
        'dashboard report-directory fallback is only for repairing legacy rows and is '
        'not acceptable evidence for a new intake.\n\n'
)


def override_args_for(statement_preflight):
    """Bank/account flags for the statement tools, when preflight resolved both.

    Both are required: half an identity would let the storage tools file a
    statement under the wrong account. shlex-quoted because a bank name
    legitimately contains spaces and apostrophes.
    """
    statement_override_args = ''
    if statement_preflight.get('bank_name') and statement_preflight.get('account_last4'):
        statement_override_args = (
            f' --bank-name {shlex.quote(str(statement_preflight["bank_name"]))}'
            f' --account-last4 {shlex.quote(str(statement_preflight["account_last4"]))}'
        )
        if statement_preflight.get('last4_source') == 'known_cards_workbook':
            statement_override_args += (
                ' --account-last4-source known_cards_workbook')
    return statement_override_args


def artifact_paths(scan_image_path, statement_preflight):
    """The parse-artifact paths this dispatch names, keyed to the scan itself.

    The token is a digest of the image path, so two scans in flight at once
    cannot overwrite each other's artifacts. A statement whose payload the
    dashboard already validated reuses that file rather than re-parsing.
    """
    statement_payload_path = statement_preflight.get('payload_path') or ''
    statement_token = hashlib.sha256(
        scan_image_path.encode('utf-8')).hexdigest()[:12]
    receipt_json_path = f'/tmp/mazda_receipt_{statement_token}.json'
    statement_json_path = (
        statement_payload_path
        or f'/tmp/mazda_statement_{statement_token}.json')
    return receipt_json_path, statement_json_path


def store_contract_for(identified):
    """How far STEP 4's result may be trusted -- it depends where the parse ran."""
    if identified:
        receipt_store_contract = (
            'This facade-identified path performs its one receipt parse during '
            'STEP 4, so parse_artifact_verified may be false. Verify its final '
            'date, amount, merchant, scope, and selected rows against the facade '
            'evidence before accepting the result. ')
    else:
        receipt_store_contract = (
            'The save path must report parse_artifact_verified=true and performs '
            'a final duplicate guard using the SAME validated date, amount, '
            'merchant, expense scope, and selected rows from STEP 0. ')
    return receipt_store_contract


def finish_block_for(scan_image_path):
    """Annotations, report build, and audit -- shared by both statement paths."""
    report_path = os.path.join(
        os.path.dirname(scan_image_path), 'report.html')
    report_dir = os.path.dirname(report_path)
    statement_finish_block = (
        f'  After store, run this exact command once, replacing <IDS> with one '
        f'comma-separated value containing every stored AND duplicate expense id '
        f'(do not use singular --expense-id, shell substitution, or per-ID calls):\n'
        f'  {MAZDA_RF_VENV_PY} '
        f'tools/receipt_scanning_tools/apply_statement_annotations.py '
        f'--image {scan_image_path} --expense-ids <IDS>\n'
        f'  `annotations_applied` is required evidence.\n'
        f'  BUILD THE DASHBOARD REPORT at {report_path}. Follow '
        f'REPORT_OUTPUT_CONTRACT.md, then run these exact commands separately:\n'
        f'  {MAZDA_RF_VENV_PY} '
        f'tools/python_tasks/verification_lib/restructure_verified_transactions.py '
        f'{report_path}\n'
        f'  {MAZDA_RF_VENV_PY} '
        f'tools/python_tasks/verification_lib/hydrate_report_categories_from_db.py '
        f'{report_path}\n'
        f'  {MAZDA_RF_VENV_PY} '
        f'tools/python_tasks/verification_lib/audit_statement_reports.py '
        f'{report_dir}\n'
        f'The finished HTML must contain id="verified-transactions", '
        f'data-vendor-key attributes, and the rol-category-picker:start marker. '
        f'CATEGORY AUTHORITY RULE: expenses.category_id is authoritative. '
        f'Record report_generated=true and report_audit_status.\n'
    )

    return statement_finish_block


def _parsed_summary(parsed):
    """The few parsed fields worth showing, so the message stays readable."""
    parsed_summary = json.dumps(
        {k: parsed[k] for k in ('transaction_date', 'total_amount', 'merchant_name',
                                 'description', 'payment_method') if k in parsed},
        default=str,
    )
    return parsed_summary


def facade_block_for_identified(fr, doc_kind, vendor, confidence, parsed):
    """The "do not classify this again" preamble, carrying the facade's findings."""
    parsed_summary = _parsed_summary(parsed)
    facade_block = (
        f'\n\nThe deterministic facade (classify + parse) ran and IDENTIFIED this document. '
        f'Do NOT re-run classify or parse — use these results directly:\n'
        f'  doc_kind: {doc_kind}\n'
        f'  vendor_key: {vendor}\n'
        f'  routing_key: {fr.get("routing_key")}\n'
        f'  confidence: {confidence} '
        f'(recommended_action: {fr.get("recommended_action")})\n'
        f'  parsed: {parsed_summary}'
    )
    return facade_block


def blocks_for_unidentified(fr, doc_kind, confidence, scan_image_path,
                            receipt_json_path):
    """The STEP 0 classify-and-parse-yourself instructions, plus their preamble.

    Returned together because the note explaining why the facade came back
    empty and the instructions that compensate for it are one thought.
    """
    # Facade did not identify the doc (doc_kind=unknown, confidence=0, or crashed).
    # This is NORMAL for JPEG receipt scans — the facade uses text extraction which
    # fails for images. Tell Mazda to use the vision-capable tools directly.
    err = fr.get('error', '') if fr else ''
    note = (f'error: {err}' if err
            else f'returned doc_kind={doc_kind!r}, confidence={confidence}')
    facade_block = (
        f'\n\nThe facade could not identify this document ({note}). '
        f'This is expected for JPEG scans — the facade uses text extraction, not vision.'
    )
    fallback_block = (
        f'\nSTEP 0 — CLASSIFY + PARSE YOURSELF (facade returned doc_kind=unknown). '
        f'executor_run, cwd=/home/adamsl/rol_finances, env={MAZDA_RF_ENV_JSON}:\n'
        f'  HARD ROUTING BARRIER: run classification as its OWN executor_run call. '
        f'Never chain the classifier to a parser or store command with `&&`, `;`, or '
        f'any other shell operator. Read `doc_type` before choosing the next command.\n'
        f'  a. Classify ONLY (Gemini vision):\n'
        f'     {MAZDA_RF_VENV_PY} tools/classify_scan.py '
        f'{scan_image_path}\n'
        f'     → {{"doc_type": "receipt"|"invoice"|"statement"|"moms_ledger"|'
        f'"tax_document"|"other", '
        f'"confidence": 0-1, "reason": "..."}}\n'
        f'  If doc_type is `bank_statement` or `statement`, STOP STEP 0 HERE and '
        f'jump directly to STATEMENT BRANCH S1. Running receipt parser/store commands '
        f'on a statement is forbidden.\n'
        f'  b. ONLY for receipt OR invoice, parse in a NEW executor_run call:\n'
        f'     {MAZDA_RF_VENV_PY} '
        f'tools/receipt_scanning_tools/receipt_parsing_tools/parse_and_categorize.py '
        f'-f {scan_image_path} --json --engine=gemini '
        f'--write-parsed-json {receipt_json_path}\n'
        f'     → JSON with merchant_name, transaction_date, total_amount, etc.\n'
        f'     This writes the source-bound validated parse artifact '
        f'{receipt_json_path}. Use that exact artifact for duplicate checking, '
        f'categorization, itemization, callback values, and STEP 4 storage. '
        f'Do not run receipt vision a second time.\n'
        f'  Derive vendor_key from merchant_name: lowercase, underscores '
        f'(e.g. "Goodwill Cascade" → "goodwill_cascade").\n\n'
    )
    return facade_block, fallback_block


def steps_for_identified_statement(scan_image_path, statement_payload_path,
                                  statement_json_path,
                                  statement_override_args):
    """Parse (unless the dashboard already did) and store, for a known statement."""
    if statement_payload_path:
        statement_steps = (
            f'2. Do not run statement vision again. The dashboard already '
            f'validated every extracted row and wrote the exact parser JSON to '
            f'{statement_payload_path}.\n'
            f'3. Via executor_run with cwd=/home/adamsl/rol_finances and '
            f'env={MAZDA_RF_ENV_JSON}, run:\n'
            f'   {MAZDA_RF_VENV_PY} '
            f'tools/receipt_scanning_tools/store_statement_transactions.py '
            f'-f {statement_payload_path} --source-file {scan_image_path}'
            f'{statement_override_args}\n'
        )
    else:
        statement_steps = (
            f'2. Via executor_run with cwd=/home/adamsl/rol_finances and '
            f'env={MAZDA_RF_ENV_JSON}, run:\n'
            f'   {MAZDA_RF_VENV_PY} '
            f'tools/receipt_scanning_tools/parse_statement_scan.py '
            f'{scan_image_path} -o {statement_json_path}'
            f'{statement_override_args}\n'
            f'3. Use {statement_json_path}, then via '
            f'executor_run with the same cwd/env run:\n'
            f'   {MAZDA_RF_VENV_PY} '
            f'tools/receipt_scanning_tools/store_statement_transactions.py '
            f'-f {statement_json_path} --source-file {scan_image_path}'
            f'{statement_override_args}\n'
        )
    return statement_steps


def statement_only_message(scan_image_path, scanner_name, vendor, confidence,
                           statement_steps, statement_finish_block,
                           conversation_id, dispatched_at):
    """The entire dispatch for a facade-identified statement.

    Receipt investigation, categorization and single-document storage are not
    merely skipped here -- they are absent. A statement can never complete
    them, and an instruction to skip them is one Mazda has been seen to ignore.
    """
    supporting_document_contract = SUPPORTING_DOCUMENT_CONTRACT
    return (
        f'A bank or credit-card statement was scanned on the {scanner_name}. '
        f'The image is: {scan_image_path}\n'
        f'The deterministic vision facade already classified it as statement '
        f'(confidence={confidence}, vendor={vendor}). Do not classify it again.\n\n'
        f'This is a STATEMENT-ONLY intake. Receipt/invoice investigation, '
        f'categorization, and all single-document parsing/storage are forbidden '
        f'and intentionally omitted from this dispatch.\n\n'
        + supporting_document_contract +
        f'1. Call load_wrapper_revision(agent_name="Mazda").\n'
        + statement_steps +
        statement_finish_block +
        f'4. Call record_trace(agent_name="Mazda", task_name="document-intake", '
        f'input_text="{scan_image_path}", agent_output=<JSON containing '
        f'document_path, doc_kind="statement", classification_confidence, '
        f'duplicate_checked=true, transactions_parsed, transactions_stored, '
        f'transactions_duplicate, transactions_skipped_credits, deposits_stored, '
        f'bank_name, account_last4, archive_paths, archive_years, and problems>).\n'
        f'5. Call judge_trace(trace_id) always. On FAIL call propose_improvement '
        f'and apply_proposal.\n'
        f'6. Always notify the dashboard via executor_run with curl POST '
        f'http://localhost:8765/api/expense-stored. The JSON must contain all '
        f'expense_ids and duplicate_expense_ids from step 3, parsed/stored counts, '
        f'doc_kind="statement", vendor="{vendor}", '
        f'document_path="{scan_image_path}", '
        f'conversation_id="{conversation_id or ""}", and '
        f'dispatched_at={float(dispatched_at or 0)}.\n'
        f'Do not stop before steps 4-6 even when every transaction is a duplicate.'
    )


def categorizer_input_for(identified, parsed, vendor):
    """STEP 3's input: prefilled when the facade knew the merchant, else built.

    When the facade did not identify the document, Mazda already holds real
    parsed data from STEP 0. Handing her the literal placeholder
    {"description": "unknown"} guarantees a categorizer miss and pushes the
    vendor onto the slower LLM-research path.
    """
    if identified:
        # Facade gave us the real merchant + vendor_key — prefill the categorizer input.
        categorizer_input = json.dumps(
            {'id_light': '', 'description': parsed.get('merchant_name') or vendor,
             'vendor_key': vendor if vendor != 'unknown' else None},
            default=str,
        )
        categorizer_input_line = (
            f"  printf '%s' '{categorizer_input}' > /tmp/mazda_cat_input.json && "
        )
    else:
        # Facade did NOT identify — by STEP 3 Mazda has REAL parsed data from STEP 0.
        # Do NOT hand her the literal placeholder {"description":"unknown"}; that
        # guarantees a categorizer miss (and pushes it onto the LLM-research path).
        categorizer_input_line = (
            '  Build the input JSON from your STEP 0 results — NOT the literal word '
            '"unknown": write {"id_light": "", "description": "<merchant_name from '
            'STEP 0 parse>", "vendor_key": "<vendor_key you derived in STEP 0>"} to '
            '/tmp/mazda_cat_input.json (e.g. via executor_write or printf), then run:\n'
        )
    return categorizer_input_line


def pipeline_message(scan_image_path, scanner_name, facade_block,
                    fallback_block, statement_json_path,
                    statement_override_args, statement_finish_block,
                    categorizer_input_line, receipt_parse_artifact_arg,
                    receipt_store_contract, conversation_id, dispatched_at):
    """The full investigate -> categorize -> store -> judge -> notify dispatch."""
    supporting_document_contract = SUPPORTING_DOCUMENT_CONTRACT
    return (
        f'A document was just scanned on the {scanner_name}. '
        f'The scanned image is at: {scan_image_path}{facade_block}\n\n'
        f'Complete the AGENTIC back half of the intake pipeline '
        f'(investigate → categorize → store → judge):\n\n'
        f'EXECUTOR RULE (read first): run every command below via executor_run — '
        f'NEVER via run_claude_code_sdk. run_claude_code_sdk executes on a different '
        f'machine where the rol_finances venv does not work; substituting it for '
        f'executor_run is a guaranteed failure. Every executor_run call MUST pass '
        f'env={MAZDA_RF_ENV_JSON}. Do NOT prefix any command with "PYTHONPATH=..." — '
        f'the executor allowlist rejects an inline env-assignment as an unknown command '
        f'("Command not in allowlist: PYTHONPATH=..."). Always use the full venv python '
        f'path shown ({MAZDA_RF_VENV_PY}) and carry PYTHONPATH via the env argument.\n\n'
        f'{supporting_document_contract}'
        f'STEP 1 — load_wrapper_revision(agent_name="Mazda"). The result includes '
        f'`instructions` — your accumulated LEARNED RULES from previous judged runs. '
        f'READ THEM AND APPLY EVERY RULE that matches this document; they override '
        f'the default steps below. Keep the returned wrapper_revision for '
        f'record_trace.\n\n'
        f'ROUTING PRECEDENCE — the explicit `doc_type` returned by classify_scan.py '
        f'is authoritative and its matching branch below overrides generic prose '
        f'rules about emails, bills, or non-receipts. In particular, an email '
        f'screenshot whose enclosed document is `invoice` MUST run the INVOICE '
        f'BRANCH; never route it away merely because it is an email or bill. A '
        f'`receipt` MUST run STEPS 2-4. Only explicit `doc_type=other` is unsupported.\n\n'
        f'{fallback_block}'
        f'DOCUMENT-STRUCTURE RULE — handwriting never changes an intact document\'s '
        f'type. A complete bank or credit-card statement with consistent issuer '
        f'letterhead, account metadata, a billing cycle, and regularly aligned rows '
        f'remains a statement regardless of the amount of handwriting, circles, '
        f'cross-outs, arithmetic, or category notes. `moms_ledger` is reserved for '
        f'Mom\'s cut-and-assembled composite made from pieces of different source '
        f'documents. A neat statement must use the STATEMENT BRANCH so it is archived; '
        f'its handwriting is handled later by apply_statement_annotations.py.\n\n'
        f'MOM LEDGER BRANCH — only if STEP 0 returns doc_type="moms_ledger" for a '
        f'visibly cut-and-assembled composite, run '
        f'moms_ledger_reconciler.py --image {scan_image_path}. Use supported '
        f'category evidence and never flatten a correct specific category back '
        f'to generic 190. Use OpenAI Codex CLI when vision reconciliation is '
        f'needed; do not run receipt or statement storage. Record '
        f'doc_kind="moms_ledger".\n\n'
        f'STATEMENT BRANCH — if this document is a bank or credit-card statement '
        f'(doc_kind "bank_statement" or "statement" from the facade or STEP 0): SKIP '
        f'STEPS 2-4 entirely — they are for single receipts and a statement can never '
        f'complete them. Run these two commands instead (executor_run, '
        f'cwd=/home/adamsl/rol_finances, env={MAZDA_RF_ENV_JSON}):\n'
        f'  S1. Extract every transaction (Gemini vision):\n'
        f'      {MAZDA_RF_VENV_PY} tools/receipt_scanning_tools/parse_statement_scan.py '
        f'{scan_image_path} -o {statement_json_path}{statement_override_args}\n'
        f'  S2. Dedupe + store them. Expenses are inserted UNCATEGORIZED (they enter '
        f'the New Records queue for a human to categorize — do NOT run the categorizer '
        f'for statements). Deposits/credits are NOT expenses: the script persists them '
        f'to the bank-side `transactions` ledger (type CREDIT, never categorized, '
        f'never reviewed by a human):\n'
        f'      {MAZDA_RF_VENV_PY} '
        f'tools/receipt_scanning_tools/store_statement_transactions.py '
        f'-f {statement_json_path} --source-file {scan_image_path}'
        f'{statement_override_args}\n'
        f'      → {{"transactions_parsed": N, "skipped_credits": N, "duplicates": N, '
        f'"stored": N, "expense_ids": [...], "deposits_stored": N, "deposit_ids": [...], '
        f'"deposit_duplicates": N, "bank_name": "...", "account_last4": "1234", '
        f'"archive_paths": [...], "archive_years": [...]}}\n'
        f'  EVERY row coming back "duplicates" or "deposit_duplicates" is a SUCCESSFUL '
        f'no-op, not a failure, and a deposit missing from expenses is CORRECT. '
        + statement_finish_block +
        f'Then continue at STEP 5 with the STATEMENT evidence JSON described there.\n\n'
        f'INVOICE BRANCH — if this document is a bill/invoice requesting payment where the '
        f'document itself does NOT show payment already made (doc_type "invoice" from '
        f'classify_scan.py — e.g. a contractor/consultant invoice with a balance due, not '
        f'stamped paid). An invoice is NOT proof a payment happened; it is a PLACEHOLDER for a '
        f'payment we expect to see evidenced later by a bank statement transaction or a paid '
        f'receipt for the SAME (date, amount). Run STEPS 2-3 normally (investigate + categorize '
        f'this vendor exactly like a receipt), then at STEP 4 add the `--invoice` flag to the '
        f'store command instead of a normal save:\n'
        f'  {MAZDA_RF_VENV_PY} '
        f'tools/receipt_scanning_tools/receipt_parsing_tools/parse_and_categorize.py '
        f'-f {scan_image_path} --save --invoice --category-id=<id from step 3>'
        f'{receipt_parse_artifact_arg} --engine=gemini\n'
        f'  → {{"success": true, "expense_id": <int>, "expense_status": '
        f'"WAITING_FOR_PAYMENT_COUNTERPART", "linked_counterpart": false, ...}}\n'
        f'This stores ONE expense row with expense_status=WAITING_FOR_PAYMENT_COUNTERPART — do '
        f'NOT create it any other way and do NOT wait for a human to confirm payment first. The '
        f'system links the eventual counterpart automatically: the NEXT time ANY document '
        f'(statement scan or receipt scan) is stored with the SAME (expense_date, amount), the '
        f'storage tools detect the waiting placeholder and UPDATE that same row (the '
        f'correct supporting-document field, '
        f'source_file, notes, expense_status → COUNTERPART_DOCUMENT_LINKED) instead of inserting '
        f'a second expense — so if `linked_counterpart: true` comes back on ANY future receipt '
        f'or statement store, that is CORRECT behavior closing out an earlier invoice, not a '
        f'duplicate to investigate. Continue to STEP 5 using doc_kind "invoice" in the evidence '
        f'JSON.\n\n'
        f'STEP 2 — INVESTIGATE (only with REAL parsed data — never pass "unknown"):\n'
        f'  a. check_vendor_key(id_light="scan", description=<merchant>, '
        f'vendor_key=<vendor_key from facade or derived above>)\n'
        f'     IMPORTANT: if the result contains a normalized/recognized vendor_key that '
        f'differs from what you supplied, USE THE NORMALIZED KEY in every later step '
        f'(categorizer input, evidence JSON) — the vendor store and its category mapping '
        f'are keyed on the normalized form.\n'
        f'  MISSING DATE RULE: if STEP 0/facade could not extract a transaction_date '
        f'(null, unreadable, or no date printed on the receipt), do NOT stop or treat '
        f'it as a blocker — use the placeholder "1970-01-01" as expense_date in '
        f'check_duplicates below and in the STEP 5 evidence JSON. '
        f'parse_and_categorize.py --save already substitutes this same placeholder '
        f'automatically when transaction_date is missing, so STEP 4 needs no special '
        f'handling. This preserves the receipt with an honest sentinel date instead of '
        f'silently guessing a date or losing the document.\n'
        f'  b. check_duplicates(id_light="scan", expense_date=<YYYY-MM-DD, or '
        f'"1970-01-01" if no date was extracted>, '
        f'amount=<decimal string from the validated parse artifact>, '
        f'description=<merchant>)\n'
        f'  A PROBABLE duplicate counts too. When check_duplicates returns '
        f'fuzzy_duplicate_id_light (same date and amount, but the vendor keys do not '
        f'match), you MUST investigate it before storing instead of treating '
        f'"not exact" as "not a duplicate". The common case is an existing row named '
        f'only by a payment instrument — "Check 11040" — which names no payee at all, '
        f'so there is no vendor evidence against the match and date+amount is the only '
        f'identity either row has. Read the existing expense and decide: if it is the '
        f'same real-world payment, treat it exactly like an exact duplicate (skip '
        f'STEP 4 storage) and report fuzzy_duplicate_expense_id in STEP 8 '
        f'duplicate_expense_ids. If it is genuinely a different payment, store and say '
        f'in the STEP 5 evidence problems why you ruled it out. On 2026-07-29 a $24.20 '
        f'contribution was stored a second time because a "Check 11040" row with the '
        f'same date and amount was dismissed as unrelated.\n'
        f'  If duplicate → STILL run STEP 4 exactly once, without '
        f'--allow-duplicate. STEP 4 is also the receipt-filing/attachment step: it '
        f'must rename the scan, archive it under readable_documents/receipts/'
        f'{{year}}/{{month}}/{{month}}_{{day}}, and attach or upgrade receipt_url on '
        f'the matched expense without inserting a second expense. A duplicate result '
        f'or linked_counterpart=true is success; a same-type durable conflict requires '
        f'verification. Still run STEP 3 categorization, record_trace, judge_trace, '
        f'and the STEP 8 callback; duplicate detection is never permission to stop '
        f'the run early. Keep the returned '
        f'exact_duplicate_expense_id — STEP 8 must report it in duplicate_expense_ids, '
        f'or the dashboard has no row to show and the Recent Report page comes up '
        f'empty for this scan.\n\n'
        f'STEP 3 — CATEGORIZE (executor_run, cwd=/home/adamsl/rol_finances, '
        f'env={MAZDA_RF_ENV_JSON}):\n'
        f'{categorizer_input_line}'
        f'  {MAZDA_RF_VENV_PY} tools/categorizer/categorizer_main.py '
        f'-i /tmp/mazda_cat_input.json --provider=auto\n'
        f'  → {{"vendor_key": "...", "category_id": <int>}}\n'
        f'  The auto provider chain tries Gemini, then ChatGPT OAuth '
        f'(EG\'s Codex OAuth first, then mom\'s approved fallback token), then Anthropic. '
        f'Only fall through to the FAIL-CLOSED CATEGORY RULE below if all three providers '
        f'fail or the vendor is genuinely unresolvable.\n'
        f'  FAIL-CLOSED CATEGORY RULE: merchant/vendor placeholders such as null, "null", '
        f'"unknown", or "receipt" are not real vendors. If merchant/vendor is unresolved '
        f'or category_id is null/zero, STILL run STEP 4 but OMIT --category-id entirely — '
        f'the store tool saves the receipt image and a NULL-category placeholder row '
        f'(expense_status=NEEDS_VENDOR_KEY) instead of failing closed, so a human can pick '
        f'the right vendor_key later via the dashboard instead of the scan being lost. '
        f'Record and judge a truthful trace reflecting the unresolved category (set '
        f'pending_vendor_review:true in the STEP 5 evidence — this is what tells the judge '
        f'a null category is a correct degraded save, not a failure), propose an '
        f'improvement, and send STEP 8 with stored:1 (the row WAS stored) and '
        f'status:"awaiting_vendor_review". If you later find the real category for this '
        f'expense (e.g. via categorizer_main.py or a vendor_category.yaml lookup), correct '
        f'the stored row with '
        f'{MAZDA_RF_VENV_PY} tools/receipt_scanning_tools/receipt_parsing_tools/'
        f'update_expense_category.py --expense-id=<id> --category-id=<id> — NEVER hand-write '
        f'SQL against the finance DB; /api/recategorize-expense is a different tool for a '
        f'different (coarser, 13-value) reporting taxonomy and will reject a vendor_category.yaml '
        f'category name.\n\n'
        f'STEP 4 — STORE (executor_run, cwd=/home/adamsl/rol_finances, '
        f'env={MAZDA_RF_ENV_JSON}). '
        f'Include --category-id=<id from step 3> when STEP 3 resolved a positive one; OMIT '
        f'the flag entirely when it did not (see FAIL-CLOSED CATEGORY RULE above — the tool '
        f'still saves the receipt + a pending-review placeholder row rather than erroring):\n'
        f'  {MAZDA_RF_VENV_PY} '
        f'tools/receipt_scanning_tools/receipt_parsing_tools/parse_and_categorize.py '
        f'-f {scan_image_path} --save --category-id=<id from step 3>'
        f'{receipt_parse_artifact_arg} --engine=gemini\n'
        f'  → {{"success": true, "expense_id": <int>, "pending_vendor_review": <true when '
        f'--category-id was omitted/invalid>, "parse_artifact_verified": '
        f'<true for the STEP 0 artifact path>, '
        f'"receipt_archive_path": "<canonical filed image>", '
        f'"archive_paths": ["<canonical filed image>"], '
        f'"parsed_amount": <the exact STEP 0 amount>, "expense_scope": '
        f'"full_receipt"|"marked_items", ...}} OR a duplicate result. '
        + receipt_store_contract +
        f'A duplicate at a different amount or scope is '
        f'not proof that this scan is a duplicate. Never retry with --allow-duplicate.\n\n'
        f'STEP 4B — ITEMIZE WHEN EVIDENCE ALLOWS (MCP tool; never hand-build SQL):\n'
        f'  For a newly stored receipt whose parsed JSON has multiple line items, call '
        f'itemize_existing_expense(doc_family="receipt", expense_id=<STEP 4 id>, '
        f'id_light=<stored id_light>, expense_date=<final stored date>, amount=<final '
        f'stored total>, description=<final merchant>, receipt_payload_json=<the exact '
        f'STEP 0 JSON>, category_ids=[<one verified positive category per item>], '
        f'receipt_url=<store result>, source_file="{scan_image_path}").\n'
        f'  The factory checks that source lines sum CENT-EXACTLY to the charge and writes '
        f'PARENT + LINE_ITEM rows in one transaction. itemizable:false is a CORRECT '
        f'fail-closed result: leave the expense STANDALONE and record the reason. Never '
        f'guess missing lines, allocate an Amazon split shipment, retry a partial write, '
        f'or issue parent/child SQL yourself. For Amazon statement charges use '
        f'doc_family="amazon_statement" only when an order ID is present; the same exact '
        f'reconciliation rule applies.\n\n'
        f'STEP 5 — record_trace(agent_name="Mazda", task_name="document-intake", '
        f'input_text=<scan path>, agent_output=<the intake-evidence JSON below>). '
        f'The task_name MUST be exactly "document-intake" so it is judged by the intake '
        f'rubric (not the statement rubric). agent_output MUST be this JSON object recording '
        f'what actually happened — the judge reads these fields:\n'
        f'  {{"document_path": "{scan_image_path}", "doc_kind": "receipt"|"invoice"|"statement"|"unknown", '
        f'"classification_confidence": <0-1>, "vendor_key": "<resolved or null>", '
        f'"vendor_key_recognized": <true|false>, '
        f'"merchant": "<the payee EXACTLY as printed on the document, from STEP 0 '
        f'classification - NOT the normalized vendor_key>", '
        f'"category_id": <int or null>, '
        f'"duplicate_checked": <true|false>, "is_duplicate": <true|false>, '
        f'"stored": <true|false>, "expense_id": <int or null>, '
        f'"linked_counterpart": <true when the save returned linked_counterpart:true — '
        f'the receipt was attached to an existing statement expense instead of inserting a '
        f'second row; expense_id is then that existing row and stored may be false>, '
        f'"intake_halted": <true ONLY when a --save/store command returned '
        f'"halted": true — see the HALT RULE below; then stored:false and expense_id:null>, '
        f'"itemization_attempted": <true|false>, "itemized": <true|false>, '
        f'"itemization_reconciled": <true only when itemization succeeded>, '
        f'"itemization_parent_id": <int or null>, '
        f'"itemization_child_ids": [<all child ids>], '
        f'"expense_status": "<NONE|WAITING_FOR_PAYMENT_COUNTERPART|COUNTERPART_DOCUMENT_LINKED, '
        f'from the store response, when doc_kind is invoice or when linked_counterpart was true>", '
        f'"pending_vendor_review": <true when STEP 4 returned pending_vendor_review:true '
        f'(a null/omitted --category-id), else false — REQUIRED whenever category_id is null; '
        f'the judge treats a null category with pending_vendor_review unset as a real failure, '
        f'not the correct degraded save the FAIL-CLOSED CATEGORY RULE describes>, '
        f'"problems": [<strings>]}}\n'
        f'  HALT RULE: if ANY `--save`/store command returns `"halted": true` (a JSON object '
        f'with a `halt` block naming a `step`/`cause`/`exception_type`), an intake step '
        f'crashed inside the tool — the pipeline fail-loud stopped instead of inserting a '
        f'possibly-duplicate row. This is NOT your fault and there is nothing to retry or work '
        f'around: do NOT re-run --save, do NOT add --allow-duplicate, do NOT hand-build a row. '
        f'Record the trace with "intake_halted": true, "stored": false, "expense_id": null, and '
        f'the halt\'s cause copied into "problems", then STILL run judge_trace and the STEP 8 '
        f'dashboard callback (send stored:0). The judge scores a halt NEEDS_REVIEW, not FAIL, so '
        f'do NOT call propose_improvement/apply_proposal for it — it is escalated to Suzuki as a '
        f'code bug, not learned around.\n'
        f'  For a STATEMENT, record this evidence JSON INSTEAD (the judge routes it '
        f'to the statement rubric — the receipt fields above do not apply):\n'
        f'  {{"document_path": "{scan_image_path}", "doc_kind": "statement", '
        f'"classification_confidence": <0-1>, "duplicate_checked": true, '
        f'"transactions_parsed": <N from S2>, "transactions_stored": <N>, '
        f'"transactions_duplicate": <N>, "transactions_skipped_credits": <N>, '
        f'"deposits_stored": <N from S2, deposits persisted to transactions>, '
        f'"bank_name": "<confirmed bank>", "account_last4": "<four digits>", '
        f'"archive_paths": [<all permanent copies>], "archive_years": [<years>], '
        f'"problems": [<strings>]}}\n'
        f'  Keep the returned trace_id.\n\n'
        f'STEP 6 — judge_trace(trace_id) — ALWAYS, on success or failure. The intake rubric '
        f'now scores intake correctly: a clean store is PASS, a correctly-detected duplicate '
        f'is PASS, and a broken stage is FAIL. The verdict is what the autonomous reflection '
        f'loop reads, so judging every run is what lets the system heal failures without a '
        f'human.\n\n'
        f'STEP 7 — CLOSE THE LOOP when the verdict is FAIL:\n'
        f'  a. propose_improvement(trace_id, failure_type=<the verdict\'s '
        f'failure_type>, summary=<what went wrong>, expected_benefit=<what improves>) '
        f'→ note the returned proposal_id.\n'
        f'  b. apply_proposal(proposal_id=<that id>, instruction_note=<ONE concrete '
        f'imperative rule that would have prevented this exact failure>). This runs '
        f'the safety gates, appends your rule to the learned instructions as a new '
        f'wrapper revision, and ACTIVATES it — your next run receives it in STEP 1 '
        f'automatically. If it returns pending_approval or a block, stop there; do '
        f'not retry and do not activate anything manually.\n\n'
        f'STEP 8 — NOTIFY DASHBOARD (fire-and-forget; ALWAYS run this after record_trace, '
        f'even when nothing new was stored — e.g. every transaction was a duplicate. The '
        f'dashboard\'s Recent Report view shows this run\'s outcome either way). '
        f'executor_run, no special cwd/env needed:\n'
        f'  curl -s --retry 3 --retry-delay 2 --retry-connrefused '
        f'-X POST http://localhost:8765/api/expense-stored '
        f'-H "Content-Type: application/json" '
        f'-d \'{{"expense_id":<first stored id, or null>,'
        f'"expense_ids":[<ALL expense ids stored this run; [] when none>],'
        f'"duplicate_expense_ids":[<EVERY already-existing expense id this run '
        f'matched but did not re-store. Statement branch: the duplicate_expense_ids '
        f'list from store_statement_transactions.py. Receipt/invoice branch: the '
        f'exact_duplicate_expense_id (and any fuzzy match id) returned by STEP 2b '
        f'check_duplicates — this field is NOT statement-only. [] only when nothing '
        f'was a duplicate>],'
        f'"scanned_statement_attached":[<EVERY existing expense id whose '
        f'scanned_statement_url was attached this run>],'
        f'"scanned_statement_path":"<permanent scanned_statements archive path, '
        f'or empty for non-statement scans>",'
        f'"outcome":"<EVIDENCE_ATTACHED when a scan only fortified existing rows, '
        f'otherwise omit>",'
        f'"rolled_back_row_count":<rows discarded by rollback; normally 0>,'
        f'"parsed":<transactions parsed>,"stored":<transactions stored>,'
        f'"deposits_stored":<deposits stored to the transactions ledger this run; '
        f'0 when none>,'
        f'"archive_paths":[<all permanent receipt or statement copies returned by '
        f'the store command>],"archive_years":[<their years>],'
        f'"expense_date":"<YYYY-MM-DD>",'
        f'"amount":"<decimal string>","vendor_key":"<vendor_key>",'
        f'"description":"<merchant_name>","receipt_url":"<scan_image_path>",'
        f'"document_path":"{scan_image_path}",'
        f'"conversation_id":"{conversation_id or ""}",'
        f'"dispatched_at":{float(dispatched_at or 0)},'
        f'"doc_kind":"<statement|receipt|invoice|unknown, from the facade or your own '
        f'classify_scan.py/STEP 0 classification — the same value you recorded '
        f'as doc_kind in STEP 5>","vendor":"<the vendor/merchant name you '
        f'identified, e.g. \\"chase\\", or \\"unknown\\">",'
        f'"status":"<omit this key normally; include "awaiting_vendor_review" ONLY when '
        f'STEP 4 returned pending_vendor_review:true, so the Recent Report view shows '
        f'this document is waiting on a human vendor pick rather than a generic failure>"'
        f'}}\'\n'
        f'Ignore errors — the dashboard degrades gracefully if unreachable.\n'
    )



def build_scan_message(scan_image_path, scanner_name, facade_result=None,
                      conversation_id=None, dispatched_at=None):
    """Assemble the dispatch for one scanned document.

    The single entry point, so no caller has to know which branch a document
    takes; server.py re-exports it as `build_mazda_scan_message`.
    """
    fr = facade_result or {}
    doc_kind = fr.get('doc_kind', 'unknown')
    vendor = fr.get('vendor') or 'unknown'
    parsed = fr.get('parsed') or {}
    confidence = fr.get('confidence') or 0.0
    identified = facade_identified(fr)

    statement_preflight = fr.get('statement_preflight') or {}
    statement_payload_path = statement_preflight.get('payload_path') or ''
    override_args = override_args_for(statement_preflight)
    receipt_json_path, statement_json_path = artifact_paths(
        scan_image_path, statement_preflight)
    receipt_parse_artifact_arg = (
        '' if identified else f' --parsed-json {receipt_json_path}')
    finish_block = finish_block_for(scan_image_path)

    if identified:
        facade_block = facade_block_for_identified(
            fr, doc_kind, vendor, confidence, parsed)
        fallback_block = ''
        if doc_kind in ('statement', 'bank_statement'):
            return statement_only_message(
                scan_image_path, scanner_name, vendor, confidence,
                steps_for_identified_statement(
                    scan_image_path, statement_payload_path,
                    statement_json_path, override_args),
                finish_block, conversation_id, dispatched_at)
    else:
        facade_block, fallback_block = blocks_for_unidentified(
            fr, doc_kind, confidence, scan_image_path, receipt_json_path)

    return pipeline_message(
        scan_image_path, scanner_name, facade_block, fallback_block,
        statement_json_path, override_args, finish_block,
        categorizer_input_for(identified, parsed, vendor),
        receipt_parse_artifact_arg, store_contract_for(identified),
        conversation_id, dispatched_at)
