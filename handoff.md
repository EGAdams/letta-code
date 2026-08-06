# Shift Handoff — 2026-08-05 — Mazda / `dashboard/server.py` rewrite

## Read these first

The next shift must read and follow all three documents before editing:

1. **GoF tactical debugging guide:** `/home/adamsl/tactical_debug_toolbox/gof_debug_tacticts.md`
2. **Rewrite skill:** `/home/adamsl/.letta/skills/chipping-away-at-server-rewrite/SKILL.md`
3. **Approved plan:** `/home/adamsl/.letta/plans/noble-lively-cloud.md`

The canonical rewrite ledger is `/home/adamsl/letta-code/notes_plans_handoffs/server_rewrite.html`.

## Current objective

Continue the incremental ports-and-adapters rewrite of `/home/adamsl/letta-code/dashboard/server.py` under the standing constraints:

- `server.py` must go down in size.
- Interfaces belong in new modules, not in `server.py`.
- Use strict Pydantic boundary models.
- Preserve routes and response behavior; do not perform a broad rewrite.
- Work one slice at a time with RED → GREEN → refactor evidence.

## Completed immediately before this handoff

The supporting-document application-boundary slice is complete.

New module: `dashboard/supporting_document_application.py`, containing the strict Pydantic DTOs, `SupportingDocumentPorts`, `ISupportingDocumentService`, and `SupportingDocumentService`.

`dashboard/server.py` now wires `_SUPPORTING_DOCUMENT_SERVICE` at the composition root and delegates supporting-document lookup/open/path/view behavior through that typed service. The following four names still exist as temporary compatibility shims and are the next deletion target:

- `lookup_supporting_documents`
- `open_supporting_document`
- `_supporting_document_path_for_expense`
- `_supporting_document_view_for_expense`

The application/policy logic has already moved out. Do **not** add more logic to these wrappers. Migrate route and test callers to the injected `ISupportingDocumentService`, then delete the wrappers once compatibility is no longer needed.

Related modules already extracted and in use:

- `dashboard/finance/supporting_documents.py`
- `dashboard/finance/report_page.py`
- `dashboard/contracts.py`
- `dashboard/supporting_document_service.py`
- `dashboard/supporting_document_slots.py`

## Measurements and validation

Latest application-boundary measurement:

- `dashboard/server.py`: **11,128 → 11,049 lines**, **-79 lines / -0.71%**.
- Latest working-file position: **+332 lines versus the 10,717 historical rewrite baseline** in the ledger.
- Attributable slice delta: **-79 lines** after separating concurrent working-tree edits.

Focused validation passed:

```text
PYTHONPATH=. /home/adamsl/rol_finances/.venv-pytest/bin/pytest dashboard/tests/test_supporting_document_dialog.py -q
30 passed
```

System Python does not provide the needed pytest/Pydantic environment. Use `/home/adamsl/rol_finances/.venv-pytest/bin/pytest` with `PYTHONPATH=.`. The broader annotation run remains environment-blocked because the Python `pytesseract` wrapper is present but the system `tesseract` executable is missing; do not report that known issue as a regression.

## Working-tree safety

There are uncommitted changes from this and concurrent dashboard work. Preserve them; do not reset, clean, amend, or overwrite unrelated files. At handoff, relevant paths include:

- `dashboard/server.py`
- `dashboard/supporting_document_application.py` (new)
- `dashboard/document_annotation.py`
- `dashboard/statement_review.py`
- `dashboard/tests/test_document_annotation.py`
- `dashboard/tests/test_supporting_document_dialog.py`
- `notes_plans_handoffs/server_rewrite.html`
- `notes_plans_handoffs/mazda_rol_finance_role.html` (new/untracked)

No commit was requested or made. Do not commit unless the project owner explicitly asks.

## Exact next shift procedure

1. Re-read the GoF tactical debugging document, rewrite skill, approved plan, and latest `ISupportingDocumentService` ledger entry.
2. Inspect the four compatibility shims and enumerate every caller with a targeted search before editing. Pay special attention to route handlers and tests that monkeypatch `_supporting_document_descriptors`; preserve that seam or replace it with an explicit fake-service contract.
3. Add or adjust focused consumer and negative contract tests first. Prove the service receives typed requests and malformed/extra fields are rejected.
4. Inject/use `ISupportingDocumentService` at the route/application boundary, while constructing the concrete only at the composition root.
5. Run the focused supporting-document suite, then relevant server tests, using the pytest venv command above.
6. Measure `server.py` immediately before and after the slice and run:

   ```bash
   /home/adamsl/.letta/skills/chipping-away-at-server-rewrite/scripts/server_size_trend.sh
   ```

7. Update `notes_plans_handoffs/server_rewrite.html` in the same change. Include RED command/failure, interface/models, callers migrated, shim deletion, focused/negative tests, type-check status, and before/after line counts.
8. Inspect `git diff` and `git status`; leave unrelated work untouched.

## Important historical context

- Trace for the prior Mazda verification run: `trace_id=64`.
- Active Mazda wrapper revision during that run: `mazda-wrapper-v001`.
- The previous supporting-document tests initially failed because callers were monkeypatched against the server-local descriptor helper. The fix retained `descriptor_builder=_supporting_document_descriptors` in the compatibility path. Re-check this behavior before deleting the shim.
- A strict Pydantic descriptor test initially failed when fixtures omitted `field`; `SupportingDocumentDescriptor.field` now defaults to `""` for the established fixture shape. Preserve compatibility unless a deliberate contract change is tested and documented.

## Larger rewrite context

The ledger's next active areas include recent-intake/scanner-report row shaping and `IFinanceReportService`. Finish the current supporting-document shim deletion as one bounded slice before moving to another region. Avoid speculative refactors, broad formatting changes, and changes to the stdlib HTTP server or route shapes.

## Last Window Scan

The live Last Window Scan was corrected and verified at:

- Dashboard: `http://100.72.158.63:8765/scanner_report.html?scanner=window`
- Canonical expense: `561`
- Suppressed duplicate: `1519`
- Merchant/date/amount: MR BURGER RESTAURANT, 2025-02-20, $33.13

The scan now displays one expense row. The View Receipt image selects the printed
`TOTAL $33.13` line instead of the lower `Approved USD $33.13` confirmation. The
red rectangle covers one line; it is intentionally no longer a three-line box.

## Root Causes and Fixes

Two database expense IDs represented the same transaction. A focused presentation
policy in `dashboard/recent_intake_view.py` now collapses equivalent rows by date,
absolute amount, and normalized merchant description while retaining genuinely
different merchants with the same date and amount. The older/evidence-bearing row
is canonical, so expense 561 is displayed.

Receipt OCR originally preferred the exact amount in the card-approval footer.
The annotation policy now:

1. Runs image OCR in both orientation/layout mode (`--psm 1`) and uniform-block
   mode (`--psm 6`).
2. Recognizes a labeled TOTAL whose final cents digit was lost by OCR (`33.1`).
3. Gives an actual line beginning with TOTAL precedence over surrounding OCR
   context windows.
4. Treats that recovered TOTAL as amount-confirmed so identity/reference fallbacks
   do not turn it into a multi-line box.

This is dashboard annotation behavior, not a Mazda judgment error. Do not coach
Mazda for this incident.

## SOLID / Rewrite Discipline

Duplicate-row behavior lives in the pure recent-intake presentation policy rather
than adding another special case to the server composition root. Annotation rules
remain behind the existing document-annotation interface.

The live `dashboard/server.py` count was 11,046 before and 11,050 after the wiring:
`+4` lines (`+0.036%`). Against the historical 10,486-line baseline it is `+564`
lines (`+5.38%`). The live rewrite plan was updated with this evidence and names
the remaining `build_recent_intake_html` renderer as the next extraction target.

## Verification

Live focused suite:

```text
25 passed in 6.75s
```

The suite covered window-scan annotation/report behavior, duplicate presentation,
and general document annotation. Final HTTP smoke check found one row for expense
561 and zero rows for expense 1519. The final served receipt was visually inspected
and boxes the TOTAL line, not the Approved line.

## Deployment and Working Tree Notes

The live dashboard runs inside `Ubuntu-26.04` on `DESKTOP-2OBSQMC`, reached through:

```bash
ssh NewUser@100.118.122.75 'wsl.exe -d Ubuntu-26.04 ...'
```

Service:

```bash
systemctl --user status dashboard-server.service
```

The live annotation cache schema is version 12, ensuring old incorrectly boxed
images are not reused. Local and live trees had pre-existing divergence; live
hotfixes were applied as narrow patches rather than overwriting whole files.

Relevant local working-tree paths are currently uncommitted:

- `dashboard/document_annotation.py`
- `dashboard/recent_intake_view.py`
- `dashboard/server.py` (contains unrelated/pre-existing work; preserve it)
- `dashboard/tests/test_document_annotation.py`
- `dashboard/tests/test_recent_intake_view.py`

The local machine lacks a working Tesseract executable, so three local image OCR
integration-style tests fail with “tesseract is not installed.” The same focused
tests passed on the live machine where Tesseract is installed. Do not interpret
those local failures as a regression.

Before any further `dashboard/server.py` change, follow
`~/.letta/skills/chipping-away-at-server-rewrite/SKILL.md`, capture before/after
line counts, and update the rewrite plan.
