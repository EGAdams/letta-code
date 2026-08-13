import { ContinuousListener } from "../abstract/continuous-listener.interface.js";

// SpeechRecognitionErrorEvent.error codes that mean the session can never
// recover on its own — everything else (e.g. "no-speech", "aborted") is
// transient and left to the existing onend auto-restart.
const FATAL_ERRORS = new Set([
  "not-allowed",
  "service-not-allowed",
  "audio-capture",
  "network",
]);

const FATAL_ERROR_MESSAGES = {
  "not-allowed": "Microphone permission was denied.",
  "service-not-allowed": "Microphone permission was denied.",
  "audio-capture": "No microphone was found.",
  network:
    "Speech recognition lost its connection (it needs network access to the browser's cloud recognizer).",
};

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
    onError,
    window: win = globalThis,
    SpeechRecognition: Recognition = globalThis.SpeechRecognition ||
      globalThis.webkitSpeechRecognition,
    lang = "en-US",
  } = {}) {
    super({ onStateChange, onResult, onError });
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
    // intentionally called stop() (see closeListening) or a fatal error just
    // ended the session (see onerror below).
    this._recognition.onend = () => {
      if (!this._stopping && this.isListening) {
        try {
          this._recognition.start();
        } catch {
          // already starting/started — ignore
        }
      }
    };

    this._recognition.onerror = (event) => {
      if (!FATAL_ERRORS.has(event.error)) return; // transient — onend will restart
      this._stopping = true;
      this._fail(
        FATAL_ERROR_MESSAGES[event.error] ??
          `Speech recognition error: ${event.error}`,
      );
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
