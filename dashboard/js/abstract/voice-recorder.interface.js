import { abstractMethod } from "./not-implemented.js";

/** Explicit states for the voice-capture State machine. */
export const RecorderState = Object.freeze({
  IDLE: "idle",
  RECORDING: "recording",
  PROCESSING: "processing",
});

/**
 * VoiceRecorder — State pattern.
 *
 * The chat interface's mic capture moves idle → recording → processing → idle.
 * The original code tangled this state with MediaRecorder calls and DOM button
 * updates. Here the transitions and guards are the concrete, testable core;
 * the device work (`openStream`, `beginCapture`, `endCapture`, `transcribe`)
 * are abstract primitives an implementation binds to MediaRecorder + fetch.
 *
 * `onStateChange(state)` is a hook so a view can update the button / LED.
 */
export class VoiceRecorder {
  constructor({ onStateChange = () => {} } = {}) {
    this._state = RecorderState.IDLE;
    this._onStateChange = onStateChange;
  }

  get state() {
    return this._state;
  }

  get isRecording() {
    return this._state === RecorderState.RECORDING;
  }

  _setState(next) {
    this._state = next;
    this._onStateChange(next);
  }

  /** Abstract: acquire a mic stream; resolve true on success. */
  async openStream() {
    abstractMethod("openStream");
  }

  /** Abstract: start capturing into a buffer. */
  beginCapture() {
    abstractMethod("beginCapture");
  }

  /** Abstract: stop capturing and resolve the recorded audio blob. */
  async endCapture() {
    abstractMethod("endCapture");
  }

  /** Abstract: upload a blob for transcription; resolve the result payload. */
  async transcribe(_blob) {
    abstractMethod("transcribe");
  }

  /**
   * Template: idle → recording. No-op (returns false) unless idle, or if the
   * mic could not be opened.
   */
  async start() {
    if (this._state !== RecorderState.IDLE) return false;
    const ok = await this.openStream();
    if (!ok) return false;
    this.beginCapture();
    this._setState(RecorderState.RECORDING);
    return true;
  }

  /**
   * Template: recording → processing → idle. Returns the transcription result,
   * or null if not currently recording.
   */
  async stop() {
    if (this._state !== RecorderState.RECORDING) return null;
    this._setState(RecorderState.PROCESSING);
    const blob = await this.endCapture();
    try {
      return await this.transcribe(blob);
    } finally {
      this._setState(RecorderState.IDLE);
    }
  }

  /** Convenience: flip between start and stop based on current state. */
  async toggle() {
    return this.isRecording ? this.stop() : this.start();
  }
}
