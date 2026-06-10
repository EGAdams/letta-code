import { TextUtils } from "./text-utils.js";

/**
 * SpeechSynthesizer — Facade.
 *
 * The original `Speech` object was a small facade over the browser
 * SpeechSynthesis API (pick a voice, strip markdown, speak, cancel). We keep it
 * a facade but make the underlying engine an injected port so the policy
 * (voice selection, cleaning, "cancel before speaking so replies never
 * overlap") can be tested against a fake engine.
 *
 * The engine port must provide: getVoices(), speak(utterance), cancel().
 */
export class SpeechSynthesizer {
  /**
   * @param {object} [engine] SpeechSynthesis-like port. Null => unsupported.
   * @param {(text:string)=>object} [utteranceFactory] builds an utterance obj.
   */
  constructor(engine = null, utteranceFactory = (text) => ({ text })) {
    this._engine = engine;
    this._utteranceFactory = utteranceFactory;
    this.voice = null;
  }

  /** Facade flag: is text-to-speech available at all? */
  get supported() {
    return !!this._engine;
  }

  /** Choose a sensible English voice from the (async) voice list. */
  pickVoice() {
    if (!this.supported) return null;
    const voices = this._engine.getVoices() || [];
    if (!voices.length) return null;
    this.voice =
      voices.find(
        (v) =>
          /en[-_]US/i.test(v.lang) && /google|natural|neural/i.test(v.name),
      ) ||
      voices.find((v) => /en[-_]US/i.test(v.lang)) ||
      voices.find((v) => /^en/i.test(v.lang)) ||
      voices[0];
    return this.voice;
  }

  /** Normalize text for reading aloud (delegates to shared util). */
  clean(text) {
    return TextUtils.stripMarkdown(text);
  }

  /**
   * Speak text. Cancels anything in flight first so replies never overlap.
   * Returns the utterance that was spoken, or null if nothing was said.
   */
  speak(text) {
    if (!this.supported) return null;
    const say = this.clean(text);
    if (!say) return null;
    this._engine.cancel();
    if (!this.voice) this.pickVoice();
    const u = this._utteranceFactory(say);
    if (this.voice) u.voice = this.voice;
    u.rate = 1.0;
    u.pitch = 1.0;
    u.volume = 1.0;
    this._engine.speak(u);
    return u;
  }

  /** Stop any in-progress speech. */
  cancel() {
    if (this.supported) this._engine.cancel();
  }
}
