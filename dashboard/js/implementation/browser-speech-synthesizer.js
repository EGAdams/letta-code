import { SpeechSynthesizer } from "../abstract/speech-synthesizer.interface.js";

/**
 * BrowserSpeechSynthesizer — concrete SpeechSynthesizer wired to the Web Speech
 * API. It supplies the engine (`window.speechSynthesis`) and an utterance
 * factory (`new SpeechSynthesisUtterance(text)`) to the base facade; all policy
 * (voice selection, markdown cleaning, cancel-before-speak) is inherited.
 *
 * `win` is injectable so a test can pass a fake window with a stub engine.
 */
export class BrowserSpeechSynthesizer extends SpeechSynthesizer {
  /** @param {Window|object} [win] */
  constructor(win = globalThis) {
    const engine = win?.speechSynthesis || null;
    const Utterance = win?.SpeechSynthesisUtterance;
    super(
      engine,
      typeof Utterance === "function"
        ? (text) => new Utterance(text)
        : (text) => ({ text }),
    );
    this._win = win;
  }

  /**
   * Voices populate asynchronously in Chrome — re-pick when they arrive.
   * Mirrors `window.speechSynthesis.onvoiceschanged = …` from the original code.
   * Safe no-op when unsupported.
   */
  bindVoiceChanges() {
    if (!this.supported) return;
    this.pickVoice();
    if (this._engine && "onvoiceschanged" in this._engine) {
      this._engine.onvoiceschanged = () => this.pickVoice();
    }
  }
}
