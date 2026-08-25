// printer-repair-panel.js — the "Fix Printer" button inside a scanner dialog.
//
// The printer is a different device from the scanner; it shares the dialog only
// because they are the same physical HP DeskJet. Every Fix Printer button on
// the page is disabled while a repair runs — there is one queue, not one per
// dialog.

import { TextUtils } from "../../abstract/text-utils.js";

export function createPrinterRepairPanel({
  printerRepair,
  resultBox,
  onRepaired,
  doc = document,
}) {
  return async function runPrinterRepair() {
    const repairButtons = doc.querySelectorAll(".scanner-fix-printer");
    repairButtons.forEach((button) => {
      button.disabled = true;
    });
    resultBox.classList.remove("hidden");
    resultBox.innerHTML =
      '<div class="pipeline-title">Printer repair</div>' +
      '<div class="pipeline-busy">Checking the HP DeskJet and repairing its Windows queue…</div>';
    const result = await printerRepair.repair();
    const message = TextUtils.esc(
      result.text || (result.ok ? "Printer fixed." : "Printer repair failed."),
    );
    resultBox.innerHTML =
      '<div class="pipeline-title">Printer repair</div>' +
      `<div class="${result.ok ? "printer-repair-success" : "pipeline-error"}">${message}</div>`;
    repairButtons.forEach((button) => {
      button.disabled = false;
    });
    // The repair may have cleared a blocker (door/jam/offline) — re-read health.
    onRepaired();
  };
}
