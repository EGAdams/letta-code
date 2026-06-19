---
name: receipt-url-audit-linking
description: Audit and repair empty or incorrect nonprofit_finance expenses.receipt_url fields by constructing the expense receipt filename, recursively searching readable_documents/receipts, classifying matches, and applying only verified links. Use when receipt indicators are missing, a View Receipt action opens the wrong file, an expense has an empty receipt_url, FNBO or other finance reports lack receipt tags, or Mazda/minions need to reconcile receipt files with expense records.
---

# Receipt URL Audit and Linking

Use the canonical fail-closed audit tool:

```bash
python3 /home/adamsl/rol_finances/tools/audit_empty_receipt_urls.py \
  --output /home/adamsl/rol_finances/readable_documents/reports/empty_receipt_url_audit_YYYYMMDD.json
```

## Matching contract

1. Construct the expected receipt stem from `expenses.id_light`:
   `<vendor>_MM_DD_YY_<dollars>_<cents>`.
2. Recursively search:
   `/home/adamsl/rol_finances/readable_documents/receipts`.
3. Treat `.jpg`, `.jpeg`, and `.png` files sharing one stem as renditions of one receipt.
4. Accept an exact stem match automatically.
5. For differing stems, require exact date and amount plus strong vendor-token agreement.
6. Never link a date/amount collision with contradictory vendors.
7. Leave uncertain matches in `review`; inspect the image and duplicate expense or
   `receipt_metadata` rows before approval.
8. Never infer a receipt for an expense merely because a static report row contains
   `has-receipt` or `data-receipt-url`; those values can be stale.

## Apply verified matches

Apply automatic high-confidence matches:

```bash
python3 /home/adamsl/rol_finances/tools/audit_empty_receipt_urls.py --apply \
  --output /home/adamsl/rol_finances/readable_documents/reports/empty_receipt_url_audit_YYYYMMDD.json
```

After manually verifying review cases, apply only their explicit IDs:

```bash
python3 /home/adamsl/rol_finances/tools/audit_empty_receipt_urls.py --apply \
  --approve-review-ids 123,456 \
  --output /home/adamsl/rol_finances/readable_documents/reports/empty_receipt_url_audit_YYYYMMDD.json
```

Do not approve review IDs without checking the actual image or corroborating DB data.

## Verify

- Confirm every newly stored path exists under `readable_documents`.
- Call `/api/receipts-present` for positive and negative examples.
- Call `/api/receipt-lookup` and verify the returned `expense_id` and file.
- Verify the browser shows a red tag and active View Receipt button only for the
  linked expense.
- Run `cd /home/adamsl/letta-code/dashboard && .venv/bin/python -m pytest tests/ -q`.

Read [references/mazda-roles.md](references/mazda-roles.md) when delegating this
workflow across Mazda's minions.
