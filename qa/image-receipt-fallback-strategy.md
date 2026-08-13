# End-to-end QA suite: Image receipt fallback strategy

## Scope

Verify compatibility only through dashboard supporting-document controls. Do not inspect Python interfaces, call project APIs, invoke annotation code, or inspect the annotation cache.

## Preconditions

- Start from a test deployment whose UI exposes expenses 1985 and 1522 plus PDF Control and Excel Control rows in a Verified Transactions table.
- PDF Control has a viewable PDF with one known matching expense row and at least one nonmatching row.
- Excel Control has a viewable workbook with one known matching expense row and at least one nonmatching row.
- Begin with a fresh annotation cache prepared by the test environment owner.

## QA-S001: Established image matches keep their existing targets

1. Open the dashboard in a browser and navigate to the fixture report.
2. Open Set Category for expense 1985 and select View Receipt.
3. Confirm exactly one red box encloses the DTE `$53.06` charge line, not the repeated total or dated balance.
4. Return to the fixture report, open Set Category for expense 1522, and select View Scanned Statement.
5. Confirm exactly one red box encloses the APPLE.COM `$10.59` row, reaches across its amount column, and excludes adjacent rows.

## QA-S002: Other document formats remain available

1. Open Set Category for PDF Control and select its available supporting-document button.
2. Confirm the PDF viewer opens at the matching page with exactly one red box around the known expense row.
3. Return to the fixture report and open Set Category for Excel Control.
4. Select its available supporting-document button.
5. Confirm the workbook opens with a red border around only the known expense row and remains readable.
