import { NoteDocument } from "../abstract/note-document.interface.js";
import { mergeFinalChunk } from "../abstract/transcript-merge.js";

const BASE = "min-height:100px;";

/**
 * The document look for Toyota's note: white text on black, no input chrome.
 * Kept next to the class that applies it rather than in dashboard.css because
 * the surrounding renderer styles its elements inline too.
 */
const NOTE_STYLE = [
  BASE,
  "min-height:160px;",
  "width:100%;",
  "background:#000;",
  "color:#fff;",
  "border:1px solid #333;",
  "border-radius:4px;",
  "padding:12px;",
  "font-family:Georgia,'Times New Roman',serif;",
  "font-size:1rem;",
  "line-height:1.5;",
  "resize:vertical;",
  "cursor:default;",
  "outline:none;",
].join("");

/**
 * TextareaNoteSurface — NoteDocument backed by a `<textarea>`.
 *
 * Template Method: the shared text handling lives here, and the two concretes
 * below differ only in how the element presents itself. Both satisfy the same
 * contract, so the renderer that hosts one never branches on which it got.
 */
class TextareaNoteSurface extends NoteDocument {
  constructor({ doc = globalThis.document, placeholder = "" } = {}) {
    super();
    this._el = doc.createElement("textarea");
    this._el.className = "am-test-input";
    this._el.placeholder = placeholder;
    this.decorate(this._el);
  }

  /** Hook: apply this surface's presentation. */
  decorate(_el) {}

  get element() {
    return this._el;
  }

  /** @override */
  getText() {
    return this._el.value || "";
  }

  /** @override */
  setText(text) {
    this._el.value = String(text ?? "");
  }

  /** @override */
  appendText(text) {
    this._el.value = mergeFinalChunk(this.getText(), String(text ?? ""));
  }
}

/**
 * The ordinary typeable message box — what every agent's Input Options page has
 * always shown. This is the default surface, so nothing about those pages
 * changes.
 */
export class EditableTextareaSurface extends TextareaNoteSurface {
  constructor(options = {}) {
    super({ placeholder: "Type or speak here…", ...options });
  }

  /** @override */
  get editable() {
    return true;
  }

  /** @override */
  decorate(el) {
    el.style.cssText = BASE;
  }
}

/**
 * Toyota's note: a read-only document display rather than an input box.
 *
 * `readOnly` (not `disabled`) on purpose — a disabled textarea cannot be
 * selected or scrolled, and the user still needs to read, scroll, and copy
 * their notes. Editing happens by speaking into the command box.
 */
export class ReadOnlyNoteSurface extends TextareaNoteSurface {
  constructor(options = {}) {
    super({
      placeholder: "Your notes appear here as you speak…",
      ...options,
    });
  }

  /** @override */
  decorate(el) {
    el.readOnly = true;
    el.setAttribute?.("aria-readonly", "true");
    el.style.cssText = NOTE_STYLE;
  }
}
