#!/usr/bin/env bash
set -euo pipefail

# Live smoke test for the exact regression that prompted this feature.  It uses
# the repo-standard Playwright CLI rather than introducing a second browser
# test framework.  The test intentionally runs against the deployed dashboard:
# the scanner pointer and its expense row are the production-shaped fixture.

BASE_URL="${MAZDA_DASHBOARD_URL:-http://100.102.209.100:8765}"
SESSION="mazda-freezer-supporting-documents-$$"
PWCLI="${PWCLI:-/home/adamsl/.letta/skills/playwright/scripts/playwright_cli.sh}"

run_code() {
  "$PWCLI" --session "$SESSION" run-code "async () => { $1 }"
}

cleanup() {
  "$PWCLI" --session "$SESSION" close >/dev/null 2>&1 || true
}
trap cleanup EXIT

"$PWCLI" --session "$SESSION" open "$BASE_URL/" >/dev/null

# Startup checks and stale review notices are unrelated to this dialog.  The
# statement-review dialog is a full-screen overlay and has no close button;
# its explicit "Leave for later" action is the safe, non-mutating dismissal.
# Handle both that dialog and the ordinary close buttons before entering
# Reports.  This is idempotent when none is present.
run_code 'await page.waitForTimeout(4000); const review = page.locator("#statement-review-dialog"); if (await review.isVisible().catch(() => false)) await review.getByRole("button", {name: "Leave for later", exact: true}).click(); for (const button of await page.getByRole("button").all()) { const label = (await button.innerText().catch(() => "")).trim(); if (/Close (this )?Dialog|Close Set Category dialog/.test(label)) await button.click().catch(() => {}); } await page.waitForTimeout(300);'
run_code 'await page.getByRole("button", {name: "ROL Finance", exact: true}).click(); await page.waitForTimeout(300); await page.getByRole("button", {name: "Scanners", exact: true}).click(); await page.waitForTimeout(300);'
run_code 'await page.getByRole("button", {name: "Last Freezer Scan", exact: true}).click(); await page.waitForTimeout(700);'

result="$(run_code 'const frame = page.frames().find((candidate) => candidate.url().includes("/scanner_report.html?scanner=freezer")); if (!frame) throw new Error("Freezer Scanner report iframe not found"); const row = frame.getByText("ANNUAL FEE Diners Club | x-0587", {exact: true}); await row.click(); const source = frame.getByRole("button", {name: "View Source Document", exact: true}); const scanned = frame.getByRole("button", {name: "View Scanned Statement", exact: true}); await scanned.waitFor(); if (await source.count() !== 0) throw new Error("duplicate View Source Document action is visible"); if (await scanned.count() !== 1) throw new Error("View Scanned Statement action is missing"); const popupPromise = page.waitForEvent("popup"); await scanned.click(); const popup = await popupPromise; await popup.waitForLoadState("domcontentloaded"); return {source_count: await source.count(), scanned_count: await scanned.count(), popup_url: popup.url()};')"

printf '%s\n' "$result"
grep -q '"source_count": 0' <<<"$result"
grep -q '"scanned_count": 1' <<<"$result"
grep -q '/supporting-document/2000/scanned_statement' <<<"$result"
printf 'PASS: Freezer Scanner exposes the archived scan once and opens it.\n'