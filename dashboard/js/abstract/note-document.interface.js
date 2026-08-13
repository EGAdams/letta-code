import { abstractMethod } from "./not-implemented.js";

/**
 * NoteDocument — the text surface the note lives on.
 *
 * This is the "Document Editing Interface" seam: whoever edits the note goes
 * through `getText`/`setText` and never learns whether the instruction came
 * from speech, the keyboard, or a future interface — and never learns that the
 * surface happens to be a `<textarea>`.
 *
 * A concrete surface also owns its own presentation (`element`), so a read-only
 * document display and an editable input box are two interchangeable
 * implementations rather than a flag threaded through a renderer.
 *
 * @typedef {object} NoteDocumentContract
 * @property {() => string} getText
 * @property {(text: string) => void} setText
 * @property {(text: string) => void} appendText
 * @property {object} element  the DOM node to place in the page
 */
export class NoteDocument {
  /** @returns {string} the note's current full text */
  getText() {
    abstractMethod("getText");
  }

  /** Replace the note's full text. */
  setText(_text) {
    abstractMethod("setText");
  }

  /** Add text to the end of the note, merging any repeated overlap. */
  appendText(_text) {
    abstractMethod("appendText");
  }

  /** The DOM node representing this surface. */
  get element() {
    return abstractMethod("element");
  }

  /**
   * Whether the user can type into this surface directly.
   *
   * Callers use it to decide whether clearing the text is a harmless input
   * reset or the deletion of a document. Defaults to the safe answer.
   */
  get editable() {
    return false;
  }
}
