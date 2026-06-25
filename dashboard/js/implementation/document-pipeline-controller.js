/**
 * DocumentPipelineController — Command for the "Process Document" action.
 *
 * It POSTs a scanned document to /api/process-document and routes the result to
 * a DocumentPipelineView. The dashboard auto-fires process() the instant a scan
 * finishes (see setupScanners → setReady), so the inline pipeline result appears
 * "at exactly the same time the scanner finishes". No polling: the backend runs
 * the cheap deterministic facade (classify + parse) synchronously for the inline
 * result, then dispatches Mazda fire-and-forget for the deeper stages.
 *
 * It programs to two interfaces — HttpClient (transport) and
 * DocumentPipelineView (presentation) — both injected, so it is fully
 * unit-testable with a fake http + a recording view.
 */

/**
 * Build the request for the Process Document action. Pure, so it is tested
 * directly (mirrors buildServerActionRequest).
 * @param {string} scanner  scanner key (e.g. "window" / "freezer")
 * @returns {{url:string, body:{scanner:string}}}
 */
export function buildProcessDocumentRequest(scanner) {
  if (!scanner) {
    throw new Error("buildProcessDocumentRequest requires { scanner }");
  }
  return { url: "/api/process-document", body: { scanner } };
}

/** Compact, defensive one-line summary of the facade's `parsed` payload. */
export function summarizeParsed(parsed) {
  if (!parsed || typeof parsed !== "object") return "";
  const bits = [];
  const vendor = parsed.vendor || parsed.vendor_name || parsed.merchant;
  if (vendor) bits.push(`vendor=${vendor}`);
  const total = parsed.total ?? parsed.amount ?? parsed.grand_total;
  if (total != null && total !== "") bits.push(`total=${total}`);
  const date = parsed.date || parsed.transaction_date || parsed.statement_date;
  if (date) bits.push(`date=${date}`);
  const items = parsed.line_items || parsed.items || parsed.transactions;
  if (Array.isArray(items)) bits.push(`${items.length} items`);
  return bits.length ? bits.join(" · ") : "structured data extracted";
}

/**
 * Pure presenter: turn one raw stage object into { name, status, summary } for
 * display. Kept here (not in the DOM view) so the formatting logic is unit
 * tested without a DOM.
 */
export function describePipelineStage(stage) {
  const name = stage?.name || "stage";
  const status = stage?.status || "pending";
  let summary = "";
  if (name === "classify" && status === "done") {
    const bits = [];
    if (stage.doc_kind) bits.push(stage.doc_kind);
    if (stage.vendor) bits.push(`vendor=${stage.vendor}`);
    if (typeof stage.confidence === "number") {
      bits.push(`${Math.round(stage.confidence * 100)}%`);
    }
    if (stage.method) bits.push(stage.method);
    if (stage.recommended_action) bits.push(`→ ${stage.recommended_action}`);
    summary = bits.join(" · ");
  } else if (name === "parse") {
    if (status === "done") summary = summarizeParsed(stage.parsed);
    else if (status === "skipped") summary = "no structured fields";
  } else if (status === "delegated") {
    summary = "delegated to Mazda";
  } else if (status === "pending") {
    summary = "pending";
  }
  return { name, status, summary };
}

export class DocumentPipelineController {
  /**
   * @param {{ http: import("../abstract/http-client.interface.js").HttpClient,
   *           view: import("../abstract/document-pipeline-view.interface.js").DocumentPipelineView,
   *           url?: string }} deps
   */
  constructor({ http, view, url = "/api/process-document" } = {}) {
    if (!http || typeof http.postJSON !== "function") {
      throw new Error("DocumentPipelineController requires { http }");
    }
    if (!view || typeof view.render !== "function") {
      throw new Error("DocumentPipelineController requires { view }");
    }
    this._http = http;
    this._view = view;
    this._url = url;
    this._inFlight = false;
  }

  /**
   * Process one scanner's latest scanned document. Drives the view through
   * setBusy → render | renderError. Never throws — a transport failure becomes
   * {ok:false, error} both in the return value and via view.renderError.
   * Concurrent calls are ignored while one is in flight.
   * @param {string} scanner
   * @returns {Promise<object>}
   */
  async process(scanner) {
    if (this._inFlight) return { ok: false, error: "already processing" };
    const { body } = buildProcessDocumentRequest(scanner);
    this._inFlight = true;
    this._view.setBusy();
    try {
      const result = await this._http.postJSON(this._url, body);
      this._view.render(result);
      return result;
    } catch (e) {
      this._view.renderError(e.message);
      return { ok: false, error: e.message };
    } finally {
      this._inFlight = false;
    }
  }
}
