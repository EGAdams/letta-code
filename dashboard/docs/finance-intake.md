# ROL Finance: reports, scanners, and the Mazda intake pipeline

Detail for the finance/scanner side of the dashboard. Summarized in `../CLAUDE.md`.

## ROL Finance Reports (Project Plans → ROL Finance → Reports)

Each report is a static `report.html` built by `~/rol_finances`, with a category-picker block
injected/re-injected idempotently by `restructure_verified_transactions.py`. Endpoints:
`recategorize-expense`, `receipt-lookup`, `receipts-present`, `rol_finances_receipts/<rel>`.
Receipt matching prefers (date, amount) parsed from filename over the DB's `receipt_url` string.

**Injector gotcha:** head CSS is injected once and not refreshed on re-run; put dialog CSS changes
in the marker-block `<style>` instead. `window.open(..., "noopener")` returns `null` by spec — not
proof of a popup blocker.

**Tile color comes only from the hero badge text.** `server._classify_report_status()` regexes
`<div class="badge...">` — `REVIEW NEEDED`/`WIP` → yellow, `FAIL` → red, `PASS` → green, unparseable
→ yellow (fails closed). Two incompatible report.html shapes exist for the same kind of statement: a
pure PDF-math-verification shape (never depends on categorization, can validly `PASS`) and a
DB-comparison shape (`REVIEW NEEDED` for as long as any row is uncategorized, which for some
accounts is indefinite and correct per policy, not a defect). Building a report in the wrong shape
for that account produces a false yellow tile unrelated to the actual statement. `~/rol_finances` is
its own git repo, checked out independently on every machine (including the one serving the live
dashboard) — a report fix here does nothing for the live tile until pushed and pulled there too, and
that pull can hit real concurrent WIP from other agent sessions. Full detail, examples, and recovery
commands: memories `project-statement-report-pipeline`, `project-dashboard-finance-report-debugging`,
`project-rol-finances-multi-machine`.

Supporting-document opens (`document_annotation.py`) are non-destructive — annotate a cached copy,
never the original. `IExpenseDocumentAnnotationService` is the port; PDF/OCR-image/Excel are
strategies wired in `build_document_annotation_service()`. A match needs date+amount,
description+amount, or a check number, else no box is drawn. On EG's handwritten scans, OCR often
misreads the amount column, so `_line_score` accepts date+payee as a lower-priority tiebreaker that
can't outrank a real amount match; `_same_row` compares vertical overlap so a row never ties (and
cancels) against itself.

## Recent Report (Reports tab default view)

`GET /recent_report.html` shows whichever document was most recently dispatched to Mazda
(`resolve_recent_report()`), in **report mode** (real `report.html` exists) or **intake mode**
(scanned doc stored straight to MySQL, page rendered live from DB by `build_recent_intake_html()`).
Bookkeeping in `dashboard/recent_report.json` (gitignored), folded by `merge_recent_intake_event()`
/ `_fold_event_into_intake`. Mazda's STEP 8 callback must fire even when `stored:0` (a correct
re-scan of an already-processed statement) so the page shows real state instead of stale/empty data.
`duplicate_expense_ids` applies to receipts/invoices too, not just statements — a duplicate-only
event with no ids falls back to resolving them from the DB by `(expense_date, amount)`, bailing if
>3 rows share that pair.

Dispatch is server-side and deduped: `run_scanner()` spawns intake processing itself the instant a
scan reports ready; `_claim_scan_dispatch()` prevents double-dispatch from the frontend's own POST.

### Manual receipt-reading actions

The manual-entry dialog exposes three explicit jobs through `POST /api/receipt-read`:

- **Circled Only** reads only locally circled, boxed, highlighted, or otherwise marked expense rows.
  It fails closed when no marked amount is visible.
- **Total Only** performs a bounded three-field read: merchant, transaction date, and final total.
- **Several Expenses** keeps the forensic path: document classification, full receipt extraction,
  and statement transaction breakup when appropriate.

`ReceiptReadService` is the Strategy context. It maps each `ReceiptReadIntent` to an injected
`IReceiptReadStrategy`; focused reads cross the `IFocusedReceiptReader` port, while the forensic
strategy owns the existing receipt/statement adapters. The browser builds the three buttons from
`RECEIPT_READ_ACTIONS` and delegates progress/model controls to `ReceiptReadControls`, keeping the
manual-entry form independent of the concrete actions. The former `/api/mazda-fill` route and
single “Mazda Fill” button no longer exist.

### Edit Expense audit trail

Every `POST /api/expense-edit` attempt writes one JSON Lines event to
`~/.local/state/letta-dashboard/expense-edit-audit.jsonl` (override with
`EXPENSE_EDIT_AUDIT_LOG`). Each event contains a UTC timestamp, action ID, the
allowlisted expense fields submitted by the browser, the JSON-level success or
failure result, changed fields, warnings, and the returned record. Unexpected
request key *names* are retained to diagnose browser/server drift, but their
values are not. The file is local mode `0600`; audit-write failures are printed
to the dashboard service log and never change the expense command's result.

The ordinary `/tmp/dashboard_8765.log` access line records only HTTP status.
Because the endpoint intentionally returns HTTP 200 for operator-facing
validation errors, use the audit trail—not the access line—to reconstruct an
individual edit.

## Scanners (Project Plans → ROL Finance → Scanners)

Two HP scanners attached to the live box: **Window** = HPI297BEA (HP OfficeJet 8120e), **Freezer** =
HP063E28 (HP DeskJet 4100). Since 2026-07-24 they are driven directly from WSL through native
`sane-airscan`/eSCL — **not Windows WIA**:

- Window: `airscan:e0:Window Scanner` → `https://10.0.0.26/eSCL`
- Freezer: `airscan:e1:Freezer Scanner` → `http://10.0.0.243/eSCL`

WSL multicast discovery is unreliable, so the addresses are static in `scanner_scripts/airscan.conf`
(installed at `/etc/sane.d/airscan.conf`). The shared `scanner_scripts/scan_airscan.sh` performs a
300-dpi flatbed JPEG scan with an 85-second timeout and preserves the existing `SCANNER_BUSY` /
`SCANNER_OFFLINE` / `Saved:` output contract. `run_scan_window.sh` writes `window_scan.jpg`;
`run_scan_freezer.sh` writes `scan_freezer.jpg`. All three scripts are deployed to
`~/planner/nonprofit_finance_db/receipt_scanning_tools/`. `SCANNERS` +
`_invoke_scanner()`/`classify_scan_result()` live in `server.py`.

| Endpoint | Purpose |
|---|---|
| `POST /api/scanner-scan` `{scanner}` | One-shot manual scan → `{status, ok, image_url\|error}` |
| `GET /api/scanner-status?scanner=` | Legacy endpoint that performs a real scan; do NOT use as a health probe |
| `GET /api/scanner-image?scanner=` | Serves the scanned JPEG |
| `GET /api/scanner-diagnostics?scanner=` | Read-only health LEDs → `{overall, checks:[{id,label,state,detail}]}` |

**Scanner Health LEDs** — `scanner_diagnostics()` first calls `_airscan_ready()`, a read-only
capability query (`scanimage -d <device> --help`; never transfers a scan). A ready direct backend
renders the actual live chain: **Scanner Backend → Scanner Service → Driver Health → Scanner Online
→ Scanner Access → No Stuck Scans**. Stale Windows WIA/WSD state must not turn these LEDs red. The
Freezer also keeps its direct LEDM hardware check at
`http://10.0.0.243/DevMgmt/ProductStatusDyn.xml`: door/jam/offline are red; paper/ink are
printing-only yellow warnings and never block scanning.

`scanner_diag.ps1`, WIA, stisvc, and WSL interop remain a legacy fallback only when AirScan is
unavailable. Front end: `ScannerDiagnosticsController`
(`js/implementation/scanner-diagnostics-controller.js`); server-side `build_scanner_diagnostics()`
owns the mapping.

`status` ∈ ready/busy/offline/error. Auto-poll is gated by `MONITORED_SCANNERS` (a `Set` in
`setupScanners` in `dashboard-boot.js`) — currently empty, so neither scanner auto-polls; both sit
idle until "Start Scan" is pressed (constant auto-polling was itself found to cause the Window
scanner reporting "busy" from shared WIA-service contention).

**Root cause/history:** on 2026-07-24 both scanners' own eSCL interfaces reported `Idle` while
Windows retained their WSD Image records as `Present:false, Problem:45`. Even elevated
`fdPHost`/`upnphost`/`stisvc` restarts plus `pnputil /scan-devices` did not reconnect them. This
explained the recurring busy/offline/power-cycle class of failures. Earlier HP Scan Doctor,
open-cover, leaked-process, and missing-interop incidents were real but are no longer on the live
scan path. Full current runbook: memory `dashboard_scanner_airscan_wia_bypass_2026_07_24`;
`dashboard_scanner_wsl_interop` is legacy history.

Install/deploy/verify:

```bash
sudo apt-get install -y sane-airscan sane-utils
sudo install -m 0644 scanner_scripts/airscan.conf /etc/sane.d/airscan.conf
install -m 0755 scanner_scripts/{scan_airscan,run_scan_window,run_scan_freezer}.sh \
  ~/planner/nonprofit_finance_db/receipt_scanning_tools/
scanimage -L
systemctl --user restart dashboard-server.service
# Restart Executor after every dashboard restart:
curl -sS -H 'Content-Type: application/json' \
  -d '{"server":"executor","action":"start"}' http://localhost:8765/api/server-action
curl -sS 'http://localhost:8765/api/scanner-diagnostics?scanner=window'
curl -sS 'http://localhost:8765/api/scanner-diagnostics?scanner=freezer'
.venv/bin/python -m pytest tests/ -q
```

Both scanners completed direct 300-dpi test scans on 2026-07-24 (Window ≈22s, Freezer ≈19s).
Browser blinking-red state can be stale after repair; hard-refresh with `Ctrl+Shift+R`.

## Scan → Mazda intake pipeline

`process_scanned_document` runs a deterministic text-extraction facade inline, then dispatches Mazda
fire-and-forget (`_notify_mazda_of_scan`, message built by pure `build_mazda_scan_message()`).

1. The facade returns `ok:true, doc_kind:unknown, confidence:0` for JPEG scans (no extractable text)
   — `mazda_facade_identified()` requires `doc_kind!=unknown AND confidence>0 AND action!=reject`,
   not just `ok`. On unknown, Mazda classifies the image herself via vision.
2. Every `rol_finances` command Mazda runs needs `PYTHONPATH=/home/adamsl/rol_finances` + its venv
   python — bare `python3 tools/...` dies with `ModuleNotFoundError`.
3. STEP 5 records `IntakeVerificationEvidence` under `task_name="document-intake"`; STEP 6 has the
   self-improvement judge score the trace (served by `mazda-tools-mcp.service` — restart after a
   rubric/tool change).

## Failed scan → Trainer (Mazda's watcher)

Normal intake does not start a Trainer model session. `intake/trainer_escalation.py` arms a cheap
in-process deadline and evaluates Mazda's STEP 8 callback through strict Pydantic contracts. A
zero/incomplete result, explicit FAIL/STALLED callback, or a missing callback after 15 minutes
summons the Trainer. Valid stored and exact-duplicate outcomes cancel the deadline. The Trainer
watches are rebuilt from persisted `processing` intakes after a dashboard restart; intakes that
already persisted `trainer_dispatched:true` are never launched twice. The Trainer watches Mazda's
transcript, verifies the STEP 1–8 contract against actual tool returns (not her prose), coaches her
on failure, and writes a report (`trainer/reports/<ts>_<scanner>.md`).

`MAZDA_TRAINER_ENABLED=0` remains an emergency kill switch;
`MAZDA_TRAINER_CALLBACK_TIMEOUT_SECONDS` adjusts the default 900-second deadline. Non-obvious: the
Trainer session dies if it ends its turn to "wait" (must Bash `sleep`-loop + report before
finishing); the SDK's `.withTimeout()` is a no-op in `@instantlyeasy/claude-code-sdk-ts@0.3.3` —
only `.withSignal()` reaches the child process, so `trainer/claude-attempt.ts` supplies its own
AbortSignal + hard deadline. A 0-byte trainer log means "still running" (bun block-buffers stdout to
a file), not "never started" — check `systemctl --user list-units 'mazda-trainer-*'`.

**Wrapper defect vs. application defect (2026-08-01).** Before coaching, the Trainer classifies the
failure: a *wrapper defect* (Mazda's instructions/tools/memory — coach her, unchanged) or an
*application defect* (a real bug in this repo's or `rol_finances`' code — she cannot fix it by
retrying). Application defects get a structured `## Escalation` block in the report (`repo_path`,
`bug_description`, `metadata`) instead of a buried sentence. The Trainer still never executes
anything under `rol_finances` and never invokes Suzuki itself — a human (or a future report-grepping
dispatcher) turns that block into Suzuki's `BugHuntRequest`. Full contract, routing rule, and exact
Suzuki invocation: `notes_plans_handoffs/mazda_suzuki_escalation_contract.md`.

## Statement review dialog (Scanner screen)

A statement `store_statement_transactions.py` refuses is quarantined to `_needs_review/` with a JSON
sidecar; `statement_review.py` + `StatementReviewDialog` poll `/api/statement-reviews` every 15s and
let EG resolve it via `/api/statement-review-resolve`. Two item kinds, both fail-closed: **workbook**
(unresolved last-4 digits — add a row to the known-accounts spreadsheet; a still-failing resolve
deliberately leaves the sidecar so the dialog reappears) and **amounts** (unreadable rows — one
prefilled input per row; a blank entry is an error, never a silent skip). The sidecar is a
self-contained retry packet, so resolving replays the store without re-scanning.

## Categorizer LLM fallback chain + provider health

`rol_finances/tools/categorizer/categorizer_main.py` (STEP 3) tries `gemini` → `chatgpt-oauth` (EG's
Codex OAuth, then mom's, synced by `codex-moms-token-sync.timer`) → `anthropic`. Every call logs
through `IProviderHealthRecorder` to `~/.mazda/provider_health.json`. Dashboard tile: Server
Management → "LLM Provider Fallbacks (Categorizer)" (yellow = fallback fired in 24h, red = every
tier's last attempt failed). **Not yet covered** by this pattern: `parsing_router/` and
`e_two_e_processing/row_sources/{_pdf_utils,llm_pdf_parser}.py` — port the same pattern there if a
failure traces to either.

## Statement Codex CLI vision fallback

`parse_statement_scan.py` / `apply_statement_annotations.py` try Gemini → OpenAI Codex CLI → legacy
ChatGPT-OAuth → standalone OpenAI. The Codex leg (`codex_cli_vision.py`) renders PDF pages to PNG
via `pdftoppm` before attaching — never send a raw PDF to the ChatGPT `input_image` backend, it's
rejected. Uses the existing Codex OAuth subscription, never `OPENAI_API_KEY`.
