---
name: rol-finance-report-category-colors
description: Diagnose and fix ROL Finance report.html files where Verified Transactions rows show no category color and the category-picker link doesn't visibly change color on save. Use when a report's hero text says "Rebuilt report restored required verification sections...", when rows carry cat-* classes but render with no background, or whenever Mazda/minions hand-author or "rebuild" a report.html instead of generating it through the normal pipeline.
---

# ROL Finance Report Category Colors

## Symptom

A report.html's **Verified Transactions** table rows have `class="cat-*"` and the
category-picker `onclick="openCategoryPicker(this)"` works (DB write succeeds, the row's
class attribute changes), but **no row ever shows a color** — before or after changing
category. Visually it looks like the picker "isn't working," but the click/DB write is fine.

## Root cause

The row classes (`cat-church-facility`, `cat-travel-and-vehicle`, etc.) only render a color
if the report's `<style>` block defines a CSS rule for that class — e.g.
`.cat-travel-and-vehicle { background: #F4B683; color: #000000; }`. The normal generation
pipeline (`create_spreadsheet.py` → `restructure_verified_transactions.py`) always includes
these rules. But when a report.html is **hand-authored or "rebuilt"** outside that pipeline
(confirmed cause: an LLM-driven rebuild that restored the verification sections and picker
JS/modal but never re-emitted the 13 `.cat-*` color rules), the `<style>` block ends up with
zero `.cat-*` rules. Every row class then matches no CSS, so the table renders colorless no
matter what category is picked — this is NOT the previously-known issue of
`apply_reporting_category_colors.py` overwriting a picker edit on regen; it's a complete
absence of the CSS rules.

**Telltale sign:** the report's hero section reads "Rebuilt report restored required
verification sections while preserving categorized expense rows and row metadata." That exact
phrase has shown up in every report found broken this way so far.

## Diagnose

Check one file:
```bash
grep -c '\.cat-office-and-administration\s*{' <report.html>
```
`0` means the CSS rules are missing. Sweep every report under the dashboard's report tree:
```bash
cd ~/rol_finances/readable_documents/bank_statements
for f in $(find . -iname "report.html" -o -iname "*verification_report.html"); do
  n=$(grep -o '\.cat-office-and-administration\s*{' "$f" | wc -l)
  echo "$n  $f"
done
```

## Fix

The canonical 13-rule color block (must match `create_spreadsheet.py`'s
`REPORTING_CATEGORY_STYLES`, `dashboard/server.py`'s `REPORTING_CATEGORY_CLASS`, and
`~/rol_finances/tools/python_tasks/verification_lib/apply_reporting_category_colors.py`'s
`REPORTING_CATEGORY_STYLES`/`CATEGORY_TO_CLASS`):

```css
.cat-church-facility { background: #B8CCE4; color: #000000; }
.cat-church-utilities { background: #95B3D7; color: #000000; }
.cat-ministry-and-worship { background: #DCE6F1; color: #000000; }
.cat-office-and-administration { background: #4F81BD; color: #FFFFFF; }
.cat-food-and-hospitality { background: #F4F199; color: #000000; }
.cat-gifts-and-love-offerings { background: #A9D18E; color: #000000; }
.cat-robert-benefits-and-medical { background: #CCC0DA; color: #000000; }
.cat-rosemary-benefits-and-medical { background: #F4B6C2; color: #000000; }
.cat-travel-and-vehicle { background: #F4B683; color: #000000; }
.cat-insurance-taxes-and-fees { background: #FCD5B4; color: #000000; }
.cat-housing { background: #DDD9C4; color: #000000; }
.cat-personal { background: #948A54; color: #FFFFFF; }
.cat-uncategorized { background: #BFBFBF; color: #000000; }
```

A file can have more than one `</style>` tag (e.g. a separate block for the "Ask Mazda"
dialog injected later in the body) — insert before the **first** `</style>` only (the head
style block), not via an unscoped string replace that could touch every `</style>` in the
file:

```python
html = open(path).read()
idx = html.find('</style>')
assert idx != -1
html = html[:idx] + css_block + html[idx:]
open(path, 'w').write(html)
```

`~/rol_finances/tools/python_tasks/verification_lib/apply_reporting_category_colors.py` has
an equivalent `add_css_if_missing()`/`build_css_block()` pair, but its `main()` also runs
`patch_verified_transactions()`, which assumes the OLD bare-`<tr>` 6-column table layout and
will silently no-op (not corrupt anything) against the current restructured/picker table —
still, prefer the targeted insert above when fixing an already-restructured report so you
don't depend on that assumption holding.

Always `cp report.html report.html.bak-<reason>-$(date +%Y%m%d_%H%M%S)` before editing in
place.

## Prevent recurrence

**If you (Mazda or a minion) ever "rebuild" or hand-author a report.html's HTML/CSS
structure instead of regenerating it through `create_spreadsheet.py` /
`restructure_verified_transactions.py`, always verify the 13 `.cat-*` rules are present
before declaring the rebuild done** — run the diagnose grep above on the file you just wrote.
This is the kind of recurring failure mode `system_message.xml`'s `<self_improvement>`
rules ask you to capture: update this skill (or your own memory) if you find another
gap in a rebuilt report rather than re-discovering this from scratch.

## Verify

- Re-run the diagnose grep — expect `1`, not `0`.
- Hard-refresh (Ctrl+Shift+R) the report tab in the dashboard
  (`http://localhost:8765/?view=rol-finance-reports`) to bust the no-store cache.
- Click a row, change category in the picker, confirm the row's background color changes
  immediately and survives a refresh.
- Cross-check against `dashboard/server.py`'s `ROL_FINANCE_REPORTS` list for which report
  dirs are wired into a dashboard tab — a broken file outside that list (e.g. one with a
  malformed `<head>`, not just missing CSS) is a different, deeper bug; don't force this fix
  onto it.

Related: `dashboard_rol_finance_category_picker_2026_06_13` and
`reference_rol_finance_reports_data_model_2026_06_14` project memory (the existing
picker/data-model write-up; this skill covers the missing-CSS failure mode specifically, not
the picker's DB-write/disk-write mechanics).
