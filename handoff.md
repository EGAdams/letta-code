# Shift Handoff — 2026-08-02

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
