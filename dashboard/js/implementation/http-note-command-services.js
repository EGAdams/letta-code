import {
  parseCompletenessDecision,
  parseNoteCommandOutcome,
} from "../abstract/note-command-contracts.js";

// The completeness check runs on every finalized speech fragment and must not
// leave the user waiting between sentences.
const COMPLETENESS_TIMEOUT_MS = 15000;
// Applying a command is one deliberate edit; it can afford a longer budget.
const APPLY_TIMEOUT_MS = 60000;

/**
 * Adapters that put `VoiceCommandChannel`'s two collaborators on the wire.
 *
 * Each one validates the response before handing it back (see
 * note-command-contracts.js) — the channel then works with a checked shape
 * rather than with whatever the endpoint happened to return. A transport error
 * resolves to the same fail-closed value as a malformed body, so a dropped
 * connection makes the channel wait rather than mangle the note.
 */
export class HttpCompletenessDetector {
  constructor({ http, endpoint = "/api/note-command-complete" }) {
    if (!http)
      throw new Error("HttpCompletenessDetector requires an HttpClient");
    this._http = http;
    this._endpoint = endpoint;
  }

  /** @returns {Promise<import("../abstract/note-command-contracts.js").CompletenessDecision>} */
  async assess(text) {
    try {
      const raw = await this._http.postJSON(
        this._endpoint,
        { text },
        { timeout: COMPLETENESS_TIMEOUT_MS },
      );
      return parseCompletenessDecision(raw);
    } catch {
      return { complete: false, reason: "" };
    }
  }
}

export class HttpNoteCommandInterpreter {
  constructor({ http, endpoint = "/api/note-command-apply" }) {
    if (!http)
      throw new Error("HttpNoteCommandInterpreter requires an HttpClient");
    this._http = http;
    this._endpoint = endpoint;
  }

  /** @returns {Promise<import("../abstract/note-command-contracts.js").NoteCommandOutcome>} */
  async apply(note, command) {
    try {
      const raw = await this._http.postJSON(
        this._endpoint,
        { note, command },
        { timeout: APPLY_TIMEOUT_MS },
      );
      return parseNoteCommandOutcome(raw, note);
    } catch (error) {
      return {
        kind: "none",
        note,
        saved: null,
        message: error?.message || "Could not reach the command service.",
      };
    }
  }
}
