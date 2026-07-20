import { abstractMethod } from "./not-implemented.js";

/** Explicit states for the continuous-listening State machine. */
export const ListenerState = Object.freeze({
  IDLE: "idle",
  LISTENING: "listening",
});

/**
 * ContinuousListener — State pattern, sibling of VoiceRecorder.
 *
 * Where VoiceRecorder is push-to-talk (record a clip, then transcribe it once
 * the mic is stopped), ContinuousListener stays open and streams recognized
 * text out continuously via `onResult(text, isFinal)` while listening — no
 * stop() needed between phrases.
 *
 * Deliberately provider-agnostic: `openListening`/`closeListening` are the
 * only abstract primitives. The first concrete binds these to the browser's
 * native SpeechRecognition API; a later concrete could instead stream raw
 * audio to a server-side wake-word model (e.g. openWakeWord) behind the same
 * start()/stop()/onResult() contract, with no caller-side changes.
 */
export class ContinuousListener {
  constructor({ onStateChange = () => {}, onResult = () => {} } = {}) {
    this._state = ListenerState.IDLE;
    this._onStateChange = onStateChange;
    this._onResult = onResult;
  }

  get state() {
    return this._state;
  }

  get isListening() {
    return this._state === ListenerState.LISTENING;
  }

  _setState(next) {
    this._state = next;
    this._onStateChange(next);
  }

  /**
   * Rebind callbacks without tearing down the underlying session. Lets a
   * long-lived listener (constructed once, e.g. in app boot) be re-claimed by
   * a freshly-rendered view (e.g. after navigation rebuilds the DOM) without
   * losing continuity of the actual listening session.
   */
  setCallbacks({ onStateChange, onResult } = {}) {
    if (onStateChange) this._onStateChange = onStateChange;
    if (onResult) this._onResult = onResult;
  }

  /** Emit a recognized chunk of text. isFinal=false for live/interim display. */
  _emitResult(text, isFinal) {
    this._onResult(text, isFinal);
  }

  /** Abstract: open the listening session; resolve true on success. */
  async openListening() {
    abstractMethod("openListening");
  }

  /** Abstract: close the listening session. */
  closeListening() {
    abstractMethod("closeListening");
  }

  /** Template: idle → listening. No-op (returns false) unless idle. */
  async start() {
    if (this._state !== ListenerState.IDLE) return false;
    const ok = await this.openListening();
    if (!ok) return false;
    this._setState(ListenerState.LISTENING);
    return true;
  }

  /** Template: listening → idle. No-op unless currently listening. */
  stop() {
    if (this._state !== ListenerState.LISTENING) return;
    this.closeListening();
    this._setState(ListenerState.IDLE);
  }

  /** Convenience: flip between start and stop based on current state. */
  async toggle() {
    return this.isListening ? this.stop() : this.start();
  }
}
