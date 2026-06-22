---
name: scan-to-report
description: End-to-end Mazda workflow for turning a scanned finance document into a verified report.html or routing a receipt-only document to the dashboard without fabricating transactions.
---

# scan-to-report

## When to use
Use this skill when a user gives Mazda a scanned finance document and wants the full pipeline documented or executed later: identify the document type, choose the correct parser, extract structured data, resolve vendor/category, produce a compliant `report.html`, and handle receipt-only cases correctly.

Core rule: **cheapest reliable tool first**. Prefer deterministic/local tools before LLM escalation. Do not invent transactions, totals, or database matches.

## Procedure

### 1) Identify the document type and choose the parser
Start by determining whether the input is a **PDF statement** or a **standalone receipt image**.

#### A. PDF statements
Use the team façade first:

```bash
python3 tools/mazda_intake.py <path> --org-id=1 --enable-parse
```

Optional stronger classifier/parser when needed:

```bash
python3 tools/mazda_intake.py <path> --org-id=1 --enable-parse --engine=gemini
```

Interpret `recommended_action` from the returned JSON:

- `auto` → confidence `>= 0.90`, proceed
- `review` → confidence `0.70–0.89`, involve the user before trusting the parse
- `reject` → confidence `< 0.70`, do not use; re-scan or ask the user

Expected JSON shape:

```json
{
  "ok": true,
  "doc_kind": "...",
  "routing_key": "...",
  "vendor": "...",
  "confidence": 0.97,
  "classification_method": "...",
  "recommended_action": "auto",
  "parsed": {...},
  "error": null
}
```

#### B. Standalone receipt images (`.jpg`, `.jpeg`, `.png`, `.bmp`)
Do **not** use `mazda_intake.py` for receipt images; its router does **not** OCR images.

Use:

```bash
python3 tools/receipt_scanning_tools/receipt_parsing_tools/parse_receipt_cli.py <path>
```

Canonical example: `tools/scan.jpg` is a **Walmart Supercenter receipt** and should be treated as a receipt-image workflow, not a bank-statement workflow.

### 2) Parse the document into structured fields
Extract the fields needed for downstream verification/reporting:

- date
- amount
- description
- line items
- statement totals / receipt totals

For statements, prefer the `parsed` object returned by `mazda_intake.py`.

For receipts, use the output of:

```bash
python3 tools/receipt_scanning_tools/receipt_parsing_tools/parse_receipt_cli.py <path>
```

If the parse is incomplete or confidence is low:
- involve the user for ambiguous values
- or delegate extraction/review to the parser minion:
  - `mazda-parser-agent`

Do not silently fill gaps with guesses.

### 3) Resolve the vendor key
Resolve a canonical `vendor_key` from the description.

Implementation reference:
- `tools/categorizer/resolve_vendor_key_with_fallback.py`

Preferred function:
- `resolve_vendor_key_with_fallback(store, description)`

Behavior:
- normalize merchant variants to one key
- prefer deterministic alias/store matching first
- use fallback logic only when direct lookup fails

Examples:
- variant merchant strings should collapse to one canonical key
- do not preserve noisy description variants as separate vendor identities

If vendor identification is unclear, delegate to:
- `mazda-vendor-identity-agent`

### 4) Categorize the transaction
Use vendor lookup first. Do **not** ask the user when a reliable lookup already exists.

Primary source:
- `tools/categorizer/vendor_category.yaml`

Rule:
1. `vendor_key -> category_id` lookup from `vendor_category.yaml`
2. resolve `category_id` to category name as needed
3. only if no reliable lookup exists, use the LLM categorizer in:
   - `tools/categorizer/find_category/`

Confidence gate:
- if categorizer confidence is `< 90%`, involve the user before finalizing
- if `>= 90%`, may auto-apply

If category reasoning is ambiguous, delegate to:
- `mazda-categorization-agent`

### 5) Verify and build `<statement_dir>/report.html`
For statement workflows, produce the final deliverable exactly at:

```text
<statement_dir>/report.html
```

Follow the report output contract:
- include verified totals/checks
- include database presence logic correctly
- include duplicate review
- include vendor/category verification
- do not treat deposits/credits as expected `expenses` rows

Then run the current injector:

```bash
python3 tools/python_tasks/verification_lib/restructure_verified_transactions.py <statement_dir>/report.html
```

The resulting report must satisfy the dashboard contract:

- contains exactly one table with:
  - `id="verified-transactions"`
- each transaction row must include:
  - `data-vendor-key`
  - `data-description`
  - `data-signed-amount`
  - `data-date`
- each row must have a:
  - `cat-<category>` CSS class
- report must contain the picker marker exactly once:
  - `<!-- rol-category-picker:start -->`

Required output rule:
- the final artifact is `report.html`, not an alternate filename

Also:
- add a **new dashboard tab** for whatever was scanned

If report assembly is unclear or multi-step, delegate to:
- `mazda-router-agent`

### 6) Receipt-only fallback: never fabricate transactions
If the scanned document is a **receipt** and there is **no matching Expense record**, do **not** create a fake row in `verified-transactions`.

Receipt matching rule:
- match by **date + absolute amount**

If there is **no matching Expense record**:
- do not fabricate a verified transaction
- route the document to the live Dashboard’s **“Receipt Only”** section
- this means receipts that have a `receipt_url` but no matching transaction/expense record

Canonical example:
- `tools/scan.jpg` → Walmart Supercenter receipt
- if no matching expense exists by date + absolute amount, it belongs in **Receipt Only**

This is a hard rule: a wrong accounting row is worse than an unlinked receipt.

## Delegation guidance
Use Mazda’s helper agents when they are the cheapest reliable option:

- parse / extract / summarize → `mazda-parser-agent`
- identify vendors → `mazda-vendor-identity-agent`
- categorize transactions → `mazda-categorization-agent`
- receipt linking → `mazda-receipt-linker-agent`
- unclear multi-step routing → `mazda-router-agent`

Prefer direct local tools when deterministic and sufficient.

## Self-check
Before declaring the workflow complete, verify:

1. Correct parser was chosen:
   - PDF statement → `tools/mazda_intake.py`
   - receipt image → `tools/receipt_scanning_tools/receipt_parsing_tools/parse_receipt_cli.py`

2. Parsed output includes the expected core fields:
   - date
   - amount
   - description
   - line items / totals where applicable

3. `vendor_key` was resolved with lookup/fallback logic, not guessed.

4. Category came from `vendor_category.yaml` first when available.

5. Any LLM category with confidence `< 90%` was escalated to the user.

6. For statement workflows:
   - `<statement_dir>/report.html` exists
   - injector was run:
     ```bash
     python3 tools/python_tasks/verification_lib/restructure_verified_transactions.py <statement_dir>/report.html
     ```
   - report contains:
     - `id="verified-transactions"`
     - `data-vendor-key`
     - `data-description`
     - `data-signed-amount`
     - `data-date`
     - `cat-<category>`
     - `<!-- rol-category-picker:start -->`

7. A new dashboard tab was added for the scanned document/report.

8. For receipt-only workflows:
   - no fake verified-transactions row was created
   - unmatched receipt was routed to **Receipt Only**

## Notes
- Run on the machine with the `rol_finances` virtual environment and project tools installed.
- Prefer reproducible checks over assumptions.
- Clearly report uncertainty instead of papering over it.