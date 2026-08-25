// scanner-report-tab.js — opening a "Last <Scanner> Scan" report tab.
//
// Three things mount together: the report iframe, Mazda's live Thoughts below
// the progress indicators, and — once the intake reaches a terminal state —
// the archive-verification terminal that proves where the document was filed.

const TERMINAL_STATUSES = ["complete", "pass", "corrected", "fail", "stalled"];
const COMPLETION_POLL_MS = 5000;

export function openScannerReportTab({ doc, http, tab, RF, AM }) {
  const scannerKey = tab.dataset.scannerReport;
  const iframe = doc.querySelector(`#${tab.dataset.target} iframe`);
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
          AM.showArchiveTerminalForScanner(scannerKey, terminalContainer);
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
