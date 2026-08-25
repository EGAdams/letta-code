// scanner-progress-panel.js — the scanner dialog's progress bar and state
// label: four terminal states (idle / busy / complete / failed) plus the timed
// yellow fill that runs while a scan or a status probe is in flight.
//
// Pure display: it owns the bar, the label and the progress timer, and knows
// nothing about scanning, HTTP, or the image modal.

export function createScannerProgressPanel({ panel, bar, state }) {
  let progressTimer = null;

  const setBar = (pct) => {
    bar.style.width = `${pct}%`;
  };
  const clearBlink = () => state.classList.remove("scanner-blink");
  const stopProgress = () => {
    if (progressTimer) {
      clearInterval(progressTimer);
      progressTimer = null;
    }
  };

  return {
    stopProgress,
    // Animate the bar from `from`% toward `from + span`% over `overMs`.
    runProgress(from, span, overMs) {
      const startedAt = Date.now();
      setBar(from);
      stopProgress();
      progressTimer = setInterval(() => {
        const t = Math.min((Date.now() - startedAt) / overMs, 1);
        setBar(from + t * span);
      }, 150);
    },
    // Probing: clear every terminal class so the fill reads as "in flight".
    setProbing(msg) {
      clearBlink();
      panel.classList.remove("scan-busy", "scan-complete", "scan-error");
      state.textContent = msg;
    },
    setBusy(msg) {
      stopProgress();
      setBar(100);
      panel.classList.remove("scan-complete", "scan-error");
      panel.classList.add("scan-busy");
      state.textContent = msg;
      state.classList.add("scanner-blink");
    },
    setComplete() {
      stopProgress();
      clearBlink();
      setBar(100);
      panel.classList.remove("scan-busy", "scan-error");
      panel.classList.add("scan-complete");
      state.textContent = "Scan Finished";
    },
    setFailed(msg) {
      stopProgress();
      clearBlink();
      setBar(100);
      panel.classList.remove("scan-busy", "scan-complete");
      panel.classList.add("scan-error");
      state.textContent = msg;
    },
    setIdle() {
      stopProgress();
      clearBlink();
      setBar(0);
      panel.classList.remove("scan-busy", "scan-complete", "scan-error");
      state.textContent = "Idle — ready to scan.";
    },
  };
}
