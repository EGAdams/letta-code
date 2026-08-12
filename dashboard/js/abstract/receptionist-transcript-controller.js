import { mergeFinalChunk } from "./transcript-merge.js";

/** State for one continuous receptionist transcript. */
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

  accept(text, isFinal) {
    const chunk = String(text || "").trim();
    if (isFinal) {
      this._committed = this._merge(this._committed, chunk);
      this._interim = "";
    } else {
      this._interim = chunk;
    }
    const next = { ...this.snapshot(), finalText: isFinal ? chunk : "" };
    this._onChange(next);
    return next;
  }
}
