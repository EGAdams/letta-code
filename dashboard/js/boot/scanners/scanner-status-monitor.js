// scanner-status-monitor.js — the recovery poller behind a scanner dialog.
//
// Strictly observation-only: it GETs /api/scanner-status on a timer so a
// scanner that came back busy/offline turns green by itself once it is
// power-cycled. It must never start a transfer — that is Start Scan's job
// alone — so nothing here POSTs.
//
// Raw fetch, not the shared HttpClient, on purpose: the probe routinely runs
// past FetchHttpClient's 30s abort budget, and the endpoint always answers
// HTTP 200 with any failure in the body.

const POLL_MS = 15000;

export function createScannerStatusMonitor({
  scanner,
  enabled,
  progress,
  applyResult,
}) {
  let pollTimer = null;
  let active = false;
  let inFlight = false;

  const readStatus = async () => {
    const res = await fetch(`/api/scanner-status?scanner=${scanner}`);
    return res.json();
  };

  const stop = () => {
    active = false;
    if (pollTimer) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
    progress.stopProgress();
  };

  const pollOnce = async () => {
    if (!active || inFlight) return;
    inFlight = true;
    // Animate a yellow fill while the probe runs so its timing is visible.
    // applyResult()/stop() end it when the probe returns.
    progress.setProbing("Checking scanner…");
    progress.runProgress(4, 88, 30000);
    try {
      const data = await readStatus();
      inFlight = false;
      if (!active) {
        progress.stopProgress();
        return;
      }
      // On recovery the status probe's transfer succeeds -> stop polling.
      if (applyResult(data) === "ready") {
        stop();
        return;
      }
    } catch {
      inFlight = false;
      if (active) progress.setBusy("Restart the Scanner Please");
    }
    if (active) pollTimer = setTimeout(pollOnce, POLL_MS);
  };

  return {
    readStatus,
    stop,
    start() {
      if (!enabled || active) return;
      active = true;
      void pollOnce();
    },
  };
}
