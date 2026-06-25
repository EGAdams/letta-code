import { DocumentPipelineView } from "../abstract/document-pipeline-view.interface.js";
import { TextUtils } from "../abstract/text-utils.js";
import { describePipelineStage } from "./document-pipeline-controller.js";

/**
 * DomDocumentPipelineView — concrete DocumentPipelineView that renders the
 * pipeline result into a DOM container inside a scanner dialog. The only
 * browser-dependent piece; all formatting decisions live in the pure
 * describePipelineStage() so this class stays a thin DOM binder.
 */
export class DomDocumentPipelineView extends DocumentPipelineView {
  /** @param {{innerHTML:string, classList:DOMTokenList}} container */
  constructor(container) {
    super();
    if (!container) {
      throw new Error("DomDocumentPipelineView requires a container element");
    }
    this._el = container;
  }

  clear() {
    this._el.classList.add("hidden");
    this._el.innerHTML = "";
  }

  setBusy() {
    this._el.classList.remove("hidden");
    this._el.innerHTML =
      '<div class="pipeline-title">Processing document…</div>' +
      '<div class="pipeline-busy">Running classify → parse ' +
      "(cheapest reliable tool first)…</div>";
  }

  renderError(message) {
    this._el.classList.remove("hidden");
    this._el.innerHTML =
      '<div class="pipeline-title">Document pipeline</div>' +
      `<div class="pipeline-error">Pipeline failed: ${TextUtils.esc(
        message || "unknown error",
      )}</div>`;
  }

  render(result) {
    this._el.classList.remove("hidden");
    const stages = Array.isArray(result?.stages) ? result.stages : [];
    const rows = stages
      .map((s) => {
        const d = describePipelineStage(s);
        return (
          `<li class="pipeline-stage stage-${TextUtils.esc(d.status)}">` +
          `<span class="pipeline-stage-name">${TextUtils.esc(d.name)}</span>` +
          `<span class="pipeline-stage-status">${TextUtils.esc(d.status)}</span>` +
          `<span class="pipeline-stage-summary">${TextUtils.esc(d.summary)}</span>` +
          "</li>"
        );
      })
      .join("");
    const note = result?.mazda_dispatched
      ? "Mazda is processing investigate → categorize → store in the background."
      : "Mazda was not dispatched (no scanned image found).";
    const err = result?.error
      ? `<div class="pipeline-error">${TextUtils.esc(result.error)}</div>`
      : "";
    this._el.innerHTML =
      '<div class="pipeline-title">Document pipeline</div>' +
      err +
      `<ul class="pipeline-stages">${rows}</ul>` +
      `<div class="pipeline-note">${TextUtils.esc(note)}</div>`;
  }
}
