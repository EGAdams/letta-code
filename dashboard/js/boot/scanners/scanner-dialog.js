// scanner-dialog.js — one `.scanner-dialog` panel: the Start Scan workflow,
// the health LEDs, and the intake pipeline. The bar and status label belong to
// the progress panel, the preview modal to the image viewer, and the
// observation-only recovery polling to the status monitor.
//
// Raw fetch, not the shared HttpClient, on purpose: a real flatbed scan runs
// past FetchHttpClient's 30s abort budget, and these endpoints always answer
// HTTP 200 with any failure in the body.

import { TextUtils } from "../../abstract/text-utils.js";
import {
  DocumentPipelineController,
  DomDocumentPipelineView,
  ScannerDiagnosticsController,
} from "../../implementation/index.js";
import { createPrinterRepairPanel } from "./printer-repair-panel.js";
import { createScannerImageViewer } from "./scanner-image-viewer.js";
import { createScannerProgressPanel } from "./scanner-progress-panel.js";
import { createScannerStatusMonitor } from "./scanner-status-monitor.js";

const BUSY_STATUSES = ["intake_busy", "busy", "offline"];

export function wireScannerDialog({
  dialog,
  http,
  printerRepair,
  monitored,
  doc = document,
  win = window,
}) {
  const scanner = dialog.dataset.scanner;
  const startBtn = dialog.querySelector(".scanner-start");
  const showBtn = dialog.querySelector(".scanner-show");
  const fixPrinterBtn = dialog.querySelector(".scanner-fix-printer");
  const clearVerificationBtn = dialog.querySelector(
    ".scanner-clear-verification",
  );
  const processBtn = dialog.querySelector(".scanner-process");
  const resultBox = dialog.querySelector(".scanner-result");
  const diagLeds = dialog.querySelector(".scanner-diag-leds");
  const diagRefreshBtn = dialog.querySelector(".scanner-diag-refresh");

  const progress = createScannerProgressPanel({
    panel: dialog.querySelector(".scanner-panel"),
    bar: dialog.querySelector(".scanner-bar"),
    state: dialog.querySelector(".scanner-state"),
  });
  const image = createScannerImageViewer({
    imageBox: dialog.querySelector(".scanner-image-box"),
    img: dialog.querySelector(".scanner-image"),
    closeBtn: dialog.querySelector(".scanner-image-close"),
    doc,
    win,
  });

  // Scanner-workflow health LEDs (WSL bridge / imaging service / driver /
  // online / stuck scans / printer device). Read-only probe — never scans.
  const diagnostics =
    diagLeds && diagRefreshBtn
      ? new ScannerDiagnosticsController({ http, scanner, esc: TextUtils.esc })
      : null;
  const refreshDiagnostics = () => {
    if (diagnostics && diagLeds) void diagnostics.refresh(diagLeds);
  };

  let scanning = false;
  let currentStatus = "idle";

  // Process Document — the intake pipeline (classify → parse inline, then
  // investigate → categorize → store dispatched to Mazda). Built from the GoF
  // controller + DOM view so the wiring here stays a thin binding.
  const pipelineView =
    processBtn && resultBox ? new DomDocumentPipelineView(resultBox) : null;
  const pipeline = pipelineView
    ? new DocumentPipelineController({ http, view: pipelineView })
    : null;
  // Fire-and-forget: the controller drives the inline view itself; no polling,
  // and a scan never waits on the pipeline.
  const runPipeline = () => {
    if (pipeline) void pipeline.process(scanner);
  };

  // Fix Printer shares this dialog's result box but is otherwise its own
  // concern (see printer-repair-panel.js).
  const runPrinterRepair =
    fixPrinterBtn && resultBox
      ? createPrinterRepairPanel({
          printerRepair,
          resultBox,
          onRepaired: refreshDiagnostics,
          doc,
        })
      : null;

  const setReady = (imageUrl) => {
    progress.setComplete();
    if (imageUrl) {
      showBtn.disabled = false;
      image.show(imageUrl);
    }
    // Auto-run the intake pipeline the instant the scan finishes and the image
    // is ready for the first step — exactly the moment the document is ready.
    if (processBtn) processBtn.disabled = false;
    runPipeline();
  };

  // Map a /api/scanner-status or /api/scanner-scan result onto the dialog.
  const applyResult = (data) => {
    const status = data.status || (data.ok ? "ready" : "error");
    currentStatus = status;
    if (clearVerificationBtn)
      clearVerificationBtn.disabled = status !== "intake_busy";
    startBtn.disabled = BUSY_STATUSES.includes(status);
    if (status === "ready") {
      setReady(data.image_url);
    } else if (status === "idle") {
      progress.setIdle();
    } else if (status === "intake_busy") {
      progress.setBusy(data.error || "Previous scan is still being verified.");
    } else if (status === "busy" || status === "offline") {
      progress.setBusy("Restart the Scanner Please");
      // A busy/offline scanner is exactly when the health LEDs earn their
      // keep — refresh so the user sees WHICH failure point to reset.
      refreshDiagnostics();
    } else {
      progress.setFailed(`Scan failed: ${data.error || "unknown error"}`);
      refreshDiagnostics();
    }
    return status;
  };

  const clearVerificationLock = async () => {
    if (
      !clearVerificationBtn ||
      !win.confirm(
        "Clear this scanner's stuck verification lock? This does not delete the scan or change any financial records.",
      )
    )
      return;
    clearVerificationBtn.disabled = true;
    try {
      const res = await fetch("/api/scanner-clear-verification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scanner }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok)
        throw new Error(data.error || `request failed (${res.status})`);
      progress.setIdle();
      currentStatus = "idle";
      startBtn.disabled = false;
      refreshDiagnostics();
    } catch (err) {
      progress.setFailed(`Could not clear verification lock: ${err.message}`);
      clearVerificationBtn.disabled = false;
    }
  };

  // Observation-only recovery polling (see scanner-status-monitor.js).
  const monitor = createScannerStatusMonitor({
    scanner,
    enabled: monitored,
    progress,
    applyResult,
  });

  // "Refresh Health" must refresh both sets of evidence: the LED diagnostics
  // and the main blinking status bar. Previously a completed Trainer left the
  // browser blinking red forever even though the server had returned to idle.
  const refreshRuntimeStatus = async () => {
    try {
      applyResult(await monitor.readStatus());
    } catch (err) {
      progress.setFailed(`Status refresh failed: ${err.message}`);
    }
  };

  // One-shot manual scan with the yellow fill (used by the Start button).
  const runManualScan = async () => {
    if (scanning) return;
    scanning = true;
    monitor.stop();
    startBtn.disabled = true;
    showBtn.disabled = true;
    if (processBtn) processBtn.disabled = true;
    if (pipelineView) pipelineView.clear();
    image.hide();
    progress.setProbing("Scanning…");
    // A real flatbed scan takes ~30s; fill over that until the actual result
    // snaps the bar green. The Window Scanner fills ~30% faster (~23s) and runs
    // all the way to 100% yellow, then sits there until the scan-complete event
    // turns it green.
    const isWindow = scanner === "window";
    progress.runProgress(4, isWindow ? 96 : 88, isWindow ? 23000 : 30000);
    try {
      const res = await fetch("/api/scanner-scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scanner }),
      });
      const status = applyResult(await res.json());
      // A monitored scanner that came back busy/offline: resume polling so it
      // auto-recovers once power-cycled.
      if (monitored && (status === "busy" || status === "offline")) {
        monitor.start();
      }
    } catch (err) {
      progress.setFailed(`Scan failed: ${err.message}`);
    } finally {
      scanning = false;
      startBtn.disabled = BUSY_STATUSES.includes(currentStatus);
    }
  };

  showBtn.addEventListener("click", () => image.show());
  startBtn.addEventListener("click", runManualScan);
  if (clearVerificationBtn)
    clearVerificationBtn.addEventListener("click", clearVerificationLock);
  if (fixPrinterBtn && runPrinterRepair)
    fixPrinterBtn.addEventListener("click", runPrinterRepair);
  if (processBtn) processBtn.addEventListener("click", runPipeline);
  if (diagRefreshBtn) {
    diagRefreshBtn.addEventListener("click", () => {
      refreshDiagnostics();
      void refreshRuntimeStatus();
    });
  }

  return {
    startMonitor: monitor.start,
    stopMonitor: monitor.stop,
    refreshDiagnostics,
  };
}
