import { abstractMethod } from "./not-implemented.js";

/**
 * DocumentPipelineView — the output Strategy for the "Process Document" action.
 *
 * The DocumentPipelineController (Command) knows WHEN to process a scanned
 * document and HOW to talk to the backend, but nothing about presentation. It
 * depends only on this interface, so the controller is unit-testable with a
 * recording fake view while the real DomDocumentPipelineView binds to the page.
 *
 * Lifecycle a controller drives: setBusy() → render(result) | renderError(msg).
 */
export class DocumentPipelineView {
  /** Show that processing has started (the facade is running). */
  setBusy() {
    abstractMethod("setBusy");
  }

  /**
   * Render a completed pipeline result.
   * @param {{ok:boolean, error?:string, mazda_dispatched?:boolean,
   *           stages?:Array<object>}} _result
   */
  render(_result) {
    abstractMethod("render");
  }

  /** Render a transport/processing failure message. */
  renderError(_message) {
    abstractMethod("renderError");
  }

  /** Clear / hide the inline result. */
  clear() {
    abstractMethod("clear");
  }
}
