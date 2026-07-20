import { ContinuousListener } from "../abstract/continuous-listener.interface.js";

/**
 * BrowserSpeechRecognitionListener — concrete ContinuousListener bound to the
 * browser's native (Chrome-family) SpeechRecognition API.
 *
 *   openListening  → new SpeechRecognition(), continuous+interim, .start()
 *   closeListening → .stop()
 *
 * The native API stops itself after a silence gap even with continuous=true;
 * while our own state is still LISTENING, `onend` restarts it so "continuous"
 * actually stays continuous from the caller's point of view.
 *
 * Every browser dependency is injectable so the whole flow is unit-testable.
 */
export class BrowserSpeechRecognitionListener extends ContinuousListener {
  constructor({
    onStateChange,
    onResult,
    window: win = globalThis,
    SpeechRecognition: Recognition = globalThis.SpeechRecognition ||
      globalThis.webkitSpeechRecognition,
    lang = "en-US",
  } = {}) {
    super({ onStateChange, onResult });
    this._window = win;
    this._Recognition = Recognition;
    this._lang = lang;
    this._recognition = null;
    this._stopping = false;
  }

  get supported() {
    return !!(this._Recognition && this._window);
  }

  /** @override Open a continuous recognition session. */
  async openListening() {
    if (!this.supported) return false;
    this._stopping = false;
    this._recognition = new this._Recognition();
    this._recognition.continuous = true;
    this._recognition.interimResults = true;
    this._recognition.lang = this._lang;

    this._recognition.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const text = result?.[0]?.transcript ?? "";
        this._emitResult(text, !!result.isFinal);
      }
    };

    // The native API stops itself after a silence gap; restart it unless we
    // intentionally called stop() (see closeListening).
    this._recognition.onend = () => {
      if (!this._stopping && this.isListening) {
        try {
          this._recognition.start();
        } catch {
          // already starting/started — ignore
        }
      }
    };

    try {
      this._recognition.start();
    } catch {
      return false;
    }
    return true;
  }

  /** @override Stop the recognition session for real (no auto-restart). */
  closeListening() {
    this._stopping = true;
    this._recognition?.stop();
    this._recognition = null;
  }
}
