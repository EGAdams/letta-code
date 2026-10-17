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
// "no-speech" and other transient errors auto-restart forever by design (see
// FATAL_ERRORS above) — correct when the mic is just between phrases, but if
// the recognizer *never* produces a single result (dead mic route, no network
// path to the browser's cloud recognizer, etc.) that same retry loop leaves
// the caller stuck on "Stop Listening" with no feedback, indefinitely. This
// caps how long we'll wait for a first/next result before treating the
// silence itself as a fatal condition.
const STALL_TIMEOUT_MS = 20_000;
const STALL_MESSAGE =
  "Not hearing anything — check the mic input, or try push-to-talk instead.";

export class BrowserSpeechRecognitionListener extends ContinuousListener {
  constructor({
    onStateChange,
    onResult,
    onError,
    window: win = globalThis,
    SpeechRecognition: Recognition = globalThis.SpeechRecognition ||
      globalThis.webkitSpeechRecognition,
    lang = "en-US",
    setTimeout: setTimeoutFn = globalThis.setTimeout.bind(globalThis),
    clearTimeout: clearTimeoutFn = globalThis.clearTimeout.bind(globalThis),
    stallTimeoutMs = STALL_TIMEOUT_MS,
  } = {}) {
    super({ onStateChange, onResult, onError });
    this._window = win;
    this._Recognition = Recognition;
    this._lang = lang;
    this._recognition = null;
    this._stopping = false;
    this._setTimeout = setTimeoutFn;
    this._clearTimeout = clearTimeoutFn;
    this._stallTimeoutMs = stallTimeoutMs;
    this._stallTimer = null;
  }

  _armStallTimer() {
    this._clearTimeout(this._stallTimer);
    this._stallTimer = this._setTimeout(() => {
      this._stopping = true;
      this._recognition?.stop();
      this._fail(STALL_MESSAGE);
    }, this._stallTimeoutMs);
  }

  _disarmStallTimer() {
    this._clearTimeout(this._stallTimer);
    this._stallTimer = null;
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
      this._armStallTimer();
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
      this._disarmStallTimer();
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
    this._armStallTimer();
    return true;
  }

  /** @override Stop the recognition session for real (no auto-restart). */
  closeListening() {
    this._stopping = true;
    this._disarmStallTimer();
    this._recognition?.stop();
    this._recognition = null;
  }
}
