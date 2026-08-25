// scanners/index.js — ROL Finance > Scanners: the two scanner dialogs, the
// queued-statement review dialog, the vendor-review panel and the Process PDF
// form.
//
// Each `.scanner-dialog` reuses the startup-panel look inline (no overlay).
// Start Scan kicks off the backend scan AND a yellow progress fill; when the
// scan returns the bar snaps green + "Scan Finished" and the image opens
// automatically.

import {
  DashboardStatementReviewActions,
  DocumentPipelineController,
  DomDocumentPipelineView,
  DomVendorReviewView,
  StatementReviewDialog,
  VendorReviewController,
} from "../../implementation/index.js";
import { wireScannerDialog } from "./scanner-dialog.js";

// Scanners whose tab keeps polling for recovery after a busy/offline result.
// Empty by design: background polling must never start a transfer, so only an
// explicitly monitored scanner may re-probe on a timer.
const MONITORED_SCANNERS = new Set();

/* A statement Mazda could not store waits in bank_statements/_needs_review/.
   The dialog polls for those and asks EG for the one missing piece — a
   workbook row, or an unreadable amount — then re-runs the store. It is built
   here (not per-dialog) so it survives navigation between tabs. */
function createStatementReviewDialog({ doc, http, AM, viewNav }) {
  const dialog = new StatementReviewDialog({
    http,
    actions: new DashboardStatementReviewActions({
      listAgents: async () => {
        if (!AM.agents) AM.agents = await http.getJSON("/api/agents");
        return AM.agents || [];
      },
      openAgentInput: (agentId) => AM.openById(agentId, "input-options"),
    }),
    // Only actually block the page while the Scanner tab (or one of its
    // sub-views) is open — a queued review shouldn't stop the user from using
    // Agents, Server Management, or any other unrelated tab.
    isRelevantView: () =>
      (doc.querySelector(".view.active")?.id || "").startsWith("scanners"),
  });
  viewNav.setStatementReviewDialog(dialog);
  return dialog;
}

/* Needs Vendor Review — ROL Finance > Scanners > Needs Vendor Review.
   Lists receipts saved with expense_status=NEEDS_VENDOR_KEY (vendor/category
   couldn't be auto-resolved, so the image + a placeholder row were saved
   anyway — see save_receipt_pending_vendor_review() in rol_finances) and lets
   a human finish the save by picking an existing vendor_key. */
function createVendorReview({ doc, http }) {
  const panelEl = doc.getElementById("vendor-review-panel");
  if (!panelEl) return null;
  let controller = null;
  controller = new VendorReviewController({
    http,
    view: new DomVendorReviewView(panelEl, {
      getVendorKeys: () => controller.listVendorKeys(),
      onPickVendor: (expenseId, vendorKey) =>
        controller.pickVendor(expenseId, vendorKey),
    }),
  });
  return controller;
}

/* Process PDF — ROL Finance > Scanners > Process PDF.
   Runs the intake pipeline (classify → parse inline, Mazda dispatched for
   investigate → categorize → store) on an existing PDF file on the server. */
function setupPdfProcessor({ doc, http }) {
  const section = doc.getElementById("scanners-pdf");
  if (!section) return;
  const pathInput = section.querySelector("#pdf-file-path");
  const labelInput = section.querySelector("#pdf-doc-label");
  const processBtn = section.querySelector(".pdf-process-btn");
  const resultBox = section.querySelector(".scanner-result");
  if (!pathInput || !processBtn || !resultBox) return;

  const pipeline = new DocumentPipelineController({
    http,
    view: new DomDocumentPipelineView(resultBox),
  });

  processBtn.addEventListener("click", () => {
    const filePath = pathInput.value.trim();
    if (!filePath) return;
    const label = labelInput ? labelInput.value.trim() : "";
    void pipeline.processFile(filePath, label || undefined);
  });
}

export function setupScanners({
  doc = document,
  win = window,
  http,
  printerRepair,
  AM,
  viewNav,
}) {
  createStatementReviewDialog({ doc, http, AM, viewNav }).start();

  const controllers = {};
  doc.querySelectorAll(".scanner-dialog").forEach((dialog) => {
    controllers[dialog.dataset.scanner] = wireScannerDialog({
      dialog,
      http,
      printerRepair,
      monitored: MONITORED_SCANNERS.has(dialog.dataset.scanner),
      doc,
      win,
    });
  });

  setupPdfProcessor({ doc, http });

  return {
    controllers,
    vendorReview: createVendorReview({ doc, http }),
    stopAllMonitors() {
      for (const c of Object.values(controllers)) c.stopMonitor();
    },
  };
}
