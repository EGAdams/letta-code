import { mergeFinalChunk } from "./transcript-merge.js";

/**
 * State for one continuous receptionist transcript.
 *
 * Recognition has two streams: a finalized prefix and a replaceable interim
 * suffix. Keeping that state outside the DOM renderer prevents an async
 * submission or a re-render from erasing words the user has already heard.
 */
export class ReceptionistTranscriptController {
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

  snapshot() {
    return {
      committed: this._committed,
      interim: this._interim,
      text: this.text,
    };
  }

  /** Accept one native recognition result and publish the visible snapshot. */
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
}
