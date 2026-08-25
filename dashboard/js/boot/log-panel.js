// log-panel.js — the two pieces the Server Management and SSH Connections
// detail panels share: a live log filter and an LED status reporter.
//
// Both panels render the same shape (note / LED row / filter input / action
// button / console host) and both drive a *LogController that reports health
// through onStatus. Only the classes each panel understands differ.

// Hide non-matching log lines, and re-apply as new rows stream in.
export function attachLogFilter(filterEl, innerEl) {
  const applyFilter = () => {
    const q = filterEl.value.trim().toLowerCase();
    innerEl.querySelectorAll(".msi-entry").forEach((el) => {
      el.style.display =
        !q || el.textContent.toLowerCase().includes(q) ? "" : "none";
    });
  };
  filterEl.addEventListener("input", applyFilter);
  new MutationObserver(applyFilter).observe(innerEl, { childList: true });
  return applyFilter;
}

/**
 * Drive the detail-panel LED from a controller's onStatus payload.
 * @param {Element} statusEl  the .srv-status row (carries the colour class)
 * @param {Element} statusText  the label inside it
 * @param {string[]} kinds  status kinds this panel renders as their own class.
 *   Server logs report up/starting/concern/down, SSH only up/down.
 * @param {string} fallback  class for any other kind — "" leaves the LED
 *   neutral (server panel), "starting" shows it as still checking (SSH panel).
 */
export function createLedReporter(statusEl, statusText, kinds, fallback = "") {
  return (st) => {
    const cls = kinds.includes(st.kind) ? st.kind : fallback;
    statusEl.className = cls ? `srv-status ${cls}` : "srv-status";
    statusText.textContent = st.label + st.text;
  };
}
