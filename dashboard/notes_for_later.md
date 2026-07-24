# Notes for Later

Updated: 2026-07-23

## Completed baseline

- The Chase 5783 statement archive now uses the actual expense range:
  `january_04__january_22`.
- The incorrect `january_04__january_28` archive folder was removed.
- Mazda refreshed the intake evidence as trace `151`; `judge_trace` returned
  `PASS`, and the final dashboard callback succeeded.
- The archive planner now excludes payment, credit, refund, and deposit dates
  from range endpoints under mixed-sign and all-positive statement formats.
- Targeted archive tests pass: `20 passed`.

## Work remaining

1. Resolve the unrecognized handwritten annotation `Dental` for expense
   `1504`. Confirm the intended finance category with EG, add the shorthand to
   the statement-annotation legend, and add a regression test.
2. Persist Mazda's archive-repair lesson in her live memfs memory. Proposal
   `111` was approved, but the tool reported that no live-memory applier was
   wired, so the proposal alone may not update Mazda's active memory.
3. Investigate the Trainer runner's dashboard status publishing response. The
   final intake callback succeeded, but the runner separately logged HTTP 200
   with `{"ok": false, "status": "pass"}` while publishing Trainer status.
4. Review and commit the uncommitted changes when ready:
   - `/home/adamsl/rol_finances/tools/receipt_scanning_tools/statement_archive.py`
   - `/home/adamsl/rol_finances/tools/receipt_scanning_tools/test_statement_archive.py`
   - `/home/adamsl/letta-code/dashboard/trainer/mazda_trainer_instructions.md`
   - the new Trainer reports under
     `/home/adamsl/letta-code/dashboard/trainer/reports/`

## Final verification report

`/home/adamsl/letta-code/dashboard/trainer/reports/20260723-155636_Window_Scanner_Date_Range_Cleanup_d1784822196595411.md`
