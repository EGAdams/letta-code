// scanner-report-controls.js — the compact Start Scan panel shown above each
// Last Window / Last Freezer report. The report itself may be synthetic or an
// archived report.html, so this control belongs in the parent dashboard shell.

import { createScannerProgressPanel } from "./scanner-progress-panel.js";

const progressTiming = (scanner) =>
  scanner === "window"
    ? { span: 96, durationMs: 23_000 }
    : { span: 88, durationMs: 30_000 };

const makeElement = (doc, tag, className, text = "") => {
  const element = doc.createElement(tag);
  element.className = className;
  element.textContent = text;
  return element;
};

export function mountScannerReportControls({
  doc,
  section,
  iframe,
  scanner,
  onScanReady,
  fetchImpl = globalThis.fetch,
  progressFactory = createScannerProgressPanel,
}) {
  const mounted = section?.querySelector(".scanner-report-controls");
  if (mounted) return { element: mounted, runScan: null };
  if (!doc || !section || !iframe || !scanner) return null;

  const panel = makeElement(
    doc,
    "div",
    "scanner-report-controls scanner-panel",
  );
  panel.dataset.scanner = scanner;

  const startButton = makeElement(
    doc,
    "button",
    "scanner-report-start",
    "Start Scan",
  );
  startButton.type = "button";

  const progressWrap = makeElement(doc, "div", "scanner-report-progress");
  const state = makeElement(
    doc,
    "div",
    "scanner-state",
    "Idle — ready to scan.",
  );
  state.ariaLive = "polite";
  const track = makeElement(doc, "div", "startup-progress-shell");
  track.ariaHidden = "true";
  const bar = makeElement(doc, "div", "startup-progress-bar scanner-bar");
  track.appendChild(bar);
  progressWrap.append(state, track);
  panel.append(startButton, progressWrap);
  section.insertBefore(panel, iframe);

  const progress = progressFactory({ panel, bar, state });
  let scanning = false;

  const runScan = async () => {
    if (scanning) return;
    scanning = true;
    startButton.disabled = true;
    progress.setProbing("Scanning…");
    const timing = progressTiming(scanner);
    progress.runProgress(4, timing.span, timing.durationMs);

    try {
      const response = await fetchImpl("/api/scanner-scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scanner }),
      });
      const data = await response.json();
      const status = data.status || (data.ok ? "ready" : "error");
      if (status === "ready") {
        progress.setComplete();
        onScanReady?.();
      } else if (status === "intake_busy") {
        progress.setBusy(
          data.error || "Previous scan is still being verified.",
        );
      } else if (status === "busy" || status === "offline") {
        progress.setBusy("Restart the Scanner Please");
      } else {
        progress.setFailed(`Scan failed: ${data.error || "unknown error"}`);
      }
    } catch (error) {
      progress.setFailed(`Scan failed: ${error.message}`);
    } finally {
      scanning = false;
      startButton.disabled = false;
    }
  };

  startButton.addEventListener("click", () => void runScan());
  return { element: panel, runScan };
}
