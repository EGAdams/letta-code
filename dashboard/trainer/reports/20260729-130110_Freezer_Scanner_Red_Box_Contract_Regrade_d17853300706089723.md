# Mazda Trainer Report

- Scanner: Freezer Scanner Red Box Contract Regrade
- Dispatch time: 2026-07-29T13:01:10.608Z
- Document path: `/home/adamsl/rol_finances/tools/receipt_scanning_tools/incoming_scans/scan_freezer_1785330063408672399_e4e29af60f85.jpg`
- Verdict: PASS

## Checklist

1. `load_wrapper_revision`
   - Seen at `2026-07-29T13:01:17+00:00`
   - Returned `wrapper_revision=wrap-v062`, active system/tool/prompt/context revisions present.

2. STEP 0 vision / parse path
   - `classify_scan.py` ran at `2026-07-29T13:01:58+00:00`
   - Returned `doc_type=receipt`, `confidence=0.99`
   - `parse_and_categorize.py --json` ran at `2026-07-29T13:02:25+00:00`
   - `parse_and_categorize.py --save` ran at `2026-07-29T13:03:44+00:00`
   - Save return included `parse_artifact_verified=true`

3. Investigate
   - `check_vendor_key` returned `recognized=true`, `vendor_key=jacob_menninga`
   - `check_duplicates` returned `is_exact_duplicate=false`

4. Categorize
   - `categorizer_main.py` via `executor_run` returned `vendor_key=jacob_menninga`, `category_id=197`

5. Store
   - Stored expense `1678`
   - Itemization succeeded for parent `1678` with child IDs `1679, 1680, 1681, 1682, 1683`
   - Store return was successful and included the parsed receipt metadata

6. Trace
   - `record_trace` called once with `task_name="document-intake"`
   - Trace saved as `279`

7. Judge
   - `judge_trace(279)` returned `PASS`

8. Improvement proposal
   - Not called, correctly, because the run passed

9. Dashboard callback
   - `curl POST /api/expense-stored` executed successfully

## Notes

- The save step logged a warning: `Could not update source_file to /home/adamsl/rol_finances/readable_documents/receipts/2025/march/march_31/jacob_menninga_03_31_25_67_25.jpg`.
- This did not block the intake contract evidence observed in the transcript.

