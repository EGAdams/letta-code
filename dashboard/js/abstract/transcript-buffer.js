import { mergeFinalChunk } from "./transcript-merge.js";

/**
 * TranscriptBuffer — accumulates one continuous speech transcript.
 *
 * Recognition has two streams: a finalized prefix and a replaceable interim
 * suffix. Keeping that state outside the DOM renderer prevents an async
 * submission or a re-render from erasing words the user has already heard.
 *
 * Two callers with different purposes share this exact behaviour, which is why
 * it is a plain buffer and not named after either of them:
 *
 *  - Toyota's note box, where `text` is the document being dictated;
 *  - the command channel, where `committed` is the instruction accumulating
 *    across the user's pauses (see voice-command-channel.js).
 *
 * @typedef {{committed: string, interim: string, text: string}} TranscriptSnapshot
 */
export class TranscriptBuffer {
  constructor({ merge = mergeFinalChunk, onChange = () => {} } = {}) {
    this._merge = merge;
    this._onChange = onChange;
    this._committed = "";
    this._interim = "";
  }

  get committed() {
    return this._committed;
  }

  get text() {
    return [this._committed, this._interim].filter(Boolean).join(" ");
  }

  /** @returns {TranscriptSnapshot} */
  snapshot() {
    return {
      committed: this._committed,
      interim: this._interim,
      text: this.text,
    };
  }

  /**
   * Accept one native recognition result and publish the visible snapshot.
   * @param {string} text
   * @param {boolean} isFinal
   * @returns {TranscriptSnapshot}
   */
  accept(text, isFinal) {
    const chunk = String(text || "").trim();
    if (isFinal) {
      this._committed = this._merge(this._committed, chunk);
      this._interim = "";
    } else {
      this._interim = chunk;
    }
    const next = this.snapshot();
    this._onChange(next);
    return next;
  }

  /**
   * Adopt `text` as the committed transcript without publishing a change.
   *
   * Needed when something other than speech rewrote the text this buffer is
   * mirroring — Toyota editing the note in response to a spoken command.
   * Without it the buffer would still hold the pre-edit wording and the next
   * dictated sentence would silently undo the edit.
   * @param {string} text
   */
  resync(text) {
    this._committed = String(text ?? "");
    this._interim = "";
  }

  /**
   * Drop everything accumulated so far and publish the empty snapshot.
   *
   * The command channel calls this once an instruction has been executed, so
   * the next thing the user says starts a fresh command rather than being
   * appended to the one Toyota just carried out.
   * @returns {TranscriptSnapshot}
   */
  reset() {
    this._committed = "";
    this._interim = "";
    const next = this.snapshot();
    this._onChange(next);
    return next;
  }
}
