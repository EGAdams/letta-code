// scanner-report-tab.js — opening a "Last <Scanner> Scan" report tab.
//
// Four things mount together: the report iframe, Mazda's live Thoughts, and —
// once the intake reaches a terminal state — the exact Letta Code conversation
// plus static evidence proving where the document was filed.

import { readScannerIntakeStatus } from "../../abstract/scanner-intake-status.js";
import { mountScannerReportControls } from "../scanners/scanner-report-controls.js";

const COMPLETION_POLL_MS = 5000;

export function openScannerReportTab({
  doc,
  http,
  tab,
  RF,
  AM,
  scannerFetch = globalThis.fetch,
  setIntervalFn = globalThis.setInterval,
  clearIntervalFn = globalThis.clearInterval,
}) {
  const scannerKey = tab.dataset.scannerReport;
  const section = doc.querySelector(`#${tab.dataset.target}`);
  const iframe = section?.querySelector("iframe");
  const archiveContainer = `#${tab.dataset.target}-archive-verification`;
  const mazdaTerminalContainer = `#${tab.dataset.target}-mazda-terminal`;
  let completionPoll = null;
  let latestIntakeAt = null;
  let ignoreIntakesThrough = null;
  const stopCompletionPolling = () => {
    if (completionPoll !== null) clearIntervalFn(completionPoll);
    completionPoll = null;
  };
  const pollCompletion = () => {
    http
      .getJSON(
        `/api/scanner-intake-status?scanner=${encodeURIComponent(scannerKey)}`,
      )
      .then((data) => {
        const intake = readScannerIntakeStatus(data);
        if (intake.dispatchedAt !== null) latestIntakeAt = intake.dispatchedAt;
        if (intake.ok && intake.terminal) {
          // run_scanner() dispatches processing on a background thread. Until
          // a newer persisted intake appears, this is still the previous
          // completed scan and must not reopen its terminal.
          if (
            ignoreIntakesThrough !== null &&
            (intake.dispatchedAt === null ||
              intake.dispatchedAt <= ignoreIntakesThrough)
          ) {
            return;
          }
          ignoreIntakesThrough = null;
          AM.showMazdaTerminalForScanner(
            mazdaTerminalContainer,
            intake.conversationId,
          );
          // The iframe may still be displaying the report it loaded before a
          // newer scan completed. Verify what the operator can actually see,
          // not whichever intake happens to be newest by the time this poll
          // fires.
          const displayedExpenseId = Number(
            iframe?.contentDocument?.querySelector("tr[data-expense-id]")
              ?.dataset.expenseId,
          );
          AM.showArchiveVerificationForScanner(
            scannerKey,
            archiveContainer,
            displayedExpenseId || null,
          );
          stopCompletionPolling();
        }
      })
      .catch(() => {
        // Ignore errors and keep polling.
      });
  };
  const startCompletionPolling = () => {
    stopCompletionPolling();
    completionPoll = setIntervalFn(pollCompletion, COMPLETION_POLL_MS);
    pollCompletion();
  };

  const controls = mountScannerReportControls({
    doc,
    section,
    iframe,
    scanner: scannerKey,
    fetchImpl: scannerFetch,
    onScanReady: () => {
      ignoreIntakesThrough = latestIntakeAt ?? 0;
      AM.clearScannerCompletionViews(mazdaTerminalContainer, archiveContainer);
      RF.loadScannerReportInto(iframe, scannerKey);
      startCompletionPolling();
    },
  });
  RF.loadScannerReportInto(iframe, scannerKey);

  const detailContainer = doc.querySelector(
    `#${tab.dataset.target}-mazda-detail`,
  );
  if (detailContainer) {
    AM.renderMazdaThoughtsInto(detailContainer, scannerKey);
  }
  startCompletionPolling();
  return { controls, startCompletionPolling, stopCompletionPolling };
}
