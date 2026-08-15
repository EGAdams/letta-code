import { TranscriptBuffer } from "./transcript-buffer.js";

/**
 * VoiceCommandChannel — the command box's policy, with no DOM and no browser
 * APIs in it.
 *
 * It is the middle of the pipeline the feature asks for:
 *
 *   speech recognition -> [ buffer -> completeness detector -> interpreter ] -> note
 *
 * and it owns exactly one decision: **when has the user finished speaking an
 * instruction?** That is answered from the accumulated command text, never from
 * a silence timer, which is what lets someone say "Put a", pause for four
 * seconds, then say "period at the end" and still get one command:
 *
 *   "Put a"                    -> detector says incomplete -> keep waiting
 *   "Put a period at the end"  -> detector says complete   -> apply to the note
 *
 * Collaborators are injected and all four are replaceable:
 *
 * @typedef {object} CompletenessDetector
 * @property {(text: string) => Promise<import("./note-command-contracts.js").CompletenessDecision>} assess
 *
 * @typedef {object} CommandInterpreter
 * @property {(note: string, command: string) => Promise<import("./note-command-contracts.js").NoteCommandOutcome>} apply
 */
export class VoiceCommandChannel {
  constructor({
    note,
    completenessDetector,
    commandInterpreter,
    buffer = new TranscriptBuffer(),
    onCommandText = () => {},
    onStatus = () => {},
  }) {
    if (!note) throw new Error("VoiceCommandChannel requires a NoteDocument");
    if (!completenessDetector)
      throw new Error("VoiceCommandChannel requires a CompletenessDetector");
    if (!commandInterpreter)
      throw new Error("VoiceCommandChannel requires a CommandInterpreter");
    this._note = note;
    this._detector = completenessDetector;
    this._interpreter = commandInterpreter;
    this._buffer = buffer;
    this._onCommandText = onCommandText;
    this._onStatus = onStatus;

    // Everything the channel does runs through this chain, so a long
    // interpreter call can never interleave with the next fragment's
    // assessment and apply one instruction twice.
    this._queue = Promise.resolve();
    this._lastAssessed = "";
    // A count, not a flag: several fragments can be queued at once, and the
    // first one finishing does not mean the channel is idle.
    this._pending = 0;
  }

  /** True while an assessment or an edit is in flight. */
  get busy() {
    return this._pending > 0;
  }

  /** The instruction accumulated so far. */
  get commandText() {
    return this._buffer.committed;
  }

  /**
   * Feed one speech recognition result in.
   *
   * Interim results are shown but never assessed — they churn word by word, and
   * an instruction is only ever judged on finalized text.
   */
  handleSpeech(text, isFinal) {
    const snapshot = this._buffer.accept(text, isFinal);
    this._onCommandText(snapshot);
    if (!isFinal) return this._queue;
    return this._assessLater(snapshot.committed.trim());
  }

  /**
   * Run a command the user supplied directly — a typed one, or the "Run
   * command" button. It skips the completeness detector: pressing the button is
   * itself the statement that the instruction is finished.
   */
  submit(text) {
    const command = String(text || "").trim();
    if (!command) {
      this._onStatus("Nothing to run.", true);
      return this._queue;
    }
    return this._enqueue(() => this._apply(command));
  }

  /** Forget the instruction accumulated so far. */
  clear() {
    this._lastAssessed = "";
    this._onCommandText(this._buffer.reset());
  }

  _assessLater(candidate) {
    // The same finalized text can arrive twice (the recognizer restarts on
    // every silence gap); assessing it again would ask the detector the
    // identical question and risk applying the instruction twice.
    if (!candidate || candidate === this._lastAssessed) return this._queue;
    this._lastAssessed = candidate;
    return this._enqueue(async () => {
      const decision = await this._detector.assess(candidate);
      if (!decision.complete) {
        this._onStatus(
          decision.reason
            ? `Waiting — ${decision.reason}.`
            : "Waiting for the rest of the command…",
        );
        return;
      }
      await this._apply(candidate);
    });
  }

  async _apply(command) {
    this._onStatus(`Working on "${command}"…`);
    const outcome = await this._interpreter.apply(
      this._note.getText(),
      command,
    );

    if (outcome.kind === "none") {
      // The note is deliberately left as-is, and so is the command text: the
      // user can rephrase and press Run rather than re-dictating from scratch.
      this._onStatus(outcome.message || "I didn't follow that.", true);
      return outcome;
    }

    if (outcome.kind === "edit") this._note.setText(outcome.note);
    this._onStatus(
      outcome.message || (outcome.kind === "save" ? "Saved." : "Done."),
    );
    this.clear();
    return outcome;
  }

  _enqueue(work) {
    this._pending += 1;
    this._queue = this._queue
      .then(work)
      .catch((error) => {
        this._onStatus(error?.message || "The command channel failed.", true);
      })
      .finally(() => {
        this._pending -= 1;
      });
    return this._queue;
  }
}
