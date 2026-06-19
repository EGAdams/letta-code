---
name: rol-finance-report-verification-audit
description: Audit and fix a ROL Finance bank-statement report.html against REPORT_OUTPUT_CONTRACT.md - catches wrong-statement copy-paste, broken/un-restructured Verified Transactions tables, sign-direction errors, vendor-key-as-category-name bugs, and duplicate/corrupted expenses rows. Use before trusting any existing report.html, before writing a new one for a new statement (e.g. February), or when a report's numbers look wrong or copy-pasted from a different account.
---

# ROL Finance Report Verification Audit

Full procedure documented in
`~/rol_finances/tools/python_tasks/verification_lib/REPORT_OUTPUT_CONTRACT.md` —
**read it first, every time**, especially Rules 4-8 (added 2026-06-18, see
`rol_finance_report_audit_2026_06_18` memory for the full incident writeup). This
skill is the condensed checklist + commands.

## Reference example

`~/rol_finances/readable_documents/bank_statements/january/business_january_february_6285/report.html`
is the most complete, fully contract-compliant report (10 required `<h2>` sections +
a working Verified Transactions picker). Read it as a structural model. Don't edit it
as a content template — it's a different account/statement.

## Checklist (run all of these — bugs from each category have been found in real reports)

1. **Wrong statement copy-pasted wholesale.** Extract the real PDF with PyPDF2 (not
   pdfplumber — has misread page count/dropped pages before) and confirm the hero /
   Statement Summary / Total Amount numbers actually came from *this* directory's PDF.
   Found twice in this project already (one report's entire body was a different
   bank account's statement).
2. **Verified Transactions table never restructured.** Check:
   ```bash
   grep -c 'id="verified-transactions"' report.html   # expect >=1 (the real <table>, prose mentions OK too)
   grep -o 'data-vendor-key=' report.html | wc -l      # expect == transaction row count
   grep -c 'rol-category-picker:start' report.html     # expect 1
   ```
   If `data-vendor-key` is 0, the picker dialog markup may exist but nothing on the
   page calls it. Fix: write a plain 6-column table (`Date, Category, Vendor Key,
   Description, Signed Amount, Status`, vendor key in `<code class="inline-code">`),
   then run:
   ```bash
   python3 ~/rol_finances/tools/python_tasks/verification_lib/restructure_verified_transactions.py report.html
   ```
   Confirm it's the *current* injector first: `grep -c rol-category-picker
   restructure_verified_transactions.py` must be > 0 — an older version only adds an
   `alert('Vendor Key')` handler with no picker dialog.
3. **Sign-direction errors.** Negative = money leaving (charges/checks/withdrawals),
   positive = money entering (deposits/credits/refunds/payments-received). Verify
   against the statement's own printed Balance Summary math exactly. The same
   merchant's refund has been found mislabeled as a positive charge in two different
   statements independently — don't assume one fix means the pattern is gone.
4. **Vendor key is a category name, not a merchant.** `data-vendor-key` must identify
   the actual merchant (`mister_car_wash_0465`), never a reporting bucket
   (`travel_vehicle`).
5. **Double-escape bug.** If a pre-restructure cell has `&amp;` and you run the
   injector, you can end up with `&amp;amp;`:
   ```bash
   sed -i 's/&amp;amp;/\&amp;/g' report.html
   ```
6. **Missing CSS color rules.** See the sibling skill
   `rol-finance-report-category-colors` — check
   `grep -c '\.cat-office-and-administration\s*{' report.html` is 1, not 0. As of
   2026-06-18 this is fixed fleet-wide, but re-check after any hand-rebuild.
7. **DB presence / duplicates / corruption.** For every transaction:
   ```bash
   cd ~/rol_finances/receipt_parsing_tools && python3 -c "
   from app.db import get_connection
   with get_connection() as conn:
       cur = conn.cursor()
       cur.execute('SELECT * FROM expenses WHERE expense_date=%s AND ABS(amount-%s)<0.01', (date, amount))
       print(cur.fetchall())
   "
   ```
   - 0 rows: INSERT (id_light `{vendor}_{MM}_{DD}_{YY}_{dollars}_{cents}`, org_id=1,
     method='OTHER', source_file=<pdf path>).
   - 2+ rows, same direction/account: keep the most descriptive/categorized one,
     delete the rest. Watch for a fully **corrupted** row (id_light implies one
     date/amount, actual `amount`/`receipt_url` columns belong to a different,
     already-correct transaction) — delete it, don't repair it.
   - 2 rows that are a legitimate cross-account transfer pair (e.g. account A "TO"
     account B, and account B's own statement has the matching "FROM" row) — this is
     NOT a duplicate, leave both.
   - Before trusting any `receipt_url`, verify the file exists:
     `find ~/rol_finances/readable_documents/receipts -iname "<basename>"`. Stale
     paths (nonexistent files, or a *different* transaction's receipt reused) are
     common — clear to NULL rather than guess. Prefer the canonical
     `receipt-url-audit-linking` skill's tool for bulk receipt relinking.
8. **Categories.** Resolve via `REPORTING_CATEGORY_ANCESTOR_MAP` in
   `~/rol_finances/receipt_parsing_tools/create_spreadsheet.py` — parse with
   `ast.literal_eval` (xlsxwriter isn't installed in plain python3, can't `import
   create_spreadsheet` directly), walk `categories.parent_id` until an id is in the
   map.

## Final verification

```bash
grep -o 'data-vendor-key=' report.html | wc -l     # == row count
grep -o 'data-description=' report.html | wc -l    # == row count
grep -o 'data-signed-amount=' report.html | wc -l   # == row count
grep -o 'data-date=' report.html | wc -l            # == row count
grep -c 'rol-category-picker:start' report.html     # 1
python3 -c "
from html.parser import HTMLParser
class P(HTMLParser):
    def __init__(self): super().__init__(); self.stack=[]
    def handle_starttag(self, tag, attrs):
        if tag not in ('br','meta','link','img','input','hr'): self.stack.append(tag)
    def handle_startendtag(self, tag, attrs): pass
    def handle_endtag(self, tag):
        if self.stack and self.stack[-1]==tag: self.stack.pop()
p = P(); p.feed(open('report.html').read())
print('unclosed:', p.stack)
"
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8765/rol_finances_reports/<dir>/report.html  # 200
```

## Multi-agent caution

`~/rol_finances` is a live, multi-agent-edited git repo (Mazda's minions, other
sessions on other machines also push to it). After a long session, check
`git status` and `git log origin/main..HEAD` / `git log HEAD..origin/main` before
assuming your local copy is the only edit in flight. If you hit a merge conflict on a
report.html or `restructure_verified_transactions.py`, check which side has
`rol-category-picker:start` present and which injector version it is (current = 575
lines, contains `recategorize-expense`; old = much shorter, `alert()`-only) — prefer
the side with the current injector and working picker, not necessarily "theirs" or
"ours" by default.

Related: `rol_finance_report_audit_2026_06_18` memory (full incident writeup),
`receipt-url-audit-linking` skill, `rol-finance-report-category-colors` skill.
