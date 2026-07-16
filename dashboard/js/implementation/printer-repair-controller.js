/** Build the fixed request used by both scanner-dialog Fix Printer buttons. */
export function buildPrinterRepairRequest() {
  return { url: "/api/fix-printer", body: {} };
}

/**
 * Command for repairing the HP DeskJet Windows queue. Transport is injected so
 * the scanner UI remains a thin binding and the behavior is unit-testable.
 */
export class PrinterRepairController {
  constructor({ http, url = "/api/fix-printer" } = {}) {
    if (!http || typeof http.postJSON !== "function") {
      throw new Error("PrinterRepairController requires { http }");
    }
    this._http = http;
    this._url = url;
    this._inFlight = false;
  }

  async repair() {
    if (this._inFlight) {
      return { ok: false, text: "Printer repair is already running." };
    }
    this._inFlight = true;
    try {
      const { body } = buildPrinterRepairRequest();
      const result = await this._http.postJSON(this._url, body);
      return {
        ...result,
        ok: result.ok !== false,
        text: result.text || "",
      };
    } catch (error) {
      return { ok: false, text: error.message };
    } finally {
      this._inFlight = false;
    }
  }
}
