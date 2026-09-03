// scanner-report-tab.js — opening a "Last <Scanner> Scan" report tab.
//
// Three things mount together: the report iframe, Mazda's live Thoughts below
// the progress indicators, and — once the intake reaches a terminal state —
// the archive-verification terminal that proves where the document was filed.

import { mountScannerReportControls } from "../scanners/scanner-report-controls.js";

const TERMINAL_STATUSES = ["complete", "pass", "corrected", "fail", "stalled"];
const COMPLETION_POLL_MS = 5000;

export function openScannerReportTab({ doc, http, tab, RF, AM }) {
  const scannerKey = tab.dataset.scannerReport;
  const section = doc.querySelector(`#${tab.dataset.target}`);
  const iframe = section?.querySelector("iframe");
  mountScannerReportControls({
    doc,
    section,
    iframe,
    scanner: scannerKey,
    onScanReady: () => RF.loadScannerReportInto(iframe, scannerKey),
  });
  RF.loadScannerReportInto(iframe, scannerKey);

  const detailContainer = doc.querySelector(
    `#${tab.dataset.target}-mazda-detail`,
  );
  if (detailContainer) {
    AM.renderMazdaThoughtsInto(detailContainer, scannerKey);
  }

  // Wait for the intake to settle, then show where the document was archived.
  const terminalContainer = `#${tab.dataset.target}-archive-terminal`;
  const pollCompletion = () => {
    http
      .getJSON(
        `/api/scanner-intake-status?scanner=${encodeURIComponent(scannerKey)}`,
      )
      .then((data) => {
        if (data?.status && TERMINAL_STATUSES.includes(data.status)) {
          // The iframe may still be displaying the report it loaded before a
          // newer scan completed. Verify what the operator can actually see,
          // not whichever intake happens to be newest by the time this poll
          // fires.
          const displayedExpenseId = Number(
            iframe?.contentDocument?.querySelector("tr[data-expense-id]")
              ?.dataset.expenseId,
          );
          AM.showArchiveTerminalForScanner(
            scannerKey,
            terminalContainer,
            displayedExpenseId || null,
          );
          clearInterval(completionPoll);
        }
      })
      .catch(() => {
        // Ignore errors and keep polling.
      });
  };
  const completionPoll = setInterval(pollCompletion, COMPLETION_POLL_MS);
  pollCompletion(); // Initial check
}
