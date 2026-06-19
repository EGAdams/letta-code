# Mazda receipt-linking roles

- **Mazda**: own the workflow, require evidence, and reject unsafe bulk updates.
- **Mazda Router**: route receipt discrepancies to Receipt Linker; include expense ID,
  date, amount, description, source document, and current receipt_url.
- **Mazda Parser**: extract and validate receipt merchant, transaction date, and total
  from the candidate image when filename evidence is insufficient.
- **Mazda Vendor Identity**: normalize expense and receipt vendors and explain token
  aliases such as `AT&T`/`at_and_t`, `VIOC`/`Valvoline`, or statement abbreviations.
- **Mazda Receipt Linker**: run the audit, classify candidates, inspect review cases,
  update receipt_url only when verified, and produce the JSON audit report.
- **Mazda Categorization**: preserve category assignments; receipt linking must not
  silently recategorize an expense.

## Known verified boundary

- Expense `1121`, Home Depot refund, `2025-01-26`, `$231.08` is linked to:
  `receipts/january/january_26/home_depot_refund__01_26_25__neg_231_08.jpeg`.
- Expense `1122`, Goodwill Gandy, `2025-01-07`, `$14.96` has no matching receipt and
  must remain unlinked unless new evidence appears.

## Safety rule

The current expense's own non-empty `receipt_url` is the authorization boundary for
receipt UI. Do not restore stale static HTML links or attach another transaction's
receipt merely to create a red tag.
