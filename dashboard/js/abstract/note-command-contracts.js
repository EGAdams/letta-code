/**
 * The two shapes that cross the network boundary for the note-command channel,
 * plus their runtime validators.
 *
 * A JSDoc typedef is a claim; these responses come from an HTTP endpoint, so
 * the claim has to be checked. Both parsers **fail closed** in the direction
 * that protects the user's note:
 *
 *  - an unrecognisable completeness reply means "not complete yet" — the
 *    channel keeps listening instead of executing half an instruction;
 *  - an unrecognisable outcome means "nothing happened" — the caller keeps the
 *    note text it already had.
 *
 * @typedef {object} CompletenessDecision
 * @property {boolean} complete
 * @property {string}  reason
 *
 * @typedef {object} SavedNote
 * @property {string} filename
 * @property {string} path
 *
 * @typedef {object} NoteCommandOutcome
 * @property {"edit"|"save"|"none"} kind
 * @property {string} note              the note's text after the command
 * @property {SavedNote|null} saved
 * @property {string} message
 */

const OUTCOME_KINDS = new Set(["edit", "save", "none"]);

const str = (value) => (typeof value === "string" ? value : "");

/**
 * @param {unknown} raw
 * @returns {CompletenessDecision}
 */
export function parseCompletenessDecision(raw) {
  if (!raw || typeof raw !== "object" || raw.ok === false) {
    return { complete: false, reason: "" };
  }
  if (typeof raw.complete !== "boolean") {
    return { complete: false, reason: "" };
  }
  return { complete: raw.complete, reason: str(raw.reason) };
}

/**
 * @param {unknown} raw
 * @param {string} currentNote text to fall back to when the reply is unusable
 * @returns {NoteCommandOutcome}
 */
export function parseNoteCommandOutcome(raw, currentNote = "") {
  const rejected = (message) => ({
    kind: "none",
    note: currentNote,
    saved: null,
    message,
  });
  if (!raw || typeof raw !== "object") return rejected("");
  if (raw.ok === false) return rejected(str(raw.error));
  if (!OUTCOME_KINDS.has(raw.kind)) return rejected("");
  // An "edit" that carries no text is a malformed reply, not an instruction to
  // blank the note.
  if (raw.kind === "edit" && !str(raw.note).trim()) return rejected("");

  const saved =
    raw.saved && typeof raw.saved === "object"
      ? { filename: str(raw.saved.filename), path: str(raw.saved.path) }
      : null;
  return {
    kind: raw.kind,
    note: typeof raw.note === "string" ? raw.note : currentNote,
    saved,
    message: str(raw.message),
  };
}
