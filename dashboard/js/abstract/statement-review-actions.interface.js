import { abstractMethod } from "./not-implemented.js";

/**
 * Port used by the statement-review dialog for actions outside the modal.
 *
 * The dialog must not know how agents are discovered, how Input Options is
 * rendered, or how a browser opens a document. Concrete dashboard navigation
 * and browser APIs belong in an implementation subclass wired by the boot
 * composition root.
 */
export class StatementReviewActions {
  /** Open Mazda's input surface with the complete review prompt. */
  async askMazda(_prompt, _review) {
    abstractMethod("askMazda");
  }

  /** Open the document belonging to the pending review. */
  showDocument(_documentUrl, _review) {
    abstractMethod("showDocument");
  }
}
