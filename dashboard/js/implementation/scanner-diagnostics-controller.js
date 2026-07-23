/**
 * ScannerDiagnosticsController — fetches and renders the scanner-workflow health
 * LEDs for one scanner dialog. The server (build_scanner_diagnostics) does all
 * the mapping and hands back fully-formed checks; this class only turns those
 * into DOM rows. Transport + escaper are injected so the pure formatting
 * (stateClass / rowHtml / render) is unit-testable in Node with no browser.
 */
export class ScannerDiagnosticsController {
  /** @param {{http:object, scanner:string, esc:(s:string)=>string}} deps */
  constructor({ http, scanner, esc } = {}) {
    if (!http || typeof http.getJSON !== "function") {
      throw new Error("ScannerDiagnosticsController requires { http }");
    }
    if (typeof esc !== "function") {
      throw new Error("ScannerDiagnosticsController requires { esc }");
    }
    this._http = http;
    this._scanner = scanner;
    this._esc = esc;
    this._inFlight = false;
  }

  /** Map a check state onto its LED CSS class. Unknown/anything-else -> grey. */
  static stateClass(state) {
    switch (state) {
      case "ok":
        return "diag-ok";
      case "warn":
        return "diag-warn";
      case "bad":
        return "diag-bad";
      default:
        return "diag-unknown";
    }
  }

  /** HTML for one LED row. `esc` injected so this stays pure/testable. */
  static rowHtml(check, esc) {
    const cls = ScannerDiagnosticsController.stateClass(check?.state);
    const label = esc(check?.label || "");
    const detail = esc(check?.detail || "");
    return (
      `<div class="scanner-diag-row ${cls}">` +
      '<span class="scanner-diag-led" aria-hidden="true"></span>' +
      '<span class="scanner-diag-text">' +
      `<span class="scanner-diag-label">${label}</span>` +
      `<span class="scanner-diag-detail">${detail}</span>` +
      "</span></div>"
    );
  }

  /** Render a diagnostics payload (or error) into `container`. */
  render(container, data) {
    const esc = this._esc;
    if (data?.error) {
      container.innerHTML =
        '<div class="scanner-diag-row diag-bad">' +
        '<span class="scanner-diag-led" aria-hidden="true"></span>' +
        '<span class="scanner-diag-text">' +
        `<span class="scanner-diag-detail">${esc(data.error)}</span>` +
        "</span></div>";
      return;
    }
    const checks = data?.checks || [];
    if (!checks.length) {
      container.innerHTML =
        '<div class="scanner-diag-empty">No diagnostics available.</div>';
      return;
    }
    container.innerHTML = checks
      .map((c) => ScannerDiagnosticsController.rowHtml(c, esc))
      .join("");
  }

  /** Fetch the latest health and render it. Coalesces concurrent calls. */
  async refresh(container) {
    if (this._inFlight) return;
    this._inFlight = true;
    container.classList.add("scanner-diag-busy");
    try {
      const data = await this._http.getJSON(
        `/api/scanner-diagnostics?scanner=${encodeURIComponent(this._scanner)}`,
        // The probe launches Windows PowerShell and can wait on an 8s WIA job,
        // so give it far more headroom than the dashboard's 30s default abort.
        { timeout: 40000 },
      );
      this.render(container, data);
    } catch (error) {
      container.innerHTML =
        '<div class="scanner-diag-row diag-unknown">' +
        '<span class="scanner-diag-led" aria-hidden="true"></span>' +
        '<span class="scanner-diag-text">' +
        `<span class="scanner-diag-detail">${this._esc(
          `Couldn't reach the diagnostics endpoint: ${error.message || error}`,
        )}</span>` +
        "</span></div>";
    } finally {
      this._inFlight = false;
      container.classList.remove("scanner-diag-busy");
    }
  }
}
