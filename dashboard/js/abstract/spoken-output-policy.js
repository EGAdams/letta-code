import { AgentEventKind, isSpeakable } from "./conversation-agent.interface.js";

/**
 * SpokenOutputPolicy — the single gate between agent output and the speaker.
 *
 * Two independent questions decide whether a sentence is read aloud, and today
 * each renderer answers both by hand:
 *
 *   1. **Is this kind speakable?**  Reasoning, tool calls, tool results and
 *      status lines are not. Only `assistant_text` is.
 *   2. **Is this turn still wanted?**  A reply from a superseded generation is
 *      stale; speaking it talks over the answer the user actually asked for.
 *
 * Putting both in one object means a second caller cannot re-answer them
 * differently, and it makes the rejection *reason* assertable — which is how
 * "the March answer was discarded" becomes a test rather than a demo.
 *
 * No DOM, no synthesizer: the policy decides, the caller speaks.
 *
 * @typedef {object} SpeechVerdict
 * @property {boolean} speak
 * @property {string}  reason   why, in words, for logs and tests
 * @property {string}  text     what to speak, trimmed; "" when rejected
 */

export const RejectionReason = Object.freeze({
  NOT_AN_EVENT: "not an agent event",
  NOT_SPEAKABLE: "kind is never spoken",
  SUPERSEDED: "generation superseded",
  EMPTY: "nothing to say",
});

export class SpokenOutputPolicy {
  /**
   * @param {object} deps
   * @param {import("./voice-session.js").VoiceSession} deps.session
   * @param {(kind: string) => boolean} [deps.speakable]  override for tests or
   *   for a caller that legitimately wants a narrower vocabulary
   */
  constructor({ session, speakable = isSpeakable }) {
    if (!session) throw new Error("SpokenOutputPolicy requires a VoiceSession");
    this._session = session;
    this._speakable = speakable;
  }

  /**
   * @param {import("./conversation-agent.interface.js").AgentEvent} event
   * @returns {SpeechVerdict}
   */
  admit(event) {
    const no = (reason) => ({ speak: false, reason, text: "" });
    if (!event || typeof event !== "object")
      return no(RejectionReason.NOT_AN_EVENT);
    if (!this._speakable(event.kind)) return no(RejectionReason.NOT_SPEAKABLE);
    // Order matters: the fence is checked before the text, so a stale reply is
    // reported as stale rather than as empty when it happens to be both.
    if (!this._session.accepts(event.generationId))
      return no(RejectionReason.SUPERSEDED);
    const text = typeof event.text === "string" ? event.text.trim() : "";
    if (!text) return no(RejectionReason.EMPTY);
    return { speak: true, reason: "speakable and current", text };
  }

  /**
   * Filter a whole turn's events down to what should be spoken, in order.
   *
   * @param {Iterable<import("./conversation-agent.interface.js").AgentEvent>} events
   * @returns {string[]}
   */
  admitAll(events) {
    const spoken = [];
    for (const event of events) {
      const verdict = this.admit(event);
      if (verdict.speak) spoken.push(verdict.text);
    }
    return spoken;
  }

  /** True when this event ends the stream, whatever else the caller does. */
  static isTerminal(event) {
    return event?.kind === AgentEventKind.TERMINAL;
  }
}
