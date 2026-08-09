# End-to-end QA suite: Image receipt fallback highlighting

## Scope

Verify the feature only through the dashboard and the receipt viewer. Do not call dashboard APIs, inspect annotation caches, query the database, or invoke annotation code directly.

The date-misparse and unavailable-file defect for expense 2005 is outside this suite. Mazda instructions, Mazda memory, finance data, and Trainer coaching are not test targets and must not be changed during QA.

## Preconditions

- Start from a test deployment whose UI exposes fixture expenses 2004, 2006, 1985, and 1522 in a Verified Transactions table.
- Map expense 2004 to the preserved real image `/home/adamsl/rol_finances/readable_documents/receipts/2025/september/september_08/river_of_life_ministries_inc_09_08_25_125_00.jpg`.
- Map expense 2006 to the preserved real image `/home/adamsl/rol_finances/readable_documents/receipts/2025/may/may_02/grand_rapids_first_05_02_25_30_00.jpg`.
- Expose four additional UI fixture rows named Unmatched Check, Ambiguous Checks, Invalid Bounds Check, and Offline Fallback Check. The test environment owner preconfigures their fallback outcomes; QA does not change backend state.
- Begin with a fresh annotation cache prepared by the test environment owner, not by the QA workflow.
- Allow the dashboard to open supporting documents in a new browser tab.

## QA-001: Real check-style receipts receive the correct box

Repeat this workflow for expense 2004 and expense 2006:

1. Open the dashboard in a browser.
2. Navigate through Project Plans, ROL Finance, and Reports to the fixture report.
3. Select the expense's Verified Transactions row to open Set Category.
4. Select View Receipt.
5. Confirm a receipt viewer opens in a new browser tab.
6. Confirm the viewer shows exactly one red box.
7. For expense 2004, confirm the box encloses the check-face payment region containing the `$125.00` payment to John Roark. Confirm it does not box the unrelated back-office or posting-detail region below the check.
8. For expense 2006, confirm the box encloses the check-face payment region containing the `$30.00` payment to Gabrielle McKay. Confirm it does not box the unrelated endorsement or posting-detail region below the check.

## QA-002: An established match remains authoritative

1. Return to the fixture report in the dashboard.
2. Open Set Category for expense 1985 and select View Receipt.
3. Confirm exactly one red box encloses the DTE `$53.06` charge line.
4. Confirm neither the repeated `$53.06` total nor the dated balance line is boxed.
5. Return to the fixture report, open Set Category for expense 1522, and select View Scanned Statement.
6. Confirm exactly one red box encloses the APPLE.COM `$10.59` transaction row and reaches across its amount column.
7. Confirm no adjacent transaction row is boxed.

## QA-003: Reopening is visually stable

For each of expenses 2004 and 2006:

1. Close the receipt-viewer tab without changing the expense.
2. Select View Receipt again from the same Set Category dialog.
3. Confirm the same single payment region is boxed and no additional red boxes appear.
4. Refresh the receipt-viewer tab.
5. Confirm the image remains readable and the same single red box remains in place.

## QA-004: Uncertain fallback results remain unboxed

Repeat this workflow for the Unmatched Check, Ambiguous Checks, Invalid Bounds Check, and Offline Fallback Check fixture rows:

1. Open Set Category from the fixture row.
2. Select View Receipt.
3. Confirm the original receipt opens and remains readable.
4. Confirm no red box appears anywhere on the receipt.
5. Confirm no unrelated region is presented as the matching expense.
