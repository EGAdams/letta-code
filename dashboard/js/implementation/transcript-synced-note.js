import { NoteDocument } from "../abstract/note-document.interface.js";

/**
 * TranscriptSyncedNote — Decorator over a NoteDocument for a note that is being
 * dictated into while something else may also rewrite it.
 *
 * Toyota's note has two writers: the speech transcript streaming in, and the
 * command channel applying an edit. The transcript buffer keeps its own copy of
 * the committed text, so an edit that goes straight to the surface would be
 * overwritten by the next dictated sentence — "put a period at the end" would
 * appear to work and then quietly undo itself.
 *
 * Wrapping the surface fixes that at the one place both writers meet: any
 * external `setText` re-seeds the buffer first. The command channel stays
 * unaware that a transcript exists, and the transcript stays unaware that
 * commands exist.
 */
export class TranscriptSyncedNote extends NoteDocument {
  constructor({ surface, transcript }) {
    super();
    if (!surface) throw new Error("TranscriptSyncedNote requires a surface");
    if (!transcript)
      throw new Error("TranscriptSyncedNote requires a transcript buffer");
    this._surface = surface;
    this._transcript = transcript;
  }

  get element() {
    return this._surface.element;
  }

  get editable() {
    return this._surface.editable;
  }

  /** @override */
  getText() {
    return this._surface.getText();
  }

  /** @override */
  setText(text) {
    this._transcript.resync(text);
    this._surface.setText(text);
  }

  /** @override */
  appendText(text) {
    this._surface.appendText(text);
    this._transcript.resync(this._surface.getText());
  }
}
