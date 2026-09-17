# dashboard/server.py refactor — handoff

**Status as of 2026-09-17.** Not yet deployed to the live box (DESKTOP-2OBSQMC). Not yet pushed to `origin/main` as of this commit — push is a separate step.

## The goal

`dashboard/server.py` was a 7638-line God Module — every route handler's business logic, every composition root, and every piece of shared state in one file. `dashboard/CLAUDE.md`'s own file-size rule ("any file over 250 lines gets split into smaller modules, along real seams") flags this as a standing violation. The ask was to shrink it as far as reasonably possible without breaking anything, by extracting business logic into `finance/`, `intake/`, `hardware/`, `model_stats/`, and `monitoring/` modules — the same packages the file already partially delegates to.

## Where it stands

| | Lines |
|---|---|
| server.py before (original) | 7638 |
| server.py now | **4400** |
| Reduction | **3238 lines, 42.4%** |

35 new modules were created (full list below), all following one dependency-injection pattern (below). The full test suite is green:

```
.venv/bin/python -m pytest tests/
# 3397 passed, 6 skipped, 3 failed
```

The 3 failures are **pre-existing and unrelated** — confirmed by running them against a clean `git worktree add <tmp> HEAD` checkout of the baseline commit, where they fail identically:

- `tests/test_intake_integration.py::test_goodwill_grand_rapids_is_a_recognized_vendor` — depends on external `~/rol_finances` vendor_category.yaml data
- `tests/test_server.py::test_recent_intake_html_lists_expenses_with_picker`
- `tests/test_server.py::test_build_scanner_report_html_placeholder_and_content` — both assert `data-vendor-key="kum_go"`, environment-dependent `manual_entry.resolve_vendor_match` behavior on this box

**`bun test js/tests` was not run** — nothing under `js/` was touched, only Python.

## The pattern (read this before touching any of the new modules)

Every extraction follows the same shape, already established in this codebase before this refactor started (`intake/mazda_dispatch.py`, `finance/recategorize.py` are the canonical pre-existing examples). This is not a new pattern invented for this work — it's the existing one, applied consistently:

```python
# in the new module, e.g. finance/expense_commands.py
from dataclasses import dataclass
from typing import Callable

@dataclass(frozen=True)
class Collaborators:
    get_expense_edit_repository: Callable
    invalidate_receipt_index: Callable
    # ... every server.py-owned thing this logic touches

def delete_stored_expense(deps: Collaborators, data, repository=None):
    # the actual business logic, unchanged from the original server.py body,
    # except every server.py name is now deps.<name>
    ...
```

```python
# in server.py — the thin wrapper that remains
from finance import expense_commands as _expense_commands  # noqa: E402

def _expense_commands_deps():
    # rebuilt FRESH on every call — never cached at import time or module scope
    return _expense_commands.Collaborators(
        get_expense_edit_repository=_get_expense_edit_repository,
        invalidate_receipt_index=_invalidate_receipt_index,
    )

def delete_stored_expense(data, repository=None):
    """POST /api/expense-delete: remove one stored row."""
    return _expense_commands.delete_stored_expense(
        _expense_commands_deps(), data, repository=repository)
```

**Why the deps builder is a function, called fresh every time, instead of a module-level constant:** `tests/test_server.py` drives almost everything through `monkeypatch.setattr(server, 'some_name', fake)`. Python resolves a bare name inside a function body at *call time*, not at definition time — so as long as the deps builder references `_get_expense_edit_repository` (the bare module-global name) rather than a value captured earlier, a test's monkeypatch on `server._get_expense_edit_repository` is still picked up the next time `_expense_commands_deps()` runs. Building the Collaborators object once at import time would silently freeze the *original* function forever, and a monkeypatched test would go on calling real code while looking green.

**The trap that bites hardest — and did, repeatedly, during this work:** when a function being extracted calls a *sibling* function that is *itself* individually monkeypatched by a test, the extracted code must route that internal call through `deps.<name>` (pointing back to the server.py wrapper) rather than calling the new module's own copy of that sibling function directly. Example from `intake/intake_folding.py`:

```python
def duplicate_callback_integrity_error(deps, event):
    ...
    rows = deps.duplicate_event_rows(clean_ids)   # NOT duplicate_event_rows(clean_ids)
```

`tests/test_server.py` does `monkeypatch.setattr(server, '_duplicate_event_rows', lambda _ids: [...])` and expects that fake to be honored inside `fold_event_into_intake`'s duplicate-checking logic. If the module called its own `duplicate_event_rows` function directly instead of `deps.duplicate_event_rows`, the monkeypatch would silently stop taking effect — `dashboard/CLAUDE.md` calls this exact failure mode out: *"the symptom is not a red test — it is a green one that took 30 seconds."* Every module below was checked against this before being considered done: grep `tests/*.py` for `monkeypatch.setattr(server, '<name>'` for every name a function touches, not just the top-level function being extracted.

**Constants and registries that tests rebind wholesale** (`monkeypatch.setattr(server, 'SCANNERS', {...})`, `RECEIPT_MOUNTS`, `ROL_FINANCE_REPORTS`, `READABLE_DOCS_BASE`, `LETTA_BASE_URL`, etc.) get the exact same treatment — they're read through the deps builder (`scanners=SCANNERS` evaluated fresh per call), never imported once and cached in the new module.

## Three specific gotchas hit this session (useful if you hit similar ones)

1. **Name collision on a new module path.** Created `finance/reporting_categories.py` for a new helper without checking whether that path already existed — it did, as the real typed reporting-category *registry* (`REPORTING_CATEGORY_CLASS` etc., a completely different concern), and got silently overwritten. Broke 46 test files at collection. Caught immediately by running the suite right after; restored via `git show HEAD:dashboard/finance/reporting_categories.py`; new content moved to `finance/reporting_category_lookup.py`. **Always `git log --oneline -1 -- <path>` before writing a new module file.**

2. **Removing a "now-unused" import can break a public re-export contract even though nothing in server.py calls it anymore.** Two examples:
   - `from model_stats.windows import _human_reset` — removed because server.py's own code no longer called it after `model_stats_agents_payload` moved out. Broke `tests/test_model_stats_models.py::TestServerReExports`, which pins a list of names that must resolve to their owning module's object (`getattr(server, name) is getattr(module, name)`) as a permanent public-API contract, independent of whether server.py's *own* code still uses the name.
   - `import shutil` / `import hashlib` — removed after their only call sites (`_stage_scan_for_mazda`, `_stage_scan_for_mazda`) moved into `intake/scan_staging.py`. Broke two tests that patch `server.shutil.which` / `server.shutil.copyfile` directly — they access `shutil` as a module *through* `server`'s namespace (module identity, shared with whatever else imports `shutil`), not because server.py's own code calls it. `import shutil` had to stay in server.py even though grep shows zero direct uses of `shutil.` in the file.
   
   **Lesson: after removing an import that `grep` says is unused, run the full test suite before concluding it's safe. Grep only proves server.py's own code doesn't reference it — it doesn't prove nothing reaches it *through* server.py's namespace.**

3. **A test that counts literal source-code occurrences is asserting an architecture invariant, not a text coincidence.** `tests/test_mazda_mode.py::test_only_one_place_decides_whether_mazda_runs` does `inspect.getsource(server).count('_dispatch_mazda_or_block(')` to prove scans and PDFs can't drift onto two different execution-mode gates. When `process_pdf_document`'s call site moved out of server.py (into `intake/pdf_document_processing.py`), the literal count in server.py dropped and the test failed. The fix was not "adjust the expected number" — it was updating the test to check the invariant across all three files now involved (server.py's `def` + both `intake/document_processing.py` and `intake/pdf_document_processing.py`'s `deps.dispatch_mazda_or_block(` call sites), because the actual guarantee (exactly one comparison point, reached from every dispatch path) still holds — it just spans more files now. The same situation happened earlier in this refactor for `process_scanned_document`'s extraction.

## Full list of new modules

### `finance/`
| Module | Lines | Extracted from |
|---|---|---|
| `statement_preflight.py` | 265 | `run_statement_preflight` + helpers |
| `recent_scans.py` | 272 | `_fetch_recent_scans`, `_fetch_receipt_only_rows`, `_fetch_month_status`, `_document_report_for_path`, `_is_uncategorized` |
| `document_association.py` | 254 | `_associated_source_paths`, `_associated_evidence_paths`, `_statement_archive_path`, `_recent_intake_archive_path`, `scanner_intake_archive_path`, `_scanner_statement_report` |
| `report_file_lookup.py` | 245 | `_find_matching_report_row`, `_report_file_for_url`, `_split_report_url`, `_resolve_report_path_alias`, `_source_document_path`, `_report_source_document_view` |
| `receipt_index.py` | 206 | the receipt-file index/cache, `_resolve_expense_receipt_path`, `_matching_expense` |
| `intake_report_builder.py` | 213 | `build_recent_intake_html` |
| `expense_lookup.py` | 155 | `_fetch_expenses_by_ids` |
| `expense_commands.py` | 155 | `search_stored_expenses`, `delete_stored_expense`, `add_sales_tax_to_expense` |
| `reporting_category_lookup.py` | 142 | `_reporting_category_for_id`, `_rol_finance_categories`, `_resolve_reporting_category`, etc. (**not** the same file as the pre-existing `finance/reporting_categories.py` registry) |
| `manual_receipt_intake.py` | 137 | `submit_manual_receipt_entry` |
| `report_attention.py` | 138 | `_extract_report_attention_detail` |
| `expense_edit_service.py` | 136 | `_edit_stored_expense` |
| `receipt_reference_sync.py` | 123 | `_update_recent_receipt_references` |
| `receipts_present.py` | 111 | `receipts_present`, `scanned_statements_present` |
| `receipt_lookup.py` | 107 | `lookup_receipt` |
| `source_document_reference.py` | 100 | `_source_document_reference` |
| `recent_reports_index.py` | 73 | `_rol_finance_recent_reports`, `_month_broken_report_label` |
| `receipt_only_report_page.py` | 74 | `build_receipt_only_report_html` |

### `intake/`
| Module | Lines | Extracted from |
|---|---|---|
| `recent_report_store.py` | 299 | the whole `/recent_report.html` pointer-file state machine: `record_recent_intake`, `merge_recent_intake_event`, `merge_recent_intake_status`, `resolve_recent_report`, etc. |
| `intake_folding.py` | 273 | `_fold_event_into_intake` + duplicate-detection helpers |
| `document_processing.py` | 235 | `process_scanned_document` (from the *previous* session) |
| `pdf_document_processing.py` | 140 | `process_pdf_document`, `reprocess_report` |
| `scanner_control.py` | 127 | `run_scanner`, `scanner_status`, `clear_scanner_verification_lock` |
| `intake_facade.py` | 112 | `run_intake_facade`, `build_pipeline_result` |
| `scan_staging.py` | 109 | `_stage_scan_for_mazda`, `_create_mazda_conversation` |
| `expense_stored_callback.py` | 103 | `record_stored_expense` |
| `scan_dispatch_claim.py` | 97 | the scan-dispatch dedupe claim (`_claim_scan_dispatch`, `_release_scan_dispatch`, `_may_retry_terminal_scan`) |
| `intake_halt.py` | 82 | `record_intake_halt`, `read_intake_halt`, `acknowledge_intake_halt` |
| `pdf_dispatch.py` | 46 | `_notify_mazda_of_pdf` |

### `hardware/`
| Module | Lines | Extracted from |
|---|---|---|
| `scanner_invoke.py` | 119 | `_invoke_scanner`, `_reap_stale_scans` |

### `monitoring/`
| Module | Lines | Extracted from |
|---|---|---|
| `agent_health.py` | 133 | `agent_health_check`, `agent_health_status`, `_uses_claude_sdk` |
| `server_status.py` | 114 | `server_health`, `compute_server_status`, `server_status_kind` |
| `agent_activity.py` | 94 | `agent_activity_status`, `_agent_activity_one`, `_msg_age_seconds` |
| `agent_list.py` | 74 | `build_agent_list` |

### `model_stats/`
| Module | Lines | Extracted from |
|---|---|---|
| `agents_payload.py` | 219 | `model_stats_agents_payload`, `_weekly_percent_remaining` |

Six files are over the 250-line guideline: `recent_scans.py` (272), `document_association.py` (254), `statement_preflight.py` (265), `intake_folding.py` (273), `recent_report_store.py` (299), and `report_file_lookup.py` is right at the edge (245). Each is a single cohesive state machine or domain rather than a grab-bag — judged acceptable over artificially splitting a single responsibility, consistent with how the pre-existing modules in this codebase (e.g. `intake/mazda_dispatch.py` at 291 lines) are already sized.

## What's deliberately NOT extracted, and why

**server.py is still 4400 lines. That is not an oversight — the remaining bulk falls into three buckets, and none of them are "just do the same thing again":**

1. **Genuine service-layer infrastructure with live side effects** (~500-600 lines combined):
   - "Generic restart dispatch" section (~305 lines): `_restart_user_unit`, `_restart_remote`, `restart_frita_executor`, `restart_document_vision`, `set_chatgpt_provider_account`, `get_chatgpt_provider_account_status` — every Server Management tab's Restart button. These run real `systemctl restart`, SSH, and OAuth token refreshes against live infrastructure. **The code itself already says, in a comment, that moving these out is "round 23's job"** — an explicit, intentional deferral by this codebase's own authors, not something this session skipped by accident.
   - "Server lifecycle" service-start handlers (~209 lines): `start_executor_server`, `start_frita_executor`, `restart_dashboard_server` (which restarts the very process serving the request), `deploy_dashboard` (git pull + self-restart), `start_logger_api`.
   
   Extracting these trades real risk (a bug in a moved SSH/subprocess call is a live-infrastructure incident, not a failed unit test) for very little architectural benefit — they're already thin, and they're already composition roots per the file's own section comments.

2. **Pure composition-root wiring**, which is what `server.py`'s own architecture doc says belongs there ("the service layer: every function and registry the dashboard exposes"):
   - `startup_tasks()` (54 lines) — a list of `BackgroundTask` objects pairing each daemon thread with its banner text. Not business logic.
   - The Mazda Trainer escalation composition root: `_build_trainer_escalation_service`, `_trainer_escalation_service` (module-level singleton), `_recover_trainer_escalations`, `_watch_intake_for_problems`, `_observe_intake_callback` — thin wiring over one singleton service object, the same shape as the already-accepted `_get_expense_edit_repository`.
   - `_supporting_document_service()`, `_get_category_taxonomy()`, `_get_expense_edit_repository()` — composition roots holding process-lifetime singletons/caches. Moving the *function* out doesn't remove the coupling to server.py's global state; it just adds an indirection.

3. **Small functions where extraction overhead now exceeds the value.** After the above extractions, essentially everything left is under 30 lines (`deploy_dashboard` 41, `restart_document_vision` 40, `patch_agent_oauth_account` 32, `scanner_diagnostics` 27, `get_code_status` 26, ...). Each of these individually costs a new file + a `Collaborators` dataclass + a deps builder + a monkeypatch audit + a full test run to save 20-40 lines net (after subtracting the thin wrapper left behind). The ratio has flipped from "clearly worth it" (the 700-line sections at the start of this work) to "marginal."

## If you want to keep going anyway

Re-run this to find the next-best target:

```bash
cd dashboard
# section-by-section size (some are now mostly-hollow — check actual function
# sizes inside a section before assuming it's still worth doing)
grep -n "^# ──" server.py

# actual function sizes, not section totals
.venv/bin/python3 - <<'EOF'
import ast
tree = ast.parse(open('server.py').read())
funcs = [(n.name, n.end_lineno-n.lineno+1) for n in tree.body
         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
for name, n in sorted(funcs, key=lambda x: -x[1])[:25]:
    print(n, name)
EOF
```

For each candidate, before writing anything:
1. `grep -c "monkeypatch.setattr(server, '<name>'" tests/*.py` for the function itself **and every server.py name it calls** — anything nonzero needs `deps.<name>` routing for that specific call, per the trap above.
2. `git log --oneline -1 -- <candidate-new-path>` — confirm the path doesn't already exist as something else.
3. After editing: full syntax check (`python3 -c "import ast; ast.parse(open('server.py').read())"`), then `import server` cleanly, then the **full** `pytest tests/` (not a filtered subset) before moving to the next one. A filtered run passing is not sufficient — see gotcha #2 above (the re-export contract tests and the `shutil`/`hashlib` tests are easy to miss if you only run tests near the function you touched).

## Not yet done

- **Not committed to `origin/main` via push** as of writing this doc — this commit is local only unless a separate push happened after.
- **Not deployed.** Per `dashboard/CLAUDE.md`: "Editing files here doesn't necessarily change what users see... every `dashboard/` change gets deployed, not just committed." The live box is `DESKTOP-2OBSQMC` (100.102.209.100). Deploy via `POST /api/server-action {"action":"deploy"}` once pushed, or `ssh adamsl@100.102.209.100 'cd ~/letta-code && git pull'` + `systemctl --user restart dashboard-server.service`, then verify with `./verify-live.sh "<marker string>"`.
- **`bun test js/tests` not run** — no JS was touched, but it's normally part of the dashboard change checklist.
- **No attempt made to reduce `http_app/get_routes.py` or `http_app/post_routes.py`** (~600 lines each per `dashboard/CLAUDE.md`) — out of scope for this pass, which was specifically about `server.py`.
